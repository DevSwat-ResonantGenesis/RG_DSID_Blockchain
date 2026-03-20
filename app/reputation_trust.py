"""
HSU-Spec Section 30: Agent Reputation & Trust System
====================================================

The trust, credibility, and reliability framework for DSID-P agents.

Reputation Pillars:
1. Performance Reputation (PR)
2. Behavioral Reputation (BR)
3. Semantic Reliability (SR)
4. Governance Compliance Score (GCS)
5. Social/Interaction Score (SIS)

Trust Tiers:
- T5 Platinum (90-100): Enterprise/Gov-grade reliability
- T4 Gold (75-89): High-performing, trusted
- T3 Silver (60-74): Stable, general-purpose
- T2 Bronze (40-59): Limited trust, supervised
- T1 Restricted (0-39): Heavily supervised or suspended

Features:
- Trust decay model
- Trust recovery mechanisms
- Marketplace integration
- Enterprise/Government integration
"""

import math
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# ============== TRUST TIERS ==============

class TrustTier(Enum):
    """Agent trust tiers"""
    T1_RESTRICTED = "T1"   # 0-39: Heavily supervised or suspended
    T2_BRONZE = "T2"       # 40-59: Limited trust, supervised
    T3_SILVER = "T3"       # 60-74: Stable, general-purpose
    T4_GOLD = "T4"         # 75-89: High-performing, trusted
    T5_PLATINUM = "T5"     # 90-100: Enterprise/Gov-grade reliability


def get_trust_tier(score: float) -> TrustTier:
    """Get trust tier from score"""
    if score >= 90:
        return TrustTier.T5_PLATINUM
    elif score >= 75:
        return TrustTier.T4_GOLD
    elif score >= 60:
        return TrustTier.T3_SILVER
    elif score >= 40:
        return TrustTier.T2_BRONZE
    else:
        return TrustTier.T1_RESTRICTED


# ============== REPUTATION PILLARS ==============

@dataclass
class PerformanceReputation:
    """Pillar 1: Performance Reputation (PR)"""
    agent_id: str
    task_success_rate: float       # 0-1
    error_frequency: float         # errors per 100 tasks
    output_quality_score: float    # 0-100
    latency_consistency: float     # 0-1 (1 = perfectly consistent)
    successful_interactions: int
    enterprise_satisfaction: float # 0-100
    
    def calculate_score(self) -> float:
        """Calculate PR score (0-100)"""
        return (
            self.task_success_rate * 30 +
            max(0, (100 - self.error_frequency * 10)) * 0.2 +
            self.output_quality_score * 0.2 +
            self.latency_consistency * 15 +
            min(100, self.successful_interactions / 10) * 0.1 +
            self.enterprise_satisfaction * 0.2
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "task_success_rate": round(self.task_success_rate, 4),
            "error_frequency": round(self.error_frequency, 4),
            "output_quality_score": round(self.output_quality_score, 2),
            "latency_consistency": round(self.latency_consistency, 4),
            "successful_interactions": self.successful_interactions,
            "enterprise_satisfaction": round(self.enterprise_satisfaction, 2),
            "pr_score": round(self.calculate_score(), 2),
        }


@dataclass
class BehavioralReputation:
    """Pillar 2: Behavioral Reputation (BR)"""
    agent_id: str
    behavior_consistency: float    # 0-1
    deviation_score: float         # 0-100 (lower is better)
    anomaly_count: int
    cooperation_quality: float     # 0-100
    conflict_rate: float           # conflicts per 100 interactions
    governance_warnings: int
    
    def calculate_score(self) -> float:
        """Calculate BR score (0-100)"""
        deviation_penalty = min(50, self.deviation_score * 0.5)
        anomaly_penalty = min(20, self.anomaly_count * 2)
        conflict_penalty = min(15, self.conflict_rate * 3)
        warning_penalty = min(15, self.governance_warnings * 5)
        
        base_score = (
            self.behavior_consistency * 50 +
            self.cooperation_quality * 0.5
        )
        
        return max(0, base_score - deviation_penalty - anomaly_penalty - conflict_penalty - warning_penalty)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "behavior_consistency": round(self.behavior_consistency, 4),
            "deviation_score": round(self.deviation_score, 2),
            "anomaly_count": self.anomaly_count,
            "cooperation_quality": round(self.cooperation_quality, 2),
            "conflict_rate": round(self.conflict_rate, 4),
            "governance_warnings": self.governance_warnings,
            "br_score": round(self.calculate_score(), 2),
        }


