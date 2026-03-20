"""
HSU-Spec Section 26: DSID-P Security Threat Model
==================================================

Full-spectrum security analysis aligned with:
- NIST 800-53
- MITRE ATT&CK for Distributed Systems
- Zero-Trust Architecture Guides
- Government digital identity frameworks
- Enterprise deep-tech risk assessments

Threat Domains:
1. Identity Threats (L1)
2. Memory/DAG Integrity Threats (L2+L3)
3. Semantic Manipulation
4. Coordination/Workflow Attacks (L4)
5. Registry Manipulation Threats (L5)
6. Infrastructure & Node Network Threats
7. Human Governance Threats

Security Principles:
1. Zero-Trust Identity
2. Immutable Lineage
3. Governance-by-Construction
4. Deterministic State Validation
5. Sovereign Isolation
"""

import hashlib
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


# ============== THREAT DOMAINS ==============

class ThreatDomain(Enum):
    """Security threat domains"""
    IDENTITY = "identity"                    # L1 threats
    DAG_INTEGRITY = "dag_integrity"          # L2+L3 threats
    SEMANTIC = "semantic"                    # Semantic subsystem threats
    COORDINATION = "coordination"            # L4 threats
    REGISTRY = "registry"                    # L5 threats
    NETWORK = "network"                      # Node network threats
    HUMAN_GOVERNANCE = "human_governance"    # Human/policy threats
    SOVEREIGN = "sovereign"                  # Sovereign deployment threats


