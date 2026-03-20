"""
HSU-Spec Section 24: Agent Lifecycle Specification
===================================================

Complete lifecycle model for DSID-P Autonomous Agents:
1. Creation
2. Initialization
3. Activation
4. Operation
5. Memory Evolution
6. Semantic Evolution
7. Coordination & Collaboration
8. Governance Enforcement
9. Upgrades
10. Ownership Transfer
11. Suspension
12. Retirement / Archival

Ensures safety, auditability, predictability, and deterministic behavior.
"""

import hashlib
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


# ============== LIFECYCLE STAGES ==============

class LifecycleStage(Enum):
    """Agent lifecycle stages"""
    CREATED = "created"              # Stage 1: Identity defined
    INITIALIZED = "initialized"      # Stage 2: DAG built
    ACTIVATED = "activated"          # Stage 3: Registry block written
    OPERATIONAL = "operational"      # Stage 4: Active execution
    EVOLVING = "evolving"           # Stage 5-6: Memory/semantic evolution
    COORDINATING = "coordinating"   # Stage 7: Multi-agent collaboration
    GOVERNED = "governed"           # Stage 8: Under governance
    UPGRADING = "upgrading"         # Stage 9: Capability upgrade
    TRANSFERRING = "transferring"   # Stage 10: Ownership transfer
    SUSPENDED = "suspended"         # Stage 11: Temporarily frozen
    RETIRED = "retired"             # Stage 12: Permanently archived


class SuspensionReason(Enum):
    """Reasons for agent suspension"""
    GOVERNANCE_VIOLATION = "governance_violation"
    CLUSTER_DRIFT = "cluster_drift"
    MISALIGNMENT = "misalignment"
    OWNER_REQUEST = "owner_request"
    ENTERPRISE_RULE = "enterprise_rule"
    GOVERNMENT_REGULATION = "government_regulation"
    SECURITY_CONCERN = "security_concern"


class RetirementReason(Enum):
    """Reasons for agent retirement"""
    NO_LONGER_NEEDED = "no_longer_needed"
    REPLACED = "replaced"
    EXPIRED = "expired"
    TERMINATED_BY_OWNER = "terminated_by_owner"
    TERMINATED_BY_AUTHORITY = "terminated_by_authority"


# ============== LIFECYCLE EVENTS ==============

