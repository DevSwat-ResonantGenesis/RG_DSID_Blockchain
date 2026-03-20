"""
HSU-Spec Section 40: DSID-P Protocol Security Architecture
==========================================================

The complete cybersecurity, integrity, and safety model for
Distributed Semantic Identity & DAG Protocol.

Seven Security Layers:
1. Cryptographic Identity Security
2. Data & Memory Security (User/Agent DAG)
3. Semantic Engine Security
4. Governance Contract Security
5. Coordination DAG Integrity
6. Registry / Ledger Security
7. Federation & Sovereign Boundary Security

Security Principles:
- Zero-trust boundaries
- Deterministic permissions
- Revocable identity control
- Semantic drift detection
- Governance contract enforcement
- Registry-based integrity proofs
"""

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ============== SECURITY LAYERS ==============

class SecurityLayer(Enum):
    """Seven security layers"""
    L1_IDENTITY = "cryptographic_identity"
    L2_DATA_MEMORY = "data_memory"
    L3_SEMANTIC = "semantic_engine"
    L4_GOVERNANCE = "governance_contract"
    L5_COORDINATION = "coordination_dag"
    L6_REGISTRY = "registry_ledger"
    L7_FEDERATION = "federation_sovereign"


class ThreatCategory(Enum):
    """Categories of security threats"""
    IDENTITY_THREATS = "identity"
    DATA_THREATS = "data"
    SEMANTIC_THREATS = "semantic"
    GOVERNANCE_THREATS = "governance"
    COORDINATION_THREATS = "coordination"
    REGISTRY_THREATS = "registry"
    FEDERATION_THREATS = "federation"


class SecurityControl(Enum):
    """Types of security controls"""
    CRYPTOGRAPHIC = "cryptographic"
    ACCESS_CONTROL = "access_control"
    MONITORING = "monitoring"
    ENFORCEMENT = "enforcement"
    ISOLATION = "isolation"
    AUDIT = "audit"


# ============== LAYER DEFINITIONS ==============

@dataclass
class SecurityLayerDefinition:
    """Definition of a security layer"""
    layer: SecurityLayer
    name: str
    responsibility: str
    threats: List[str]
    protections: List[str]
    cryptographic_requirements: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer": self.layer.value,
            "name": self.name,
            "responsibility": self.responsibility,
            "threats": self.threats,
            "protections": self.protections,
            "cryptographic_requirements": self.cryptographic_requirements,
        }


@dataclass
class ThreatDefinition:
    """Definition of a security threat"""
    threat_id: str
    category: ThreatCategory
    name: str
    description: str
    severity: str  # "low", "medium", "high", "critical"
    mitigations: List[str]
    affected_layers: List[SecurityLayer]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "threat_id": self.threat_id,
            "category": self.category.value,
            "name": self.name,
            "description": self.description,
            "severity": self.severity,
            "mitigations": self.mitigations,
            "affected_layers": [l.value for l in self.affected_layers],
        }


@dataclass
class SecurityControlDefinition:
    """Definition of a security control"""
    control_id: str
    control_type: SecurityControl
    name: str
    description: str
    implementation: str
    layers_applied: List[SecurityLayer]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "control_id": self.control_id,
            "control_type": self.control_type.value,
            "name": self.name,
            "description": self.description,
            "implementation": self.implementation,
            "layers_applied": [l.value for l in self.layers_applied],
        }


# ============== SECURITY CATALOG ==============