@dataclass
class SemanticReliability:
    """Pillar 3: Semantic Reliability (SR)"""
    agent_id: str
    drift_velocity: float          # lower is better
    cluster_consistency: float     # 0-1
    vector_coherence: float        # 0-1
    domain_alignment: float        # 0-100
    misalignment_recoveries: int
    
    def calculate_score(self) -> float:
        """Calculate SR score (0-100)"""
        drift_penalty = min(30, self.drift_velocity * 100)
        recovery_bonus = min(10, self.misalignment_recoveries * 2)
        
        base_score = (
            self.cluster_consistency * 30 +
            self.vector_coherence * 30 +
            self.domain_alignment * 0.4
        )
        
        return max(0, min(100, base_score - drift_penalty + recovery_bonus))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "drift_velocity": round(self.drift_velocity, 6),
            "cluster_consistency": round(self.cluster_consistency, 4),
            "vector_coherence": round(self.vector_coherence, 4),
            "domain_alignment": round(self.domain_alignment, 2),
            "misalignment_recoveries": self.misalignment_recoveries,
            "sr_score": round(self.calculate_score(), 2),
        }


@dataclass
class GovernanceComplianceScore:
    """Pillar 4: Governance Compliance Score (GCS)"""
    agent_id: str
    policy_violations: int
    permission_breaches: int
    unauthorized_writes: int
    delegation_misuse: int
    compliance_audits_passed: int
    compliance_audits_failed: int
    supervisory_interventions: int
    
    def calculate_score(self) -> float:
        """Calculate GCS score (0-100)"""
        violation_penalty = min(30, self.policy_violations * 10)
        breach_penalty = min(25, self.permission_breaches * 8)
        write_penalty = min(20, self.unauthorized_writes * 10)
        delegation_penalty = min(15, self.delegation_misuse * 5)
        intervention_penalty = min(10, self.supervisory_interventions * 3)
        
        total_audits = self.compliance_audits_passed + self.compliance_audits_failed
        audit_bonus = (self.compliance_audits_passed / total_audits * 20) if total_audits > 0 else 10
        
        base_score = 100 + audit_bonus
        penalties = violation_penalty + breach_penalty + write_penalty + delegation_penalty + intervention_penalty
        
        return max(0, base_score - penalties)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "policy_violations": self.policy_violations,
            "permission_breaches": self.permission_breaches,
            "unauthorized_writes": self.unauthorized_writes,
            "delegation_misuse": self.delegation_misuse,
            "compliance_audits_passed": self.compliance_audits_passed,
            "compliance_audits_failed": self.compliance_audits_failed,
            "supervisory_interventions": self.supervisory_interventions,
            "gcs_score": round(self.calculate_score(), 2),
        }


@dataclass
class SocialInteractionScore:
    """Pillar 5: Social/Interaction Score (SIS)"""
    agent_id: str
    peer_evaluations_positive: int
    peer_evaluations_negative: int
    enterprise_ratings_sum: float
    enterprise_ratings_count: int
    conflict_resolutions_success: int
    conflict_resolutions_failed: int
    cooperation_frequency: int
    legitimate_refusals: int
    incorrect_refusals: int
    
    def calculate_score(self) -> float:
        """Calculate SIS score (0-100)"""
        total_peer = self.peer_evaluations_positive + self.peer_evaluations_negative
        peer_score = (self.peer_evaluations_positive / total_peer * 30) if total_peer > 0 else 15
        
        enterprise_score = (self.enterprise_ratings_sum / self.enterprise_ratings_count * 0.3) if self.enterprise_ratings_count > 0 else 15
        
        total_conflicts = self.conflict_resolutions_success + self.conflict_resolutions_failed
        conflict_score = (self.conflict_resolutions_success / total_conflicts * 20) if total_conflicts > 0 else 10
        
        cooperation_score = min(20, self.cooperation_frequency / 10)
        
        total_refusals = self.legitimate_refusals + self.incorrect_refusals
        refusal_penalty = (self.incorrect_refusals / total_refusals * 10) if total_refusals > 0 else 0
        
        return max(0, min(100, peer_score + enterprise_score + conflict_score + cooperation_score - refusal_penalty))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "peer_evaluations_positive": self.peer_evaluations_positive,
            "peer_evaluations_negative": self.peer_evaluations_negative,
            "enterprise_ratings_avg": round(
                self.enterprise_ratings_sum / self.enterprise_ratings_count, 2
            ) if self.enterprise_ratings_count > 0 else 0,
            "conflict_resolutions_success": self.conflict_resolutions_success,
            "cooperation_frequency": self.cooperation_frequency,
            "sis_score": round(self.calculate_score(), 2),
        }


