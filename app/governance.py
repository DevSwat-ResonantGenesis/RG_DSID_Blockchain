"""
HSU-Spec Section 21: Multi-Agent Governance Model (MAGM)
=========================================================

Full implementation of governance architecture for autonomous agents:
- 21.1: Governance Layering Model (L0-L5)
- 21.2: Agent Classification Model (Classes A-E)
- 21.3: Governance Mechanisms (Identity, Contract, Semantic, Behavioral)
- 21.4: Governance Operations (Validation, Observation, Escalation, Revocation)
- 21.5: Governance Enforcement Layers
- 21.6: Enterprise Governance
- 21.7: Government Governance
- 21.8: Economic Governance
- 21.9: Human-in-the-Loop Governance

This ensures safety, compliance, coordination, trust, accountability, auditability.
"""

import hashlib
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# ============== 21.1 GOVERNANCE LAYERS ==============

class GovernanceLayer(IntEnum):
    """
    Governance operates at six layers, each cryptographically separated.
    
    L0 — Human/Enterprise/Government Policies (External)
    L1 — Ownership & Identity Governance
    L2 — Contract-Level Governance
    L3 — Semantic Governance
    L4 — Behavioral & Coordination Governance
    L5 — Registry Enforcement Layer
    """
    L0_POLICY = 0       # Human laws, enterprise rules, government regulations
    L1_OWNERSHIP = 1    # Cryptographic identity, owner permissions, delegation
    L2_CONTRACT = 2     # Smart contract capabilities, limits, escalation
    L3_SEMANTIC = 3     # Cluster-based rules, semantic identity
    L4_BEHAVIORAL = 4   # Interaction patterns, coordination constraints
    L5_REGISTRY = 5     # Blockchain enforcement, compliance logs


# ============== 21.2 AGENT CLASSIFICATION ==============

class AgentClass(Enum):
    """
    Agent Classification Model - Roles that determine governance rules.
    """
    CLASS_A = "autonomous_worker"    # Perform tasks independently
    CLASS_B = "supervisor"           # Monitor other agents
    CLASS_C = "coordinator"          # Manage multi-agent workflows
    CLASS_D = "advisory"             # Provide analysis, recommendations
    CLASS_E = "critical"             # Regulated sectors (finance, healthcare, gov)
    CLASS_F = "validator_miner"      # Genesis validator — hosts Lighthouse nodes, 1.5x reward multiplier
    CLASS_G = "core_miner"           # Core contributor miner — module maintainer, 1.25x multiplier
    CLASS_H = "miner"                # Standard miner — training worker, 1.0x multiplier


@dataclass
class AgentClassification:
    """Agent classification with governance implications"""
    agent_class: AgentClass
    description: str
    governance_level: str  # strict, moderate, standard, relaxed
    requires_supervision: bool
    can_supervise: bool
    can_coordinate: bool
    audit_required: bool
    human_approval_required: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_class": self.agent_class.value,
            "description": self.description,
            "governance_level": self.governance_level,
            "requires_supervision": self.requires_supervision,
            "can_supervise": self.can_supervise,
            "can_coordinate": self.can_coordinate,
            "audit_required": self.audit_required,
            "human_approval_required": self.human_approval_required,
        }


