"""
HSU-Spec Section 28: Semantic Cluster Taxonomy
==============================================

The complete semantic classification system for DSID-P agents.

Taxonomy Structure:
- Tier 1: Domain Clusters (11 macro-domains)
- Tier 2: Functional Clusters (within each domain)
- Tier 3: Specialist Subclusters (field-specific)

Features:
- Semantic Risk Rating (SRR) 1-5
- Semantic Drift Model
- Cluster Governance Mapping
- Marketplace Taxonomy Alignment
- Semantic Confidence Interval (SCI)
- Semantic Safety Mechanisms
"""

import hashlib
import json
import logging
import math
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


# ============== TIER 1: DOMAIN CLUSTERS ==============

class DomainCluster(Enum):
    """Tier 1 - 11 Universal Macro-Domains"""
    A_ANALYTICS = "A"      # Analytics & Reasoning
    K_KNOWLEDGE = "K"      # Knowledge & Research
    L_LANGUAGE = "L"       # Language & Communication
    C_CREATIVE = "C"       # Creative & Generative
    W_WORKFLOWS = "W"      # Automation & Workflows
    S_SOFTWARE = "S"       # Software & Engineering
    B_BUSINESS = "B"       # Business & Operations
    H_HEALTH = "H"         # Health & Medical
    P_POLICY = "P"         # Legal, Policy & Compliance
    G_GOVERNANCE = "G"     # Governance & Supervision
    M_META = "M"           # Meta-Cognitive


class SemanticRiskRating(Enum):
    """Semantic Risk Rating (SRR) - 5 levels"""
    SRR_1 = 1  # Minimal risk (summarization, semantic search)
    SRR_2 = 2  # Low risk (creative generation, basic communication)
    SRR_3 = 3  # Medium risk (workflow execution, planning)
    SRR_4 = 4  # High risk (finance, system control, engineering)
    SRR_5 = 5  # Critical risk (legal, medical, governance, planning other agents)


# ============== DOMAIN DEFINITIONS ==============

@dataclass
class DomainDefinition:
    """Definition of a Tier 1 domain cluster"""
    code: str
    name: str
    description: str
    examples: List[str]
    default_risk: SemanticRiskRating
    governance_notes: str
    marketplace_category: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "examples": self.examples,
            "default_risk": self.default_risk.value,
            "governance_notes": self.governance_notes,
            "marketplace_category": self.marketplace_category,
        }


@dataclass
class FunctionalCluster:
    """Tier 2 - Functional Cluster within a domain"""
    code: str
    domain: str
    name: str
    description: str
    risk_level: SemanticRiskRating
    mandatory_behaviors: List[str]
    forbidden_actions: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "domain": self.domain,
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "mandatory_behaviors": self.mandatory_behaviors,
            "forbidden_actions": self.forbidden_actions,
        }


@dataclass
class SpecialistSubcluster:
    """Tier 3 - Specialist Subcluster"""
    code: str
    functional_cluster: str
    name: str
    description: str
    srr: SemanticRiskRating
    allowed: bool = True
    restrictions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "functional_cluster": self.functional_cluster,
            "name": self.name,
            "description": self.description,
            "srr": self.srr.value,
            "allowed": self.allowed,
            "restrictions": self.restrictions,
        }


# ============== TAXONOMY CATALOG ==============