# ============== AGENT TRUST SCORE ==============

@dataclass
class WeightProfile:
    """Weight profile for ATS calculation"""
    name: str
    pr_weight: float
    br_weight: float
    sr_weight: float
    gcs_weight: float
    sis_weight: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "pr_weight": self.pr_weight,
            "br_weight": self.br_weight,
            "sr_weight": self.sr_weight,
            "gcs_weight": self.gcs_weight,
            "sis_weight": self.sis_weight,
        }


# Predefined weight profiles
WEIGHT_PROFILES = {
    "low_risk": WeightProfile(
        name="Low Risk (Creative)",
        pr_weight=0.30,
        br_weight=0.25,
        sr_weight=0.10,
        gcs_weight=0.10,
        sis_weight=0.25,
    ),
    "medium_risk": WeightProfile(
        name="Medium Risk (Workflow/Automation)",
        pr_weight=0.20,
        br_weight=0.20,
        sr_weight=0.20,
        gcs_weight=0.20,
        sis_weight=0.20,
    ),
    "high_risk": WeightProfile(
        name="High Risk (Legal/Finance/Medical)",
        pr_weight=0.15,
        br_weight=0.25,
        sr_weight=0.25,
        gcs_weight=0.30,
        sis_weight=0.05,
    ),
    "supervisor": WeightProfile(
        name="Supervisor/Governance",
        pr_weight=0.10,
        br_weight=0.20,
        sr_weight=0.30,
        gcs_weight=0.35,
        sis_weight=0.05,
    ),
}


@dataclass
class AgentTrustScore:
    """Complete Agent Trust Score (ATS)"""
    agent_id: str
    pr_score: float
    br_score: float
    sr_score: float
    gcs_score: float
    sis_score: float
    weight_profile: str
    ats: float
    tier: TrustTier
    calculated_at: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "pillar_scores": {
                "performance_reputation": round(self.pr_score, 2),
                "behavioral_reputation": round(self.br_score, 2),
                "semantic_reliability": round(self.sr_score, 2),
                "governance_compliance": round(self.gcs_score, 2),
                "social_interaction": round(self.sis_score, 2),
            },
            "weight_profile": self.weight_profile,
            "ats": round(self.ats, 2),
            "tier": self.tier.value,
            "tier_name": {
                TrustTier.T5_PLATINUM: "Platinum",
                TrustTier.T4_GOLD: "Gold",
                TrustTier.T3_SILVER: "Silver",
                TrustTier.T2_BRONZE: "Bronze",
                TrustTier.T1_RESTRICTED: "Restricted",
            }[self.tier],
            "calculated_at": self.calculated_at,
        }


class TrustScoreCalculator:
    """Calculate Agent Trust Score"""
    
    def __init__(self):
        self._scores: Dict[str, AgentTrustScore] = {}
        self._history: Dict[str, List[AgentTrustScore]] = {}
    
    def calculate(
        self,
        agent_id: str,
        pr: PerformanceReputation,
        br: BehavioralReputation,
        sr: SemanticReliability,
        gcs: GovernanceComplianceScore,
        sis: SocialInteractionScore,
        weight_profile: str = "medium_risk",
    ) -> AgentTrustScore:
        """Calculate ATS for an agent"""
        
        profile = WEIGHT_PROFILES.get(weight_profile, WEIGHT_PROFILES["medium_risk"])
        
        pr_score = pr.calculate_score()
        br_score = br.calculate_score()
        sr_score = sr.calculate_score()
        gcs_score = gcs.calculate_score()
        sis_score = sis.calculate_score()
        
        ats = (
            pr_score * profile.pr_weight +
            br_score * profile.br_weight +
            sr_score * profile.sr_weight +
            gcs_score * profile.gcs_weight +
            sis_score * profile.sis_weight
        )
        
        tier = get_trust_tier(ats)
        
        score = AgentTrustScore(
            agent_id=agent_id,
            pr_score=pr_score,
            br_score=br_score,
            sr_score=sr_score,
            gcs_score=gcs_score,
            sis_score=sis_score,
            weight_profile=weight_profile,
            ats=ats,
            tier=tier,
            calculated_at=int(time.time() * 1000),
        )
        
        self._scores[agent_id] = score
        
        if agent_id not in self._history:
            self._history[agent_id] = []
        self._history[agent_id].append(score)
        
        return score
    
    def get_score(self, agent_id: str) -> Optional[AgentTrustScore]:
        return self._scores.get(agent_id)
    
    def get_history(self, agent_id: str) -> List[AgentTrustScore]:
        return self._history.get(agent_id, [])