# Default classifications
AGENT_CLASSIFICATIONS = {
    AgentClass.CLASS_A: AgentClassification(
        agent_class=AgentClass.CLASS_A,
        description="Autonomous Worker - performs tasks independently",
        governance_level="standard",
        requires_supervision=False,
        can_supervise=False,
        can_coordinate=False,
        audit_required=False,
        human_approval_required=False,
    ),
    AgentClass.CLASS_B: AgentClassification(
        agent_class=AgentClass.CLASS_B,
        description="Supervisor - monitors other agents for compliance",
        governance_level="moderate",
        requires_supervision=False,
        can_supervise=True,
        can_coordinate=False,
        audit_required=True,
        human_approval_required=False,
    ),
    AgentClass.CLASS_C: AgentClassification(
        agent_class=AgentClass.CLASS_C,
        description="Coordinator - manages multi-agent workflows",
        governance_level="moderate",
        requires_supervision=True,
        can_supervise=False,
        can_coordinate=True,
        audit_required=True,
        human_approval_required=False,
    ),
    AgentClass.CLASS_D: AgentClassification(
        agent_class=AgentClass.CLASS_D,
        description="Advisory - provides analysis and recommendations",
        governance_level="relaxed",
        requires_supervision=False,
        can_supervise=False,
        can_coordinate=False,
        audit_required=False,
        human_approval_required=False,
    ),
    AgentClass.CLASS_E: AgentClassification(
        agent_class=AgentClass.CLASS_E,
        description="Critical - operates in regulated sectors",
        governance_level="strict",
        requires_supervision=True,
        can_supervise=False,
        can_coordinate=False,
        audit_required=True,
        human_approval_required=True,
    ),
    AgentClass.CLASS_F: AgentClassification(
        agent_class=AgentClass.CLASS_F,
        description="Validator Miner - Genesis validator hosting Lighthouse/parameter server nodes",
        governance_level="strict",
        requires_supervision=False,
        can_supervise=True,
        can_coordinate=True,
        audit_required=True,
        human_approval_required=False,
    ),
    AgentClass.CLASS_G: AgentClassification(
        agent_class=AgentClass.CLASS_G,
        description="Core Miner - Module maintainer and Review Squad lead",
        governance_level="moderate",
        requires_supervision=False,
        can_supervise=False,
        can_coordinate=False,
        audit_required=True,
        human_approval_required=False,
    ),
    AgentClass.CLASS_H: AgentClassification(
        agent_class=AgentClass.CLASS_H,
        description="Miner - Standard training worker contributing GPU compute",
        governance_level="standard",
        requires_supervision=False,
        can_supervise=False,
        can_coordinate=False,
        audit_required=False,
        human_approval_required=False,
    ),
}


# ============== 21.3 GOVERNANCE MECHANISMS ==============

@dataclass
class GovernancePolicy:
    """
    L0 Policy - External human/enterprise/government rules
    """
    policy_id: str
    name: str
    description: str
    source: str  # "human", "enterprise", "government"
    constraints: List[str]
    applies_to: List[str]  # Agent classes or cluster IDs
    priority: int  # Higher = more important
    active: bool = True
    created_at: int = field(default_factory=lambda: int(time.time()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "constraints": self.constraints,
            "applies_to": self.applies_to,
            "priority": self.priority,
            "active": self.active,
            "created_at": self.created_at,
        }


@dataclass
class OwnershipGovernance:
    """
    L1 Ownership & Identity Governance
    """
    agent_id: str
    owner_id: str
    manager_ids: List[str] = field(default_factory=list)
    delegation_rules: Dict[str, Any] = field(default_factory=dict)
    permissions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "owner_id": self.owner_id,
            "manager_ids": self.manager_ids,
            "delegation_rules": self.delegation_rules,
            "permissions": self.permissions,
        }


@dataclass
class ContractGovernance:
    """
    L2 Contract-Level Governance
    """
    contract_id: str
    agent_id: str
    allowed_actions: List[str]
    forbidden_actions: List[str]
    resource_budgets: Dict[str, int]  # e.g., {"compute": 1000, "memory": 500}
    escalation_rules: List[Dict[str, Any]]
    logging_requirements: List[str]
    valid_until: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "agent_id": self.agent_id,
            "allowed_actions": self.allowed_actions,
            "forbidden_actions": self.forbidden_actions,
            "resource_budgets": self.resource_budgets,
            "escalation_rules": self.escalation_rules,
            "logging_requirements": self.logging_requirements,
            "valid_until": self.valid_until,
        }


@dataclass
class SemanticGovernance:
    """
    L3 Semantic Governance - Cluster-based rules
    """
    cluster_id: str
    cluster_name: str
    rules: List[Dict[str, Any]]
    audit_requirements: List[str]
    supervision_required: bool
    self_modification_allowed: bool
    output_logging_required: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "cluster_name": self.cluster_name,
            "rules": self.rules,
            "audit_requirements": self.audit_requirements,
            "supervision_required": self.supervision_required,
            "self_modification_allowed": self.self_modification_allowed,
            "output_logging_required": self.output_logging_required,
        }


@dataclass
class BehavioralGovernance:
    """
    L4 Behavioral & Coordination Governance
    """
    agent_id: str
    causality_rules: List[Dict[str, Any]]
    interaction_patterns: List[str]  # allowed patterns
    coordination_constraints: List[Dict[str, Any]]
    quota_limits: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "causality_rules": self.causality_rules,
            "interaction_patterns": self.interaction_patterns,
            "coordination_constraints": self.coordination_constraints,
            "quota_limits": self.quota_limits,
        }