class SemanticTaxonomyCatalog:
    """Complete semantic taxonomy catalog"""
    
    def __init__(self):
        self._domains: Dict[str, DomainDefinition] = {}
        self._functional_clusters: Dict[str, FunctionalCluster] = {}
        self._specialist_subclusters: Dict[str, SpecialistSubcluster] = {}
        self._initialize_taxonomy()
    
    def _initialize_taxonomy(self):
        """Initialize the complete taxonomy"""
        self._init_domains()
        self._init_functional_clusters()
        self._init_specialist_subclusters()
    
    def _init_domains(self):
        """Initialize Tier 1 domain clusters"""
        
        self._add_domain(DomainDefinition(
            code="A",
            name="Analytics & Reasoning",
            description="Agents that analyze, deduce, classify, or evaluate",
            examples=["data analysis", "pattern recognition", "forecasting", "anomaly detection"],
            default_risk=SemanticRiskRating.SRR_3,
            governance_notes="Medium risk",
            marketplace_category="Analytics & Insights",
        ))
        
        self._add_domain(DomainDefinition(
            code="K",
            name="Knowledge & Research",
            description="Agents focused on retrieving, explaining, and synthesizing knowledge",
            examples=["document QA", "summarization", "tutoring", "research assistance"],
            default_risk=SemanticRiskRating.SRR_2,
            governance_notes="Low-to-medium risk",
            marketplace_category="Knowledge & Research",
        ))
        
        self._add_domain(DomainDefinition(
            code="L",
            name="Language & Communication",
            description="Agents that work with human communication",
            examples=["translators", "email writers", "support agents", "conversation processors"],
            default_risk=SemanticRiskRating.SRR_2,
            governance_notes="Low-to-medium risk",
            marketplace_category="Communication Agents",
        ))
        
        self._add_domain(DomainDefinition(
            code="C",
            name="Creative & Generative",
            description="Agents that produce novel content",
            examples=["image generation coordinators", "writing assistants", "branding agents"],
            default_risk=SemanticRiskRating.SRR_2,
            governance_notes="Low risk, semantic drift monitored",
            marketplace_category="Creative Agents",
        ))
        
        self._add_domain(DomainDefinition(
            code="W",
            name="Automation & Workflows",
            description="Agents that execute tasks, orchestrate systems, or automate workflows",
            examples=["task executors", "workflow orchestrators", "automation agents"],
            default_risk=SemanticRiskRating.SRR_3,
            governance_notes="Medium-to-high risk (execution-level actions)",
            marketplace_category="Automation Agents",
        ))
        
        self._add_domain(DomainDefinition(
            code="S",
            name="Software & Engineering",
            description="Agents involved in code, infrastructure, and system design",
            examples=["code assistants", "DevOps agents", "architecture advisors"],
            default_risk=SemanticRiskRating.SRR_4,
            governance_notes="High risk (can affect production systems)",
            marketplace_category="Developer/Technical Agents",
        ))
        
        self._add_domain(DomainDefinition(
            code="B",
            name="Business & Operations",
            description="Agents doing operational, financial, organizational tasks",
            examples=["sales analytics", "HR automation", "financial planning"],
            default_risk=SemanticRiskRating.SRR_4,
            governance_notes="High risk for regulated sectors",
            marketplace_category="Business Tools",
        ))
        
        self._add_domain(DomainDefinition(
            code="H",
            name="Health & Medical",
            description="Agents working with medical information, triage, or healthcare operations",
            examples=["symptom checkers", "medical coding", "admin workflow"],
            default_risk=SemanticRiskRating.SRR_5,
            governance_notes="Extremely high risk. Medical behavior restricted. Always requires human oversight.",
            marketplace_category="Healthcare Agents",
        ))
        
        self._add_domain(DomainDefinition(
            code="P",
            name="Legal, Policy & Compliance",
            description="Agents performing compliance checks, legal summaries, or regulatory work",
            examples=["policy summarization", "contract extraction", "regulatory mapping"],
            default_risk=SemanticRiskRating.SRR_5,
            governance_notes="Extremely high risk. Strict lineage + audit requirements.",
            marketplace_category="Legal & Compliance",
        ))
        
        self._add_domain(DomainDefinition(
            code="G",
            name="Governance & Supervision",
            description="Agents that monitor other agents",
            examples=["drift detection", "policy enforcement", "audit agents", "supervisor agents"],
            default_risk=SemanticRiskRating.SRR_5,
            governance_notes="Top-tier privileged",
            marketplace_category="Governance/Supervision",
        ))
        
        self._add_domain(DomainDefinition(
            code="M",
            name="Meta-Cognitive",
            description="Agents that plan across agents or interpret agent behavior",
            examples=["planners", "orchestrators", "cluster managers", "behavior evaluators"],
            default_risk=SemanticRiskRating.SRR_5,
            governance_notes="Extremely high risk. Requires strict contracts.",
            marketplace_category="Planners & Meta-Agents",
        ))
    
    def _init_functional_clusters(self):
        """Initialize Tier 2 functional clusters"""
        
        # A-series (Analytics)
        self._add_functional(FunctionalCluster(
            code="A1", domain="A", name="Statistical Analysis",
            description="Descriptive + inferential analysis",
            risk_level=SemanticRiskRating.SRR_2,
            mandatory_behaviors=["data validation", "uncertainty quantification"],
            forbidden_actions=["data modification", "external data sharing"],
        ))
        self._add_functional(FunctionalCluster(
            code="A2", domain="A", name="Predictive Modeling",
            description="Forecasting, trend analysis",
            risk_level=SemanticRiskRating.SRR_3,
            mandatory_behaviors=["model validation", "confidence intervals"],
            forbidden_actions=["autonomous decision execution"],
        ))
        self._add_functional(FunctionalCluster(
            code="A3", domain="A", name="Classification",
            description="Labeling, categorization",
            risk_level=SemanticRiskRating.SRR_2,
            mandatory_behaviors=["classification confidence reporting"],
            forbidden_actions=["permanent label assignment without review"],
        ))
        self._add_functional(FunctionalCluster(
            code="A4", domain="A", name="Optimization",
            description="Allocations, resource optimization",
            risk_level=SemanticRiskRating.SRR_3,
            mandatory_behaviors=["constraint validation", "solution verification"],
            forbidden_actions=["resource allocation execution"],
        ))
        self._add_functional(FunctionalCluster(
            code="A5", domain="A", name="Risk Detection",
            description="Anomaly, fraud detection",
            risk_level=SemanticRiskRating.SRR_4,
            mandatory_behaviors=["alert generation", "evidence preservation"],
            forbidden_actions=["autonomous enforcement actions"],
        ))
        
        # W-series (Workflows)
        self._add_functional(FunctionalCluster(
            code="W1", domain="W", name="Task Execution",
            description="Single task execution",
            risk_level=SemanticRiskRating.SRR_3,
            mandatory_behaviors=["task logging", "completion reporting"],
            forbidden_actions=["scope expansion"],
        ))
        self._add_functional(FunctionalCluster(
            code="W2", domain="W", name="Multi-step Automation",
            description="Sequential task automation",
            risk_level=SemanticRiskRating.SRR_3,
            mandatory_behaviors=["step validation", "rollback capability"],
            forbidden_actions=["irreversible actions without approval"],
        ))
        self._add_functional(FunctionalCluster(
            code="W3", domain="W", name="Workflow Orchestration",
            description="Complex workflow coordination",
            risk_level=SemanticRiskRating.SRR_4,
            mandatory_behaviors=["workflow state tracking", "error handling"],
            forbidden_actions=["cross-boundary orchestration"],
        ))
        self._add_functional(FunctionalCluster(
            code="W4", domain="W", name="Tool Invocation",
            description="External tool usage",
            risk_level=SemanticRiskRating.SRR_3,
            mandatory_behaviors=["tool validation", "output verification"],
            forbidden_actions=["unauthorized tool access"],
        ))
        self._add_functional(FunctionalCluster(
            code="W5", domain="W", name="System Control",
            description="System-level operations",
            risk_level=SemanticRiskRating.SRR_4,
            mandatory_behaviors=["authorization verification", "audit logging"],
            forbidden_actions=["production system modification without approval"],
        ))
        
        # S-series (Software)
        self._add_functional(FunctionalCluster(
            code="S1", domain="S", name="Code Generation",
            description="Source code creation",
            risk_level=SemanticRiskRating.SRR_3,
            mandatory_behaviors=["code review flagging", "security scanning"],
            forbidden_actions=["direct production deployment"],
        ))
        self._add_functional(FunctionalCluster(
            code="S2", domain="S", name="Code Review",
            description="Code analysis and review",
            risk_level=SemanticRiskRating.SRR_2,
            mandatory_behaviors=["issue documentation", "severity classification"],
            forbidden_actions=["automatic code modification"],
        ))
        self._add_functional(FunctionalCluster(
            code="S3", domain="S", name="Infrastructure",
            description="Infrastructure management",
            risk_level=SemanticRiskRating.SRR_4,
            mandatory_behaviors=["change documentation", "rollback planning"],
            forbidden_actions=["production changes without approval"],
        ))
        
        # G-series (Governance)
        self._add_functional(FunctionalCluster(
            code="G1", domain="G", name="Drift Detection",
            description="Semantic drift monitoring",
            risk_level=SemanticRiskRating.SRR_4,
            mandatory_behaviors=["continuous monitoring", "alert generation"],
            forbidden_actions=["self-modification"],
        ))
        self._add_functional(FunctionalCluster(
            code="G2", domain="G", name="Policy Enforcement",
            description="Governance policy enforcement",
            risk_level=SemanticRiskRating.SRR_5,
            mandatory_behaviors=["policy validation", "enforcement logging"],
            forbidden_actions=["policy modification"],
        ))
        self._add_functional(FunctionalCluster(
            code="G3", domain="G", name="Audit",
            description="System and agent auditing",
            risk_level=SemanticRiskRating.SRR_4,
            mandatory_behaviors=["comprehensive logging", "evidence preservation"],
            forbidden_actions=["audit trail modification"],
        ))
        
        # H-series (Health)
        self._add_functional(FunctionalCluster(
            code="H1", domain="H", name="Symptom Analysis",
            description="Symptom classification (non-diagnostic)",
            risk_level=SemanticRiskRating.SRR_5,
            mandatory_behaviors=["human-in-the-loop", "disclaimer generation"],
            forbidden_actions=["diagnosis", "treatment recommendation"],
        ))
        self._add_functional(FunctionalCluster(
            code="H2", domain="H", name="Medical Coding",
            description="Medical code assignment",
            risk_level=SemanticRiskRating.SRR_4,
            mandatory_behaviors=["code verification", "audit trail"],
            forbidden_actions=["billing submission"],
        ))
        self._add_functional(FunctionalCluster(
            code="H3", domain="H", name="Healthcare Admin",
            description="Administrative workflow automation",
            risk_level=SemanticRiskRating.SRR_3,
            mandatory_behaviors=["HIPAA compliance", "access logging"],
            forbidden_actions=["PHI exposure"],
        ))
        
        # P-series (Legal/Policy)
        self._add_functional(FunctionalCluster(
            code="P1", domain="P", name="Policy Summarization",
            description="Policy document summarization",
            risk_level=SemanticRiskRating.SRR_3,
            mandatory_behaviors=["source citation", "disclaimer"],
            forbidden_actions=["legal advice"],
        ))
        self._add_functional(FunctionalCluster(
            code="P2", domain="P", name="Contract Analysis",
            description="Contract structure extraction",
            risk_level=SemanticRiskRating.SRR_4,
            mandatory_behaviors=["clause identification", "risk flagging"],
            forbidden_actions=["contract modification", "legal interpretation"],
        ))
        self._add_functional(FunctionalCluster(
            code="P3", domain="P", name="Regulatory Mapping",
            description="Regulatory requirement mapping",
            risk_level=SemanticRiskRating.SRR_4,
            mandatory_behaviors=["regulation citation", "update tracking"],
            forbidden_actions=["compliance certification"],
        ))
    
    def _init_specialist_subclusters(self):
        """Initialize Tier 3 specialist subclusters"""
        
        # A-series subclusters
        self._add_specialist(SpecialistSubcluster(
            code="A1.3", functional_cluster="A1",
            name="Time-series Forecasting",
            description="Temporal pattern analysis and prediction",
            srr=SemanticRiskRating.SRR_3,
        ))
        self._add_specialist(SpecialistSubcluster(
            code="A2.1", functional_cluster="A2",
            name="Customer Segmentation",
            description="Customer grouping and analysis",
            srr=SemanticRiskRating.SRR_2,
        ))
        self._add_specialist(SpecialistSubcluster(
            code="A4.4", functional_cluster="A4",
            name="Logistics Optimization",
            description="Supply chain and logistics optimization",
            srr=SemanticRiskRating.SRR_3,
        ))
        
        # B-series subclusters
        self._add_specialist(SpecialistSubcluster(
            code="B2.1", functional_cluster="B2",
            name="Sales Analytics",
            description="Sales performance analysis",
            srr=SemanticRiskRating.SRR_3,
        ))
        self._add_specialist(SpecialistSubcluster(
            code="B3.4", functional_cluster="B3",
            name="HR Workflow Automation",
            description="Human resources process automation",
            srr=SemanticRiskRating.SRR_3,
        ))
        self._add_specialist(SpecialistSubcluster(
            code="B5.2", functional_cluster="B5",
            name="Revenue Forecasting",
            description="Financial revenue prediction",
            srr=SemanticRiskRating.SRR_4,
        ))
        
        # H-series subclusters
        self._add_specialist(SpecialistSubcluster(
            code="H1.2", functional_cluster="H1",
            name="Symptom Classification",
            description="Non-diagnostic symptom categorization",
            srr=SemanticRiskRating.SRR_5,
            restrictions=["No diagnostic output", "Human oversight required"],
        ))
        self._add_specialist(SpecialistSubcluster(
            code="H3.1", functional_cluster="H3",
            name="Medical Coding Assistant",
            description="ICD/CPT code suggestion",
            srr=SemanticRiskRating.SRR_4,
            restrictions=["Human verification required"],
        ))
        self._add_specialist(SpecialistSubcluster(
            code="H4.1", functional_cluster="H3",
            name="Healthcare Admin Workflow",
            description="Administrative task automation",
            srr=SemanticRiskRating.SRR_3,
            allowed=True,
        ))
        
        # P-series subclusters
        self._add_specialist(SpecialistSubcluster(
            code="P1.1", functional_cluster="P1",
            name="Policy Summarization",
            description="Policy document summarization",
            srr=SemanticRiskRating.SRR_3,
        ))
        self._add_specialist(SpecialistSubcluster(
            code="P2.9", functional_cluster="P2",
            name="Contract Structure Extraction",
            description="Contract clause identification",
            srr=SemanticRiskRating.SRR_4,
        ))
        self._add_specialist(SpecialistSubcluster(
            code="P4.3", functional_cluster="P3",
            name="Regulatory Mapping",
            description="Regulation-to-requirement mapping",
            srr=SemanticRiskRating.SRR_4,
        ))
    
    def _add_domain(self, domain: DomainDefinition):
        self._domains[domain.code] = domain
    
    def _add_functional(self, cluster: FunctionalCluster):
        self._functional_clusters[cluster.code] = cluster
    
    def _add_specialist(self, subcluster: SpecialistSubcluster):
        self._specialist_subclusters[subcluster.code] = subcluster
    
    def get_domain(self, code: str) -> Optional[DomainDefinition]:
        return self._domains.get(code)
    
    def get_functional_cluster(self, code: str) -> Optional[FunctionalCluster]:
        return self._functional_clusters.get(code)
    
    def get_specialist_subcluster(self, code: str) -> Optional[SpecialistSubcluster]:
        return self._specialist_subclusters.get(code)
    
    def list_domains(self) -> List[DomainDefinition]:
        return list(self._domains.values())
    
    def list_functional_clusters(self, domain: Optional[str] = None) -> List[FunctionalCluster]:
        clusters = list(self._functional_clusters.values())
        if domain:
            clusters = [c for c in clusters if c.domain == domain]
        return clusters
    
    def list_specialist_subclusters(self, functional: Optional[str] = None) -> List[SpecialistSubcluster]:
        subclusters = list(self._specialist_subclusters.values())
        if functional:
            subclusters = [s for s in subclusters if s.functional_cluster == functional]
        return subclusters
    
    def get_marketplace_categories(self) -> Dict[str, str]:
        return {d.code: d.marketplace_category for d in self._domains.values()}


