"""
BLOCKCHAIN SHARDING
===================

Most advanced blockchain: Horizontal scaling through sharding.
Parallel transaction processing across multiple shards.

Features:
- Dynamic shard allocation
- Cross-shard transactions
- Shard state management
- Load balancing
- Shard reorganization
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

logger = logging.getLogger(__name__)


class ShardStatus(Enum):
    ACTIVE = "active"
    SYNCING = "syncing"
    REORGANIZING = "reorganizing"
    INACTIVE = "inactive"


@dataclass
class ShardBlock:
    """A block within a shard."""
    id: str
    shard_id: str
    height: int
    previous_hash: str
    transactions: List[Dict[str, Any]]
    state_root: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @property
    def hash(self) -> str:
        data = f"{self.shard_id}{self.height}{self.previous_hash}{self.state_root}"
        return hashlib.sha256(data.encode()).hexdigest()


@dataclass
class Shard:
    """A single shard in the blockchain."""
    id: str
    shard_index: int
    status: ShardStatus = ShardStatus.ACTIVE
    blocks: List[ShardBlock] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    validators: Set[str] = field(default_factory=set)
    
    # Metrics
    transaction_count: int = 0
    last_block_time: Optional[str] = None
    
    def get_latest_block(self) -> Optional[ShardBlock]:
        return self.blocks[-1] if self.blocks else None
    
    def get_state_root(self) -> str:
        state_str = str(sorted(self.state.items()))
        return hashlib.sha256(state_str.encode()).hexdigest()


@dataclass
class CrossShardTransaction:
    """Transaction spanning multiple shards."""
    id: str
    source_shard: str
    target_shard: str
    sender: str
    receiver: str
    data: Dict[str, Any]
    status: str = "pending"  # pending, locked, committed, failed
    lock_proof: Optional[str] = None
    commit_proof: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ShardAssigner:
    """Assigns addresses and transactions to shards."""
    
    def __init__(self, num_shards: int):
        self.num_shards = num_shards
    
    def get_shard_for_address(self, address: str) -> int:
        """Determine which shard an address belongs to."""
        address_hash = hashlib.sha256(address.encode()).hexdigest()
        return int(address_hash[:8], 16) % self.num_shards
    
    def get_shard_for_transaction(self, tx: Dict[str, Any]) -> int:
        """Determine which shard should process a transaction."""
        sender = tx.get("sender", "")
        return self.get_shard_for_address(sender)
    
    def is_cross_shard(self, sender: str, receiver: str) -> bool:
        """Check if transaction is cross-shard."""
        return self.get_shard_for_address(sender) != self.get_shard_for_address(receiver)


class CrossShardCoordinator:
    """
    Coordinates cross-shard transactions using 2-phase commit.
    """
    
    def __init__(self):
        self.pending_transactions: Dict[str, CrossShardTransaction] = {}
        self.locks: Dict[str, Set[str]] = {}  # shard_id -> locked tx_ids
    
    async def initiate_cross_shard(
        self,
        source_shard: str,
        target_shard: str,
        sender: str,
        receiver: str,
        data: Dict[str, Any],
    ) -> CrossShardTransaction:
        """Initiate a cross-shard transaction."""
        tx = CrossShardTransaction(
            id=str(uuid4()),
            source_shard=source_shard,
            target_shard=target_shard,
            sender=sender,
            receiver=receiver,
            data=data,
        )
        
        self.pending_transactions[tx.id] = tx
        
        logger.info(f"Cross-shard tx initiated: {tx.id}")
        return tx
    
    async def lock_phase(self, tx_id: str, shard_manager: 'ShardManager') -> bool:
        """Phase 1: Lock resources on both shards."""
        tx = self.pending_transactions.get(tx_id)
        if not tx:
            return False
        
        # Lock on source shard
        source_locked = await self._lock_on_shard(tx.source_shard, tx_id, tx.data, shard_manager)
        if not source_locked:
            tx.status = "failed"
            return False
        
        # Lock on target shard
        target_locked = await self._lock_on_shard(tx.target_shard, tx_id, tx.data, shard_manager)
        if not target_locked:
            await self._unlock_on_shard(tx.source_shard, tx_id, shard_manager)
            tx.status = "failed"
            return False
        
        tx.status = "locked"
        tx.lock_proof = hashlib.sha256(f"{tx_id}:locked".encode()).hexdigest()
        
        return True
    
    async def commit_phase(self, tx_id: str, shard_manager: 'ShardManager') -> bool:
        """Phase 2: Commit on both shards."""
        tx = self.pending_transactions.get(tx_id)
        if not tx or tx.status != "locked":
            return False
        
        # Commit on source
        await self._commit_on_shard(tx.source_shard, tx_id, tx.data, shard_manager)
        
        # Commit on target
        await self._commit_on_shard(tx.target_shard, tx_id, tx.data, shard_manager)
        
        tx.status = "committed"
        tx.commit_proof = hashlib.sha256(f"{tx_id}:committed".encode()).hexdigest()
        
        logger.info(f"Cross-shard tx committed: {tx_id}")
        return True
    
    async def _lock_on_shard(
        self,
        shard_id: str,
        tx_id: str,
        data: Dict[str, Any],
        shard_manager: 'ShardManager',
    ) -> bool:
        """Lock resources on a shard."""
        if shard_id not in self.locks:
            self.locks[shard_id] = set()
        
        self.locks[shard_id].add(tx_id)
        return True
    
    async def _unlock_on_shard(
        self,
        shard_id: str,
        tx_id: str,
        shard_manager: 'ShardManager',
    ):
        """Unlock resources on a shard."""
        if shard_id in self.locks:
            self.locks[shard_id].discard(tx_id)
    
    async def _commit_on_shard(
        self,
        shard_id: str,
        tx_id: str,
        data: Dict[str, Any],
        shard_manager: 'ShardManager',
    ):
        """Commit transaction on a shard."""
        # Remove lock
        if shard_id in self.locks:
            self.locks[shard_id].discard(tx_id)
        
        # Apply to shard state
        shard = shard_manager.get_shard(shard_id)
        if shard:
            shard.state[f"cross_shard_{tx_id}"] = data


class ShardManager:
    """
    Manages all shards in the blockchain.
    """
    
    DEFAULT_NUM_SHARDS = 4
    
    def __init__(self, num_shards: int = None):
        self.num_shards = num_shards or self.DEFAULT_NUM_SHARDS
        self.shards: Dict[str, Shard] = {}
        self.assigner = ShardAssigner(self.num_shards)
        self.cross_shard_coordinator = CrossShardCoordinator()
        
        # Initialize shards
        for i in range(self.num_shards):
            shard = Shard(
                id=f"shard_{i}",
                shard_index=i,
            )
            self.shards[shard.id] = shard
    
    def get_shard(self, shard_id: str) -> Optional[Shard]:
        """Get a shard by ID."""
        return self.shards.get(shard_id)
    
    def get_shard_for_address(self, address: str) -> Shard:
        """Get the shard for an address."""
        shard_index = self.assigner.get_shard_for_address(address)
        return self.shards[f"shard_{shard_index}"]
    
    async def submit_transaction(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a transaction to the appropriate shard."""
        sender = tx.get("sender", "")
        receiver = tx.get("receiver", "")
        
        if self.assigner.is_cross_shard(sender, receiver):
            return await self._handle_cross_shard_tx(tx)
        else:
            return await self._handle_single_shard_tx(tx)
    
    async def _handle_single_shard_tx(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        """Handle transaction within a single shard."""
        shard = self.get_shard_for_address(tx.get("sender", ""))
        
        # Add to pending transactions
        tx["id"] = str(uuid4())
        tx["shard_id"] = shard.id
        tx["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        # Update shard state
        shard.state[tx["id"]] = tx
        shard.transaction_count += 1
        
        return {
            "success": True,
            "tx_id": tx["id"],
            "shard_id": shard.id,
            "cross_shard": False,
        }
    
    async def _handle_cross_shard_tx(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cross-shard transaction."""
        sender = tx.get("sender", "")
        receiver = tx.get("receiver", "")
        
        source_shard = self.get_shard_for_address(sender)
        target_shard = self.get_shard_for_address(receiver)
        
        # Initiate cross-shard
        cross_tx = await self.cross_shard_coordinator.initiate_cross_shard(
            source_shard=source_shard.id,
            target_shard=target_shard.id,
            sender=sender,
            receiver=receiver,
            data=tx,
        )
        
        # Execute 2-phase commit
        locked = await self.cross_shard_coordinator.lock_phase(cross_tx.id, self)
        if not locked:
            return {
                "success": False,
                "error": "Failed to lock resources",
                "cross_shard": True,
            }
        
        committed = await self.cross_shard_coordinator.commit_phase(cross_tx.id, self)
        if not committed:
            return {
                "success": False,
                "error": "Failed to commit",
                "cross_shard": True,
            }
        
        source_shard.transaction_count += 1
        target_shard.transaction_count += 1
        
        return {
            "success": True,
            "tx_id": cross_tx.id,
            "source_shard": source_shard.id,
            "target_shard": target_shard.id,
            "cross_shard": True,
        }
    
    async def create_block(self, shard_id: str, transactions: List[Dict[str, Any]]) -> Optional[ShardBlock]:
        """Create a new block on a shard."""
        shard = self.get_shard(shard_id)
        if not shard:
            return None
        
        latest = shard.get_latest_block()
        previous_hash = latest.hash if latest else "genesis"
        height = (latest.height + 1) if latest else 0
        
        block = ShardBlock(
            id=str(uuid4()),
            shard_id=shard_id,
            height=height,
            previous_hash=previous_hash,
            transactions=transactions,
            state_root=shard.get_state_root(),
        )
        
        shard.blocks.append(block)
        shard.last_block_time = block.timestamp
        
        logger.info(f"Block {height} created on {shard_id}")
        return block
    
    async def rebalance_shards(self):
        """Rebalance load across shards."""
        # Calculate load per shard
        loads = {
            shard_id: shard.transaction_count
            for shard_id, shard in self.shards.items()
        }
        
        avg_load = sum(loads.values()) / len(loads) if loads else 0
        
        # Mark overloaded shards for reorganization
        for shard_id, load in loads.items():
            if load > avg_load * 1.5:
                self.shards[shard_id].status = ShardStatus.REORGANIZING
                logger.info(f"Shard {shard_id} marked for rebalancing")
    
    def add_shard(self) -> Shard:
        """Dynamically add a new shard."""
        new_index = self.num_shards
        self.num_shards += 1
        self.assigner = ShardAssigner(self.num_shards)
        
        shard = Shard(
            id=f"shard_{new_index}",
            shard_index=new_index,
        )
        self.shards[shard.id] = shard
        
        logger.info(f"New shard added: {shard.id}")
        return shard
    
    def get_stats(self) -> Dict[str, Any]:
        """Get sharding statistics."""
        return {
            "num_shards": self.num_shards,
            "total_transactions": sum(s.transaction_count for s in self.shards.values()),
            "total_blocks": sum(len(s.blocks) for s in self.shards.values()),
            "cross_shard_pending": len(self.cross_shard_coordinator.pending_transactions),
            "shards": {
                shard_id: {
                    "status": shard.status.value,
                    "transactions": shard.transaction_count,
                    "blocks": len(shard.blocks),
                }
                for shard_id, shard in self.shards.items()
            },
        }


# Global instance
_shard_manager: Optional[ShardManager] = None


def get_shard_manager() -> ShardManager:
    """Get or create shard manager."""
    global _shard_manager
    if _shard_manager is None:
        _shard_manager = ShardManager()
    return _shard_manager