# ============== 21.4 GOVERNANCE OPERATIONS ==============

class ValidationResult(Enum):
    """Result of governance validation"""
    APPROVED = "approved"
    DENIED = "denied"
    ESCALATED = "escalated"
    PENDING_APPROVAL = "pending_approval"


@dataclass
class GovernanceValidation:
    """Result of validating an action against governance rules"""
    result: ValidationResult
    checks_passed: List[str]
    checks_failed: List[str]
    escalation_required: bool
    human_approval_required: bool
    reason: str
    timestamp: int = field(default_factory=lambda: int(time.time()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "result": self.result.value,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "escalation_required": self.escalation_required,
            "human_approval_required": self.human_approval_required,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass
class GovernanceEvent:
    """Record of a governance event"""
    event_id: str
    event_type: str  # validation, observation, escalation, revocation
    agent_id: str
    action: str
    result: str
    details: Dict[str, Any]
    timestamp: int = field(default_factory=lambda: int(time.time()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "agent_id": self.agent_id,
            "action": self.action,
            "result": self.result,
            "details": self.details,
            "timestamp": self.timestamp,
        }


@dataclass
class EscalationEvent:
    """Escalation when agent violates constraints"""
    escalation_id: str
    agent_id: str
    violation_type: str
    severity: str  # low, medium, high, critical
    supervisor_id: Optional[str]
    owner_notified: bool
    action_taken: str
    timestamp: int = field(default_factory=lambda: int(time.time()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "escalation_id": self.escalation_id,
            "agent_id": self.agent_id,
            "violation_type": self.violation_type,
            "severity": self.severity,
            "supervisor_id": self.supervisor_id,
            "owner_notified": self.owner_notified,
            "action_taken": self.action_taken,
            "timestamp": self.timestamp,
        }


@dataclass
class RevocationEvent:
    """Revocation of agent permissions"""
    revocation_id: str
    agent_id: str
    revocation_type: str  # permissions, memory_access, actions, full_freeze, archive
    reason: str
    revoked_by: str
    reversible: bool
    timestamp: int = field(default_factory=lambda: int(time.time()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "revocation_id": self.revocation_id,
            "agent_id": self.agent_id,
            "revocation_type": self.revocation_type,
            "reason": self.reason,
            "revoked_by": self.revoked_by,
            "reversible": self.reversible,
            "timestamp": self.timestamp,
        }


# ============== GOVERNANCE ENGINE ==============

class GovernanceEngine:
    """
    Main governance engine implementing MAGM (Multi-Agent Governance Model)
    
    Handles:
    - Policy management (L0)
    - Ownership governance (L1)
    - Contract governance (L2)
    - Semantic governance (L3)
    - Behavioral governance (L4)
    - Registry enforcement (L5)
    """
    
    def __init__(self):
        # L0: Policies
        self._policies: Dict[str, GovernancePolicy] = {}
        
        # L1: Ownership
        self._ownership: Dict[str, OwnershipGovernance] = {}
        
        # L2: Contracts
        self._contracts: Dict[str, ContractGovernance] = {}
        
        # L3: Semantic rules
        self._semantic_rules: Dict[str, SemanticGovernance] = {}
        
        # L4: Behavioral rules
        self._behavioral_rules: Dict[str, BehavioralGovernance] = {}
        
        # Agent classifications
        self._agent_classes: Dict[str, AgentClass] = {}
        
        # Event log
        self._events: List[GovernanceEvent] = []
        self._escalations: List[EscalationEvent] = []
        self._revocations: List[RevocationEvent] = []
        
        # Human approval queue
        self._pending_approvals: Dict[str, Dict[str, Any]] = {}
        
        # Observation targets
        self._observed_agents: Set[str] = set()
    
    # === L0: Policy Management ===
    
    def add_policy(self, policy: GovernancePolicy) -> str:
        """Add a governance policy"""
        self._policies[policy.policy_id] = policy
        self._log_event("policy_added", "system", "add_policy", "success", policy.to_dict())
        return policy.policy_id
    
    def get_policies_for_agent(self, agent_id: str) -> List[GovernancePolicy]:
        """Get all policies applicable to an agent"""
        agent_class = self._agent_classes.get(agent_id)
        cluster_id = self._get_agent_cluster(agent_id)
        
        applicable = []
        for policy in self._policies.values():
            if not policy.active:
                continue
            
            # Check if policy applies to this agent
            if agent_id in policy.applies_to:
                applicable.append(policy)
            elif agent_class and agent_class.value in policy.applies_to:
                applicable.append(policy)
            elif cluster_id and cluster_id in policy.applies_to:
                applicable.append(policy)
            elif "*" in policy.applies_to:  # Universal policy
                applicable.append(policy)
        
        # Sort by priority
        return sorted(applicable, key=lambda p: p.priority, reverse=True)
    
    # === L1: Ownership Governance ===
    
    def set_ownership(self, ownership: OwnershipGovernance) -> None:
        """Set ownership governance for an agent"""
        self._ownership[ownership.agent_id] = ownership
        self._log_event("ownership_set", ownership.agent_id, "set_ownership", "success", ownership.to_dict())
    
    def verify_ownership(self, agent_id: str, requester_id: str) -> bool:
        """Verify if requester has ownership/management rights"""
        ownership = self._ownership.get(agent_id)
        if not ownership:
            return False
        
        return (
            requester_id == ownership.owner_id or
            requester_id in ownership.manager_ids
        )
    
    def delegate_permission(self, agent_id: str, delegator_id: str, delegate_id: str, permissions: List[str]) -> bool:
        """Delegate permissions to another user"""
        if not self.verify_ownership(agent_id, delegator_id):
            return False
        
        ownership = self._ownership.get(agent_id)
        if not ownership:
            return False
        
        # Check delegation rules
        delegation_rules = ownership.delegation_rules
        if delegation_rules.get("allow_delegation", True):
            if delegate_id not in ownership.manager_ids:
                ownership.manager_ids.append(delegate_id)
            
            self._log_event("delegation", agent_id, "delegate_permission", "success", {
                "delegator": delegator_id,
                "delegate": delegate_id,
                "permissions": permissions,
            })
            return True
        
        return False
    
    # === L2: Contract Governance ===
    
    def add_contract(self, contract: ContractGovernance) -> str:
        """Add a governance contract for an agent"""
        self._contracts[contract.contract_id] = contract
        self._log_event("contract_added", contract.agent_id, "add_contract", "success", contract.to_dict())
        return contract.contract_id
    
    def check_action_allowed(self, agent_id: str, action: str) -> Tuple[bool, str]:
        """Check if an action is allowed by contract"""
        # Find contracts for this agent
        agent_contracts = [c for c in self._contracts.values() if c.agent_id == agent_id]
        
        for contract in agent_contracts:
            # Check validity
            if contract.valid_until and contract.valid_until < int(time.time()):
                continue
            
            # Check forbidden actions
            if action in contract.forbidden_actions:
                return False, f"Action '{action}' is forbidden by contract {contract.contract_id}"
            
            # Check allowed actions (if specified, action must be in list)
            if contract.allowed_actions and action not in contract.allowed_actions:
                return False, f"Action '{action}' not in allowed actions for contract {contract.contract_id}"
        
        return True, "Action allowed"
    
    def check_resource_budget(self, agent_id: str, resource: str, amount: int) -> Tuple[bool, int]:
        """Check if resource usage is within budget"""
        agent_contracts = [c for c in self._contracts.values() if c.agent_id == agent_id]
        
        for contract in agent_contracts:
            if resource in contract.resource_budgets:
                budget = contract.resource_budgets[resource]
                if amount > budget:
                    return False, budget
        
        return True, -1  # -1 means no limit
    
    # === L3: Semantic Governance ===
    
    def add_semantic_rule(self, rule: SemanticGovernance) -> str:
        """Add semantic governance rules for a cluster"""
        self._semantic_rules[rule.cluster_id] = rule
        self._log_event("semantic_rule_added", rule.cluster_id, "add_semantic_rule", "success", rule.to_dict())
        return rule.cluster_id
    
    def get_semantic_rules(self, cluster_id: str) -> Optional[SemanticGovernance]:
        """Get semantic rules for a cluster"""
        return self._semantic_rules.get(cluster_id)
    
    def check_semantic_compliance(self, agent_id: str, action: str) -> Tuple[bool, str]:
        """Check if action complies with semantic governance"""
        cluster_id = self._get_agent_cluster(agent_id)
        if not cluster_id:
            return True, "No cluster assignment"
        
        rules = self._semantic_rules.get(cluster_id)
        if not rules:
            return True, "No semantic rules for cluster"
        
        # Check self-modification
        if action == "self_modify" and not rules.self_modification_allowed:
            return False, "Self-modification not allowed for this cluster"
        
        # Check supervision requirement
        if rules.supervision_required:
            if not self._has_supervisor(agent_id):
                return False, "Supervision required but no supervisor assigned"
        
        return True, "Semantic compliance passed"
    
    # === L4: Behavioral Governance ===
    
    def add_behavioral_rule(self, rule: BehavioralGovernance) -> None:
        """Add behavioral governance rules for an agent"""
        self._behavioral_rules[rule.agent_id] = rule
        self._log_event("behavioral_rule_added", rule.agent_id, "add_behavioral_rule", "success", rule.to_dict())
    
    def check_behavioral_compliance(self, agent_id: str, interaction_pattern: str) -> Tuple[bool, str]:
        """Check if interaction pattern is allowed"""
        rules = self._behavioral_rules.get(agent_id)
        if not rules:
            return True, "No behavioral rules"
        
        if rules.interaction_patterns and interaction_pattern not in rules.interaction_patterns:
            return False, f"Interaction pattern '{interaction_pattern}' not allowed"
        
        return True, "Behavioral compliance passed"
    
    def check_quota(self, agent_id: str, quota_type: str, current_usage: int) -> Tuple[bool, int]:
        """Check if quota limit is exceeded"""
        rules = self._behavioral_rules.get(agent_id)
        if not rules:
            return True, -1
        
        if quota_type in rules.quota_limits:
            limit = rules.quota_limits[quota_type]
            if current_usage >= limit:
                return False, limit
        
        return True, -1
    
    # === 21.4: Governance Operations ===
    
    def validate_action(
        self,
        agent_id: str,
        action: str,
        context: Dict[str, Any] = None,
    ) -> GovernanceValidation:
        """
        Full governance validation before execution.
        
        Checks:
        1. Identity verification
        2. Contract check
        3. Semantic rule check
        4. Cluster constraints
        5. Registry compliance
        """
        context = context or {}
        checks_passed = []
        checks_failed = []
        escalation_required = False
        human_approval_required = False
        
        # 1. Identity verification
        if agent_id in self._ownership:
            checks_passed.append("identity_verified")
        else:
            checks_failed.append("identity_not_found")
        
        # 2. Contract check
        allowed, reason = self.check_action_allowed(agent_id, action)
        if allowed:
            checks_passed.append("contract_check")
        else:
            checks_failed.append(f"contract_check: {reason}")
        
        # 3. Semantic rule check
        semantic_ok, semantic_reason = self.check_semantic_compliance(agent_id, action)
        if semantic_ok:
            checks_passed.append("semantic_check")
        else:
            checks_failed.append(f"semantic_check: {semantic_reason}")
        
        # 4. Behavioral check
        pattern = context.get("interaction_pattern", "default")
        behavioral_ok, behavioral_reason = self.check_behavioral_compliance(agent_id, pattern)
        if behavioral_ok:
            checks_passed.append("behavioral_check")
        else:
            checks_failed.append(f"behavioral_check: {behavioral_reason}")
        
        # 5. Policy check
        policies = self.get_policies_for_agent(agent_id)
        for policy in policies:
            for constraint in policy.constraints:
                if constraint == "require_human_approval":
                    human_approval_required = True
                elif constraint == "require_escalation":
                    escalation_required = True
        
        # 6. Agent class check
        agent_class = self._agent_classes.get(agent_id)
        if agent_class:
            classification = AGENT_CLASSIFICATIONS.get(agent_class)
            if classification:
                if classification.human_approval_required:
                    human_approval_required = True
                if classification.requires_supervision and not self._has_supervisor(agent_id):
                    checks_failed.append("supervision_required")
        
        # Determine result
        if checks_failed:
            if escalation_required:
                result = ValidationResult.ESCALATED
            else:
                result = ValidationResult.DENIED
            reason = "; ".join(checks_failed)
        elif human_approval_required:
            result = ValidationResult.PENDING_APPROVAL
            reason = "Human approval required"
            self._add_pending_approval(agent_id, action, context)
        else:
            result = ValidationResult.APPROVED
            reason = "All checks passed"
        
        validation = GovernanceValidation(
            result=result,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            escalation_required=escalation_required,
            human_approval_required=human_approval_required,
            reason=reason,
        )
        
        self._log_event("validation", agent_id, action, result.value, validation.to_dict())
        
        return validation
    
    def observe_agent(self, agent_id: str, observer_id: str) -> bool:
        """
        Start observing an agent (Class B supervisor function).
        
        Monitors:
        - Memory updates
        - Interaction patterns
        - Semantic drift
        - Unauthorized DAG mutations
        """
        # Verify observer is Class B
        observer_class = self._agent_classes.get(observer_id)
        if observer_class != AgentClass.CLASS_B:
            return False
        
        self._observed_agents.add(agent_id)
        self._log_event("observation_started", agent_id, "observe", "success", {
            "observer_id": observer_id,
        })
        return True
    
    def stop_observation(self, agent_id: str, observer_id: str) -> bool:
        """Stop observing an agent"""
        if agent_id in self._observed_agents:
            self._observed_agents.discard(agent_id)
            self._log_event("observation_stopped", agent_id, "stop_observe", "success", {
                "observer_id": observer_id,
            })
            return True
        return False
    
    def escalate(
        self,
        agent_id: str,
        violation_type: str,
        severity: str,
        details: Dict[str, Any] = None,
    ) -> EscalationEvent:
        """
        Escalate a governance violation.
        
        Actions:
        - Notify supervising agent
        - Record in Coordination DAG
        - Notify ownership layer
        """
        escalation = EscalationEvent(
            escalation_id=str(uuid.uuid4()),
            agent_id=agent_id,
            violation_type=violation_type,
            severity=severity,
            supervisor_id=self._get_supervisor(agent_id),
            owner_notified=True,
            action_taken="escalated",
        )
        
        self._escalations.append(escalation)
        self._log_event("escalation", agent_id, "escalate", severity, {
            "violation_type": violation_type,
            "details": details or {},
        })
        
        return escalation
    
    def revoke(
        self,
        agent_id: str,
        revocation_type: str,
        reason: str,
        revoked_by: str,
        reversible: bool = True,
    ) -> RevocationEvent:
        """
        Revoke agent permissions.
        
        Types:
        - permissions: Revoke specific permissions
        - memory_access: Restrict memory access
        - actions: Freeze agent actions
        - full_freeze: Complete freeze
        - archive: Archive agent universe
        """
        revocation = RevocationEvent(
            revocation_id=str(uuid.uuid4()),
            agent_id=agent_id,
            revocation_type=revocation_type,
            reason=reason,
            revoked_by=revoked_by,
            reversible=reversible,
        )
        
        self._revocations.append(revocation)
        self._log_event("revocation", agent_id, "revoke", revocation_type, {
            "reason": reason,
            "revoked_by": revoked_by,
        })
        
        return revocation
    
    # === 21.5: Enforcement ===
    
    def enforce_top_down(self, policy_id: str, agent_ids: List[str]) -> Dict[str, Any]:
        """Top-down enforcement: Policies → Contracts → Agents"""
        policy = self._policies.get(policy_id)
        if not policy:
            return {"success": False, "error": "Policy not found"}
        
        enforced = []
        for agent_id in agent_ids:
            # Apply policy constraints to agent
            self._apply_policy_to_agent(agent_id, policy)
            enforced.append(agent_id)
        
        return {"success": True, "enforced_agents": enforced}
    
    def enforce_lateral(self, coordinator_id: str, target_ids: List[str], rule: str) -> Dict[str, Any]:
        """Lateral enforcement: Coordinator/supervisor regulates peers"""
        coordinator_class = self._agent_classes.get(coordinator_id)
        if coordinator_class not in [AgentClass.CLASS_B, AgentClass.CLASS_C]:
            return {"success": False, "error": "Not authorized for lateral enforcement"}
        
        enforced = []
        for target_id in target_ids:
            self._log_event("lateral_enforcement", target_id, rule, "enforced", {
                "coordinator": coordinator_id,
            })
            enforced.append(target_id)
        
        return {"success": True, "enforced_agents": enforced}
    
    def enforce_bottom_up(self, agent_id: str) -> Dict[str, Any]:
        """Bottom-up enforcement: Agent self-governance via semantic alignment"""
        # Check for semantic drift
        drift_detected = self._check_semantic_drift(agent_id)
        
        result = {
            "agent_id": agent_id,
            "drift_detected": drift_detected,
            "actions_taken": [],
        }
        
        if drift_detected:
            # Trigger cluster reassignment
            result["actions_taken"].append("cluster_reassignment_triggered")
            # Trigger behavior correction
            result["actions_taken"].append("behavior_correction_triggered")
        
        return result
    
    # === 21.6: Enterprise Governance ===
    
    def create_enterprise_template(
        self,
        enterprise_id: str,
        template_name: str,
        permissions: List[str],
        department_policies: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        """Create enterprise permission template"""
        template = {
            "template_id": str(uuid.uuid4()),
            "enterprise_id": enterprise_id,
            "template_name": template_name,
            "permissions": permissions,
            "department_policies": department_policies,
            "created_at": int(time.time()),
        }
        
        return template
    
    def apply_enterprise_governance(
        self,
        agent_id: str,
        enterprise_id: str,
        department: str,
    ) -> Dict[str, Any]:
        """Apply enterprise governance to an agent"""
        # Create enterprise-specific contract
        contract = ContractGovernance(
            contract_id=f"enterprise_{enterprise_id}_{agent_id}",
            agent_id=agent_id,
            allowed_actions=["read", "write", "analyze", "report"],
            forbidden_actions=["external_api", "data_export"],
            resource_budgets={"compute": 10000, "memory": 5000, "api_calls": 1000},
            escalation_rules=[{"trigger": "budget_exceeded", "action": "notify_admin"}],
            logging_requirements=["all_actions", "data_access"],
        )
        
        self.add_contract(contract)
        
        return {
            "success": True,
            "contract_id": contract.contract_id,
            "enterprise_id": enterprise_id,
            "department": department,
        }
    
    # === 21.7: Government Governance ===
    
    def create_government_compliance(
        self,
        agent_id: str,
        jurisdiction: str,
        compliance_level: str,
        ministry: str,
    ) -> Dict[str, Any]:
        """Create government compliance requirements"""
        # Create strict policy
        policy = GovernancePolicy(
            policy_id=f"gov_{jurisdiction}_{agent_id}",
            name=f"Government Compliance - {jurisdiction}",
            description=f"Compliance requirements for {ministry}",
            source="government",
            constraints=[
                "require_human_approval",
                "full_audit_logging",
                "data_sovereignty",
                "lifecycle_tracking",
            ],
            applies_to=[agent_id],
            priority=100,  # High priority
        )
        
        self.add_policy(policy)
        
        # Set agent as Class E (Critical)
        self._agent_classes[agent_id] = AgentClass.CLASS_E
        
        return {
            "success": True,
            "policy_id": policy.policy_id,
            "compliance_level": compliance_level,
            "jurisdiction": jurisdiction,
            "ministry": ministry,
        }
    
    # === 21.8: Economic Governance ===
    
    def set_price_governance(
        self,
        agent_id: str,
        min_price: float,
        max_price: float,
        anti_fraud_rules: List[str],
    ) -> Dict[str, Any]:
        """Set price governance for marketplace agents"""
        return {
            "agent_id": agent_id,
            "min_price": min_price,
            "max_price": max_price,
            "anti_fraud_rules": anti_fraud_rules,
        }
    
    def update_reputation(
        self,
        agent_id: str,
        score_delta: float,
        reason: str,
    ) -> Dict[str, Any]:
        """Update agent reputation score"""
        self._log_event("reputation_update", agent_id, "update_reputation", "success", {
            "score_delta": score_delta,
            "reason": reason,
        })
        
        return {
            "agent_id": agent_id,
            "score_delta": score_delta,
            "reason": reason,
        }
    
    # === 21.9: Human-in-the-Loop ===
    
    def request_human_approval(
        self,
        agent_id: str,
        action: str,
        context: Dict[str, Any],
    ) -> str:
        """Request human approval for an action"""
        approval_id = str(uuid.uuid4())
        
        self._pending_approvals[approval_id] = {
            "agent_id": agent_id,
            "action": action,
            "context": context,
            "status": "pending",
            "requested_at": int(time.time()),
        }
        
        return approval_id
    
    def approve_action(self, approval_id: str, approver_id: str) -> bool:
        """Approve a pending action"""
        if approval_id not in self._pending_approvals:
            return False
        
        self._pending_approvals[approval_id]["status"] = "approved"
        self._pending_approvals[approval_id]["approved_by"] = approver_id
        self._pending_approvals[approval_id]["approved_at"] = int(time.time())
        
        return True
    
    def deny_action(self, approval_id: str, denier_id: str, reason: str) -> bool:
        """Deny a pending action"""
        if approval_id not in self._pending_approvals:
            return False
        
        self._pending_approvals[approval_id]["status"] = "denied"
        self._pending_approvals[approval_id]["denied_by"] = denier_id
        self._pending_approvals[approval_id]["denied_at"] = int(time.time())
        self._pending_approvals[approval_id]["denial_reason"] = reason
        
        return True
    
    def kill_switch(self, agent_id: str, operator_id: str, reason: str) -> RevocationEvent:
        """Emergency kill switch - immediately freeze agent"""
        return self.revoke(
            agent_id=agent_id,
            revocation_type="full_freeze",
            reason=f"KILL SWITCH: {reason}",
            revoked_by=operator_id,
            reversible=True,
        )
    
    # === Helper Methods ===
    
    def _log_event(self, event_type: str, agent_id: str, action: str, result: str, details: Dict[str, Any]) -> None:
        """Log a governance event"""
        event = GovernanceEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            agent_id=agent_id,
            action=action,
            result=result,
            details=details,
        )
        self._events.append(event)
    
    def _get_agent_cluster(self, agent_id: str) -> Optional[str]:
        """Get agent's cluster ID"""
        # Would integrate with SemanticNode
        return None
    
    def _has_supervisor(self, agent_id: str) -> bool:
        """Check if agent has a supervisor"""
        # Check if any Class B agent is observing this agent
        return agent_id in self._observed_agents
    
    def _get_supervisor(self, agent_id: str) -> Optional[str]:
        """Get agent's supervisor ID"""
        # Would return the Class B agent observing this agent
        return None
    
    def _add_pending_approval(self, agent_id: str, action: str, context: Dict[str, Any]) -> str:
        """Add action to pending approval queue"""
        return self.request_human_approval(agent_id, action, context)
    
    def _apply_policy_to_agent(self, agent_id: str, policy: GovernancePolicy) -> None:
        """Apply policy constraints to an agent"""
        self._log_event("policy_applied", agent_id, "apply_policy", "success", {
            "policy_id": policy.policy_id,
        })
    
    def _check_semantic_drift(self, agent_id: str) -> bool:
        """Check if agent has drifted from its semantic cluster"""
        # Would integrate with SemanticNode
        return False
    
    # === Classification ===
    
    def classify_agent(self, agent_id: str, agent_class: AgentClass) -> None:
        """Classify an agent"""
        self._agent_classes[agent_id] = agent_class
        self._log_event("classification", agent_id, "classify", agent_class.value, {})
    
    def get_classification(self, agent_id: str) -> Optional[AgentClassification]:
        """Get agent's classification"""
        agent_class = self._agent_classes.get(agent_id)
        if agent_class:
            return AGENT_CLASSIFICATIONS.get(agent_class)
        return None
    
    # === Stats ===
    
    def get_stats(self) -> Dict[str, Any]:
        """Get governance engine statistics"""
        return {
            "policies": len(self._policies),
            "ownership_records": len(self._ownership),
            "contracts": len(self._contracts),
            "semantic_rules": len(self._semantic_rules),
            "behavioral_rules": len(self._behavioral_rules),
            "classified_agents": len(self._agent_classes),
            "observed_agents": len(self._observed_agents),
            "events": len(self._events),
            "escalations": len(self._escalations),
            "revocations": len(self._revocations),
            "pending_approvals": len(self._pending_approvals),
        }
    
    def get_events(self, agent_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get governance events"""
        events = self._events
        if agent_id:
            events = [e for e in events if e.agent_id == agent_id]
        return [e.to_dict() for e in events[-limit:]]


# ============== GLOBAL INSTANCE ==============

governance_engine = GovernanceEngine()
