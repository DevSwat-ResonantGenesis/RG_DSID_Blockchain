"""
Dual-Class Blockchain System (HSU-Spec Layer 5)
================================================

Implements the two-class block architecture:
- Class U (User Blocks): One per user, contains user sphere root
- Class A (Agent Blocks): One per agent cluster, contains agent state

This is NOT a consensus blockchain - it's for proof-of-existence and ownership.
"""

import hashlib
import secrets
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class BlockClass(Enum):
    """Block classification"""
    USER = "U"      # User Block
    AGENT = "A"     # Agent Block


class BlockStatus(Enum):
    """Block status"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SUPERSEDED = "superseded"


@dataclass
class UserBlock:
    """
    Class U - User Block
    
    Created once per user. Contains:
    - User identity hash (Layer 1)
    - User's master hash sphere (Layer 2 root)
    - Encrypted references to all user's agents
    - User transaction history
    - Ownership rules
    - Smart contract definitions
    """
    block_class: str = "U"
    block_number: int = 0
    block_hash: str = ""
    previous_block_hash: Optional[str] = None
    
    # User Identity (Layer 1)
    user_id: str = ""
    user_dsid: str = ""
    public_key: Optional[str] = None
    identity_hash: str = ""  # H(public_key)
    
    # User Sphere Root (Layer 2)
    sphere_root: str = ""  # Root hash of user's data universe
    sphere_version: int = 1
    
    # Agent References (encrypted)
    agent_dsids: List[str] = field(default_factory=list)
    agent_count: int = 0
    
    # Transaction History
    transaction_merkle_root: str = ""
    transaction_count: int = 0
    
    # Ownership Rules (Smart Contract)
    ownership_rules: Dict[str, Any] = field(default_factory=dict)
    
    # State
    status: BlockStatus = BlockStatus.PENDING
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    # Signature
    signature: Optional[str] = None
    
    def compute_hash(self) -> str:
        """Compute block hash from contents"""
        content = (
            f"{self.block_class}:"
            f"{self.block_number}:"
            f"{self.previous_block_hash or 'genesis'}:"
            f"{self.user_dsid}:"
            f"{self.identity_hash}:"
            f"{self.sphere_root}:"
            f"{self.transaction_merkle_root}:"
            f"{self.created_at.isoformat()}"
        )
        return hashlib.sha256(content.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "block_class": self.block_class,
            "block_number": self.block_number,
            "block_hash": self.block_hash,
            "previous_block_hash": self.previous_block_hash,
            "user_id": self.user_id,
            "user_dsid": self.user_dsid,
            "identity_hash": self.identity_hash,
            "sphere_root": self.sphere_root,
            "sphere_version": self.sphere_version,
            "agent_count": self.agent_count,
            "transaction_count": self.transaction_count,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class AgentBlock:
    """
    Class A - Agent Block
    
    Created per agent cluster. Contains:
    - Agent identity hash
    - Cluster ID
    - Owner hash (encrypted)
    - Operational history
    - Version history
    - Transferred ownership events
    - Rental contracts
    - Performance metrics
    - Hash-sphere pointer to agent data (Layers 3 and 4)
    """
    block_class: str = "A"
    block_number: int = 0
    block_hash: str = ""
    previous_block_hash: Optional[str] = None
    
    # Agent Identity (Layer 1)
    agent_id: str = ""
    agent_dsid: str = ""
    agent_hash: str = ""  # Resonance hash
    
    # Cluster Membership
    cluster_id: str = ""
    cluster_name: str = ""
    
    # Owner Reference (encrypted)
    owner_dsid: str = ""  # Encrypted owner DSID
    owner_hash: str = ""  # H(owner_dsid)
    
    # Agent Sphere Root (Layer 3)
    state_root: str = ""  # Root of agent's state sphere
    memory_root: str = ""  # Root of agent's memory sphere
    capability_root: str = ""  # Root of capability definitions
    
    # Version History
    version: int = 1
    version_history: List[str] = field(default_factory=list)  # List of previous state roots
    
    # Ownership Events
    ownership_transfers: List[Dict[str, Any]] = field(default_factory=list)
    rental_contracts: List[Dict[str, Any]] = field(default_factory=list)
    
    # Performance Metrics
    total_interactions: int = 0
    success_rate: float = 0.0
    avg_response_time_ms: int = 0
    
    # Transaction History
    transaction_merkle_root: str = ""
    transaction_count: int = 0
    
    # State
    status: BlockStatus = BlockStatus.PENDING
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    # Signature
    signature: Optional[str] = None
    
    def compute_hash(self) -> str:
        """Compute block hash from contents"""
        content = (
            f"{self.block_class}:"
            f"{self.block_number}:"
            f"{self.previous_block_hash or 'genesis'}:"
            f"{self.agent_dsid}:"
            f"{self.cluster_id}:"
            f"{self.owner_hash}:"
            f"{self.state_root}:"
            f"{self.transaction_merkle_root}:"
            f"{self.created_at.isoformat()}"
        )
        return hashlib.sha256(content.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "block_class": self.block_class,
            "block_number": self.block_number,
            "block_hash": self.block_hash,
            "previous_block_hash": self.previous_block_hash,
            "agent_id": self.agent_id,
            "agent_dsid": self.agent_dsid,
            "cluster_id": self.cluster_id,
            "cluster_name": self.cluster_name,
            "owner_hash": self.owner_hash,
            "state_root": self.state_root,
            "version": self.version,
            "total_interactions": self.total_interactions,
            "success_rate": self.success_rate,
            "transaction_count": self.transaction_count,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
        }


class DualClassBlockchain:
    """
    Dual-Class Blockchain Manager
    
    Manages User Blocks (Class U) and Agent Blocks (Class A).
    
    Architecture:
    - User Blocks expand vertically (user updates)
    - Agent Blocks expand horizontally (new agents/clusters)
    
    UserBlock → UserHashSphereLayer
    AgentBlock → AgentClusterSphereLayer
    """
    
    def __init__(self):
        self._user_blocks: Dict[str, UserBlock] = {}  # user_id -> latest block
        self._agent_blocks: Dict[str, AgentBlock] = {}  # agent_id -> latest block
        self._block_chain: List[Dict[str, Any]] = []  # Ordered chain
        self._next_block_number = 1
    
    def _hash(self, data: str) -> str:
        """Generate SHA-256 hash"""
        return hashlib.sha256(data.encode()).hexdigest()
    
    def _generate_dsid(self, entity_type: str, content_hash: str) -> str:
        """Generate a DSID identifier"""
        random_suffix = secrets.token_hex(4)
        return f"dsid:v1:{entity_type}:{content_hash[:16]}:{random_suffix}"
    
    # ==========================================
    # USER BLOCK OPERATIONS
    # ==========================================
    
    def create_user_block(
        self,
        user_id: str,
        public_key: Optional[str] = None,
        initial_data: Optional[Dict[str, Any]] = None,
    ) -> UserBlock:
        """
        Create a new User Block (Class U).
        
        Called when a new user registers on the platform.
        """
        # Generate identity hash
        identity_hash = self._hash(public_key or user_id)
        
        # Generate user DSID
        user_dsid = self._generate_dsid("user", identity_hash)
        
        # Generate initial sphere root
        sphere_data = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            **(initial_data or {}),
        }
        sphere_root = self._hash(str(sphere_data))
        
        # Get previous block hash
        previous_hash = None
        if self._block_chain:
            previous_hash = self._block_chain[-1].get("block_hash")
        
        # Create block
        block = UserBlock(
            block_number=self._next_block_number,
            user_id=user_id,
            user_dsid=user_dsid,
            public_key=public_key,
            identity_hash=identity_hash,
            sphere_root=sphere_root,
            previous_block_hash=previous_hash,
            ownership_rules={
                "can_create_agents": True,
                "max_agents": 100,
                "can_transfer_agents": True,
            },
        )
        
        # Compute block hash
        block.block_hash = block.compute_hash()
        block.status = BlockStatus.CONFIRMED
        
        # Store
        self._user_blocks[user_id] = block
        self._block_chain.append({
            "block_class": "U",
            "block_number": block.block_number,
            "block_hash": block.block_hash,
            "entity_id": user_id,
        })
        self._next_block_number += 1
        
        logger.info(f"📦 Created User Block #{block.block_number} for user {user_id[:8]}...")
        
        return block
    
    def update_user_block(
        self,
        user_id: str,
        new_sphere_root: Optional[str] = None,
        new_agent_dsids: Optional[List[str]] = None,
        transaction_hash: Optional[str] = None,
    ) -> Optional[UserBlock]:
        """
        Update a User Block with new state.
        
        Creates a new version of the block (supersedes old one).
        """
        if user_id not in self._user_blocks:
            logger.warning(f"User block not found for {user_id}")
            return None
        
        old_block = self._user_blocks[user_id]
        
        # Mark old block as superseded
        old_block.status = BlockStatus.SUPERSEDED
        
        # Create new block
        new_block = UserBlock(
            block_number=self._next_block_number,
            user_id=user_id,
            user_dsid=old_block.user_dsid,
            public_key=old_block.public_key,
            identity_hash=old_block.identity_hash,
            sphere_root=new_sphere_root or old_block.sphere_root,
            sphere_version=old_block.sphere_version + 1,
            agent_dsids=new_agent_dsids or old_block.agent_dsids,
            agent_count=len(new_agent_dsids) if new_agent_dsids else old_block.agent_count,
            transaction_count=old_block.transaction_count + (1 if transaction_hash else 0),
            previous_block_hash=old_block.block_hash,
            ownership_rules=old_block.ownership_rules,
        )
        
        # Update transaction merkle root if new transaction
        if transaction_hash:
            all_tx_hashes = [old_block.transaction_merkle_root, transaction_hash]
            new_block.transaction_merkle_root = self._compute_merkle_root(all_tx_hashes)
        else:
            new_block.transaction_merkle_root = old_block.transaction_merkle_root
        
        # Compute hash and confirm
        new_block.block_hash = new_block.compute_hash()
        new_block.status = BlockStatus.CONFIRMED
        
        # Store
        self._user_blocks[user_id] = new_block
        self._block_chain.append({
            "block_class": "U",
            "block_number": new_block.block_number,
            "block_hash": new_block.block_hash,
            "entity_id": user_id,
        })
        self._next_block_number += 1
        
        logger.info(f"📦 Updated User Block #{new_block.block_number} (v{new_block.sphere_version})")
        
        return new_block
    
    def get_user_block(self, user_id: str) -> Optional[UserBlock]:
        """Get the latest User Block for a user"""
        return self._user_blocks.get(user_id)
    
    # ==========================================
    # AGENT BLOCK OPERATIONS
    # ==========================================
    
    def create_agent_block(
        self,
        agent_id: str,
        agent_hash: str,
        owner_id: str,
        cluster_id: str,
        cluster_name: str = "",
        capabilities: Optional[Dict[str, Any]] = None,
    ) -> AgentBlock:
        """
        Create a new Agent Block (Class A).
        
        Called when a new agent is created.
        """
        # Generate agent DSID
        agent_dsid = self._generate_dsid("agent", agent_hash)
        
        # Get owner hash (encrypted reference)
        owner_dsid = self._user_blocks.get(owner_id, UserBlock()).user_dsid
        owner_hash = self._hash(owner_dsid or owner_id)
        
        # Generate state roots
        state_data = {
            "agent_id": agent_id,
            "created_at": datetime.utcnow().isoformat(),
        }
        state_root = self._hash(str(state_data))
        memory_root = self._hash(f"memory:{agent_id}")
        capability_root = self._hash(str(capabilities or {}))
        
        # Get previous block hash
        previous_hash = None
        if self._block_chain:
            previous_hash = self._block_chain[-1].get("block_hash")
        
        # Create block
        block = AgentBlock(
            block_number=self._next_block_number,
            agent_id=agent_id,
            agent_dsid=agent_dsid,
            agent_hash=agent_hash,
            cluster_id=cluster_id,
            cluster_name=cluster_name,
            owner_dsid=owner_dsid,
            owner_hash=owner_hash,
            state_root=state_root,
            memory_root=memory_root,
            capability_root=capability_root,
            previous_block_hash=previous_hash,
        )
        
        # Compute block hash
        block.block_hash = block.compute_hash()
        block.status = BlockStatus.CONFIRMED
        
        # Store
        self._agent_blocks[agent_id] = block
        self._block_chain.append({
            "block_class": "A",
            "block_number": block.block_number,
            "block_hash": block.block_hash,
            "entity_id": agent_id,
        })
        self._next_block_number += 1
        
        # Update owner's user block with new agent reference
        if owner_id in self._user_blocks:
            user_block = self._user_blocks[owner_id]
            new_agents = user_block.agent_dsids + [agent_dsid]
            self.update_user_block(owner_id, new_agent_dsids=new_agents)
        
        logger.info(f"📦 Created Agent Block #{block.block_number} for agent {agent_id[:8]}...")
        
        return block
    
    def update_agent_block(
        self,
        agent_id: str,
        new_state_root: Optional[str] = None,
        new_memory_root: Optional[str] = None,
        interaction_count: int = 0,
        success_count: int = 0,
        response_time_ms: int = 0,
        transaction_hash: Optional[str] = None,
    ) -> Optional[AgentBlock]:
        """
        Update an Agent Block with new state.
        """
        if agent_id not in self._agent_blocks:
            logger.warning(f"Agent block not found for {agent_id}")
            return None
        
        old_block = self._agent_blocks[agent_id]
        
        # Mark old block as superseded
        old_block.status = BlockStatus.SUPERSEDED
        
        # Calculate new metrics
        total_interactions = old_block.total_interactions + interaction_count
        if total_interactions > 0:
            old_successes = old_block.success_rate * old_block.total_interactions
            new_success_rate = (old_successes + success_count) / total_interactions
        else:
            new_success_rate = 0.0
        
        # Create new block
        new_block = AgentBlock(
            block_number=self._next_block_number,
            agent_id=agent_id,
            agent_dsid=old_block.agent_dsid,
            agent_hash=old_block.agent_hash,
            cluster_id=old_block.cluster_id,
            cluster_name=old_block.cluster_name,
            owner_dsid=old_block.owner_dsid,
            owner_hash=old_block.owner_hash,
            state_root=new_state_root or old_block.state_root,
            memory_root=new_memory_root or old_block.memory_root,
            capability_root=old_block.capability_root,
            version=old_block.version + 1,
            version_history=old_block.version_history + [old_block.state_root],
            ownership_transfers=old_block.ownership_transfers,
            rental_contracts=old_block.rental_contracts,
            total_interactions=total_interactions,
            success_rate=new_success_rate,
            avg_response_time_ms=response_time_ms or old_block.avg_response_time_ms,
            transaction_count=old_block.transaction_count + (1 if transaction_hash else 0),
            previous_block_hash=old_block.block_hash,
        )
        
        # Update transaction merkle root
        if transaction_hash:
            all_tx_hashes = [old_block.transaction_merkle_root, transaction_hash]
            new_block.transaction_merkle_root = self._compute_merkle_root(all_tx_hashes)
        else:
            new_block.transaction_merkle_root = old_block.transaction_merkle_root
        
        # Compute hash and confirm
        new_block.block_hash = new_block.compute_hash()
        new_block.status = BlockStatus.CONFIRMED
        
        # Store
        self._agent_blocks[agent_id] = new_block
        self._block_chain.append({
            "block_class": "A",
            "block_number": new_block.block_number,
            "block_hash": new_block.block_hash,
            "entity_id": agent_id,
        })
        self._next_block_number += 1
        
        logger.info(f"📦 Updated Agent Block #{new_block.block_number} (v{new_block.version})")
        
        return new_block
    
    def get_agent_block(self, agent_id: str) -> Optional[AgentBlock]:
        """Get the latest Agent Block for an agent"""
        return self._agent_blocks.get(agent_id)
    
    def transfer_agent_ownership(
        self,
        agent_id: str,
        new_owner_id: str,
        transfer_type: str = "permanent",  # permanent, rental, delegation
        rental_duration_hours: Optional[int] = None,
    ) -> Optional[AgentBlock]:
        """
        Transfer agent ownership to a new user.
        """
        if agent_id not in self._agent_blocks:
            return None
        
        old_block = self._agent_blocks[agent_id]
        old_owner_dsid = old_block.owner_dsid
        
        # Get new owner DSID
        new_owner_dsid = self._user_blocks.get(new_owner_id, UserBlock()).user_dsid
        new_owner_hash = self._hash(new_owner_dsid or new_owner_id)
        
        # Create transfer record
        transfer_record = {
            "from_dsid": old_owner_dsid,
            "to_dsid": new_owner_dsid,
            "transfer_type": transfer_type,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if transfer_type == "rental" and rental_duration_hours:
            transfer_record["rental_duration_hours"] = rental_duration_hours
            transfer_record["rental_expires_at"] = (
                datetime.utcnow().timestamp() + (rental_duration_hours * 3600)
            )
        
        # Update block with new owner
        old_block.status = BlockStatus.SUPERSEDED
        
        new_block = AgentBlock(
            block_number=self._next_block_number,
            agent_id=agent_id,
            agent_dsid=old_block.agent_dsid,
            agent_hash=old_block.agent_hash,
            cluster_id=old_block.cluster_id,
            cluster_name=old_block.cluster_name,
            owner_dsid=new_owner_dsid,
            owner_hash=new_owner_hash,
            state_root=old_block.state_root,
            memory_root=old_block.memory_root,
            capability_root=old_block.capability_root,
            version=old_block.version + 1,
            version_history=old_block.version_history + [old_block.state_root],
            ownership_transfers=old_block.ownership_transfers + [transfer_record],
            rental_contracts=old_block.rental_contracts,
            total_interactions=old_block.total_interactions,
            success_rate=old_block.success_rate,
            avg_response_time_ms=old_block.avg_response_time_ms,
            transaction_count=old_block.transaction_count + 1,
            previous_block_hash=old_block.block_hash,
        )
        
        new_block.block_hash = new_block.compute_hash()
        new_block.status = BlockStatus.CONFIRMED
        
        self._agent_blocks[agent_id] = new_block
        self._block_chain.append({
            "block_class": "A",
            "block_number": new_block.block_number,
            "block_hash": new_block.block_hash,
            "entity_id": agent_id,
        })
        self._next_block_number += 1
        
        logger.info(f"📦 Transferred agent {agent_id[:8]}... to {new_owner_id[:8]}...")
        
        return new_block
    
    # ==========================================
    # CHAIN OPERATIONS
    # ==========================================
    
    def _compute_merkle_root(self, hashes: List[str]) -> str:
        """Compute Merkle root from hashes"""
        if not hashes:
            return self._hash("")
        
        if len(hashes) == 1:
            return hashes[0]
        
        working = hashes.copy()
        if len(working) % 2 == 1:
            working.append(working[-1])
        
        while len(working) > 1:
            new_level = []
            for i in range(0, len(working), 2):
                combined = working[i] + working[i + 1]
                new_level.append(self._hash(combined))
            working = new_level
        
        return working[0]
    
    def verify_chain(self) -> Tuple[bool, str]:
        """Verify the integrity of the blockchain"""
        if not self._block_chain:
            return True, "Empty chain is valid"
        
        for i, block_ref in enumerate(self._block_chain):
            block_class = block_ref["block_class"]
            entity_id = block_ref["entity_id"]
            stored_hash = block_ref["block_hash"]
            
            # Get the actual block
            if block_class == "U":
                block = self._user_blocks.get(entity_id)
            else:
                block = self._agent_blocks.get(entity_id)
            
            if not block:
                continue  # Block may have been superseded
            
            # Verify hash
            computed_hash = block.compute_hash()
            if computed_hash != stored_hash and block.status == BlockStatus.CONFIRMED:
                return False, f"Hash mismatch at block #{block_ref['block_number']}"
            
            # Verify chain linkage (skip first block)
            if i > 0:
                expected_prev = self._block_chain[i - 1]["block_hash"]
                if block.previous_block_hash != expected_prev:
                    return False, f"Chain linkage broken at block #{block_ref['block_number']}"
        
        return True, "Chain verified"
    
    def get_chain_stats(self) -> Dict[str, Any]:
        """Get blockchain statistics"""
        user_blocks = [b for b in self._block_chain if b["block_class"] == "U"]
        agent_blocks = [b for b in self._block_chain if b["block_class"] == "A"]
        
        return {
            "total_blocks": len(self._block_chain),
            "user_blocks": len(user_blocks),
            "agent_blocks": len(agent_blocks),
            "active_users": len(self._user_blocks),
            "active_agents": len(self._agent_blocks),
            "next_block_number": self._next_block_number,
            "chain_valid": self.verify_chain()[0],
        }
    
    def get_blocks_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all blocks related to a user"""
        blocks = []
        
        # User's own block
        if user_id in self._user_blocks:
            blocks.append(self._user_blocks[user_id].to_dict())
        
        # User's agent blocks
        for agent_id, agent_block in self._agent_blocks.items():
            if agent_block.owner_hash == self._hash(
                self._user_blocks.get(user_id, UserBlock()).user_dsid or user_id
            ):
                blocks.append(agent_block.to_dict())
        
        return blocks


# Global instance
dual_class_blockchain = DualClassBlockchain()


# Convenience functions
def create_user_block(user_id: str, public_key: Optional[str] = None) -> UserBlock:
    """Create a User Block"""
    return dual_class_blockchain.create_user_block(user_id, public_key)


def create_agent_block(
    agent_id: str,
    agent_hash: str,
    owner_id: str,
    cluster_id: str,
    cluster_name: str = "",
) -> AgentBlock:
    """Create an Agent Block"""
    return dual_class_blockchain.create_agent_block(
        agent_id, agent_hash, owner_id, cluster_id, cluster_name
    )


def get_user_block(user_id: str) -> Optional[UserBlock]:
    """Get User Block"""
    return dual_class_blockchain.get_user_block(user_id)


def get_agent_block(agent_id: str) -> Optional[AgentBlock]:
    """Get Agent Block"""
    return dual_class_blockchain.get_agent_block(agent_id)


def get_chain_stats() -> Dict[str, Any]:
    """Get chain statistics"""
    return dual_class_blockchain.get_chain_stats()
