"""
HSU-Spec Section 23: DSID-P Interoperability Layer (IOL)
=========================================================

How DSID-P integrates with external systems, models, agents, platforms.

Subsystems:
1. Identity Bridge Layer
2. Semantic Translation Layer
3. Memory Gateway Layer
4. Coordination Adapter Layer
5. External Agent Adapter Layer
6. External Model Adapter Layer
7. Registry Compatibility Layer
8. Transport Adapters

Philosophy:
- DSID-P never loses control of identity or memory
- External systems operate at edges, not core
- Interoperability is deterministic and traceable
- DSID-P is source of truth for agent state
- Semantic alignment ensures consistent meaning
"""

import hashlib
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# ============== EXTERNAL IDENTITY TYPES ==============

class ExternalIdentityType(Enum):
    """Supported external identity types"""
    OAUTH = "oauth"
    JWT = "jwt"
    OKTA = "okta"
    AZURE_AD = "azure_ad"
    GOVERNMENT_ID = "government_id"
    AGENT_RUNTIME_ID = "agent_runtime_id"
    API_KEY = "api_key"
    CLIENT_ID = "client_id"
    CUSTOM = "custom"


class ExternalModelType(Enum):
    """Supported external AI models"""
    OPENAI_GPT = "openai_gpt"
    ANTHROPIC_CLAUDE = "anthropic_claude"
    GOOGLE_GEMINI = "google_gemini"
    META_LLAMA = "meta_llama"
    MISTRAL = "mistral"
    LOCAL_MODEL = "local_model"
    ENTERPRISE_MODEL = "enterprise_model"
    GOVERNMENT_LLM = "government_llm"


class ExternalAgentType(Enum):
    """Supported external agent frameworks"""
    LANGCHAIN = "langchain"
    AUTOGEN = "autogen"
    CREWAI = "crewai"
    CUSTOM_BOT = "custom_bot"
    RPA_BOT = "rpa_bot"
    RULE_BASED = "rule_based"


class ExternalRegistryType(Enum):
    """Supported external registries/blockchains"""
    ETHEREUM = "ethereum"
    HYPERLEDGER = "hyperledger"
    CORDA = "corda"
    FILECOIN = "filecoin"
    GOVERNMENT_PKI = "government_pki"
    ENTERPRISE_AUDIT = "enterprise_audit"


class TransportType(Enum):
    """Supported transport protocols"""
    REST = "rest"
    WEBSOCKET = "websocket"
    GRPC = "grpc"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    IBM_MQ = "ibm_mq"
    HTTPS_MUTUAL_AUTH = "https_mutual_auth"


# ============== 23.3 IDENTITY BRIDGE LAYER ==============

@dataclass
class ExternalIdentity:
    """External identity mapping"""
    external_id: str
    external_type: ExternalIdentityType
    provider: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: int = field(default_factory=lambda: int(time.time()))


