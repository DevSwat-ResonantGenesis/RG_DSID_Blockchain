"""Blockchain Service main application."""

import asyncio
import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

# Optional shared imports for Docker compatibility
try:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from shared.errors import setup_exception_handlers
    HAS_SHARED_ERRORS = True
except ImportError:
    HAS_SHARED_ERRORS = False
    setup_exception_handlers = None

from .routers import router
from .routers_distributed import router as distributed_router
from .routers_advanced_blockchain import router as advanced_blockchain_router
from .identity_registry import router as identity_router
from .db import engine, Base
from .models import AuditEntry, HashNode, Block, BlockTransaction


BLOCK_MINE_INTERVAL = 10  # seconds


ANCHOR_BLOCK_INTERVAL = 10  # Anchor to Base Sepolia every N blocks


async def _try_external_anchor(block_number: int):
    """Attempt to anchor internal chain state to Base Sepolia."""
    import os
    from .db import async_session
    from .models import AnchorRecord, Block
    from sqlalchemy import select

    anchor_private_key = os.getenv("ANCHOR_PRIVATE_KEY", "")
    anchor_rpc = os.getenv("ANCHOR_RPC_URL", "")
    anchor_contract = os.getenv("ANCHOR_CONTRACT_ADDRESS", "")

    if not anchor_rpc or not anchor_contract:
        return

    try:
        async with async_session() as session:
            # Compute merkle root of last ANCHOR_BLOCK_INTERVAL blocks
            result = await session.execute(
                select(Block)
                .where(Block.block_number > block_number - ANCHOR_BLOCK_INTERVAL)
                .where(Block.block_number <= block_number)
                .order_by(Block.block_number)
            )
            blocks = result.scalars().all()

            if not blocks:
                return

            import hashlib
            block_hashes = [b.block_hash for b in blocks]
            combined = "".join(block_hashes)
            anchor_merkle_root = hashlib.sha256(combined.encode()).hexdigest()

            # Record the anchor (even without on-chain write)
            anchor_record = AnchorRecord(
                anchor_type="block_range",
                internal_hash=anchor_merkle_root,
                internal_block_number=block_number,
                external_chain=os.getenv("ANCHOR_CHAIN", "base"),
                external_tx_hash=f"pending:{anchor_merkle_root[:16]}",
                contract_address=anchor_contract,
                status="pending" if not anchor_private_key else "submitting",
            )
            session.add(anchor_record)
            await session.commit()

            logger.info(
                "Anchor record created for blocks %d-%d  merkle=%s  status=%s",
                block_number - ANCHOR_BLOCK_INTERVAL + 1,
                block_number,
                anchor_merkle_root[:16],
                anchor_record.status,
            )

            # If private key is available, actually write to Base Sepolia
            if anchor_private_key:
                try:
                    from web3 import Web3
                    w3 = Web3(Web3.HTTPProvider(anchor_rpc))
                    if w3.is_connected():
                        # Minimal MemoryAnchors ABI for anchor function
                        abi = [{"inputs": [{"name": "contentHash", "type": "bytes32"}], "name": "anchor", "outputs": [], "stateMutability": "nonpayable", "type": "function"}]
                        contract = w3.eth.contract(
                            address=Web3.to_checksum_address(anchor_contract),
                            abi=abi,
                        )
                        account = w3.eth.account.from_key(anchor_private_key)
                        content_hash_bytes = bytes.fromhex(anchor_merkle_root)

                        tx = contract.functions.anchor(content_hash_bytes).build_transaction({
                            "from": account.address,
                            "nonce": w3.eth.get_transaction_count(account.address),
                            "gas": 100000,
                            "gasPrice": w3.eth.gas_price,
                        })
                        signed = account.sign_transaction(tx)
                        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

                        anchor_record.external_tx_hash = tx_hash.hex()
                        anchor_record.status = "submitted"
                        await session.commit()

                        logger.info("Anchored to Base Sepolia: tx=%s", tx_hash.hex())
                except Exception as chain_err:
                    logger.warning("External anchor write failed: %s", chain_err)
                    anchor_record.status = "failed"
                    await session.commit()

    except Exception as exc:
        logger.error("External anchor error: %s", exc)