# ============== TRUST DECAY MODEL ==============

@dataclass
class TrustDecayConfig:
    """Configuration for trust decay"""
    base_decay_rate: float = 0.001      # Per day
    inactivity_multiplier: float = 2.0   # Multiplier for inactive agents
    outdated_graph_penalty: float = 0.05 # Penalty for outdated behavior graph
    drift_penalty_rate: float = 0.02     # Penalty per drift event
    gov_certified_reduction: float = 0.5 # Decay reduction for certified agents
    enterprise_verified_reduction: float = 0.3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_decay_rate": self.base_decay_rate,
            "inactivity_multiplier": self.inactivity_multiplier,
            "outdated_graph_penalty": self.outdated_graph_penalty,
            "drift_penalty_rate": self.drift_penalty_rate,
            "gov_certified_reduction": self.gov_certified_reduction,
            "enterprise_verified_reduction": self.enterprise_verified_reduction,
        }


class TrustDecayEngine:
    """Apply trust decay over time"""
    
    def __init__(self, config: TrustDecayConfig = None):
        self.config = config or TrustDecayConfig()
    
    def apply_decay(
        self,
        current_score: float,
        days_inactive: int = 0,
        behavior_graph_age_days: int = 0,
        drift_events: int = 0,
        is_gov_certified: bool = False,
        is_enterprise_verified: bool = False,
    ) -> Tuple[float, Dict[str, float]]:
        """Apply decay to trust score"""
        
        # Calculate decay rate
        decay_rate = self.config.base_decay_rate
        
        # Inactivity multiplier
        if days_inactive > 30:
            decay_rate *= self.config.inactivity_multiplier
        
        # Certifications reduce decay
        if is_gov_certified:
            decay_rate *= (1 - self.config.gov_certified_reduction)
        if is_enterprise_verified:
            decay_rate *= (1 - self.config.enterprise_verified_reduction)
        
        # Calculate penalties
        inactivity_penalty = decay_rate * days_inactive
        graph_penalty = self.config.outdated_graph_penalty if behavior_graph_age_days > 90 else 0
        drift_penalty = self.config.drift_penalty_rate * drift_events
        
        total_decay = inactivity_penalty + graph_penalty + drift_penalty
        new_score = max(0, current_score * (1 - total_decay))
        
        breakdown = {
            "inactivity_penalty": round(inactivity_penalty, 6),
            "graph_penalty": round(graph_penalty, 6),
            "drift_penalty": round(drift_penalty, 6),
            "total_decay": round(total_decay, 6),
        }
        
        return new_score, breakdown


# ============== TRUST RECOVERY ==============

class TrustRecoveryAction(Enum):
    """Actions that can recover trust"""
    VERIFIED_TASK = "verified_task"
    GOVERNANCE_AUDIT_PASSED = "governance_audit_passed"
    SEMANTIC_REALIGNMENT = "semantic_realignment"
    PEER_COOPERATION = "peer_cooperation"
    SUPERVISED_UPGRADE = "supervised_upgrade"
    ENTERPRISE_CERTIFICATION = "enterprise_certification"
    GOVERNMENT_CERTIFICATION = "government_certification"


@dataclass
class TrustRecoveryEvent:
    """A trust recovery event"""
    event_id: str
    agent_id: str
    action: TrustRecoveryAction
    score_before: float
    score_after: float
    recovery_amount: float
    timestamp: int
    verified_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "agent_id": self.agent_id,
            "action": self.action.value,
            "score_before": round(self.score_before, 2),
            "score_after": round(self.score_after, 2),
            "recovery_amount": round(self.recovery_amount, 2),
            "timestamp": self.timestamp,
            "verified_by": self.verified_by,
        }


