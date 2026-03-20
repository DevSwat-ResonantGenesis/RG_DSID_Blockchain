"""
HSU-Spec Section 32: Federation & Multi-Tenant Sovereignty Model
================================================================

How DSID-P enables cross-organization interoperability while ensuring
strict sovereign and tenant isolation.

Sovereignty Principles:
1. Local Control
2. No Shared Global State
3. Federated Interoperability
4. Deterministic Trust Boundaries
5. Multi-Layer Isolation

Federation Scopes:
- Scope 1: Intra-Tenant Federation
- Scope 2: Inter-Enterprise Federation
- Scope 3: Inter-Ministry Federation (Government)
- Scope 4: Inter-Nation Federation

Federation Maturity Levels:
FM-1 to FM-7 (Single-tenant to Global federation)
"""

import hashlib
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ============== FEDERATION SCOPES ==============

class FederationScope(Enum):
    """Federation scope levels"""
    SCOPE_1_INTRA_TENANT = "intra_tenant"
    SCOPE_2_INTER_ENTERPRISE = "inter_enterprise"
    SCOPE_3_INTER_MINISTRY = "inter_ministry"
    SCOPE_4_INTER_NATION = "inter_nation"


class FederationMaturityLevel(Enum):
    """Federation maturity levels"""
    FM_1 = 1  # Single-tenant isolation
    FM_2 = 2  # Intra-enterprise federation
    FM_3 = 3  # Cross-enterprise federation
    FM_4 = 4  # Inter-ministry federation
    FM_5 = 5  # National sovereign federation
    FM_6 = 6  # Multi-nation federation
    FM_7 = 7  # Global, semantic-governed federation


class IsolationLevel(Enum):
    """Isolation levels for multi-tenancy"""
    IDENTITY = "identity"
    MEMORY = "memory"
    SEMANTIC = "semantic"
    COORDINATION = "coordination"
    REGISTRY = "registry"
    NETWORK = "network"


# ============== TENANT DEFINITIONS ==============

@dataclass
class Tenant:
    """A tenant in the DSID-P system"""
    tenant_id: str
    name: str
    tenant_type: str  # "enterprise", "ministry", "nation", "organization"
    region: str
    jurisdiction: str
    isolation_levels: List[IsolationLevel]
    federation_scope: FederationScope
    maturity_level: FederationMaturityLevel
    created_at: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "tenant_type": self.tenant_type,
            "region": self.region,
            "jurisdiction": self.jurisdiction,
            "isolation_levels": [l.value for l in self.isolation_levels],
            "federation_scope": self.federation_scope.value,
            "maturity_level": self.maturity_level.value,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass
class TenantPartition:
    """A partition within a tenant (department, ministry, etc.)"""
    partition_id: str
    tenant_id: str
    name: str
    partition_type: str  # "department", "ministry", "division"
    dag_namespace: str
    semantic_namespace: str
    governance_policy_id: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "partition_id": self.partition_id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "partition_type": self.partition_type,
            "dag_namespace": self.dag_namespace,
            "semantic_namespace": self.semantic_namespace,
            "governance_policy_id": self.governance_policy_id,
        }


# ============== FEDERATION TRUST ==============

@dataclass
class FederatedIdentityCredential:
    """Credential for cross-boundary identity trust"""
    credential_id: str
    issuer_tenant_id: str
    subject_tenant_id: str
    agent_id: str
    trust_tier: str
    semantic_cluster: str
    risk_classification: str
    governance_contract_hash: str
    valid_from: int
    valid_until: int
    signature: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "credential_id": self.credential_id,
            "issuer_tenant_id": self.issuer_tenant_id,
            "subject_tenant_id": self.subject_tenant_id,
            "agent_id": self.agent_id,
            "trust_tier": self.trust_tier,
            "semantic_cluster": self.semantic_cluster,
            "risk_classification": self.risk_classification,
            "governance_contract_hash": self.governance_contract_hash,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "signature": self.signature,
        }