async def _background_block_miner():
    """Background task: mine pending transactions into blocks every BLOCK_MINE_INTERVAL seconds."""
    from .chain import blockchain_manager
    from .db import async_session

    logger.info("Background block miner started (interval=%ds)", BLOCK_MINE_INTERVAL)
    await asyncio.sleep(5)  # let the app finish startup

    while True:
        try:
            async with async_session() as session:
                block = await blockchain_manager.mine_block(
                    validator="resonant-genesis-node-0",
                    db_session=session,
                )
                if block:
                    logger.info(
                        "Mined block #%d  txs=%d  hash=%s",
                        block.block_number,
                        block.transaction_count,
                        block.block_hash[:16],
                    )
                    # External anchoring trigger
                    if block.block_number > 0 and block.block_number % ANCHOR_BLOCK_INTERVAL == 0:
                        await _try_external_anchor(block.block_number)

        except Exception as exc:
            logger.error("Block miner error: %s", exc, exc_info=True)

        await asyncio.sleep(BLOCK_MINE_INTERVAL)


async def _backfill_existing_dsids():
    """One-time: create transactions for existing DSIDs that have no transaction yet."""
    from .chain import transaction_manager
    from .db import async_session
    from .models import DSID as DSIDModel
    from .models import BlockTransaction
    from sqlalchemy import select, func

    await asyncio.sleep(3)  # let DB init finish

    try:
        async with async_session() as session:
            all_dsids_result = await session.execute(
                select(DSIDModel).order_by(DSIDModel.created_at)
            )
            all_dsids = all_dsids_result.scalars().all()

            if not all_dsids:
                logger.info("Backfill: no DSIDs to backfill")
                return

            tx_count = (await session.execute(
                select(func.count(BlockTransaction.id))
            )).scalar() or 0

            if tx_count > 0:
                logger.info("Backfill: %d transactions already exist, skipping", tx_count)
                return

            logger.info("Backfill: creating transactions for %d existing DSIDs", len(all_dsids))

            for dsid_obj in all_dsids:
                await transaction_manager.create_transaction(
                    tx_type="dsid_register",
                    payload={
                        "dsid": dsid_obj.dsid,
                        "entity_type": dsid_obj.entity_type,
                        "entity_id": str(dsid_obj.entity_id),
                        "content_hash": dsid_obj.content_hash,
                        "metadata_hash": dsid_obj.metadata_hash,
                        "lineage_depth": dsid_obj.lineage_depth,
                        "parent_dsid": dsid_obj.parent_dsid,
                        "root_dsid": dsid_obj.root_dsid,
                        "backfilled": True,
                        "original_created_at": dsid_obj.created_at.isoformat() if dsid_obj.created_at else None,
                    },
                    from_dsid=dsid_obj.parent_dsid,
                    to_dsid=dsid_obj.dsid,
                    db_session=session,
                )

            logger.info("Backfill: created %d transactions, ready for mining", len(all_dsids))

    except Exception as exc:
        logger.error("Backfill error: %s", exc, exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup, launch background miner."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    backfill_task = asyncio.create_task(_backfill_existing_dsids())
    miner_task = asyncio.create_task(_background_block_miner())

    yield

    miner_task.cancel()
    backfill_task.cancel()
    try:
        await miner_task
    except asyncio.CancelledError:
        pass
    try:
        await backfill_task
    except asyncio.CancelledError:
        pass
    logger.info("Background block miner stopped")


app = FastAPI(
    title="Blockchain Service",
    description="DSID-P, hash lineage, transaction graph, and audit chain",
    version="0.1.0",
    lifespan=lifespan,
    redirect_slashes=False,  # Prevent 307 redirects that expose internal Docker hostnames
)

# Setup standardized exception handlers
if HAS_SHARED_ERRORS and setup_exception_handlers:
    setup_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(distributed_router)  # Real distributed blockchain with consensus
app.include_router(advanced_blockchain_router)  # Smart contracts, ZK proofs, sharding, cross-chain
app.include_router(identity_router)  # Crypto identity registry (Layer 4)


@app.get("/")
async def root():
    return {"service": "blockchain", "version": "0.1.0", "distributed": True}


@app.get("/health")
async def health():
    return {"status": "ok", "miner": "active"}