@dataclass
class IdentityMapping:
    """Mapping between external and DSID-P identities"""
    mapping_id: str
    dsidp_identity: str
    external_identities: List[ExternalIdentity]
    primary_external: Optional[str] = None
    provenance_anchored: bool = False
    created_at: int = field(default_factory=lambda: int(time.time()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "dsidp_identity": self.dsidp_identity,
            "external_identities": [
                {
                    "external_id": e.external_id,
                    "external_type": e.external_type.value,
                    "provider": e.provider,
                    "metadata": e.metadata,
                }
                for e in self.external_identities
            ],
            "primary_external": self.primary_external,
            "provenance_anchored": self.provenance_anchored,
            "created_at": self.created_at,
        }


class IdentityBridge:
    """
    Section 23.3: Identity Bridge Layer
    
    Maps external identities to DSID-P identities.
    """
    
    def __init__(self):
        self._mappings: Dict[str, IdentityMapping] = {}
        self._external_to_dsidp: Dict[str, str] = {}  # external_id -> dsidp_identity
    
    def create_dsidp_identity_from_external(
        self,
        external_id: str,
        external_type: ExternalIdentityType,
        provider: str,
        metadata: Dict[str, Any] = None,
    ) -> IdentityMapping:
        """Create DSID-P identity from external identity"""
        # Generate DSID-P identity hash
        identity_data = f"{external_type.value}:{provider}:{external_id}"
        dsidp_identity = hashlib.sha256(identity_data.encode()).hexdigest()
        
        external = ExternalIdentity(
            external_id=external_id,
            external_type=external_type,
            provider=provider,
            metadata=metadata or {},
        )
        
        mapping = IdentityMapping(
            mapping_id=str(uuid.uuid4()),
            dsidp_identity=dsidp_identity,
            external_identities=[external],
            primary_external=external_id,
        )
        
        self._mappings[mapping.mapping_id] = mapping
        self._external_to_dsidp[external_id] = dsidp_identity
        
        return mapping
    
    def link_external_identity(
        self,
        dsidp_identity: str,
        external_id: str,
        external_type: ExternalIdentityType,
        provider: str,
    ) -> bool:
        """Link additional external identity to existing DSID-P identity"""
        # Find existing mapping
        for mapping in self._mappings.values():
            if mapping.dsidp_identity == dsidp_identity:
                external = ExternalIdentity(
                    external_id=external_id,
                    external_type=external_type,
                    provider=provider,
                )
                mapping.external_identities.append(external)
                self._external_to_dsidp[external_id] = dsidp_identity
                return True
        return False
    
    def resolve_identity(self, external_id: str) -> Optional[str]:
        """Resolve external ID to DSID-P identity"""
        return self._external_to_dsidp.get(external_id)
    
    def get_mapping(self, dsidp_identity: str) -> Optional[IdentityMapping]:
        """Get identity mapping by DSID-P identity"""
        for mapping in self._mappings.values():
            if mapping.dsidp_identity == dsidp_identity:
                return mapping
        return None
    
    def anchor_provenance(self, mapping_id: str) -> bool:
        """Anchor identity provenance in L1/L5"""
        if mapping_id in self._mappings:
            self._mappings[mapping_id].provenance_anchored = True
            return True
        return False


# ============== 23.4 SEMANTIC TRANSLATION LAYER ==============

@dataclass
class EmbeddingTranslation:
    """Translation of external embedding to DSID-P space"""
    source_model: ExternalModelType
    source_vector: List[float]
    translated_vector: List[float]
    cluster_assignment: Optional[str] = None
    drift_score: float = 0.0
    timestamp: int = field(default_factory=lambda: int(time.time()))


class SemanticTranslator:
    """
    Section 23.4: Semantic Translation Layer
    
    Aligns different embedding spaces into DSID-P's cluster system.
    """
    
    def __init__(self, target_dimension: int = 384):
        self.target_dimension = target_dimension
        self._translations: List[EmbeddingTranslation] = []
        self._model_mappings: Dict[ExternalModelType, Dict[str, Any]] = {}
    
    def register_model_mapping(
        self,
        model_type: ExternalModelType,
        source_dimension: int,
        transformation_matrix: Optional[List[List[float]]] = None,
    ) -> None:
        """Register a model's embedding mapping"""
        self._model_mappings[model_type] = {
            "source_dimension": source_dimension,
            "transformation_matrix": transformation_matrix,
        }
    
    def translate_embedding(
        self,
        source_vector: List[float],
        source_model: ExternalModelType,
    ) -> EmbeddingTranslation:
        """Translate external embedding to DSID-P space"""
        # Normalize and resize to target dimension
        if len(source_vector) > self.target_dimension:
            # Truncate
            translated = source_vector[:self.target_dimension]
        elif len(source_vector) < self.target_dimension:
            # Pad with zeros
            translated = source_vector + [0.0] * (self.target_dimension - len(source_vector))
        else:
            translated = source_vector.copy()
        
        # Normalize
        magnitude = sum(v ** 2 for v in translated) ** 0.5
        if magnitude > 0:
            translated = [v / magnitude for v in translated]
        
        translation = EmbeddingTranslation(
            source_model=source_model,
            source_vector=source_vector,
            translated_vector=translated,
        )
        
        self._translations.append(translation)
        return translation
    
    def detect_drift(
        self,
        vector1: List[float],
        vector2: List[float],
    ) -> float:
        """Detect semantic drift between vectors"""
        if len(vector1) != len(vector2):
            return 1.0  # Maximum drift
        
        # Cosine similarity
        dot_product = sum(a * b for a, b in zip(vector1, vector2))
        mag1 = sum(v ** 2 for v in vector1) ** 0.5
        mag2 = sum(v ** 2 for v in vector2) ** 0.5
        
        if mag1 == 0 or mag2 == 0:
            return 1.0
        
        similarity = dot_product / (mag1 * mag2)
        drift = 1.0 - similarity
        return max(0.0, min(1.0, drift))
    
    def align_cross_model(
        self,
        vectors: List[Tuple[List[float], ExternalModelType]],
    ) -> List[List[float]]:
        """Align vectors from different models into common space"""
        aligned = []
        for vector, model in vectors:
            translation = self.translate_embedding(vector, model)
            aligned.append(translation.translated_vector)
        return aligned


# ============== 23.5 MEMORY GATEWAY LAYER ==============

class MemoryOperation(Enum):
    """Memory operations supported through gateway"""
    PROPOSE_MEMORY = "propose_memory"
    READ_MEMORY = "read_memory"
    APPEND_EVENT = "append_event"


@dataclass
class MemoryProposal:
    """Proposed memory update from external system"""
    proposal_id: str
    agent_id: str
    operation: MemoryOperation
    content: Dict[str, Any]
    source_system: str
    requires_approval: bool = True
    approved: bool = False
    dag_node_id: Optional[str] = None
    lineage_entry: Optional[str] = None
    timestamp: int = field(default_factory=lambda: int(time.time()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "agent_id": self.agent_id,
            "operation": self.operation.value,
            "content": self.content,
            "source_system": self.source_system,
            "requires_approval": self.requires_approval,
            "approved": self.approved,
            "dag_node_id": self.dag_node_id,
            "lineage_entry": self.lineage_entry,
            "timestamp": self.timestamp,
        }


class MemoryGateway:
    """
    Section 23.5: Memory Gateway Layer
    
    Allows external tools to read/write memory without breaking DAG structure.
    
    Rules:
    1. External systems cannot directly mutate DAG structures
    2. All changes routed through gateway
    3. Every update produces: DAG node, semantic recalculation, lineage entry
    """
    
    def __init__(self):
        self._proposals: Dict[str, MemoryProposal] = {}
        self._permissions: Dict[str, List[str]] = {}  # agent_id -> allowed_systems
    
    def grant_permission(self, agent_id: str, system_id: str) -> None:
        """Grant a system permission to access agent memory"""
        if agent_id not in self._permissions:
            self._permissions[agent_id] = []
        if system_id not in self._permissions[agent_id]:
            self._permissions[agent_id].append(system_id)
    
    def check_permission(self, agent_id: str, system_id: str) -> bool:
        """Check if system has permission"""
        return system_id in self._permissions.get(agent_id, [])
    
    def propose_memory(
        self,
        agent_id: str,
        content: Dict[str, Any],
        source_system: str,
        requires_approval: bool = True,
    ) -> MemoryProposal:
        """Propose a memory update (requires governance approval)"""
        proposal = MemoryProposal(
            proposal_id=str(uuid.uuid4()),
            agent_id=agent_id,
            operation=MemoryOperation.PROPOSE_MEMORY,
            content=content,
            source_system=source_system,
            requires_approval=requires_approval,
        )
        
        self._proposals[proposal.proposal_id] = proposal
        return proposal
    
    def approve_proposal(self, proposal_id: str) -> bool:
        """Approve a memory proposal"""
        if proposal_id in self._proposals:
            proposal = self._proposals[proposal_id]
            proposal.approved = True
            
            # Create DAG node
            node_data = json.dumps(proposal.content, sort_keys=True).encode()
            proposal.dag_node_id = hashlib.sha256(node_data).hexdigest()
            
            # Create lineage entry
            proposal.lineage_entry = hashlib.sha256(
                f"{proposal.agent_id}:{proposal.dag_node_id}:{proposal.timestamp}".encode()
            ).hexdigest()
            
            return True
        return False
    
    def read_memory(
        self,
        agent_id: str,
        node_id: str,
        system_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Read memory node (permissioned)"""
        if not self.check_permission(agent_id, system_id):
            return None
        
        # Would integrate with actual DAG storage
        return {"node_id": node_id, "agent_id": agent_id, "access_granted": True}
    
    def get_pending_proposals(self, agent_id: Optional[str] = None) -> List[MemoryProposal]:
        """Get pending memory proposals"""
        proposals = list(self._proposals.values())
        if agent_id:
            proposals = [p for p in proposals if p.agent_id == agent_id]
        return [p for p in proposals if not p.approved and p.requires_approval]


# ============== 23.6 COORDINATION ADAPTER LAYER ==============

@dataclass
class WorkflowTranslation:
    """Translation of external workflow to DSID-P coordination DAG"""
    translation_id: str
    source_format: str  # bpmn, autogen, crewai, etc.
    source_workflow: Dict[str, Any]
    dsidp_events: List[Dict[str, Any]]
    actor_mappings: Dict[str, str]  # external_actor -> dsidp_identity
    timestamp: int = field(default_factory=lambda: int(time.time()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "translation_id": self.translation_id,
            "source_format": self.source_format,
            "event_count": len(self.dsidp_events),
            "actor_count": len(self.actor_mappings),
            "timestamp": self.timestamp,
        }


class CoordinationAdapter:
    """
    Section 23.6: Coordination Adapter Layer
    
    Translates external workflow formats into DSID-P's coordination DAG.
    """
    
    def __init__(self):
        self._translations: Dict[str, WorkflowTranslation] = {}
    
    def translate_workflow(
        self,
        source_format: str,
        workflow: Dict[str, Any],
        actor_mappings: Dict[str, str],
    ) -> WorkflowTranslation:
        """Translate external workflow to DSID-P coordination events"""
        dsidp_events = []
        
        # Extract tasks/steps from workflow
        tasks = workflow.get("tasks", workflow.get("steps", []))
        
        for i, task in enumerate(tasks):
            event = {
                "event_id": str(uuid.uuid4()),
                "type": "workflow_step",
                "sequence": i,
                "actor": actor_mappings.get(task.get("actor", "unknown"), "unknown"),
                "action": task.get("action", task.get("name", "unknown")),
                "inputs": task.get("inputs", {}),
                "outputs": task.get("outputs", {}),
                "timestamp": int(time.time() * 1000),
            }
            dsidp_events.append(event)
        
        translation = WorkflowTranslation(
            translation_id=str(uuid.uuid4()),
            source_format=source_format,
            source_workflow=workflow,
            dsidp_events=dsidp_events,
            actor_mappings=actor_mappings,
        )
        
        self._translations[translation.translation_id] = translation
        return translation
    
    def translate_bpmn(self, bpmn_workflow: Dict[str, Any]) -> WorkflowTranslation:
        """Translate BPMN workflow"""
        return self.translate_workflow("bpmn", bpmn_workflow, {})
    
    def translate_autogen(self, autogen_workflow: Dict[str, Any]) -> WorkflowTranslation:
        """Translate Autogen workflow"""
        return self.translate_workflow("autogen", autogen_workflow, {})
    
    def translate_crewai(self, crewai_workflow: Dict[str, Any]) -> WorkflowTranslation:
        """Translate CrewAI workflow"""
        return self.translate_workflow("crewai", crewai_workflow, {})


# ============== 23.7 EXTERNAL AGENT ADAPTER ==============

@dataclass
class ImportedAgent:
    """External agent imported into DSID-P"""
    import_id: str
    external_type: ExternalAgentType
    external_agent_id: str
    dsidp_identity: str
    dsidp_sphere_root: Optional[str] = None
    cluster_id: Optional[str] = None
    governance_contract: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    active: bool = True
    imported_at: int = field(default_factory=lambda: int(time.time()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "import_id": self.import_id,
            "external_type": self.external_type.value,
            "external_agent_id": self.external_agent_id,
            "dsidp_identity": self.dsidp_identity,
            "dsidp_sphere_root": self.dsidp_sphere_root,
            "cluster_id": self.cluster_id,
            "governance_contract": self.governance_contract,
            "capabilities": self.capabilities,
            "active": self.active,
            "imported_at": self.imported_at,
        }


class ExternalAgentAdapter:
    """
    Section 23.7: External Agent Adapter Layer
    
    Imports agents from other ecosystems into DSID-P.
    """
    
    def __init__(self):
        self._imported_agents: Dict[str, ImportedAgent] = {}
    
    def import_agent(
        self,
        external_type: ExternalAgentType,
        external_agent_id: str,
        capabilities: List[str] = None,
        initial_cluster: Optional[str] = None,
    ) -> ImportedAgent:
        """Import external agent into DSID-P"""
        # Generate DSID-P identity
        identity_data = f"{external_type.value}:{external_agent_id}"
        dsidp_identity = hashlib.sha256(identity_data.encode()).hexdigest()
        
        # Create empty sphere root
        sphere_root = hashlib.sha256(f"sphere:{dsidp_identity}".encode()).hexdigest()
        
        imported = ImportedAgent(
            import_id=str(uuid.uuid4()),
            external_type=external_type,
            external_agent_id=external_agent_id,
            dsidp_identity=dsidp_identity,
            dsidp_sphere_root=sphere_root,
            cluster_id=initial_cluster,
            capabilities=capabilities or [],
        )
        
        self._imported_agents[imported.import_id] = imported
        return imported
    
    def attach_governance(self, import_id: str, contract_id: str) -> bool:
        """Attach governance contract to imported agent"""
        if import_id in self._imported_agents:
            self._imported_agents[import_id].governance_contract = contract_id
            return True
        return False
    
    def assign_cluster(self, import_id: str, cluster_id: str) -> bool:
        """Assign imported agent to semantic cluster"""
        if import_id in self._imported_agents:
            self._imported_agents[import_id].cluster_id = cluster_id
            return True
        return False
    
    def get_imported_agent(self, import_id: str) -> Optional[ImportedAgent]:
        """Get imported agent by ID"""
        return self._imported_agents.get(import_id)
    
    def list_imported_agents(self, external_type: Optional[ExternalAgentType] = None) -> List[ImportedAgent]:
        """List imported agents"""
        agents = list(self._imported_agents.values())
        if external_type:
            agents = [a for a in agents if a.external_type == external_type]
        return agents


# ============== 23.8 EXTERNAL MODEL ADAPTER ==============

@dataclass
class ModelConnection:
    """Connection to external AI model"""
    connection_id: str
    model_type: ExternalModelType
    model_name: str
    endpoint: Optional[str] = None
    api_key_configured: bool = False
    capabilities: List[str] = field(default_factory=list)
    active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "model_type": self.model_type.value,
            "model_name": self.model_name,
            "endpoint": self.endpoint,
            "api_key_configured": self.api_key_configured,
            "capabilities": self.capabilities,
            "active": self.active,
        }


class ExternalModelAdapter:
    """
    Section 23.8: External Model Adapter Layer
    
    Allows any LLM to serve as agent reasoning engine.
    
    Key Rule: Models produce output; DSID-P governs structure and identity.
    """
    
    def __init__(self):
        self._connections: Dict[str, ModelConnection] = {}
    
    def register_model(
        self,
        model_type: ExternalModelType,
        model_name: str,
        endpoint: Optional[str] = None,
        capabilities: List[str] = None,
    ) -> ModelConnection:
        """Register an external model"""
        connection = ModelConnection(
            connection_id=str(uuid.uuid4()),
            model_type=model_type,
            model_name=model_name,
            endpoint=endpoint,
            capabilities=capabilities or ["reasoning", "generation"],
        )
        
        self._connections[connection.connection_id] = connection
        return connection
    
    def configure_api_key(self, connection_id: str) -> bool:
        """Mark API key as configured (actual key stored securely elsewhere)"""
        if connection_id in self._connections:
            self._connections[connection_id].api_key_configured = True
            return True
        return False
    
    def get_model(self, connection_id: str) -> Optional[ModelConnection]:
        """Get model connection"""
        return self._connections.get(connection_id)
    
    def list_models(self, model_type: Optional[ExternalModelType] = None) -> List[ModelConnection]:
        """List registered models"""
        models = list(self._connections.values())
        if model_type:
            models = [m for m in models if m.model_type == model_type]
        return models


# ============== 23.9 REGISTRY COMPATIBILITY LAYER ==============

@dataclass
class ExternalAnchor:
    """Anchor to external registry/blockchain"""
    anchor_id: str
    registry_type: ExternalRegistryType
    dsidp_block_id: str
    external_tx_id: Optional[str] = None
    external_block_id: Optional[str] = None
    anchored: bool = False
    timestamp: int = field(default_factory=lambda: int(time.time()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "anchor_id": self.anchor_id,
            "registry_type": self.registry_type.value,
            "dsidp_block_id": self.dsidp_block_id,
            "external_tx_id": self.external_tx_id,
            "external_block_id": self.external_block_id,
            "anchored": self.anchored,
            "timestamp": self.timestamp,
        }


class RegistryBridge:
    """
    Section 23.9: Registry Compatibility Layer
    
    Interoperability with other registries, blockchains, ledgers.
    """
    
    def __init__(self):
        self._anchors: Dict[str, ExternalAnchor] = {}
        self._external_proofs: Dict[str, Dict[str, Any]] = {}
    
    def anchor_to_external(
        self,
        dsidp_block_id: str,
        registry_type: ExternalRegistryType,
    ) -> ExternalAnchor:
        """Anchor DSID-P block to external registry"""
        anchor = ExternalAnchor(
            anchor_id=str(uuid.uuid4()),
            registry_type=registry_type,
            dsidp_block_id=dsidp_block_id,
        )
        
        self._anchors[anchor.anchor_id] = anchor
        return anchor
    
    def confirm_anchor(
        self,
        anchor_id: str,
        external_tx_id: str,
        external_block_id: Optional[str] = None,
    ) -> bool:
        """Confirm external anchor with transaction ID"""
        if anchor_id in self._anchors:
            anchor = self._anchors[anchor_id]
            anchor.external_tx_id = external_tx_id
            anchor.external_block_id = external_block_id
            anchor.anchored = True
            return True
        return False
    
    def import_external_proof(
        self,
        registry_type: ExternalRegistryType,
        external_proof: Dict[str, Any],
    ) -> str:
        """Import external proof into DSID-P"""
        proof_id = str(uuid.uuid4())
        self._external_proofs[proof_id] = {
            "registry_type": registry_type.value,
            "proof": external_proof,
            "imported_at": int(time.time()),
        }
        return proof_id
    
    def get_anchor(self, anchor_id: str) -> Optional[ExternalAnchor]:
        """Get anchor by ID"""
        return self._anchors.get(anchor_id)
    
    def list_anchors(self, registry_type: Optional[ExternalRegistryType] = None) -> List[ExternalAnchor]:
        """List anchors"""
        anchors = list(self._anchors.values())
        if registry_type:
            anchors = [a for a in anchors if a.registry_type == registry_type]
        return anchors


# ============== 23.10 TRANSPORT ADAPTERS ==============

@dataclass
class TransportConfig:
    """Transport adapter configuration"""
    config_id: str
    transport_type: TransportType
    endpoint: str
    auth_type: str = "none"
    active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "config_id": self.config_id,
            "transport_type": self.transport_type.value,
            "endpoint": self.endpoint,
            "auth_type": self.auth_type,
            "active": self.active,
        }


class TransportManager:
    """
    Section 23.10: Transport Adapters
    
    Supports multiple I/O standards for deployment flexibility.
    """
    
    def __init__(self):
        self._configs: Dict[str, TransportConfig] = {}
    
    def register_transport(
        self,
        transport_type: TransportType,
        endpoint: str,
        auth_type: str = "none",
    ) -> TransportConfig:
        """Register a transport adapter"""
        config = TransportConfig(
            config_id=str(uuid.uuid4()),
            transport_type=transport_type,
            endpoint=endpoint,
            auth_type=auth_type,
        )
        
        self._configs[config.config_id] = config
        return config
    
    def get_transport(self, config_id: str) -> Optional[TransportConfig]:
        """Get transport config"""
        return self._configs.get(config_id)
    
    def list_transports(self, transport_type: Optional[TransportType] = None) -> List[TransportConfig]:
        """List transport configs"""
        configs = list(self._configs.values())
        if transport_type:
            configs = [c for c in configs if c.transport_type == transport_type]
        return configs


# ============== INTEROPERABILITY MANAGER ==============

class InteroperabilityManager:
    """
    Main manager for DSID-P Interoperability Layer
    
    Provides unified access to all interoperability subsystems.
    """
    
    def __init__(self):
        self.identity_bridge = IdentityBridge()
        self.semantic_translator = SemanticTranslator()
        self.memory_gateway = MemoryGateway()
        self.coordination_adapter = CoordinationAdapter()
        self.agent_adapter = ExternalAgentAdapter()
        self.model_adapter = ExternalModelAdapter()
        self.registry_bridge = RegistryBridge()
        self.transport_manager = TransportManager()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get interoperability statistics"""
        return {
            "identity_mappings": len(self.identity_bridge._mappings),
            "semantic_translations": len(self.semantic_translator._translations),
            "memory_proposals": len(self.memory_gateway._proposals),
            "workflow_translations": len(self.coordination_adapter._translations),
            "imported_agents": len(self.agent_adapter._imported_agents),
            "registered_models": len(self.model_adapter._connections),
            "external_anchors": len(self.registry_bridge._anchors),
            "transport_configs": len(self.transport_manager._configs),
        }


# ============== GLOBAL INSTANCE ==============

interop_manager = InteroperabilityManager()