@dataclass
class TrustBridge:
    """Trust bridge between tenants"""
    bridge_id: str
    tenant_a_id: str
    tenant_b_id: str
    scope: FederationScope
    trust_level: str  # "full", "limited", "read_only"
    semantic_alignment_map_id: Optional[str]
    governance_intersection_id: Optional[str]
    established_at: int
    expires_at: Optional[int]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "bridge_id": self.bridge_id,
            "tenant_a_id": self.tenant_a_id,
            "tenant_b_id": self.tenant_b_id,
            "scope": self.scope.value,
            "trust_level": self.trust_level,
            "semantic_alignment_map_id": self.semantic_alignment_map_id,
            "governance_intersection_id": self.governance_intersection_id,
            "established_at": self.established_at,
            "expires_at": self.expires_at,
        }


# ============== SEMANTIC FEDERATION ==============

@dataclass
class SemanticAlignmentMap:
    """Map for semantic alignment between tenants"""
    map_id: str
    source_tenant_id: str
    target_tenant_id: str
    cluster_mappings: Dict[str, str]  # source_cluster -> target_cluster
    drift_boundary_mappings: Dict[str, float]
    risk_equivalency: Dict[str, str]  # source_risk -> target_risk
    created_at: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "map_id": self.map_id,
            "source_tenant_id": self.source_tenant_id,
            "target_tenant_id": self.target_tenant_id,
            "cluster_mappings": self.cluster_mappings,
            "drift_boundary_mappings": self.drift_boundary_mappings,
            "risk_equivalency": self.risk_equivalency,
            "created_at": self.created_at,
        }


@dataclass
class ClusterMeaningSignature:
    """Semantic signature for a cluster"""
    signature_id: str
    tenant_id: str
    cluster_code: str
    meaning_hash: str
    drift_boundary: float
    risk_level: int
    capabilities: List[str]
    restrictions: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "signature_id": self.signature_id,
            "tenant_id": self.tenant_id,
            "cluster_code": self.cluster_code,
            "meaning_hash": self.meaning_hash,
            "drift_boundary": self.drift_boundary,
            "risk_level": self.risk_level,
            "capabilities": self.capabilities,
            "restrictions": self.restrictions,
        }


# ============== FEDERATION PROOFS ==============

@dataclass
class FederationProof:
    """Proof for cross-boundary interactions"""
    proof_id: str
    interaction_id: str
    source_tenant_id: str
    target_tenant_id: str
    proof_type: str  # "identity", "semantic", "governance", "coordination"
    proof_data: Dict[str, Any]
    signature: str
    timestamp: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "interaction_id": self.interaction_id,
            "source_tenant_id": self.source_tenant_id,
            "target_tenant_id": self.target_tenant_id,
            "proof_type": self.proof_type,
            "proof_data": self.proof_data,
            "signature": self.signature,
            "timestamp": self.timestamp,
        }


@dataclass
class CrossBoundaryInteraction:
    """Record of a cross-boundary interaction"""
    interaction_id: str
    source_tenant_id: str
    target_tenant_id: str
    source_agent_id: str
    target_agent_id: Optional[str]
    interaction_type: str  # "request", "response", "delegation", "data_exchange"
    proofs: List[str]  # proof_ids
    governance_a_approved: bool
    governance_b_approved: bool
    status: str  # "pending", "approved", "rejected", "completed"
    timestamp: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "interaction_id": self.interaction_id,
            "source_tenant_id": self.source_tenant_id,
            "target_tenant_id": self.target_tenant_id,
            "source_agent_id": self.source_agent_id,
            "target_agent_id": self.target_agent_id,
            "interaction_type": self.interaction_type,
            "proofs": self.proofs,
            "governance_a_approved": self.governance_a_approved,
            "governance_b_approved": self.governance_b_approved,
            "status": self.status,
            "timestamp": self.timestamp,
        }