class SecurityCatalog:
    """Catalog of security definitions"""
    
    def __init__(self):
        self._layers: Dict[str, SecurityLayerDefinition] = {}
        self._threats: Dict[str, ThreatDefinition] = {}
        self._controls: Dict[str, SecurityControlDefinition] = {}
        self._initialize()
    
    def _initialize(self):
        """Initialize security catalog"""
        self._init_layers()
        self._init_threats()
        self._init_controls()
    
    def _init_layers(self):
        """Initialize security layers"""
        
        self._add_layer(SecurityLayerDefinition(
            layer=SecurityLayer.L1_IDENTITY,
            name="Cryptographic Identity Security",
            responsibility="Identity is the root of DSID-P security",
            threats=["Spoofing", "Hijacking", "Forged delegation", "Stolen keys"],
            protections=[
                "Hardware-backed keys (optional)",
                "Identity rotation",
                "Revocation registries",
                "Tamper-proof registry records",
                "MFA for sensitive identity changes",
            ],
            cryptographic_requirements=[
                "Asymmetric public/private key pairs",
                "Multi-signature ownership transfers",
                "Revocable consent tokens",
                "Cryptographic hashes of metadata",
            ],
        ))
        
        self._add_layer(SecurityLayerDefinition(
            layer=SecurityLayer.L2_DATA_MEMORY,
            name="Data & Memory Security",
            responsibility="Memory structures must remain private, tamper-proof, and auditable",
            threats=["Unauthorized access", "Data tampering", "Memory leakage"],
            protections=[
                "CBOR encoding",
                "SHA3-256 hashing",
                "Timestamping",
                "Signing",
                "Append-only structure",
                "AES-256-GCM encryption for storage",
                "TLS 1.3 / QUIC for transit",
            ],
            cryptographic_requirements=[
                "Node hashing (SHA3-256)",
                "Node signing",
                "Encrypted payloads (AES-256-GCM)",
                "Secure transport (TLS 1.3)",
            ],
        ))
        
        self._add_layer(SecurityLayerDefinition(
            layer=SecurityLayer.L3_SEMANTIC,
            name="Semantic Engine Security",
            responsibility="Semantic vectors can be a major attack surface if unprotected",
            threats=[
                "Adversarial semantic attacks",
                "Data poisoning",
                "Embedding manipulation",
                "Unauthorized cluster switching",
            ],
            protections=[
                "Drift thresholds",
                "Semantic walls between clusters",
                "Cluster-specific risk policies",
                "Semantic audit logs",
                "Supervisor-agent verification",
            ],
            cryptographic_requirements=[
                "Semantic vector integrity verification",
                "Cluster assignment validation",
                "Drift metric signing",
            ],
        ))
        
        self._add_layer(SecurityLayerDefinition(
            layer=SecurityLayer.L4_GOVERNANCE,
            name="Governance Contract Security",
            responsibility="Governance Contracts enforce behavioral safety rules",
            threats=["Contract bypass", "Unauthorized escalation", "Policy circumvention"],
            protections=[
                "Pre-execution contract checking",
                "Protocol-level enforcement",
                "Coordination layer logging",
                "Automatic restriction on violation",
            ],
            cryptographic_requirements=[
                "Contract hash verification",
                "Action signature validation",
                "Enforcement log signing",
            ],
        ))
        
        self._add_layer(SecurityLayerDefinition(
            layer=SecurityLayer.L5_COORDINATION,
            name="Coordination DAG Integrity",
            responsibility="Workflows must be tamper-resistant and fully auditable",
            threats=["Replay attacks", "Forgeries", "History deletion", "Unauthorized execution"],
            protections=[
                "Event hashing",
                "Event signing",
                "Timestamping",
                "Parent linking",
                "Deterministic replay",
            ],
            cryptographic_requirements=[
                "Event hash chain",
                "Event signatures",
                "Causality graph integrity",
            ],
        ))
        
        self._add_layer(SecurityLayerDefinition(
            layer=SecurityLayer.L6_REGISTRY,
            name="Registry / Ledger Security",
            responsibility="The registry is the root of integrity and consensus",
            threats=["Rollback attacks", "Chain rewriting", "Tampering", "Unauthorized block insertion"],
            protections=[
                "Merkle roots",
                "Chained block hashes",
                "Multi-signature authentication",
                "Secure node environments",
                "PKI trust",
            ],
            cryptographic_requirements=[
                "Multi-signature consensus",
                "Merkle root verification",
                "Block hash chaining",
                "PKI-based node authentication",
            ],
        ))
        
        self._add_layer(SecurityLayerDefinition(
            layer=SecurityLayer.L7_FEDERATION,
            name="Federation & Sovereign Boundary Security",
            responsibility="The highest layer: nation-to-nation / tenant-to-tenant boundaries",
            threats=[
                "Semantic attacks across borders",
                "Governance circumvention",
                "Cross-sovereign escalation",
                "Data leakage",
                "Jurisdiction violations",
            ],
            protections=[
                "Federated semantic maps",
                "National governance contracts",
                "Registry-to-registry signatures",
                "Identity proof verification",
                "Semantic domain proof",
                "Governance compatibility check",
            ],
            cryptographic_requirements=[
                "Cross-registry signatures",
                "Federated identity proofs",
                "Semantic commitment verification",
            ],
        ))
    
    def _init_threats(self):
        """Initialize threat definitions"""
        
        self._add_threat(ThreatDefinition(
            threat_id="T-001",
            category=ThreatCategory.IDENTITY_THREATS,
            name="Identity Spoofing",
            description="Attacker impersonates a legitimate identity",
            severity="critical",
            mitigations=[
                "Cryptographic identity verification",
                "Signature validation",
                "Revocation registry checks",
            ],
            affected_layers=[SecurityLayer.L1_IDENTITY],
        ))
        
        self._add_threat(ThreatDefinition(
            threat_id="T-002",
            category=ThreatCategory.DATA_THREATS,
            name="DAG Tampering",
            description="Attacker modifies DAG nodes to alter history",
            severity="critical",
            mitigations=[
                "Hash verification",
                "Signature validation",
                "Append-only enforcement",
                "Multi-node replication",
            ],
            affected_layers=[SecurityLayer.L2_DATA_MEMORY],
        ))
        
        self._add_threat(ThreatDefinition(
            threat_id="T-003",
            category=ThreatCategory.SEMANTIC_THREATS,
            name="Adversarial Semantic Attack",
            description="Attacker manipulates embeddings to force agent into unsafe domain",
            severity="high",
            mitigations=[
                "Drift thresholds",
                "Semantic walls",
                "Supervisor verification",
                "Restricted mode triggering",
            ],
            affected_layers=[SecurityLayer.L3_SEMANTIC],
        ))
        
        self._add_threat(ThreatDefinition(
            threat_id="T-004",
            category=ThreatCategory.GOVERNANCE_THREATS,
            name="Governance Bypass",
            description="Agent attempts to execute actions without governance approval",
            severity="high",
            mitigations=[
                "Pre-execution contract checking",
                "Protocol-level enforcement",
                "Automatic restriction",
                "Admin alerting",
            ],
            affected_layers=[SecurityLayer.L4_GOVERNANCE],
        ))
        
        self._add_threat(ThreatDefinition(
            threat_id="T-005",
            category=ThreatCategory.COORDINATION_THREATS,
            name="Workflow Replay Attack",
            description="Attacker replays old workflow events to cause unintended actions",
            severity="medium",
            mitigations=[
                "Timestamp validation",
                "Nonce tracking",
                "Parent hash verification",
            ],
            affected_layers=[SecurityLayer.L5_COORDINATION],
        ))
        
        self._add_threat(ThreatDefinition(
            threat_id="T-006",
            category=ThreatCategory.REGISTRY_THREATS,
            name="Registry Rollback",
            description="Attacker attempts to roll back registry to previous state",
            severity="critical",
            mitigations=[
                "Multi-signature consensus",
                "Block hash chaining",
                "Distributed verification",
            ],
            affected_layers=[SecurityLayer.L6_REGISTRY],
        ))
        
        self._add_threat(ThreatDefinition(
            threat_id="T-007",
            category=ThreatCategory.FEDERATION_THREATS,
            name="Cross-Border Data Leakage",
            description="Data crosses sovereign boundaries without authorization",
            severity="critical",
            mitigations=[
                "Federation proof requirements",
                "Semantic boundary enforcement",
                "Data residency controls",
                "Only proofs/hashes cross boundaries",
            ],
            affected_layers=[SecurityLayer.L7_FEDERATION],
        ))
    
    def _init_controls(self):
        """Initialize security controls"""
        
        self._add_control(SecurityControlDefinition(
            control_id="SC-001",
            control_type=SecurityControl.CRYPTOGRAPHIC,
            name="Asymmetric Key Infrastructure",
            description="Ed25519 or secp256k1 key pairs for all identities",
            implementation="Identity layer key generation and management",
            layers_applied=[SecurityLayer.L1_IDENTITY, SecurityLayer.L6_REGISTRY],
        ))
        
        self._add_control(SecurityControlDefinition(
            control_id="SC-002",
            control_type=SecurityControl.CRYPTOGRAPHIC,
            name="SHA3-256 Hashing",
            description="All DAG nodes hashed with SHA3-256",
            implementation="Hash = SHA3-256(CBOR(node_content))",
            layers_applied=[SecurityLayer.L2_DATA_MEMORY, SecurityLayer.L5_COORDINATION],
        ))
        
        self._add_control(SecurityControlDefinition(
            control_id="SC-003",
            control_type=SecurityControl.CRYPTOGRAPHIC,
            name="AES-256-GCM Encryption",
            description="All stored data encrypted at rest",
            implementation="Encrypted blob storage with key management",
            layers_applied=[SecurityLayer.L2_DATA_MEMORY],
        ))
        
        self._add_control(SecurityControlDefinition(
            control_id="SC-004",
            control_type=SecurityControl.ACCESS_CONTROL,
            name="Zero-Trust Boundaries",
            description="No implicit trust between any components",
            implementation="All requests require authentication and authorization",
            layers_applied=[
                SecurityLayer.L1_IDENTITY, SecurityLayer.L4_GOVERNANCE,
                SecurityLayer.L7_FEDERATION,
            ],
        ))
        
        self._add_control(SecurityControlDefinition(
            control_id="SC-005",
            control_type=SecurityControl.MONITORING,
            name="Semantic Drift Detection",
            description="Continuous monitoring of agent semantic vectors",
            implementation="Drift velocity calculation with threshold alerts",
            layers_applied=[SecurityLayer.L3_SEMANTIC],
        ))
        
        self._add_control(SecurityControlDefinition(
            control_id="SC-006",
            control_type=SecurityControl.ENFORCEMENT,
            name="Governance Contract Enforcement",
            description="All actions checked against governance contracts before execution",
            implementation="Pre-execution policy evaluation engine",
            layers_applied=[SecurityLayer.L4_GOVERNANCE],
        ))
        
        self._add_control(SecurityControlDefinition(
            control_id="SC-007",
            control_type=SecurityControl.ISOLATION,
            name="Multi-Layer Data Isolation",
            description="Data isolated at user, agent, tenant, ministry, national levels",
            implementation="Partitioned storage with access controls",
            layers_applied=[SecurityLayer.L2_DATA_MEMORY, SecurityLayer.L7_FEDERATION],
        ))
        
        self._add_control(SecurityControlDefinition(
            control_id="SC-008",
            control_type=SecurityControl.AUDIT,
            name="Immutable Audit Logging",
            description="All actions logged immutably for forensic analysis",
            implementation="Append-only audit log with cryptographic verification",
            layers_applied=[
                SecurityLayer.L4_GOVERNANCE, SecurityLayer.L5_COORDINATION,
                SecurityLayer.L6_REGISTRY,
            ],
        ))
    
    def _add_layer(self, layer: SecurityLayerDefinition):
        self._layers[layer.layer.value] = layer
    
    def _add_threat(self, threat: ThreatDefinition):
        self._threats[threat.threat_id] = threat
    
    def _add_control(self, control: SecurityControlDefinition):
        self._controls[control.control_id] = control
    
    def get_layer(self, layer: str) -> Optional[SecurityLayerDefinition]:
        return self._layers.get(layer)
    
    def list_layers(self) -> List[SecurityLayerDefinition]:
        return list(self._layers.values())
    
    def get_threat(self, threat_id: str) -> Optional[ThreatDefinition]:
        return self._threats.get(threat_id)
    
    def list_threats(self, category: Optional[str] = None) -> List[ThreatDefinition]:
        threats = list(self._threats.values())
        if category:
            threats = [t for t in threats if t.category.value == category]
        return threats
    
    def get_control(self, control_id: str) -> Optional[SecurityControlDefinition]:
        return self._controls.get(control_id)
    
    def list_controls(self, control_type: Optional[str] = None) -> List[SecurityControlDefinition]:
        controls = list(self._controls.values())
        if control_type:
            controls = [c for c in controls if c.control_type.value == control_type]
        return controls