class TrustRecoveryEngine:
    """Handle trust recovery for agents"""
    
    RECOVERY_AMOUNTS = {
        TrustRecoveryAction.VERIFIED_TASK: 0.5,
        TrustRecoveryAction.GOVERNANCE_AUDIT_PASSED: 5.0,
        TrustRecoveryAction.SEMANTIC_REALIGNMENT: 3.0,
        TrustRecoveryAction.PEER_COOPERATION: 1.0,
        TrustRecoveryAction.SUPERVISED_UPGRADE: 4.0,
        TrustRecoveryAction.ENTERPRISE_CERTIFICATION: 10.0,
        TrustRecoveryAction.GOVERNMENT_CERTIFICATION: 15.0,
    }
    
    def __init__(self):
        self._events: Dict[str, List[TrustRecoveryEvent]] = {}
    
    def apply_recovery(
        self,
        agent_id: str,
        current_score: float,
        action: TrustRecoveryAction,
        verified_by: Optional[str] = None,
    ) -> TrustRecoveryEvent:
        """Apply trust recovery"""
        
        recovery_amount = self.RECOVERY_AMOUNTS.get(action, 1.0)
        new_score = min(100, current_score + recovery_amount)
        
        event = TrustRecoveryEvent(
            event_id=str(uuid.uuid4()),
            agent_id=agent_id,
            action=action,
            score_before=current_score,
            score_after=new_score,
            recovery_amount=recovery_amount,
            timestamp=int(time.time() * 1000),
            verified_by=verified_by,
        )
        
        if agent_id not in self._events:
            self._events[agent_id] = []
        self._events[agent_id].append(event)
        
        return event
    
    def get_recovery_history(self, agent_id: str) -> List[TrustRecoveryEvent]:
        return self._events.get(agent_id, [])


# ============== TRUST ENFORCEMENT ==============

@dataclass
class TrustEnforcementRule:
    """Trust enforcement rule"""
    rule_id: str
    name: str
    min_tier: TrustTier
    applies_to: List[str]  # cluster codes
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "min_tier": self.min_tier.value,
            "applies_to": self.applies_to,
            "description": self.description,
        }


class TrustEnforcementEngine:
    """Enforce trust-based rules"""
    
    def __init__(self):
        self._rules: Dict[str, TrustEnforcementRule] = {}
        self._initialize_rules()
    
    def _initialize_rules(self):
        """Initialize enforcement rules"""
        
        self._add_rule(TrustEnforcementRule(
            rule_id="TE-001",
            name="High-Risk Cluster Access",
            min_tier=TrustTier.T4_GOLD,
            applies_to=["H", "P", "G", "B"],
            description="Legal, Medical, Governance, Financial clusters require T4+",
        ))
        
        self._add_rule(TrustEnforcementRule(
            rule_id="TE-002",
            name="Supervisory Agent Requirement",
            min_tier=TrustTier.T5_PLATINUM,
            applies_to=["G"],
            description="Supervisory agents must be T5 Platinum",
        ))
        
        self._add_rule(TrustEnforcementRule(
            rule_id="TE-003",
            name="Critical Agent Collaboration",
            min_tier=TrustTier.T3_SILVER,
            applies_to=["S", "W"],
            description="Software and Workflow agents need T3+ for critical collaboration",
        ))
        
        self._add_rule(TrustEnforcementRule(
            rule_id="TE-004",
            name="Marketplace Visibility",
            min_tier=TrustTier.T2_BRONZE,
            applies_to=["*"],
            description="T1 Restricted agents have limited marketplace visibility",
        ))
    
    def _add_rule(self, rule: TrustEnforcementRule):
        self._rules[rule.rule_id] = rule
    
    def check_access(
        self,
        agent_tier: TrustTier,
        cluster_code: str,
    ) -> Dict[str, Any]:
        """Check if agent has access based on trust tier"""
        
        violations = []
        for rule in self._rules.values():
            if cluster_code in rule.applies_to or "*" in rule.applies_to:
                tier_order = [TrustTier.T1_RESTRICTED, TrustTier.T2_BRONZE, 
                             TrustTier.T3_SILVER, TrustTier.T4_GOLD, TrustTier.T5_PLATINUM]
                
                if tier_order.index(agent_tier) < tier_order.index(rule.min_tier):
                    violations.append({
                        "rule_id": rule.rule_id,
                        "rule_name": rule.name,
                        "required_tier": rule.min_tier.value,
                        "agent_tier": agent_tier.value,
                    })
        
        return {
            "allowed": len(violations) == 0,
            "violations": violations,
        }
    
    def list_rules(self) -> List[TrustEnforcementRule]:
        return list(self._rules.values())