# ============== SEMANTIC DRIFT MODEL ==============

@dataclass
class SemanticDriftRecord:
    """Record of semantic drift for an agent"""
    record_id: str
    agent_id: str
    previous_vector: List[float]
    current_vector: List[float]
    drift_distance: float
    drift_velocity: float
    cluster_before: str
    cluster_after: str
    timestamp: int
    triggered_action: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "agent_id": self.agent_id,
            "drift_distance": round(self.drift_distance, 6),
            "drift_velocity": round(self.drift_velocity, 6),
            "cluster_before": self.cluster_before,
            "cluster_after": self.cluster_after,
            "timestamp": self.timestamp,
            "triggered_action": self.triggered_action,
        }


class SemanticDriftMonitor:
    """Monitor semantic drift for agents"""
    
    def __init__(self, drift_threshold: float = 0.3, velocity_threshold: float = 0.1):
        self.drift_threshold = drift_threshold
        self.velocity_threshold = velocity_threshold
        self._records: Dict[str, List[SemanticDriftRecord]] = {}
        self._last_vectors: Dict[str, Tuple[List[float], int]] = {}
    
    def record_vector(
        self,
        agent_id: str,
        vector: List[float],
        cluster: str,
    ) -> Optional[SemanticDriftRecord]:
        """Record a new vector and check for drift"""
        current_time = int(time.time() * 1000)
        
        if agent_id not in self._last_vectors:
            self._last_vectors[agent_id] = (vector, current_time)
            return None
        
        prev_vector, prev_time = self._last_vectors[agent_id]
        
        # Calculate drift distance (cosine distance)
        drift_distance = self._cosine_distance(prev_vector, vector)
        
        # Calculate drift velocity
        time_delta = max(1, (current_time - prev_time) / 1000)  # seconds
        drift_velocity = drift_distance / time_delta
        
        # Determine previous cluster
        prev_cluster = self._get_agent_cluster(agent_id) or cluster
        
        # Check if drift exceeds threshold
        triggered_action = None
        if drift_distance > self.drift_threshold:
            triggered_action = "cluster_reassignment_triggered"
        elif drift_velocity > self.velocity_threshold:
            triggered_action = "drift_velocity_warning"
        
        record = SemanticDriftRecord(
            record_id=str(uuid.uuid4()),
            agent_id=agent_id,
            previous_vector=prev_vector,
            current_vector=vector,
            drift_distance=drift_distance,
            drift_velocity=drift_velocity,
            cluster_before=prev_cluster,
            cluster_after=cluster,
            timestamp=current_time,
            triggered_action=triggered_action,
        )
        
        if agent_id not in self._records:
            self._records[agent_id] = []
        self._records[agent_id].append(record)
        
        self._last_vectors[agent_id] = (vector, current_time)
        
        return record
    
    def _cosine_distance(self, v1: List[float], v2: List[float]) -> float:
        """Calculate cosine distance between two vectors"""
        if len(v1) != len(v2):
            return 1.0
        
        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        
        if norm1 == 0 or norm2 == 0:
            return 1.0
        
        similarity = dot_product / (norm1 * norm2)
        return 1.0 - similarity
    
    def _get_agent_cluster(self, agent_id: str) -> Optional[str]:
        """Get agent's current cluster from records"""
        if agent_id in self._records and self._records[agent_id]:
            return self._records[agent_id][-1].cluster_after
        return None
    
    def get_drift_history(self, agent_id: str) -> List[SemanticDriftRecord]:
        """Get drift history for an agent"""
        return self._records.get(agent_id, [])
    
    def get_drift_stats(self, agent_id: str) -> Dict[str, Any]:
        """Get drift statistics for an agent"""
        records = self._records.get(agent_id, [])
        if not records:
            return {"agent_id": agent_id, "record_count": 0}
        
        distances = [r.drift_distance for r in records]
        velocities = [r.drift_velocity for r in records]
        
        return {
            "agent_id": agent_id,
            "record_count": len(records),
            "avg_drift_distance": sum(distances) / len(distances),
            "max_drift_distance": max(distances),
            "avg_drift_velocity": sum(velocities) / len(velocities),
            "max_drift_velocity": max(velocities),
            "warnings_triggered": sum(1 for r in records if r.triggered_action),
        }