class ThreatSeverity(Enum):
    """Threat severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatStatus(Enum):
    """Threat detection status"""
    DETECTED = "detected"
    MITIGATED = "mitigated"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class MitigationLayer(Enum):
    """Layer where mitigation is applied"""
    L1_IDENTITY = "L1"
    L2_USER_DAG = "L2"
    L3_AGENT_DAG = "L3"
    L4_COORDINATION = "L4"
    L5_REGISTRY = "L5"
    SEMANTIC = "semantic"
    GOVERNANCE = "governance"
    NETWORK = "network"


# ============== THREAT DEFINITIONS ==============

@dataclass
class ThreatDefinition:
    """Definition of a security threat"""
    threat_id: str
    name: str
    domain: ThreatDomain
    description: str
    attack_vector: str
    impact: str
    severity: ThreatSeverity
    mitigation_layers: List[MitigationLayer]
    mitigations: List[str]
    indicators: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "threat_id": self.threat_id,
            "name": self.name,
            "domain": self.domain.value,
            "description": self.description,
            "attack_vector": self.attack_vector,
            "impact": self.impact,
            "severity": self.severity.value,
            "mitigation_layers": [l.value for l in self.mitigation_layers],
            "mitigations": self.mitigations,
            "indicators": self.indicators,
        }


@dataclass
class ThreatEvent:
    """A detected threat event"""
    event_id: str
    threat_id: str
    domain: ThreatDomain
    severity: ThreatSeverity
    status: ThreatStatus
    source_entity: str
    target_entity: Optional[str]
    details: Dict[str, Any]
    detected_at: int
    resolved_at: Optional[int] = None
    mitigation_applied: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "threat_id": self.threat_id,
            "domain": self.domain.value,
            "severity": self.severity.value,
            "status": self.status.value,
            "source_entity": self.source_entity,
            "target_entity": self.target_entity,
            "details": self.details,
            "detected_at": self.detected_at,
            "resolved_at": self.resolved_at,
            "mitigation_applied": self.mitigation_applied,
        }


# ============== THREAT CATALOG ==============

class ThreatCatalog:
    """
    Catalog of all defined threats in DSID-P
    Based on Section 26 threat taxonomy
    """
    
    def __init__(self):
        self._threats: Dict[str, ThreatDefinition] = {}
        self._initialize_threats()
    
    def _initialize_threats(self):
        """Initialize the threat catalog with Section 26 threats"""
        
        # ===== IDENTITY THREATS (L1) =====
        
        self._add_threat(ThreatDefinition(
            threat_id="T001",
            name="Identity Spoofing",
            domain=ThreatDomain.IDENTITY,
            description="Adversary tries to impersonate an agent, user, or enterprise",
            attack_vector="Forged tokens, stolen credentials",
            impact="Unauthorized agent actions",
            severity=ThreatSeverity.CRITICAL,
            mitigation_layers=[MitigationLayer.L1_IDENTITY, MitigationLayer.L5_REGISTRY],
            mitigations=[
                "Immutable identity objects",
                "Signature validation",
                "Registry anchoring",
                "Governance contracts tied to identity",
                "Mandatory identity lineage checks",
            ],
            indicators=[
                "Multiple identity claims from same source",
                "Signature verification failures",
                "Identity not found in registry",
            ],
        ))
        
        self._add_threat(ThreatDefinition(
            threat_id="T002",
            name="Ownership Tampering",
            domain=ThreatDomain.IDENTITY,
            description="Attacker attempts to alter ownership of an agent",
            attack_vector="Registry manipulation, forged transfer requests",
            impact="Unauthorized control of agent",
            severity=ThreatSeverity.HIGH,
            mitigation_layers=[MitigationLayer.L5_REGISTRY, MitigationLayer.GOVERNANCE],
            mitigations=[
                "L5 registry blocks contain ownership proofs",
                "Cross-node consensus on ownership",
                "Transfer contracts require multi-party signatures",
            ],
            indicators=[
                "Ownership change without proper signatures",
                "Registry block hash mismatch",
                "Missing transfer authorization",
            ],
        ))
        
        self._add_threat(ThreatDefinition(
            threat_id="T003",
            name="Session Hijacking",
            domain=ThreatDomain.IDENTITY,
            description="Session tokens intercepted in external systems",
            attack_vector="Man-in-the-middle, token theft",
            impact="Unauthorized session access",
            severity=ThreatSeverity.MEDIUM,
            mitigation_layers=[MitigationLayer.L1_IDENTITY, MitigationLayer.NETWORK],
            mitigations=[
                "DSID-P actions require identity proofs, not just app sessions",
                "All high-value operations require re-authentication",
            ],
            indicators=[
                "Session used from multiple IPs",
                "Unusual access patterns",
                "Token reuse after expiration",
            ],
        ))
        
        # ===== DAG INTEGRITY THREATS (L2+L3) =====
        
        self._add_threat(ThreatDefinition(
            threat_id="T004",
            name="Unauthorized DAG Mutation",
            domain=ThreatDomain.DAG_INTEGRITY,
            description="Attacker attempts to alter memory or behavior graph nodes",
            attack_vector="Direct node manipulation, API exploitation",
            impact="Agent misalignment or false memory",
            severity=ThreatSeverity.CRITICAL,
            mitigation_layers=[MitigationLayer.L2_USER_DAG, MitigationLayer.L3_AGENT_DAG],
            mitigations=[
                "Append-only DAG",
                "Hash-anchored lineage",
                "Invalid hashes rejected",
                "Supervisor agents detect anomalies",
                "Semantic drift detection triggers alarms",
            ],
            indicators=[
                "Hash verification failure",
                "Parent node not found",
                "Unexpected node structure",
            ],
        ))
        
        self._add_threat(ThreatDefinition(
            threat_id="T005",
            name="DAG Corruption / Desynchronization",
            domain=ThreatDomain.DAG_INTEGRITY,
            description="Corruption through infrastructure failure or targeted tampering",
            attack_vector="Storage corruption, network partition",
            impact="Data loss, inconsistent state",
            severity=ThreatSeverity.HIGH,
            mitigation_layers=[MitigationLayer.L2_USER_DAG, MitigationLayer.L3_AGENT_DAG, MitigationLayer.NETWORK],
            mitigations=[
                "Multiple replicas",
                "Deterministic reconstruction",
                "Cold/warm rehydration modes",
                "Node-level cross-validation of roots",
            ],
            indicators=[
                "Root hash mismatch across nodes",
                "Reconstruction failure",
                "Missing DAG segments",
            ],
        ))
        
        self._add_threat(ThreatDefinition(
            threat_id="T006",
            name="Memory Injection",
            domain=ThreatDomain.DAG_INTEGRITY,
            description="Adversary tries to insert false memory into an agent",
            attack_vector="Memory Gateway bypass, API exploitation",
            impact="Agent behavior manipulation",
            severity=ThreatSeverity.HIGH,
            mitigation_layers=[MitigationLayer.L3_AGENT_DAG, MitigationLayer.GOVERNANCE],
            mitigations=[
                "Memory Gateway Layer mediates all writes",
                "Only authorized identities can append",
                "Contract-bound memory limits",
                "Supervisor-agent verification",
            ],
            indicators=[
                "Memory write from unauthorized source",
                "Memory content policy violation",
                "Unusual memory growth rate",
            ],
        ))
        
        # ===== SEMANTIC THREATS =====
        
        self._add_threat(ThreatDefinition(
            threat_id="T007",
            name="Semantic Poisoning",
            domain=ThreatDomain.SEMANTIC,
            description="Adversary manipulates vectors to push agent into wrong cluster",
            attack_vector="Crafted inputs, embedding manipulation",
            impact="Bypass governance, escalate permissions, distort behavior",
            severity=ThreatSeverity.CRITICAL,
            mitigation_layers=[MitigationLayer.SEMANTIC, MitigationLayer.GOVERNANCE],
            mitigations=[
                "Semantic drift thresholds",
                "Cluster integrity rules",
                "Multi-vector averaging (reduces single-outlier impact)",
                "Supervisor agents review cluster changes",
            ],
            indicators=[
                "Rapid cluster changes",
                "Drift score exceeds threshold",
                "Vector anomaly detected",
            ],
        ))
        
        self._add_threat(ThreatDefinition(
            threat_id="T008",
            name="Mis-clustering",
            domain=ThreatDomain.SEMANTIC,
            description="Unintentional drift due to rare or contradictory inputs",
            attack_vector="Edge case inputs, data quality issues",
            impact="Incorrect governance application",
            severity=ThreatSeverity.MEDIUM,
            mitigation_layers=[MitigationLayer.SEMANTIC, MitigationLayer.GOVERNANCE],
            mitigations=[
                "Periodic recalibration",
                "Semantic outlier scoring",
                "Human/enterprise override for sensitive agents",
            ],
            indicators=[
                "Cluster assignment instability",
                "Outlier score exceeds threshold",
                "Governance rule conflicts",
            ],
        ))
        
        # ===== COORDINATION THREATS (L4) =====
        
        self._add_threat(ThreatDefinition(
            threat_id="T009",
            name="Workflow Manipulation",
            domain=ThreatDomain.COORDINATION,
            description="Attacker modifies coordination events or causes false lineage",
            attack_vector="Event injection, causality chain tampering",
            impact="False audit trail, workflow corruption",
            severity=ThreatSeverity.HIGH,
            mitigation_layers=[MitigationLayer.L4_COORDINATION, MitigationLayer.GOVERNANCE],
            mitigations=[
                "Append-only L4 DAG",
                "Causality chain hash checks",
                "Event signatures required",
                "Supervisor agents monitoring workflow consistency",
            ],
            indicators=[
                "Causality chain break",
                "Event signature invalid",
                "Unexpected event source",
            ],
        ))
        
        self._add_threat(ThreatDefinition(
            threat_id="T010",
            name="Delegation Abuse",
            domain=ThreatDomain.COORDINATION,
            description="Agent delegates tasks to unauthorized agents",
            attack_vector="Permission escalation, contract bypass",
            impact="Unauthorized actions by delegated agents",
            severity=ThreatSeverity.HIGH,
            mitigation_layers=[MitigationLayer.L4_COORDINATION, MitigationLayer.GOVERNANCE],
            mitigations=[
                "Strict delegation rules in governance contracts",
                "Cluster-based permission boundaries",
                "Lineage linking delegation to identity",
            ],
            indicators=[
                "Delegation to unauthorized cluster",
                "Delegation chain exceeds depth limit",
                "Missing delegation authorization",
            ],
        ))
        
        # ===== REGISTRY THREATS (L5) =====
        
        self._add_threat(ThreatDefinition(
            threat_id="T011",
            name="Block Rewriting",
            domain=ThreatDomain.REGISTRY,
            description="Attacker attempts to rewrite agent or user registration blocks",
            attack_vector="Direct registry manipulation",
            impact="False identity records, ownership fraud",
            severity=ThreatSeverity.CRITICAL,
            mitigation_layers=[MitigationLayer.L5_REGISTRY, MitigationLayer.NETWORK],
            mitigations=[
                "No global consensus needed → private sovereign chain",
                "Blocks are signed",
                "Multi-node verification",
                "Cross-check identity lineage",
            ],
            indicators=[
                "Block hash mismatch",
                "Signature verification failure",
                "Block not found in peer nodes",
            ],
        ))
        
        self._add_threat(ThreatDefinition(
            threat_id="T012",
            name="Forking / Chain Tampering",
            domain=ThreatDomain.REGISTRY,
            description="Adversary creates parallel version of registry",
            attack_vector="Node compromise, network partition exploitation",
            impact="Inconsistent registry state",
            severity=ThreatSeverity.HIGH,
            mitigation_layers=[MitigationLayer.L5_REGISTRY, MitigationLayer.NETWORK],
            mitigations=[
                "Authoritative nodes in sovereign deployments",
                "Chain-of-custody validation",
                "Root-hash comparison",
                "Enterprise/government signature anchoring",
            ],
            indicators=[
                "Chain divergence detected",
                "Multiple chain heads",
                "Root hash inconsistency",
            ],
        ))
        
        # ===== NETWORK THREATS =====
        
        self._add_threat(ThreatDefinition(
            threat_id="T013",
            name="Node Spoofing",
            domain=ThreatDomain.NETWORK,
            description="Fake node pretends to be valid DSID-P node",
            attack_vector="Identity forgery, certificate theft",
            impact="Data exfiltration, false data injection",
            severity=ThreatSeverity.HIGH,
            mitigation_layers=[MitigationLayer.NETWORK, MitigationLayer.L1_IDENTITY],
            mitigations=[
                "Node identity certificates",
                "Mutual authentication",
                "Zero-trust handshake protocols",
            ],
            indicators=[
                "Certificate validation failure",
                "Unknown node identity",
                "Handshake protocol violation",
            ],
        ))
        
        self._add_threat(ThreatDefinition(
            threat_id="T014",
            name="Transport Manipulation",
            domain=ThreatDomain.NETWORK,
            description="Man-in-the-middle changes messages between nodes",
            attack_vector="Network interception, message tampering",
            impact="Data corruption, false commands",
            severity=ThreatSeverity.HIGH,
            mitigation_layers=[MitigationLayer.NETWORK],
            mitigations=[
                "Message signing",
                "CBOR canonicalization",
                "Deterministic message verification",
            ],
            indicators=[
                "Message signature invalid",
                "CBOR decode failure",
                "Message hash mismatch",
            ],
        ))
        
        # ===== HUMAN GOVERNANCE THREATS =====
        
        self._add_threat(ThreatDefinition(
            threat_id="T015",
            name="Misconfiguration",
            domain=ThreatDomain.HUMAN_GOVERNANCE,
            description="Incorrect governance policy, permission error, unsafe defaults",
            attack_vector="Human error, lack of validation",
            impact="Security gaps, compliance failures",
            severity=ThreatSeverity.MEDIUM,
            mitigation_layers=[MitigationLayer.GOVERNANCE],
            mitigations=[
                "Governance templates",
                "Semantic roles",
                "Automated validation rules",
                "Supervisory agent checks",
            ],
            indicators=[
                "Policy validation warnings",
                "Unusual permission grants",
                "Default policy in use",
            ],
        ))
        
        self._add_threat(ThreatDefinition(
            threat_id="T016",
            name="Insider Threat",
            domain=ThreatDomain.HUMAN_GOVERNANCE,
            description="Authorized user misuses system",
            attack_vector="Privilege abuse, data exfiltration",
            impact="Data breach, system compromise",
            severity=ThreatSeverity.HIGH,
            mitigation_layers=[MitigationLayer.GOVERNANCE, MitigationLayer.L1_IDENTITY],
            mitigations=[
                "Lineage tracking",
                "Auditability",
                "Permission tiers",
                "Mandatory supervisor approval for sensitive actions",
            ],
            indicators=[
                "Unusual access patterns",
                "Bulk data access",
                "Off-hours activity",
            ],
        ))
        
        self._add_threat(ThreatDefinition(
            threat_id="T017",
            name="Over-permissive Agents",
            domain=ThreatDomain.HUMAN_GOVERNANCE,
            description="Agent receives too much access due to poor contract design",
            attack_vector="Contract misconfiguration",
            impact="Unauthorized data access, action scope creep",
            severity=ThreatSeverity.MEDIUM,
            mitigation_layers=[MitigationLayer.GOVERNANCE, MitigationLayer.L3_AGENT_DAG],
            mitigations=[
                "Default deny-all policies",
                "Semantic-risk-based permissions",
                "Periodic contract reviews",
            ],
            indicators=[
                "Permission scope exceeds cluster norms",
                "Contract review overdue",
                "High-risk actions without supervision",
            ],
        ))
        
        # ===== SOVEREIGN THREATS =====
        
        self._add_threat(ThreatDefinition(
            threat_id="T018",
            name="Regulatory Compliance Failure",
            domain=ThreatDomain.SOVEREIGN,
            description="Improper audit trails, missing lineage, lack of transparency",
            attack_vector="Process gaps, incomplete implementation",
            impact="Legal liability, regulatory penalties",
            severity=ThreatSeverity.HIGH,
            mitigation_layers=[MitigationLayer.L4_COORDINATION, MitigationLayer.GOVERNANCE],
            mitigations=[
                "Immutable coordination DAG",
                "Reconstructable memory",
                "Full identity lineage",
                "Policy-based governance",
            ],
            indicators=[
                "Audit trail gaps",
                "Missing lineage entries",
                "Compliance check failures",
            ],
        ))
        
        self._add_threat(ThreatDefinition(
            threat_id="T019",
            name="Cross-Ministry Contamination",
            domain=ThreatDomain.SOVEREIGN,
            description="Unauthorized data interchange between governmental departments",
            attack_vector="Permission misconfiguration, data leakage",
            impact="Data sovereignty violation, privacy breach",
            severity=ThreatSeverity.CRITICAL,
            mitigation_layers=[MitigationLayer.L2_USER_DAG, MitigationLayer.L3_AGENT_DAG, MitigationLayer.GOVERNANCE],
            mitigations=[
                "Role-based identity segregation",
                "Cluster-bound data silos",
                "L2/L3 memory isolation",
            ],
            indicators=[
                "Cross-boundary data access",
                "Unauthorized cluster interaction",
                "Data residency violation",
            ],
        ))
    
    def _add_threat(self, threat: ThreatDefinition):
        """Add a threat to the catalog"""
        self._threats[threat.threat_id] = threat
    
    def get_threat(self, threat_id: str) -> Optional[ThreatDefinition]:
        """Get threat by ID"""
        return self._threats.get(threat_id)
    
    def list_threats(self, domain: Optional[ThreatDomain] = None) -> List[ThreatDefinition]:
        """List threats, optionally filtered by domain"""
        threats = list(self._threats.values())
        if domain:
            threats = [t for t in threats if t.domain == domain]
        return threats
    
    def get_threats_by_severity(self, severity: ThreatSeverity) -> List[ThreatDefinition]:
        """Get threats by severity level"""
        return [t for t in self._threats.values() if t.severity == severity]
    
    def get_threat_matrix(self) -> Dict[str, Dict[str, str]]:
        """Get threat matrix summary"""
        matrix = {}
        for threat in self._threats.values():
            matrix[threat.threat_id] = {
                "name": threat.name,
                "domain": threat.domain.value,
                "severity": threat.severity.value,
                "mitigation_layers": ", ".join(l.value for l in threat.mitigation_layers),
            }
        return matrix


# ============== THREAT DETECTION ENGINE ==============

class ThreatDetectionEngine:
    """
    Engine for detecting and managing security threats
    """
    
    def __init__(self):
        self.catalog = ThreatCatalog()
        self._events: Dict[str, ThreatEvent] = {}
        self._active_threats: Dict[str, List[str]] = {}  # entity -> event_ids
    
    def detect_threat(
        self,
        threat_id: str,
        source_entity: str,
        target_entity: Optional[str] = None,
        details: Dict[str, Any] = None,
    ) -> ThreatEvent:
        """Record a detected threat"""
        threat = self.catalog.get_threat(threat_id)
        if not threat:
            raise ValueError(f"Unknown threat ID: {threat_id}")
        
        event = ThreatEvent(
            event_id=str(uuid.uuid4()),
            threat_id=threat_id,
            domain=threat.domain,
            severity=threat.severity,
            status=ThreatStatus.DETECTED,
            source_entity=source_entity,
            target_entity=target_entity,
            details=details or {},
            detected_at=int(time.time() * 1000),
        )
        
        self._events[event.event_id] = event
        
        if source_entity not in self._active_threats:
            self._active_threats[source_entity] = []
        self._active_threats[source_entity].append(event.event_id)
        
        logger.warning(f"Threat detected: {threat.name} ({threat_id}) from {source_entity}")
        
        return event
    
    def mitigate_threat(
        self,
        event_id: str,
        mitigation_applied: str,
    ) -> ThreatEvent:
        """Mark a threat as mitigated"""
        if event_id not in self._events:
            raise ValueError(f"Unknown event ID: {event_id}")
        
        event = self._events[event_id]
        event.status = ThreatStatus.MITIGATED
        event.mitigation_applied = mitigation_applied
        
        return event
    
    def escalate_threat(self, event_id: str) -> ThreatEvent:
        """Escalate a threat for human review"""
        if event_id not in self._events:
            raise ValueError(f"Unknown event ID: {event_id}")
        
        event = self._events[event_id]
        event.status = ThreatStatus.ESCALATED
        
        logger.warning(f"Threat escalated: {event.threat_id} ({event_id})")
        
        return event
    
    def resolve_threat(self, event_id: str) -> ThreatEvent:
        """Mark a threat as resolved"""
        if event_id not in self._events:
            raise ValueError(f"Unknown event ID: {event_id}")
        
        event = self._events[event_id]
        event.status = ThreatStatus.RESOLVED
        event.resolved_at = int(time.time() * 1000)
        
        # Remove from active threats
        if event.source_entity in self._active_threats:
            if event_id in self._active_threats[event.source_entity]:
                self._active_threats[event.source_entity].remove(event_id)
        
        return event
    
    def mark_false_positive(self, event_id: str) -> ThreatEvent:
        """Mark a threat as false positive"""
        if event_id not in self._events:
            raise ValueError(f"Unknown event ID: {event_id}")
        
        event = self._events[event_id]
        event.status = ThreatStatus.FALSE_POSITIVE
        event.resolved_at = int(time.time() * 1000)
        
        return event
    
    def get_event(self, event_id: str) -> Optional[ThreatEvent]:
        """Get threat event by ID"""
        return self._events.get(event_id)
    
    def get_active_threats(self, entity: Optional[str] = None) -> List[ThreatEvent]:
        """Get active (unresolved) threats"""
        if entity:
            event_ids = self._active_threats.get(entity, [])
            return [self._events[eid] for eid in event_ids if eid in self._events]
        
        return [e for e in self._events.values() 
                if e.status in [ThreatStatus.DETECTED, ThreatStatus.ESCALATED]]
    
    def get_threat_history(
        self,
        entity: Optional[str] = None,
        domain: Optional[ThreatDomain] = None,
    ) -> List[ThreatEvent]:
        """Get threat history with optional filters"""
        events = list(self._events.values())
        
        if entity:
            events = [e for e in events if e.source_entity == entity or e.target_entity == entity]
        if domain:
            events = [e for e in events if e.domain == domain]
        
        return sorted(events, key=lambda e: e.detected_at, reverse=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get threat detection statistics"""
        total = len(self._events)
        by_status = {}
        by_domain = {}
        by_severity = {}
        
        for event in self._events.values():
            status = event.status.value
            by_status[status] = by_status.get(status, 0) + 1
            
            domain = event.domain.value
            by_domain[domain] = by_domain.get(domain, 0) + 1
            
            severity = event.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1
        
        return {
            "total_events": total,
            "by_status": by_status,
            "by_domain": by_domain,
            "by_severity": by_severity,
            "active_threats": len(self.get_active_threats()),
        }