# ============== MARKETPLACE INTEGRATION ==============

class MarketplaceTrustIntegration:
    """Integrate trust with marketplace"""
    
    def calculate_price_multiplier(self, ats: float) -> float:
        """Calculate price multiplier based on ATS"""
        # PriceMultiplier = 1 + (ATS / 100)
        return 1 + (ats / 100)
    
    def get_visibility_level(self, tier: TrustTier) -> str:
        """Get marketplace visibility level"""
        visibility_map = {
            TrustTier.T5_PLATINUM: "featured",
            TrustTier.T4_GOLD: "promoted",
            TrustTier.T3_SILVER: "standard",
            TrustTier.T2_BRONZE: "limited",
            TrustTier.T1_RESTRICTED: "restricted",
        }
        return visibility_map.get(tier, "restricted")
    
    def get_marketplace_badge(self, tier: TrustTier) -> Dict[str, Any]:
        """Get marketplace badge for tier"""
        badges = {
            TrustTier.T5_PLATINUM: {"name": "Platinum Verified", "color": "#E5E4E2", "icon": "shield-check"},
            TrustTier.T4_GOLD: {"name": "Gold Trusted", "color": "#FFD700", "icon": "star"},
            TrustTier.T3_SILVER: {"name": "Silver Reliable", "color": "#C0C0C0", "icon": "check-circle"},
            TrustTier.T2_BRONZE: {"name": "Bronze", "color": "#CD7F32", "icon": "circle"},
            TrustTier.T1_RESTRICTED: {"name": "Restricted", "color": "#808080", "icon": "alert-circle"},
        }
        return badges.get(tier, badges[TrustTier.T1_RESTRICTED])


# ============== TRUST HISTORY & LINEAGE ==============

@dataclass
class TrustEvent:
    """A trust-related event"""
    event_id: str
    agent_id: str
    event_type: str  # "score_change", "tier_change", "violation", "recovery", "warning"
    details: Dict[str, Any]
    timestamp: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "agent_id": self.agent_id,
            "event_type": self.event_type,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class TrustHistoryManager:
    """Manage trust history and lineage"""
    
    def __init__(self):
        self._events: Dict[str, List[TrustEvent]] = {}
    
    def record_event(
        self,
        agent_id: str,
        event_type: str,
        details: Dict[str, Any],
    ) -> TrustEvent:
        """Record a trust event"""
        
        event = TrustEvent(
            event_id=str(uuid.uuid4()),
            agent_id=agent_id,
            event_type=event_type,
            details=details,
            timestamp=int(time.time() * 1000),
        )
        
        if agent_id not in self._events:
            self._events[agent_id] = []
        self._events[agent_id].append(event)
        
        return event
    
    def get_history(self, agent_id: str, event_type: Optional[str] = None) -> List[TrustEvent]:
        """Get trust history for an agent"""
        events = self._events.get(agent_id, [])
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events
    
    def get_audit_report(self, agent_id: str) -> Dict[str, Any]:
        """Generate audit report for an agent"""
        events = self._events.get(agent_id, [])
        
        return {
            "agent_id": agent_id,
            "total_events": len(events),
            "event_breakdown": {
                "score_changes": len([e for e in events if e.event_type == "score_change"]),
                "tier_changes": len([e for e in events if e.event_type == "tier_change"]),
                "violations": len([e for e in events if e.event_type == "violation"]),
                "recoveries": len([e for e in events if e.event_type == "recovery"]),
                "warnings": len([e for e in events if e.event_type == "warning"]),
            },
            "first_event": events[0].timestamp if events else None,
            "last_event": events[-1].timestamp if events else None,
        }


# ============== GLOBAL INSTANCES ==============

trust_calculator = TrustScoreCalculator()
decay_engine = TrustDecayEngine()
recovery_engine = TrustRecoveryEngine()
enforcement_engine = TrustEnforcementEngine()
marketplace_integration = MarketplaceTrustIntegration()
history_manager = TrustHistoryManager()