# ============== TENANT MANAGER ==============

class TenantManager:
    """Manage tenants and partitions"""
    
    def __init__(self):
        self._tenants: Dict[str, Tenant] = {}
        self._partitions: Dict[str, TenantPartition] = {}
    
    def create_tenant(
        self,
        name: str,
        tenant_type: str,
        region: str,
        jurisdiction: str,
        federation_scope: FederationScope = FederationScope.SCOPE_1_INTRA_TENANT,
        maturity_level: FederationMaturityLevel = FederationMaturityLevel.FM_1,
    ) -> Tenant:
        """Create a new tenant"""
        
        tenant = Tenant(
            tenant_id=str(uuid.uuid4()),
            name=name,
            tenant_type=tenant_type,
            region=region,
            jurisdiction=jurisdiction,
            isolation_levels=[
                IsolationLevel.IDENTITY,
                IsolationLevel.MEMORY,
                IsolationLevel.SEMANTIC,
                IsolationLevel.COORDINATION,
                IsolationLevel.REGISTRY,
            ],
            federation_scope=federation_scope,
            maturity_level=maturity_level,
            created_at=int(time.time() * 1000),
        )
        
        self._tenants[tenant.tenant_id] = tenant
        return tenant
    
    def create_partition(
        self,
        tenant_id: str,
        name: str,
        partition_type: str,
        governance_policy_id: str,
    ) -> Optional[TenantPartition]:
        """Create a partition within a tenant"""
        
        if tenant_id not in self._tenants:
            return None
        
        partition = TenantPartition(
            partition_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=name,
            partition_type=partition_type,
            dag_namespace=f"{tenant_id}/{name.lower().replace(' ', '_')}",
            semantic_namespace=f"semantic/{tenant_id}/{name.lower().replace(' ', '_')}",
            governance_policy_id=governance_policy_id,
        )
        
        self._partitions[partition.partition_id] = partition
        return partition
    
    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        return self._tenants.get(tenant_id)
    
    def list_tenants(self, tenant_type: Optional[str] = None) -> List[Tenant]:
        tenants = list(self._tenants.values())
        if tenant_type:
            tenants = [t for t in tenants if t.tenant_type == tenant_type]
        return tenants
    
    def get_partition(self, partition_id: str) -> Optional[TenantPartition]:
        return self._partitions.get(partition_id)
    
    def list_partitions(self, tenant_id: str) -> List[TenantPartition]:
        return [p for p in self._partitions.values() if p.tenant_id == tenant_id]


# ============== FEDERATION MANAGER ==============