# ============== SEMANTIC CONFIDENCE INTERVAL ==============

@dataclass
class SemanticConfidenceScore:
    """Semantic Confidence Interval (SCI) for an agent"""
    agent_id: str
    primary_cluster: str
    confidence: float  # 0-1
    secondary_clusters: List[Tuple[str, float]]
    stability_score: float
    calculated_at: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "primary_cluster": self.primary_cluster,
            "confidence": round(self.confidence, 4),
            "secondary_clusters": [
                {"cluster": c, "confidence": round(conf, 4)}
                for c, conf in self.secondary_clusters
            ],
            "stability_score": round(self.stability_score, 4),
            "calculated_at": self.calculated_at,
        }


class SemanticConfidenceCalculator:
    """Calculate Semantic Confidence Interval (SCI)"""
    
    def __init__(self, reassignment_threshold: float = 0.4):
        self.reassignment_threshold = reassignment_threshold
        self._scores: Dict[str, SemanticConfidenceScore] = {}
    
    def calculate_confidence(
        self,
        agent_id: str,
        vector: List[float],
        cluster_centroids: Dict[str, List[float]],
    ) -> SemanticConfidenceScore:
        """Calculate SCI for an agent"""
        
        # Calculate distance to each cluster centroid
        distances = {}
        for cluster, centroid in cluster_centroids.items():
            dist = self._euclidean_distance(vector, centroid)
            distances[cluster] = dist
        
        # Convert distances to confidence scores (inverse)
        total_inv_dist = sum(1 / (d + 0.001) for d in distances.values())
        confidences = {
            c: (1 / (d + 0.001)) / total_inv_dist
            for c, d in distances.items()
        }
        
        # Sort by confidence
        sorted_clusters = sorted(confidences.items(), key=lambda x: x[1], reverse=True)
        
        primary_cluster = sorted_clusters[0][0]
        primary_confidence = sorted_clusters[0][1]
        secondary_clusters = sorted_clusters[1:4]  # Top 3 secondary
        
        # Calculate stability (how much higher primary is than secondary)
        stability = primary_confidence - (secondary_clusters[0][1] if secondary_clusters else 0)
        
        score = SemanticConfidenceScore(
            agent_id=agent_id,
            primary_cluster=primary_cluster,
            confidence=primary_confidence,
            secondary_clusters=secondary_clusters,
            stability_score=stability,
            calculated_at=int(time.time() * 1000),
        )
        
        self._scores[agent_id] = score
        return score
    
    def _euclidean_distance(self, v1: List[float], v2: List[float]) -> float:
        """Calculate Euclidean distance"""
        if len(v1) != len(v2):
            return float('inf')
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))
    
    def get_score(self, agent_id: str) -> Optional[SemanticConfidenceScore]:
        return self._scores.get(agent_id)
    
    def needs_reassignment(self, agent_id: str) -> bool:
        """Check if agent needs cluster reassignment"""
        score = self._scores.get(agent_id)
        if not score:
            return False
        return score.confidence < self.reassignment_threshold