# ============== INCIDENT RESPONSE ==============

@dataclass
class IncidentResponse:
    """Incident response procedure"""
    step: int
    action: str
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "action": self.action,
            "description": self.description,
        }


INCIDENT_RESPONSE_PROCEDURE = [
    IncidentResponse(1, "Restrict agent", "Immediately restrict the affected agent's capabilities"),
    IncidentResponse(2, "Freeze workflow", "Halt any in-progress workflows involving the agent"),
    IncidentResponse(3, "Generate incident ledger entry", "Create immutable record of the incident"),
    IncidentResponse(4, "Notify administrators", "Alert relevant administrators and security team"),
    IncidentResponse(5, "Begin forensic DAG replay", "Replay coordination DAG to understand incident"),
]


# ============== HARDENING DEFAULTS ==============

HARDENING_DEFAULTS = [
    "TLS 1.3 for all communications",
    "Encrypted DAG storage (AES-256-GCM)",
    "HSM-backed identity keys (optional)",
    "Rate-limiting at gateways",
    "Role-based identity permissions",
    "Continuous semantic monitoring",
    "Multi-signature for registry commits",
    "Audit logging for all actions",
]


# ============== SUPERVISOR AGENT SECURITY ==============

SUPERVISOR_AGENT_CAPABILITIES = [
    "Drift detection",
    "Anomalous pattern detection",
    "Governance violation detection",
    "Performance anomaly detection",
    "Identity inconsistency detection",
]


# ============== GLOBAL INSTANCES ==============

security_catalog = SecurityCatalog()