class FederationManager:
    """Manage federation between tenants"""
    
    def __init__(self, tenant_manager: TenantManager):
        self.tenant_manager = tenant_manager
        self._trust_bridges: Dict[str, TrustBridge] = {}
        self._credentials: Dict[str, FederatedIdentityCredential] = {}
        self._alignment_maps: Dict[str, SemanticAlignmentMap] = {}
        self._proofs: Dict[str, FederationProof] = {}
        self._interactions: Dict[str, CrossBoundaryInteraction] = {}
    
    def establish_trust_bridge(
        self,
        tenant_a_id: str,
        tenant_b_id: str,
        scope: FederationScope,
        trust_level: str = "limited",
        expires_in_days: Optional[int] = None,
    ) -> Optional[TrustBridge]:
        """Establish a trust bridge between tenants"""
        
        tenant_a = self.tenant_manager.get_tenant(tenant_a_id)
        tenant_b = self.tenant_manager.get_tenant(tenant_b_id)
        
        if not tenant_a or not tenant_b:
            return None
        
        expires_at = None
        if expires_in_days:
            expires_at = int(time.time() * 1000) + (expires_in_days * 24 * 60 * 60 * 1000)
        
        bridge = TrustBridge(
            bridge_id=str(uuid.uuid4()),
            tenant_a_id=tenant_a_id,
            tenant_b_id=tenant_b_id,
            scope=scope,
            trust_level=trust_level,
            semantic_alignment_map_id=None,
            governance_intersection_id=None,
            established_at=int(time.time() * 1000),
            expires_at=expires_at,
        )
        
        self._trust_bridges[bridge.bridge_id] = bridge
        return bridge
    
    def issue_credential(
        self,
        issuer_tenant_id: str,
        subject_tenant_id: str,
        agent_id: str,
        trust_tier: str,
        semantic_cluster: str,
        risk_classification: str,
        governance_contract_hash: str,
        valid_days: int = 365,
    ) -> FederatedIdentityCredential:
        """Issue a federated identity credential"""
        
        now = int(time.time() * 1000)
        valid_until = now + (valid_days * 24 * 60 * 60 * 1000)
        
        # Generate signature (simplified)
        sig_data = f"{issuer_tenant_id}:{subject_tenant_id}:{agent_id}:{now}"
        signature = hashlib.sha256(sig_data.encode()).hexdigest()[:32]
        
        credential = FederatedIdentityCredential(
            credential_id=str(uuid.uuid4()),
            issuer_tenant_id=issuer_tenant_id,
            subject_tenant_id=subject_tenant_id,
            agent_id=agent_id,
            trust_tier=trust_tier,
            semantic_cluster=semantic_cluster,
            risk_classification=risk_classification,
            governance_contract_hash=governance_contract_hash,
            valid_from=now,
            valid_until=valid_until,
            signature=signature,
        )
        
        self._credentials[credential.credential_id] = credential
        return credential
    
    def create_semantic_alignment(
        self,
        source_tenant_id: str,
        target_tenant_id: str,
        cluster_mappings: Dict[str, str],
        drift_mappings: Dict[str, float],
        risk_mappings: Dict[str, str],
    ) -> SemanticAlignmentMap:
        """Create a semantic alignment map between tenants"""
        
        alignment = SemanticAlignmentMap(
            map_id=str(uuid.uuid4()),
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            cluster_mappings=cluster_mappings,
            drift_boundary_mappings=drift_mappings,
            risk_equivalency=risk_mappings,
            created_at=int(time.time() * 1000),
        )
        
        self._alignment_maps[alignment.map_id] = alignment
        return alignment
    
    def create_interaction(
        self,
        source_tenant_id: str,
        target_tenant_id: str,
        source_agent_id: str,
        interaction_type: str,
        target_agent_id: Optional[str] = None,
    ) -> CrossBoundaryInteraction:
        """Create a cross-boundary interaction"""
        
        interaction = CrossBoundaryInteraction(
            interaction_id=str(uuid.uuid4()),
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
            interaction_type=interaction_type,
            proofs=[],
            governance_a_approved=False,
            governance_b_approved=False,
            status="pending",
            timestamp=int(time.time() * 1000),
        )
        
        self._interactions[interaction.interaction_id] = interaction
        return interaction
    
    def approve_interaction(
        self,
        interaction_id: str,
        tenant_id: str,
    ) -> Optional[CrossBoundaryInteraction]:
        """Approve an interaction from a tenant's governance"""
        
        interaction = self._interactions.get(interaction_id)
        if not interaction:
            return None
        
        if tenant_id == interaction.source_tenant_id:
            interaction.governance_a_approved = True
        elif tenant_id == interaction.target_tenant_id:
            interaction.governance_b_approved = True
        
        # Both must approve
        if interaction.governance_a_approved and interaction.governance_b_approved:
            interaction.status = "approved"
        
        return interaction
    
    def generate_proof(
        self,
        interaction_id: str,
        proof_type: str,
        proof_data: Dict[str, Any],
    ) -> FederationProof:
        """Generate a federation proof"""
        
        interaction = self._interactions.get(interaction_id)
        
        sig_data = f"{interaction_id}:{proof_type}:{time.time()}"
        signature = hashlib.sha256(sig_data.encode()).hexdigest()[:32]
        
        proof = FederationProof(
            proof_id=str(uuid.uuid4()),
            interaction_id=interaction_id,
            source_tenant_id=interaction.source_tenant_id if interaction else "",
            target_tenant_id=interaction.target_tenant_id if interaction else "",
            proof_type=proof_type,
            proof_data=proof_data,
            signature=signature,
            timestamp=int(time.time() * 1000),
        )
        
        self._proofs[proof.proof_id] = proof
        
        if interaction:
            interaction.proofs.append(proof.proof_id)
        
        return proof
    
    def get_trust_bridge(self, bridge_id: str) -> Optional[TrustBridge]:
        return self._trust_bridges.get(bridge_id)
    
    def list_trust_bridges(self, tenant_id: Optional[str] = None) -> List[TrustBridge]:
        bridges = list(self._trust_bridges.values())
        if tenant_id:
            bridges = [b for b in bridges 
                      if b.tenant_a_id == tenant_id or b.tenant_b_id == tenant_id]
        return bridges
    
    def get_credential(self, credential_id: str) -> Optional[FederatedIdentityCredential]:
        return self._credentials.get(credential_id)
    
    def get_interaction(self, interaction_id: str) -> Optional[CrossBoundaryInteraction]:
        return self._interactions.get(interaction_id)
    
    def list_interactions(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[CrossBoundaryInteraction]:
        interactions = list(self._interactions.values())
        if tenant_id:
            interactions = [i for i in interactions 
                          if i.source_tenant_id == tenant_id or i.target_tenant_id == tenant_id]
        if status:
            interactions = [i for i in interactions if i.status == status]
        return interactions


# ============== SOVEREIGNTY VALIDATOR ==============

class SovereigntyValidator:
    """Validate sovereignty rules for federation"""
    
    def validate_cross_boundary_request(
        self,
        source_tenant: Tenant,
        target_tenant: Tenant,
        trust_bridge: Optional[TrustBridge],
        agent_trust_tier: str,
        semantic_cluster: str,
        risk_level: int,
    ) -> Dict[str, Any]:
        """Validate a cross-boundary request"""
        
        issues = []
        
        # Check trust bridge exists
        if not trust_bridge:
            issues.append("No trust bridge established between tenants")
        
        # Check trust bridge scope
        if trust_bridge:
            # Verify scope is appropriate
            if source_tenant.tenant_type == "nation" or target_tenant.tenant_type == "nation":
                if trust_bridge.scope != FederationScope.SCOPE_4_INTER_NATION:
                    issues.append("Inter-nation scope required for national tenants")
        
        # Check trust tier requirements
        tier_order = ["T1", "T2", "T3", "T4", "T5"]
        if agent_trust_tier in tier_order:
            tier_idx = tier_order.index(agent_trust_tier)
            if tier_idx < 2:  # Below T3
                issues.append(f"Agent trust tier {agent_trust_tier} too low for cross-boundary")
        
        # Check risk level
        if risk_level >= 4:
            issues.append("High-risk agents require additional approval for cross-boundary")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "source_tenant": source_tenant.name,
            "target_tenant": target_tenant.name,
            "trust_bridge_id": trust_bridge.bridge_id if trust_bridge else None,
        }
    
    def check_data_boundary(
        self,
        tenant: Tenant,
        data_type: str,
        target_region: str,
    ) -> Dict[str, Any]:
        """Check if data can cross boundaries"""
        
        # Data must stay in jurisdiction
        if tenant.jurisdiction != target_region:
            return {
                "allowed": False,
                "reason": f"Data must stay in jurisdiction {tenant.jurisdiction}",
            }
        
        return {
            "allowed": True,
            "reason": "Data boundary check passed",
        }


# ============== GLOBAL INSTANCES ==============

tenant_manager = TenantManager()
federation_manager = FederationManager(tenant_manager)
sovereignty_validator = SovereigntyValidator()