# ============== SECURITY POSTURE ASSESSMENT ==============

@dataclass
class SecurityPosture:
    """Security posture assessment result"""
    assessment_id: str
    timestamp: int
    overall_score: float  # 0-100
    domain_scores: Dict[str, float]
    findings: List[Dict[str, Any]]
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "timestamp": self.timestamp,
            "overall_score": round(self.overall_score, 2),
            "domain_scores": {k: round(v, 2) for k, v in self.domain_scores.items()},
            "findings": self.findings,
            "recommendations": self.recommendations,
        }


class SecurityPostureAssessor:
    """
    Assesses overall security posture of the DSID-P deployment
    """
    
    def __init__(self, threat_engine: ThreatDetectionEngine):
        self.threat_engine = threat_engine
    
    def assess(self) -> SecurityPosture:
        """Perform security posture assessment"""
        stats = self.threat_engine.get_stats()
        
        # Calculate domain scores (100 - penalty for active threats)
        domain_scores = {}
        for domain in ThreatDomain:
            domain_threats = [e for e in self.threat_engine.get_active_threats() 
                           if e.domain == domain]
            penalty = sum(
                50 if e.severity == ThreatSeverity.CRITICAL else
                30 if e.severity == ThreatSeverity.HIGH else
                15 if e.severity == ThreatSeverity.MEDIUM else 5
                for e in domain_threats
            )
            domain_scores[domain.value] = max(0, 100 - penalty)
        
        # Overall score is weighted average
        overall_score = sum(domain_scores.values()) / len(domain_scores) if domain_scores else 100
        
        # Generate findings
        findings = []
        for event in self.threat_engine.get_active_threats():
            threat = self.threat_engine.catalog.get_threat(event.threat_id)
            findings.append({
                "event_id": event.event_id,
                "threat": threat.name if threat else event.threat_id,
                "severity": event.severity.value,
                "status": event.status.value,
                "source": event.source_entity,
            })
        
        # Generate recommendations
        recommendations = []
        if stats.get("by_severity", {}).get("critical", 0) > 0:
            recommendations.append("Address critical threats immediately")
        if stats.get("by_status", {}).get("escalated", 0) > 0:
            recommendations.append("Review escalated threats requiring human attention")
        if domain_scores.get("identity", 100) < 80:
            recommendations.append("Strengthen identity verification controls")
        if domain_scores.get("semantic", 100) < 80:
            recommendations.append("Review semantic drift thresholds")
        if not recommendations:
            recommendations.append("Security posture is healthy - maintain current controls")
        
        return SecurityPosture(
            assessment_id=str(uuid.uuid4()),
            timestamp=int(time.time() * 1000),
            overall_score=overall_score,
            domain_scores=domain_scores,
            findings=findings,
            recommendations=recommendations,
        )


# ============== GLOBAL INSTANCES ==============

threat_catalog = ThreatCatalog()
threat_engine = ThreatDetectionEngine()
security_assessor = SecurityPostureAssessor(threat_engine)
