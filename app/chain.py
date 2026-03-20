"""Internal blockchain and block management."""

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Block, BlockTransaction, TransactionGraph, StateSnapshot
from .dsid import hash_lineage_manager
from .config import settings


class BlockchainManager:
    """Manages the internal blockchain."""

    async def get_latest_block(
        self,
        db_session: AsyncSession,
    ) -> Optional[Block]:
        """Get the latest block."""
        result = await db_session.execute(
            select(Block).order_by(Block.block_number.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_block_by_number(
        self,
        block_number: int,
        db_session: AsyncSession,
    ) -> Optional[Block]:
        """Get a block by its number."""
        result = await db_session.execute(
            select(Block).where(Block.block_number == block_number)
        )
        return result.scalar_one_or_none()

    async def get_block_by_hash(
        self,
        block_hash: str,
        db_session: AsyncSession,
    ) -> Optional[Block]:
        """Get a block by its hash."""
        result = await db_session.execute(
            select(Block).where(Block.block_hash == block_hash)
        )
        return result.scalar_one_or_none()

    async def create_block(
        self,
        transactions: List[BlockTransaction],
        validator: Optional[str] = None,
        db_session: AsyncSession = None,
    ) -> Block:
        """Create a new block with transactions."""
        # Get previous block
        latest = await self.get_latest_block(db_session)
        
        block_number = (latest.block_number + 1) if latest else 0
        previous_hash = latest.block_hash if latest else "0" * 64
        
        # Compute transaction hashes
        tx_hashes = [tx.tx_hash for tx in transactions]
        merkle_root = hash_lineage_manager.compute_merkle_root(tx_hashes)
        transactions_hash = hashlib.sha256("".join(tx_hashes).encode()).hexdigest()
        
        # Compute block hash
        timestamp = datetime.utcnow()
        block_content = {
            "block_number": block_number,
            "previous_hash": previous_hash,
            "merkle_root": merkle_root,
            "timestamp": timestamp.isoformat(),
            "transaction_count": len(transactions),
        }
        block_hash = hashlib.sha256(
            json.dumps(block_content, sort_keys=True).encode()
        ).hexdigest()
        
        # Create block
        block = Block(
            block_number=block_number,
            block_hash=block_hash,
            previous_block_hash=previous_hash,
            merkle_root=merkle_root,
            transaction_count=len(transactions),
            transactions_hash=transactions_hash,
            timestamp=timestamp,
            validator=validator,
        )
        db_session.add(block)
        
        # Update transactions with block reference
        for idx, tx in enumerate(transactions):
            tx.block_id = block.id
            tx.block_number = block_number
            tx.tx_index = idx
            tx.status = "confirmed"
            tx.confirmed_at = timestamp
        
        await db_session.commit()
        await db_session.refresh(block)
        return block

    async def get_pending_transactions(
        self,
        limit: int = None,
        db_session: AsyncSession = None,
    ) -> List[BlockTransaction]:
        """Get pending transactions for next block."""
        limit = limit or settings.MAX_TRANSACTIONS_PER_BLOCK
        
        result = await db_session.execute(
            select(BlockTransaction)
            .where(BlockTransaction.status == "pending")
            .order_by(BlockTransaction.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mine_block(
        self,
        validator: Optional[str] = None,
        db_session: AsyncSession = None,
    ) -> Optional[Block]:
        """Mine a new block with pending transactions."""
        transactions = await self.get_pending_transactions(db_session=db_session)
        
        if not transactions:
            return None
        
        return await self.create_block(
            transactions=transactions,
            validator=validator,
            db_session=db_session,
        )

    async def verify_chain(
        self,
        from_block: int = 0,
        to_block: Optional[int] = None,
        db_session: AsyncSession = None,
    ) -> Dict[str, Any]:
        """Verify blockchain integrity."""
        latest = await self.get_latest_block(db_session)
        if not latest:
            return {"valid": True, "blocks_checked": 0}
        
        to_block = to_block or latest.block_number
        
        errors = []
        blocks_checked = 0
        
        previous_hash = None
        for block_num in range(from_block, to_block + 1):
            block = await self.get_block_by_number(block_num, db_session)
            if not block:
                errors.append(f"Missing block {block_num}")
                continue
            
            blocks_checked += 1
            
            # Verify chain linkage
            if previous_hash and block.previous_block_hash != previous_hash:
                errors.append(f"Block {block_num}: Invalid previous hash")
            
            # Verify merkle root
            result = await db_session.execute(
                select(BlockTransaction)
                .where(BlockTransaction.block_id == block.id)
                .order_by(BlockTransaction.tx_index)
            )
            transactions = result.scalars().all()
            tx_hashes = [tx.tx_hash for tx in transactions]
            computed_merkle = hash_lineage_manager.compute_merkle_root(tx_hashes)
            
            if computed_merkle != block.merkle_root:
                errors.append(f"Block {block_num}: Invalid merkle root")
            
            previous_hash = block.block_hash
        
        return {
            "valid": len(errors) == 0,
            "blocks_checked": blocks_checked,
            "errors": errors,
        }

    async def get_chain_stats(
        self,
        db_session: AsyncSession,
    ) -> Dict[str, Any]:
        """Get blockchain statistics."""
        latest = await self.get_latest_block(db_session)
        
        # Total transactions
        tx_count = await db_session.execute(
            select(func.count(BlockTransaction.id))
        )
        total_transactions = tx_count.scalar() or 0
        
        # Pending transactions
        pending_count = await db_session.execute(
            select(func.count(BlockTransaction.id))
            .where(BlockTransaction.status == "pending")
        )
        pending_transactions = pending_count.scalar() or 0
        
        return {
            "chain_id": settings.CHAIN_ID,
            "latest_block": latest.block_number if latest else -1,
            "latest_block_hash": latest.block_hash if latest else None,
            "total_transactions": total_transactions,
            "pending_transactions": pending_transactions,
        }


class TransactionManager:
    """Manages blockchain transactions."""

    def compute_tx_hash(self, tx_data: Dict[str, Any]) -> str:
        """Compute transaction hash."""
        return hashlib.sha256(
            json.dumps(tx_data, sort_keys=True).encode()
        ).hexdigest()

    async def create_transaction(
        self,
        tx_type: str,
        payload: Dict[str, Any],
        from_dsid: Optional[str] = None,
        to_dsid: Optional[str] = None,
        signature: Optional[str] = None,
        db_session: AsyncSession = None,
    ) -> BlockTransaction:
        """Create a new transaction."""
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        
        tx_data = {
            "type": tx_type,
            "from": from_dsid,
            "to": to_dsid,
            "payload_hash": payload_hash,
            "timestamp": datetime.utcnow().isoformat(),
        }
        tx_hash = self.compute_tx_hash(tx_data)
        
        tx = BlockTransaction(
            tx_hash=tx_hash,
            tx_type=tx_type,
            from_dsid=from_dsid,
            to_dsid=to_dsid,
            payload=payload,
            payload_hash=payload_hash,
            signature=signature,
            status="pending",
        )
        db_session.add(tx)
        await db_session.commit()
        await db_session.refresh(tx)
        return tx

    async def get_transaction(
        self,
        tx_hash: str,
        db_session: AsyncSession,
    ) -> Optional[BlockTransaction]:
        """Get a transaction by hash."""
        result = await db_session.execute(
            select(BlockTransaction).where(BlockTransaction.tx_hash == tx_hash)
        )
        return result.scalar_one_or_none()

    async def get_transactions_by_dsid(
        self,
        dsid: str,
        limit: int = 50,
        db_session: AsyncSession = None,
    ) -> List[BlockTransaction]:
        """Get transactions involving a DSID."""
        result = await db_session.execute(
            select(BlockTransaction)
            .where(
                (BlockTransaction.from_dsid == dsid) |
                (BlockTransaction.to_dsid == dsid)
            )
            .order_by(BlockTransaction.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class TransactionGraphManager:
    """Manages transaction graph relationships."""

    async def add_edge(
        self,
        from_tx_hash: str,
        to_tx_hash: str,
        relationship: str,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        db_session: AsyncSession = None,
    ) -> TransactionGraph:
        """Add an edge to the transaction graph."""
        edge = TransactionGraph(
            from_tx_hash=from_tx_hash,
            to_tx_hash=to_tx_hash,
            relationship=relationship,
            weight=weight,
            metadata=metadata,
        )
        db_session.add(edge)
        await db_session.commit()
        await db_session.refresh(edge)
        return edge

    async def get_connected_transactions(
        self,
        tx_hash: str,
        direction: str = "both",  # in, out, both
        relationship: Optional[str] = None,
        db_session: AsyncSession = None,
    ) -> List[TransactionGraph]:
        """Get connected transactions in the graph."""
        if direction == "out":
            stmt = select(TransactionGraph).where(TransactionGraph.from_tx_hash == tx_hash)
        elif direction == "in":
            stmt = select(TransactionGraph).where(TransactionGraph.to_tx_hash == tx_hash)
        else:
            stmt = select(TransactionGraph).where(
                (TransactionGraph.from_tx_hash == tx_hash) |
                (TransactionGraph.to_tx_hash == tx_hash)
            )
        
        if relationship:
            stmt = stmt.where(TransactionGraph.relationship == relationship)
        
        result = await db_session.execute(stmt)
        return list(result.scalars().all())

    async def get_transaction_path(
        self,
        from_tx_hash: str,
        to_tx_hash: str,
        max_depth: int = 10,
        db_session: AsyncSession = None,
    ) -> List[str]:
        """Find path between two transactions (BFS)."""
        if from_tx_hash == to_tx_hash:
            return [from_tx_hash]
        
        visited = {from_tx_hash}
        queue = [(from_tx_hash, [from_tx_hash])]
        
        while queue and len(visited) < 1000:  # Limit search
            current, path = queue.pop(0)
            
            if len(path) > max_depth:
                continue
            
            edges = await self.get_connected_transactions(
                current, direction="out", db_session=db_session
            )
            
            for edge in edges:
                next_tx = edge.to_tx_hash
                if next_tx == to_tx_hash:
                    return path + [next_tx]
                
                if next_tx not in visited:
                    visited.add(next_tx)
                    queue.append((next_tx, path + [next_tx]))
        
        return []  # No path found

    async def get_graph_stats(
        self,
        db_session: AsyncSession,
    ) -> Dict[str, Any]:
        """Get transaction graph statistics."""
        edge_count = await db_session.execute(
            select(func.count(TransactionGraph.id))
        )
        
        relationship_counts = await db_session.execute(
            select(TransactionGraph.relationship, func.count(TransactionGraph.id))
            .group_by(TransactionGraph.relationship)
        )
        
        return {
            "total_edges": edge_count.scalar() or 0,
            "relationships": dict(relationship_counts.all()),
        }


blockchain_manager = BlockchainManager()
transaction_manager = TransactionManager()
graph_manager = TransactionGraphManager()
