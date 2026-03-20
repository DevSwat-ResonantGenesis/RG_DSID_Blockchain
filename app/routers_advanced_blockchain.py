"""
ADVANCED BLOCKCHAIN API
=======================

API for smart contracts, zero-knowledge proofs, sharding, and cross-chain.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

from .smart_contracts import get_contract_engine, SmartContractEngine
from .zero_knowledge import get_zk_engine, ZKProofEngine
from .sharding import get_shard_manager, ShardManager
from .cross_chain import get_cross_chain_bridge, CrossChainBridge, ChainType

router = APIRouter(prefix="/advanced", tags=["advanced-blockchain"])


# === REQUEST MODELS ===

class DeployContractRequest(BaseModel):
    creator: str
    code: str
    abi: List[Dict[str, Any]]
    constructor_args: Optional[List[Any]] = None
    gas_limit: int = 3000000


class CallContractRequest(BaseModel):
    method: str
    args: List[Any]
    sender: str
    value: int = 0
    gas_limit: int = 1000000


class CreateCommitmentRequest(BaseModel):
    value: int


class ProveKnowledgeRequest(BaseModel):
    secret: int


class ProveRangeRequest(BaseModel):
    value: int
    max_bits: int = 64


class PrivateTransactionRequest(BaseModel):
    sender_balance: int
    amount: int
    receiver: str


class SubmitTransactionRequest(BaseModel):
    sender: str
    receiver: str
    data: Dict[str, Any]


class InitiateBridgeRequest(BaseModel):
    source_chain: str
    target_chain: str
    sender: str
    receiver: str
    asset: str
    amount: int


class CreateSwapRequest(BaseModel):
    initiator: str
    participant: str
    initiator_chain: str
    participant_chain: str
    initiator_asset: str
    initiator_amount: int
    participant_asset: str
    participant_amount: int


class CrossChainMessageRequest(BaseModel):
    source_chain: str
    target_chain: str
    sender: str
    receiver: str
    payload: Dict[str, Any]


# === DEPENDENCIES ===

def get_contracts() -> SmartContractEngine:
    return get_contract_engine()


def get_zk() -> ZKProofEngine:
    return get_zk_engine()


def get_shards() -> ShardManager:
    return get_shard_manager()


def get_bridge() -> CrossChainBridge:
    return get_cross_chain_bridge()


# === SMART CONTRACTS ===

@router.post("/contracts/deploy")
async def deploy_contract(
    request: DeployContractRequest,
    engine: SmartContractEngine = Depends(get_contracts),
):
    """Deploy a new smart contract."""
    result = await engine.deploy_contract(
        creator=request.creator,
        code=request.code,
        abi=request.abi,
        constructor_args=request.constructor_args,
        gas_limit=request.gas_limit,
    )
    return result


@router.post("/contracts/{contract_id}/call")
async def call_contract(
    contract_id: str,
    request: CallContractRequest,
    engine: SmartContractEngine = Depends(get_contracts),
):
    """Call a smart contract method."""
    result = await engine.call_contract(
        contract_id=contract_id,
        method=request.method,
        args=request.args,
        sender=request.sender,
        value=request.value,
        gas_limit=request.gas_limit,
    )
    return result


@router.get("/contracts/{contract_id}")
async def get_contract(
    contract_id: str,
    engine: SmartContractEngine = Depends(get_contracts),
):
    """Get contract details."""
    contract = engine.get_contract(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    return {
        "id": contract.id,
        "address": contract.address,
        "creator": contract.creator,
        "status": contract.status.value,
        "version": contract.version,
        "total_calls": contract.total_calls,
        "total_gas_used": contract.total_gas_used,
    }


@router.get("/contracts/{contract_id}/events")
async def get_contract_events(
    contract_id: str,
    event_name: Optional[str] = None,
    limit: int = 100,
    engine: SmartContractEngine = Depends(get_contracts),
):
    """Get contract events."""
    events = engine.get_events(contract_id, event_name, limit)
    return {
        "events": [
            {
                "name": e.event_name,
                "data": e.data,
                "timestamp": e.timestamp,
            }
            for e in events
        ],
    }


@router.get("/contracts/stats")
async def get_contract_stats(
    engine: SmartContractEngine = Depends(get_contracts),
):
    """Get contract engine statistics."""
    return engine.get_stats()


# === ZERO-KNOWLEDGE PROOFS ===

@router.post("/zk/commitment")
async def create_commitment(
    request: CreateCommitmentRequest,
    zk: ZKProofEngine = Depends(get_zk),
):
    """Create a Pedersen commitment."""
    commitment_id, blinding = zk.create_commitment(request.value)
    return {
        "commitment_id": commitment_id,
        "blinding_factor": blinding,  # Keep this secret!
    }


@router.post("/zk/prove/knowledge")
async def prove_knowledge(
    request: ProveKnowledgeRequest,
    zk: ZKProofEngine = Depends(get_zk),
):
    """Generate proof of knowledge."""
    proof_id = zk.prove_knowledge(request.secret)
    return {"proof_id": proof_id}


@router.post("/zk/verify/knowledge/{proof_id}")
async def verify_knowledge(
    proof_id: str,
    zk: ZKProofEngine = Depends(get_zk),
):
    """Verify a knowledge proof."""
    verified = zk.verify_knowledge_proof(proof_id)
    return {"verified": verified}


@router.post("/zk/prove/range")
async def prove_range(
    request: ProveRangeRequest,
    zk: ZKProofEngine = Depends(get_zk),
):
    """Generate a range proof."""
    proof_id = zk.prove_range(request.value, request.max_bits)
    return {"proof_id": proof_id}


@router.post("/zk/private-transaction")
async def create_private_transaction(
    request: PrivateTransactionRequest,
    zk: ZKProofEngine = Depends(get_zk),
):
    """Create a private transaction."""
    tx_id = zk.create_private_transaction(
        sender_balance=request.sender_balance,
        amount=request.amount,
        receiver=request.receiver,
    )
    
    if not tx_id:
        raise HTTPException(status_code=400, detail="Failed to create private transaction")
    
    return {"transaction_id": tx_id}


@router.post("/zk/verify-transaction/{tx_id}")
async def verify_private_transaction(
    tx_id: str,
    zk: ZKProofEngine = Depends(get_zk),
):
    """Verify a private transaction."""
    verified = zk.verify_private_transaction(tx_id)
    return {"verified": verified}


@router.get("/zk/stats")
async def get_zk_stats(
    zk: ZKProofEngine = Depends(get_zk),
):
    """Get ZK proof engine statistics."""
    return zk.get_stats()


# === SHARDING ===

@router.post("/shards/transaction")
async def submit_sharded_transaction(
    request: SubmitTransactionRequest,
    manager: ShardManager = Depends(get_shards),
):
    """Submit a transaction to the sharded blockchain."""
    result = await manager.submit_transaction({
        "sender": request.sender,
        "receiver": request.receiver,
        "data": request.data,
    })
    return result


@router.get("/shards/{shard_id}")
async def get_shard(
    shard_id: str,
    manager: ShardManager = Depends(get_shards),
):
    """Get shard details."""
    shard = manager.get_shard(shard_id)
    if not shard:
        raise HTTPException(status_code=404, detail="Shard not found")
    
    return {
        "id": shard.id,
        "index": shard.shard_index,
        "status": shard.status.value,
        "blocks": len(shard.blocks),
        "transactions": shard.transaction_count,
        "validators": len(shard.validators),
    }


@router.post("/shards/{shard_id}/block")
async def create_shard_block(
    shard_id: str,
    transactions: List[Dict[str, Any]],
    manager: ShardManager = Depends(get_shards),
):
    """Create a new block on a shard."""
    block = await manager.create_block(shard_id, transactions)
    if not block:
        raise HTTPException(status_code=400, detail="Failed to create block")
    
    return {
        "block_id": block.id,
        "height": block.height,
        "hash": block.hash,
        "transactions": len(block.transactions),
    }


@router.post("/shards/add")
async def add_shard(
    manager: ShardManager = Depends(get_shards),
):
    """Add a new shard."""
    shard = manager.add_shard()
    return {"shard_id": shard.id, "index": shard.shard_index}


@router.post("/shards/rebalance")
async def rebalance_shards(
    manager: ShardManager = Depends(get_shards),
):
    """Trigger shard rebalancing."""
    await manager.rebalance_shards()
    return {"rebalancing": True}


@router.get("/shards/stats")
async def get_shard_stats(
    manager: ShardManager = Depends(get_shards),
):
    """Get sharding statistics."""
    return manager.get_stats()


# === CROSS-CHAIN BRIDGE ===

@router.post("/bridge/initiate")
async def initiate_bridge(
    request: InitiateBridgeRequest,
    bridge: CrossChainBridge = Depends(get_bridge),
):
    """Initiate a cross-chain bridge transfer."""
    try:
        source = ChainType(request.source_chain)
        target = ChainType(request.target_chain)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chain type")
    
    tx = await bridge.initiate_bridge(
        source_chain=source,
        target_chain=target,
        sender=request.sender,
        receiver=request.receiver,
        asset=request.asset,
        amount=request.amount,
    )
    
    return {"bridge_id": tx.id, "status": tx.status.value}


@router.post("/bridge/{bridge_id}/lock")
async def lock_bridge_assets(
    bridge_id: str,
    bridge: CrossChainBridge = Depends(get_bridge),
):
    """Lock assets for bridge transfer."""
    success = await bridge.lock_assets(bridge_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to lock assets")
    return {"locked": True}


@router.post("/bridge/{bridge_id}/relay")
async def relay_bridge_proof(
    bridge_id: str,
    bridge: CrossChainBridge = Depends(get_bridge),
):
    """Relay proof to target chain."""
    success = await bridge.relay_proof(bridge_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to relay proof")
    return {"relayed": True}


@router.post("/bridge/{bridge_id}/mint")
async def mint_bridge_assets(
    bridge_id: str,
    bridge: CrossChainBridge = Depends(get_bridge),
):
    """Mint assets on target chain."""
    success = await bridge.mint_assets(bridge_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to mint assets")
    return {"minted": True}


@router.get("/bridge/{bridge_id}")
async def get_bridge_status(
    bridge_id: str,
    bridge: CrossChainBridge = Depends(get_bridge),
):
    """Get bridge transaction status."""
    status = bridge.get_bridge_status(bridge_id)
    if not status:
        raise HTTPException(status_code=404, detail="Bridge not found")
    return status


@router.post("/bridge/swap")
async def create_atomic_swap(
    request: CreateSwapRequest,
    bridge: CrossChainBridge = Depends(get_bridge),
):
    """Create an atomic swap."""
    try:
        init_chain = ChainType(request.initiator_chain)
        part_chain = ChainType(request.participant_chain)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chain type")
    
    swap = await bridge.create_atomic_swap(
        initiator=request.initiator,
        participant=request.participant,
        initiator_chain=init_chain,
        participant_chain=part_chain,
        initiator_asset=request.initiator_asset,
        initiator_amount=request.initiator_amount,
        participant_asset=request.participant_asset,
        participant_amount=request.participant_amount,
    )
    
    return {
        "swap_id": swap.id,
        "secret_hash": swap.secret_hash,
        "secret": swap.secret,  # Only for initiator
    }


@router.post("/bridge/swap/{swap_id}/fund")
async def fund_atomic_swap(
    swap_id: str,
    funder: str,
    bridge: CrossChainBridge = Depends(get_bridge),
):
    """Fund an atomic swap."""
    success = await bridge.fund_swap(swap_id, funder)
    return {"funded": success}


@router.post("/bridge/swap/{swap_id}/claim")
async def claim_atomic_swap(
    swap_id: str,
    claimer: str,
    secret: str,
    bridge: CrossChainBridge = Depends(get_bridge),
):
    """Claim an atomic swap."""
    success = await bridge.claim_swap(swap_id, claimer, secret)
    return {"claimed": success}


@router.post("/bridge/message")
async def send_cross_chain_message(
    request: CrossChainMessageRequest,
    bridge: CrossChainBridge = Depends(get_bridge),
):
    """Send a cross-chain message."""
    try:
        source = ChainType(request.source_chain)
        target = ChainType(request.target_chain)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chain type")
    
    message = await bridge.send_cross_chain_message(
        source_chain=source,
        target_chain=target,
        sender=request.sender,
        receiver=request.receiver,
        payload=request.payload,
    )
    
    return {"message_id": message.id, "nonce": message.nonce}


@router.get("/bridge/stats")
async def get_bridge_stats(
    bridge: CrossChainBridge = Depends(get_bridge),
):
    """Get bridge statistics."""
    return bridge.get_stats()


# === SYSTEM STATUS ===

@router.get("/status")
async def get_advanced_blockchain_status(
    contracts: SmartContractEngine = Depends(get_contracts),
    zk: ZKProofEngine = Depends(get_zk),
    shards: ShardManager = Depends(get_shards),
    bridge: CrossChainBridge = Depends(get_bridge),
):
    """Get complete status of advanced blockchain features."""
    return {
        "smart_contracts": contracts.get_stats(),
        "zero_knowledge": zk.get_stats(),
        "sharding": shards.get_stats(),
        "cross_chain": bridge.get_stats(),
        "status": "operational",
        "platform": "Most Advanced Real Blockchain",
    }