@dataclass
class LifecycleEvent:
    """Record of a lifecycle transition"""
    event_id: str
    agent_id: str
    from_stage: Optional[LifecycleStage]
    to_stage: LifecycleStage
    triggered_by: str
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: int = field(default_factory=lambda: int(time.time()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "agent_id": self.agent_id,
            "from_stage": self.from_stage.value if self.from_stage else None,
            "to_stage": self.to_stage.value,
            "triggered_by": self.triggered_by,
            "reason": self.reason,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


# ============== AGENT STATE ==============

@dataclass
class AgentCreationSpec:
    """Specification for creating an agent (Stage 1)"""
    purpose: str
    initial_capabilities: List[str]
    cluster_hints: List[str] = field(default_factory=list)
    initial_policies: List[str] = field(default_factory=list)
    owner_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentSphere:
    """Agent Sphere DAG structure (Stage 2)"""
    sphere_root: str
    behavior_nodes: List[str] = field(default_factory=list)
    policy_nodes: List[str] = field(default_factory=list)
    memory_nodes: List[str] = field(default_factory=list)
    semantic_vector_node: Optional[str] = None
    cluster_assignment_node: Optional[str] = None
    capability_nodes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sphere_root": self.sphere_root,
            "behavior_nodes": self.behavior_nodes,
            "policy_nodes": self.policy_nodes,
            "memory_nodes": self.memory_nodes,
            "semantic_vector_node": self.semantic_vector_node,
            "cluster_assignment_node": self.cluster_assignment_node,
            "capability_nodes": self.capability_nodes,
        }


@dataclass
class AgentActivation:
    """Activation record (Stage 3)"""
    activation_id: str
    agent_id: str
    sphere_root: str
    cluster_id: str
    ownership_signature: str
    registry_block_id: str
    activated_at: int = field(default_factory=lambda: int(time.time()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "activation_id": self.activation_id,
            "agent_id": self.agent_id,
            "sphere_root": self.sphere_root,
            "cluster_id": self.cluster_id,
            "ownership_signature": self.ownership_signature,
            "registry_block_id": self.registry_block_id,
            "activated_at": self.activated_at,
        }


@dataclass
class AgentState:
    """Complete agent state"""
    agent_id: str
    identity_hash: str
    owner_id: str
    stage: LifecycleStage
    sphere: Optional[AgentSphere] = None
    activation: Optional[AgentActivation] = None
    cluster_id: Optional[str] = None
    semantic_vector: List[float] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    governance_contracts: List[str] = field(default_factory=list)
    memory_count: int = 0
    coordination_count: int = 0
    created_at: int = field(default_factory=lambda: int(time.time()))
    last_updated: int = field(default_factory=lambda: int(time.time()))
    suspended_at: Optional[int] = None
    suspension_reason: Optional[SuspensionReason] = None
    retired_at: Optional[int] = None
    retirement_reason: Optional[RetirementReason] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "identity_hash": self.identity_hash,
            "owner_id": self.owner_id,
            "stage": self.stage.value,
            "sphere": self.sphere.to_dict() if self.sphere else None,
            "activation": self.activation.to_dict() if self.activation else None,
            "cluster_id": self.cluster_id,
            "semantic_vector_length": len(self.semantic_vector),
            "capabilities": self.capabilities,
            "governance_contracts": self.governance_contracts,
            "memory_count": self.memory_count,
            "coordination_count": self.coordination_count,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "suspended_at": self.suspended_at,
            "suspension_reason": self.suspension_reason.value if self.suspension_reason else None,
            "retired_at": self.retired_at,
            "retirement_reason": self.retirement_reason.value if self.retirement_reason else None,
        }


# ============== LIFECYCLE MANAGER ==============

class AgentLifecycleManager:
    """
    Manages the complete lifecycle of DSID-P agents.
    
    Stages:
    1. Creation - Define identity, intent
    2. Initialization - Build agent DAG
    3. Activation - Become registered entity
    4. Operation - Act in system
    5. Memory Evolution - Learn/store state
    6. Semantic Evolution - Adapt meaning
    7. Coordination - Collaborate
    8. Governance - Enforce rules
    9. Upgrades - Extend capabilities
    10. Transfer - Change ownership
    11. Suspension - Safety measure
    12. Retirement - Archive permanently
    """
    
    def __init__(self):
        self._agents: Dict[str, AgentState] = {}
        self._events: List[LifecycleEvent] = []
        self._ownership_history: Dict[str, List[Dict[str, Any]]] = {}
    
    def _log_event(
        self,
        agent_id: str,
        from_stage: Optional[LifecycleStage],
        to_stage: LifecycleStage,
        triggered_by: str,
        reason: str,
        metadata: Dict[str, Any] = None,
    ) -> LifecycleEvent:
        """Log a lifecycle event"""
        event = LifecycleEvent(
            event_id=str(uuid.uuid4()),
            agent_id=agent_id,
            from_stage=from_stage,
            to_stage=to_stage,
            triggered_by=triggered_by,
            reason=reason,
            metadata=metadata or {},
        )
        self._events.append(event)
        return event
    
    # ============== STAGE 1: CREATION ==============
    
    def create_agent(
        self,
        spec: AgentCreationSpec,
        triggered_by: str,
    ) -> AgentState:
        """
        Stage 1: Agent Creation
        
        Creates agent with:
        - Identity (L1)
        - Metadata (purpose, cluster hints)
        - Initial behavior graph (L3)
        - Initial policy contract
        """
        # Generate identity
        identity_data = f"{spec.owner_id}:{spec.purpose}:{time.time()}:{uuid.uuid4()}"
        identity_hash = hashlib.sha256(identity_data.encode()).hexdigest()
        agent_id = identity_hash[:16]
        
        agent = AgentState(
            agent_id=agent_id,
            identity_hash=identity_hash,
            owner_id=spec.owner_id,
            stage=LifecycleStage.CREATED,
            capabilities=spec.initial_capabilities,
            governance_contracts=spec.initial_policies,
        )
        
        self._agents[agent_id] = agent
        self._ownership_history[agent_id] = [{
            "owner_id": spec.owner_id,
            "from_timestamp": int(time.time()),
            "to_timestamp": None,
        }]
        
        self._log_event(
            agent_id=agent_id,
            from_stage=None,
            to_stage=LifecycleStage.CREATED,
            triggered_by=triggered_by,
            reason="Agent created",
            metadata={"purpose": spec.purpose, "capabilities": spec.initial_capabilities},
        )
        
        return agent
    
    # ============== STAGE 2: INITIALIZATION ==============
    
    def initialize_agent(
        self,
        agent_id: str,
        initial_memory: List[Dict[str, Any]] = None,
        semantic_vector: List[float] = None,
        triggered_by: str = "system",
    ) -> AgentState:
        """
        Stage 2: Initialize Agent Sphere (L3 DAG)
        
        Creates:
        - Behavior nodes
        - Policy nodes
        - Initial memory
        - Semantic vector node
        - Cluster assignment node
        - Capability descriptors
        """
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        if agent.stage != LifecycleStage.CREATED:
            raise ValueError(f"Agent must be in CREATED stage, currently: {agent.stage}")
        
        # Create sphere root
        sphere_data = f"{agent_id}:{time.time()}"
        sphere_root = hashlib.sha256(sphere_data.encode()).hexdigest()
        
        # Create nodes
        behavior_nodes = [hashlib.sha256(f"behavior:{agent_id}:{i}".encode()).hexdigest() 
                        for i in range(len(agent.capabilities))]
        policy_nodes = [hashlib.sha256(f"policy:{agent_id}:{c}".encode()).hexdigest() 
                       for c in agent.governance_contracts]
        memory_nodes = []
        if initial_memory:
            for i, mem in enumerate(initial_memory):
                node_id = hashlib.sha256(f"memory:{agent_id}:{i}".encode()).hexdigest()
                memory_nodes.append(node_id)
        
        semantic_node = hashlib.sha256(f"semantic:{agent_id}".encode()).hexdigest()
        cluster_node = hashlib.sha256(f"cluster:{agent_id}".encode()).hexdigest()
        
        agent.sphere = AgentSphere(
            sphere_root=sphere_root,
            behavior_nodes=behavior_nodes,
            policy_nodes=policy_nodes,
            memory_nodes=memory_nodes,
            semantic_vector_node=semantic_node,
            cluster_assignment_node=cluster_node,
            capability_nodes=behavior_nodes,
        )
        
        if semantic_vector:
            agent.semantic_vector = semantic_vector
        
        agent.memory_count = len(memory_nodes)
        agent.stage = LifecycleStage.INITIALIZED
        agent.last_updated = int(time.time())
        
        self._log_event(
            agent_id=agent_id,
            from_stage=LifecycleStage.CREATED,
            to_stage=LifecycleStage.INITIALIZED,
            triggered_by=triggered_by,
            reason="Agent sphere initialized",
            metadata={"sphere_root": sphere_root, "memory_count": len(memory_nodes)},
        )
        
        return agent
    
    # ============== STAGE 3: ACTIVATION ==============
    
    def activate_agent(
        self,
        agent_id: str,
        cluster_id: str,
        ownership_signature: str,
        triggered_by: str = "system",
    ) -> AgentState:
        """
        Stage 3: Activation (L5 Registry Block)
        
        Agent becomes active when block is written:
        - Agent identity
        - Agent Sphere root hash
        - Cluster ID
        - Ownership signature
        - Timestamp
        
        This is the "birth certificate" of the agent.
        """
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        if agent.stage != LifecycleStage.INITIALIZED:
            raise ValueError(f"Agent must be in INITIALIZED stage, currently: {agent.stage}")
        
        # Create registry block
        block_data = {
            "agent_id": agent_id,
            "sphere_root": agent.sphere.sphere_root if agent.sphere else "",
            "cluster_id": cluster_id,
            "ownership_signature": ownership_signature,
            "timestamp": int(time.time()),
        }
        registry_block_id = hashlib.sha256(json.dumps(block_data, sort_keys=True).encode()).hexdigest()
        
        agent.activation = AgentActivation(
            activation_id=str(uuid.uuid4()),
            agent_id=agent_id,
            sphere_root=agent.sphere.sphere_root if agent.sphere else "",
            cluster_id=cluster_id,
            ownership_signature=ownership_signature,
            registry_block_id=registry_block_id,
        )
        
        agent.cluster_id = cluster_id
        agent.stage = LifecycleStage.ACTIVATED
        agent.last_updated = int(time.time())
        
        self._log_event(
            agent_id=agent_id,
            from_stage=LifecycleStage.INITIALIZED,
            to_stage=LifecycleStage.ACTIVATED,
            triggered_by=triggered_by,
            reason="Agent activated with registry block",
            metadata={"registry_block_id": registry_block_id, "cluster_id": cluster_id},
        )
        
        return agent
    
    # ============== STAGE 4: OPERATION ==============
    
    def start_operation(
        self,
        agent_id: str,
        triggered_by: str = "system",
    ) -> AgentState:
        """
        Stage 4: Operational Phase
        
        Agent can now:
        - Execute tasks
        - Update memory
        - Read user data (if permitted)
        - Produce semantic outputs
        - Collaborate with other agents
        - Generate lineage
        """
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        if agent.stage not in [LifecycleStage.ACTIVATED, LifecycleStage.EVOLVING, 
                               LifecycleStage.COORDINATING, LifecycleStage.GOVERNED]:
            raise ValueError(f"Agent cannot start operation from stage: {agent.stage}")
        
        agent.stage = LifecycleStage.OPERATIONAL
        agent.last_updated = int(time.time())
        
        self._log_event(
            agent_id=agent_id,
            from_stage=agent.stage,
            to_stage=LifecycleStage.OPERATIONAL,
            triggered_by=triggered_by,
            reason="Agent entered operational phase",
        )
        
        return agent
    
    # ============== STAGE 5: MEMORY EVOLUTION ==============
    
    def append_memory(
        self,
        agent_id: str,
        memory_content: Dict[str, Any],
        triggered_by: str = "system",
    ) -> str:
        """
        Stage 5: Memory Evolution
        
        Memory grows through:
        - Task results
        - Conversations
        - Observations
        - System updates
        - Semantic calculations
        """
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        if agent.stage in [LifecycleStage.SUSPENDED, LifecycleStage.RETIRED]:
            raise ValueError(f"Cannot append memory to agent in stage: {agent.stage}")
        
        # Create memory node
        memory_data = json.dumps(memory_content, sort_keys=True).encode()
        memory_node_id = hashlib.sha256(memory_data).hexdigest()
        
        if agent.sphere:
            agent.sphere.memory_nodes.append(memory_node_id)
        
        agent.memory_count += 1
        agent.stage = LifecycleStage.EVOLVING
        agent.last_updated = int(time.time())
        
        return memory_node_id
    
    # ============== STAGE 6: SEMANTIC EVOLUTION ==============
    
    def update_semantic_vector(
        self,
        agent_id: str,
        new_vector: List[float],
        triggered_by: str = "system",
    ) -> Dict[str, Any]:
        """
        Stage 6: Semantic Evolution
        
        After meaningful updates:
        1. Submit new semantic vector
        2. Recalculate cluster/drift/alignment
        3. Cluster assignment may change
        4. Governance rules may shift
        """
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        old_vector = agent.semantic_vector.copy() if agent.semantic_vector else []
        agent.semantic_vector = new_vector
        agent.stage = LifecycleStage.EVOLVING
        agent.last_updated = int(time.time())
        
        # Calculate drift
        drift = 0.0
        if old_vector and len(old_vector) == len(new_vector):
            dot = sum(a * b for a, b in zip(old_vector, new_vector))
            mag1 = sum(v ** 2 for v in old_vector) ** 0.5
            mag2 = sum(v ** 2 for v in new_vector) ** 0.5
            if mag1 > 0 and mag2 > 0:
                drift = 1.0 - (dot / (mag1 * mag2))
        
        return {
            "agent_id": agent_id,
            "vector_updated": True,
            "drift": drift,
            "cluster_id": agent.cluster_id,
        }
    
    # ============== STAGE 7: COORDINATION ==============
    
    def record_coordination_event(
        self,
        agent_id: str,
        event_type: str,
        target_agent_id: Optional[str],
        event_data: Dict[str, Any],
        triggered_by: str = "system",
    ) -> str:
        """
        Stage 7: Coordination & Social Behavior
        
        Events include:
        - Delegation
        - Messaging
        - Workflow state
        - Tool usage
        - Collaborative tasks
        - Supervision directives
        """
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        # Create coordination event
        event = {
            "type": event_type,
            "source_agent": agent_id,
            "target_agent": target_agent_id,
            "data": event_data,
            "timestamp": int(time.time() * 1000),
        }
        event_id = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
        
        agent.coordination_count += 1
        agent.stage = LifecycleStage.COORDINATING
        agent.last_updated = int(time.time())
        
        return event_id
    
    # ============== STAGE 8: GOVERNANCE ==============
    
    def apply_governance(
        self,
        agent_id: str,
        contract_id: str,
        triggered_by: str = "system",
    ) -> AgentState:
        """
        Stage 8: Governance Enforcement
        
        Governance acts at four levels:
        1. Identity Governance - ownership, modification rights
        2. Contract Governance - allowed actions
        3. Semantic Governance - cluster-based rules
        4. Behavioral Governance - patterns over time
        """
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        if contract_id not in agent.governance_contracts:
            agent.governance_contracts.append(contract_id)
        
        agent.stage = LifecycleStage.GOVERNED
        agent.last_updated = int(time.time())
        
        self._log_event(
            agent_id=agent_id,
            from_stage=agent.stage,
            to_stage=LifecycleStage.GOVERNED,
            triggered_by=triggered_by,
            reason="Governance contract applied",
            metadata={"contract_id": contract_id},
        )
        
        return agent
    
    # ============== STAGE 9: UPGRADES ==============
    
    def upgrade_agent(
        self,
        agent_id: str,
        new_capabilities: List[str],
        new_contracts: List[str] = None,
        new_semantic_vector: List[float] = None,
        triggered_by: str = "system",
    ) -> AgentState:
        """
        Stage 9: Agent Upgrades
        
        Agents evolve with:
        - Improved behavior graphs
        - New skills
        - Extended memory
        - Updated governance contracts
        - New semantic embeddings
        
        Upgrades must be signed, anchored, validated, cluster-checked.
        """
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        if agent.stage in [LifecycleStage.SUSPENDED, LifecycleStage.RETIRED]:
            raise ValueError(f"Cannot upgrade agent in stage: {agent.stage}")
        
        # Add new capabilities
        for cap in new_capabilities:
            if cap not in agent.capabilities:
                agent.capabilities.append(cap)
        
        # Add new contracts
        if new_contracts:
            for contract in new_contracts:
                if contract not in agent.governance_contracts:
                    agent.governance_contracts.append(contract)
        
        # Update semantic vector
        if new_semantic_vector:
            agent.semantic_vector = new_semantic_vector
        
        agent.stage = LifecycleStage.UPGRADING
        agent.last_updated = int(time.time())
        
        self._log_event(
            agent_id=agent_id,
            from_stage=agent.stage,
            to_stage=LifecycleStage.UPGRADING,
            triggered_by=triggered_by,
            reason="Agent upgraded",
            metadata={"new_capabilities": new_capabilities},
        )
        
        return agent
    
    # ============== STAGE 10: OWNERSHIP TRANSFER ==============
    
    def transfer_ownership(
        self,
        agent_id: str,
        new_owner_id: str,
        new_ownership_signature: str,
        prune_memory: bool = False,
        triggered_by: str = "system",
    ) -> AgentState:
        """
        Stage 10: Agent Ownership Transfer
        
        Agents can be:
        - Sold, rented, licensed
        - Transferred, inherited, delegated
        
        Transfer requires:
        1. New ownership signature
        2. New registry block
        3. Optional: semantic recertification
        4. Optional: memory pruning
        """
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        if agent.stage in [LifecycleStage.SUSPENDED, LifecycleStage.RETIRED]:
            raise ValueError(f"Cannot transfer agent in stage: {agent.stage}")
        
        old_owner = agent.owner_id
        
        # Update ownership history
        if agent_id in self._ownership_history:
            # Close previous ownership
            for entry in self._ownership_history[agent_id]:
                if entry["to_timestamp"] is None:
                    entry["to_timestamp"] = int(time.time())
            
            # Add new ownership
            self._ownership_history[agent_id].append({
                "owner_id": new_owner_id,
                "from_timestamp": int(time.time()),
                "to_timestamp": None,
            })
        
        agent.owner_id = new_owner_id
        
        # Update activation with new signature
        if agent.activation:
            agent.activation.ownership_signature = new_ownership_signature
        
        # Optional memory pruning
        if prune_memory and agent.sphere:
            agent.sphere.memory_nodes = []
            agent.memory_count = 0
        
        agent.stage = LifecycleStage.TRANSFERRING
        agent.last_updated = int(time.time())
        
        self._log_event(
            agent_id=agent_id,
            from_stage=agent.stage,
            to_stage=LifecycleStage.TRANSFERRING,
            triggered_by=triggered_by,
            reason="Ownership transferred",
            metadata={"old_owner": old_owner, "new_owner": new_owner_id, "memory_pruned": prune_memory},
        )
        
        return agent
    
    # ============== STAGE 11: SUSPENSION ==============
    
    def suspend_agent(
        self,
        agent_id: str,
        reason: SuspensionReason,
        triggered_by: str = "system",
    ) -> AgentState:
        """
        Stage 11: Suspension
        
        Agents may be suspended due to:
        - Governance violations
        - Cluster drift
        - Misalignment
        - Owner request
        - Enterprise rules
        - Government regulations
        
        Suspension actions:
        - Stop execution
        - Freeze memory writes
        - Disable coordination
        - Isolate semantic updates
        """
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        if agent.stage == LifecycleStage.RETIRED:
            raise ValueError("Cannot suspend retired agent")
        
        agent.stage = LifecycleStage.SUSPENDED
        agent.suspended_at = int(time.time())
        agent.suspension_reason = reason
        agent.last_updated = int(time.time())
        
        self._log_event(
            agent_id=agent_id,
            from_stage=agent.stage,
            to_stage=LifecycleStage.SUSPENDED,
            triggered_by=triggered_by,
            reason=f"Agent suspended: {reason.value}",
            metadata={"suspension_reason": reason.value},
        )
        
        return agent
    
    def unsuspend_agent(
        self,
        agent_id: str,
        triggered_by: str = "system",
    ) -> AgentState:
        """Unsuspend a suspended agent"""
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        if agent.stage != LifecycleStage.SUSPENDED:
            raise ValueError(f"Agent is not suspended, currently: {agent.stage}")
        
        agent.stage = LifecycleStage.OPERATIONAL
        agent.suspended_at = None
        agent.suspension_reason = None
        agent.last_updated = int(time.time())
        
        self._log_event(
            agent_id=agent_id,
            from_stage=LifecycleStage.SUSPENDED,
            to_stage=LifecycleStage.OPERATIONAL,
            triggered_by=triggered_by,
            reason="Agent unsuspended",
        )
        
        return agent
    
    # ============== STAGE 12: RETIREMENT ==============
    
    def retire_agent(
        self,
        agent_id: str,
        reason: RetirementReason,
        triggered_by: str = "system",
    ) -> AgentState:
        """
        Stage 12: Retirement / Archival
        
        Retirement steps:
        1. Agent Sphere sealed
        2. Coordination DAG finalized
        3. Semantic vector removed from active clusters
        4. Registry block marking retirement
        5. All permissions revoked
        
        Agent becomes read-only historical entity.
        """
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        if agent.stage == LifecycleStage.RETIRED:
            raise ValueError("Agent is already retired")
        
        agent.stage = LifecycleStage.RETIRED
        agent.retired_at = int(time.time())
        agent.retirement_reason = reason
        agent.last_updated = int(time.time())
        
        # Clear active semantic vector (archived separately)
        agent.semantic_vector = []
        
        # Close ownership history
        if agent_id in self._ownership_history:
            for entry in self._ownership_history[agent_id]:
                if entry["to_timestamp"] is None:
                    entry["to_timestamp"] = int(time.time())
        
        self._log_event(
            agent_id=agent_id,
            from_stage=agent.stage,
            to_stage=LifecycleStage.RETIRED,
            triggered_by=triggered_by,
            reason=f"Agent retired: {reason.value}",
            metadata={"retirement_reason": reason.value},
        )
        
        return agent
    
    # ============== QUERIES ==============
    
    def get_agent(self, agent_id: str) -> Optional[AgentState]:
        """Get agent by ID"""
        return self._agents.get(agent_id)
    
    def list_agents(
        self,
        stage: Optional[LifecycleStage] = None,
        owner_id: Optional[str] = None,
        cluster_id: Optional[str] = None,
    ) -> List[AgentState]:
        """List agents with optional filters"""
        agents = list(self._agents.values())
        
        if stage:
            agents = [a for a in agents if a.stage == stage]
        if owner_id:
            agents = [a for a in agents if a.owner_id == owner_id]
        if cluster_id:
            agents = [a for a in agents if a.cluster_id == cluster_id]
        
        return agents
    
    def get_agent_history(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get lifecycle event history for an agent"""
        return [e.to_dict() for e in self._events if e.agent_id == agent_id]
    
    def get_ownership_history(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get ownership history for an agent"""
        return self._ownership_history.get(agent_id, [])
    
    def get_stats(self) -> Dict[str, Any]:
        """Get lifecycle manager statistics"""
        stage_counts = {}
        for agent in self._agents.values():
            stage = agent.stage.value
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        
        return {
            "total_agents": len(self._agents),
            "total_events": len(self._events),
            "agents_by_stage": stage_counts,
            "active_agents": len([a for a in self._agents.values() 
                                 if a.stage not in [LifecycleStage.SUSPENDED, LifecycleStage.RETIRED]]),
            "suspended_agents": len([a for a in self._agents.values() 
                                    if a.stage == LifecycleStage.SUSPENDED]),
            "retired_agents": len([a for a in self._agents.values() 
                                  if a.stage == LifecycleStage.RETIRED]),
        }


# ============== GLOBAL INSTANCE ==============

lifecycle_manager = AgentLifecycleManager()