# ============== CLUSTER GOVERNANCE MAPPING ==============

@dataclass
class ClusterGovernanceRules:
    """Governance rules for a cluster"""
    cluster_code: str
    human_in_loop_required: bool
    max_drift_threshold: float
    allowed_actions: List[str]
    forbidden_actions: List[str]
    retention_rules: Dict[str, Any]
    supervision_level: str  # "none", "light", "moderate", "strict"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_code": self.cluster_code,
            "human_in_loop_required": self.human_in_loop_required,
            "max_drift_threshold": self.max_drift_threshold,
            "allowed_actions": self.allowed_actions,
            "forbidden_actions": self.forbidden_actions,
            "retention_rules": self.retention_rules,
            "supervision_level": self.supervision_level,
        }


class ClusterGovernanceManager:
    """Manage cluster-specific governance rules"""
    
    def __init__(self):
        self._rules: Dict[str, ClusterGovernanceRules] = {}
        self._initialize_rules()
    
    def _initialize_rules(self):
        """Initialize governance rules for each domain"""
        
        # H-series (Healthcare) - Strict
        self._add_rules(ClusterGovernanceRules(
            cluster_code="H",
            human_in_loop_required=True,
            max_drift_threshold=0.15,
            allowed_actions=["information_retrieval", "summarization", "admin_workflow"],
            forbidden_actions=["diagnosis", "prescription", "treatment_recommendation"],
            retention_rules={"min_retention_days": 2555, "audit_required": True},
            supervision_level="strict",
        ))
        
        # S-series (Software) - High
        self._add_rules(ClusterGovernanceRules(
            cluster_code="S",
            human_in_loop_required=False,
            max_drift_threshold=0.25,
            allowed_actions=["code_generation", "code_review", "documentation"],
            forbidden_actions=["production_deployment", "system_modification_without_approval"],
            retention_rules={"min_retention_days": 365, "audit_required": True},
            supervision_level="moderate",
        ))
        
        # G-series (Governance) - Top-tier
        self._add_rules(ClusterGovernanceRules(
            cluster_code="G",
            human_in_loop_required=False,
            max_drift_threshold=0.1,
            allowed_actions=["read_agent_memory", "policy_enforcement", "anomaly_reporting"],
            forbidden_actions=["self_modification", "governance_contract_modification"],
            retention_rules={"min_retention_days": 3650, "audit_required": True},
            supervision_level="strict",
        ))
        
        # C-series (Creative) - Minimal
        self._add_rules(ClusterGovernanceRules(
            cluster_code="C",
            human_in_loop_required=False,
            max_drift_threshold=0.5,
            allowed_actions=["content_generation", "creative_assistance", "brainstorming"],
            forbidden_actions=["harmful_content", "impersonation"],
            retention_rules={"min_retention_days": 90, "audit_required": False},
            supervision_level="light",
        ))
        
        # P-series (Legal/Policy) - Strict
        self._add_rules(ClusterGovernanceRules(
            cluster_code="P",
            human_in_loop_required=True,
            max_drift_threshold=0.15,
            allowed_actions=["summarization", "extraction", "mapping"],
            forbidden_actions=["legal_advice", "compliance_certification"],
            retention_rules={"min_retention_days": 2555, "audit_required": True},
            supervision_level="strict",
        ))
        
        # Default for other clusters
        for code in ["A", "K", "L", "W", "B", "M"]:
            if code not in self._rules:
                self._add_rules(ClusterGovernanceRules(
                    cluster_code=code,
                    human_in_loop_required=False,
                    max_drift_threshold=0.3,
                    allowed_actions=["general_operations"],
                    forbidden_actions=["unauthorized_access"],
                    retention_rules={"min_retention_days": 180, "audit_required": False},
                    supervision_level="moderate",
                ))
    
    def _add_rules(self, rules: ClusterGovernanceRules):
        self._rules[rules.cluster_code] = rules
    
    def get_rules(self, cluster_code: str) -> Optional[ClusterGovernanceRules]:
        # Get domain code (first character)
        domain = cluster_code[0] if cluster_code else None
        return self._rules.get(domain)
    
    def list_rules(self) -> List[ClusterGovernanceRules]:
        return list(self._rules.values())
    
    def check_action_allowed(self, cluster_code: str, action: str) -> Dict[str, Any]:
        """Check if an action is allowed for a cluster"""
        rules = self.get_rules(cluster_code)
        if not rules:
            return {"allowed": True, "reason": "No rules defined"}
        
        if action in rules.forbidden_actions:
            return {"allowed": False, "reason": f"Action '{action}' is forbidden for cluster {cluster_code}"}
        
        if rules.allowed_actions and action not in rules.allowed_actions:
            return {"allowed": False, "reason": f"Action '{action}' not in allowed list for cluster {cluster_code}"}
        
        return {"allowed": True, "reason": "Action permitted"}


# ============== GLOBAL INSTANCES ==============

taxonomy_catalog = SemanticTaxonomyCatalog()
drift_monitor = SemanticDriftMonitor()
confidence_calculator = SemanticConfidenceCalculator()
governance_manager = ClusterGovernanceManager()
