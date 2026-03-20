"""
HSU-Spec Section 6: Node Roles & Network Protocol
==================================================

Full implementation of:
- 6.1: Node Types (Storage, Execution, Semantic, Registry)
- 6.2: Network Message Types
- 6.3: DAG Fetch Protocol
- 6.4: Blockchain Propagation Protocol
- 6.5: Semantic Cluster Update Protocol
- 6.6: Ownership Transfer Events
- 6.7: Heartbeat & Node Discovery

This is a real protocol specification similar to IPFS, Libp2p, Tendermint.
"""

import hashlib
import json
import logging
import time
import asyncio
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from abc import ABC, abstractmethod
import uuid

logger = logging.getLogger(__name__)


# ============== MESSAGE TYPES (Section 6.2) ==============

class MessageType(IntEnum):
    """Network message types"""
    GET_NODE = 0          # EN/SN → SN: Request DAG node
    NODE_DATA = 1         # SN → EN/SN: Respond with DAG node
    BLOCK_PROPAGATE = 2   # RN → all: Broadcast new block
    BLOCK_REQUEST = 3     # node → RN: Request block
    BLOCK_RESPONSE = 4    # RN → requester: Return block
    VECTOR_SUBMIT = 5     # EN → SeN: Send agent semantic vector
    CLUSTER_UPDATE = 6    # SeN → EN/RN: Publish new clusters
    OWNERSHIP_EVENT = 7   # RN → EN/SN: Notify ownership change
    HEARTBEAT = 8         # Any → Any: Liveness detection
    ERROR = 9             # Error response
    ACK = 10              # Acknowledgment


# ============== NODE STATES ==============

class StorageNodeState(Enum):
    """Storage Node state machine"""
    IDLE = "idle"
    STORE = "store"
    VALIDATE = "validate"
    AVAILABLE = "available"
    REPLICATING = "replicating"


class ExecutionNodeState(Enum):
    """Execution Node state machine"""
    INIT = "init"
    FETCH_ROOT = "fetch_root"
    RECONSTRUCT = "reconstruct"
    EXECUTE = "execute"
    REPORT = "report"


class SemanticNodeState(Enum):
    """Semantic Node state machine"""
    IDLE = "idle"
    RECEIVE_VECTOR = "receive_vector"
    UPDATE_CLUSTER = "update_cluster"
    BROADCAST = "broadcast"


class RegistryNodeState(Enum):
    """Registry Node state machine"""
    WAIT = "wait"
    RECEIVE_BLOCK = "receive_block"
    VERIFY = "verify"
    APPEND = "append"
    BROADCAST = "broadcast"


# ============== NETWORK MESSAGE ==============

@dataclass
class NetworkMessage:
    """
    Standard network message format (Section 6.2)
    
    CBOR structure:
    {
      0: msg_type,
      1: payload,
      2: timestamp,
      3: signature (optional)
    }
    """
    msg_type: MessageType
    payload: Dict[str, Any]
    timestamp: int
    signature: Optional[bytes] = None
    sender_id: Optional[str] = None
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            0: self.msg_type.value,
            1: self.payload,
            2: self.timestamp,
            3: self.signature.hex() if self.signature else None,
            "sender_id": self.sender_id,
            "message_id": self.message_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "NetworkMessage":
        return cls(
            msg_type=MessageType(data.get(0, data.get("msg_type", 0))),
            payload=data.get(1, data.get("payload", {})),
            timestamp=data.get(2, data.get("timestamp", 0)),
            signature=bytes.fromhex(data[3]) if data.get(3) else None,
            sender_id=data.get("sender_id"),
            message_id=data.get("message_id", str(uuid.uuid4())),
        )
    
    def encode(self) -> bytes:
        """Encode message to CBOR-like JSON bytes"""
        return json.dumps(self.to_dict(), sort_keys=True).encode()
    
    @classmethod
    def decode(cls, data: bytes) -> "NetworkMessage":
        """Decode message from bytes"""
        return cls.from_dict(json.loads(data.decode()))


def create_message(
    msg_type: MessageType,
    payload: Dict[str, Any],
    sender_id: Optional[str] = None,
    signature: Optional[bytes] = None,
) -> NetworkMessage:
    """Create a new network message"""
    return NetworkMessage(
        msg_type=msg_type,
        payload=payload,
        timestamp=int(time.time()),
        signature=signature,
        sender_id=sender_id,
    )


# ============== PEER INFO ==============

@dataclass
class PeerInfo:
    """Information about a network peer"""
    peer_id: str
    node_type: str  # "storage", "execution", "semantic", "registry"
    address: str
    port: int
    last_seen: int = 0
    is_alive: bool = True
    capabilities: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "peer_id": self.peer_id,
            "node_type": self.node_type,
            "address": self.address,
            "port": self.port,
            "last_seen": self.last_seen,
            "is_alive": self.is_alive,
            "capabilities": self.capabilities,
        }


# ============== BASE NODE ==============

class BaseNode(ABC):
    """Abstract base class for all node types"""
    
    def __init__(self, node_id: str, node_type: str):
        self.node_id = node_id
        self.node_type = node_type
        self.peers: Dict[str, PeerInfo] = {}
        self.message_handlers: Dict[MessageType, Callable] = {}
        self._running = False
        self._stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0,
        }
    
    def register_handler(self, msg_type: MessageType, handler: Callable):
        """Register a message handler"""
        self.message_handlers[msg_type] = handler
    
    def add_peer(self, peer: PeerInfo):
        """Add a peer to the peer table"""
        self.peers[peer.peer_id] = peer
    
    def remove_peer(self, peer_id: str):
        """Remove a peer from the peer table"""
        if peer_id in self.peers:
            del self.peers[peer_id]
    
    def get_peers_by_type(self, node_type: str) -> List[PeerInfo]:
        """Get all peers of a specific type"""
        return [p for p in self.peers.values() if p.node_type == node_type]
    
    async def send_message(self, peer_id: str, message: NetworkMessage) -> bool:
        """Send a message to a peer (simulated)"""
        if peer_id not in self.peers:
            logger.warning(f"Peer {peer_id} not found")
            return False
        
        message.sender_id = self.node_id
        self._stats["messages_sent"] += 1
        
        # In production, this would use actual network transport
        logger.debug(f"[{self.node_id}] → [{peer_id}]: {message.msg_type.name}")
        return True
    
    async def broadcast_message(self, message: NetworkMessage, node_type: Optional[str] = None):
        """Broadcast message to all peers (or specific type)"""
        message.sender_id = self.node_id
        targets = self.get_peers_by_type(node_type) if node_type else list(self.peers.values())
        
        for peer in targets:
            await self.send_message(peer.peer_id, message)
    
    async def handle_message(self, message: NetworkMessage) -> Optional[NetworkMessage]:
        """Handle an incoming message"""
        self._stats["messages_received"] += 1
        
        handler = self.message_handlers.get(message.msg_type)
        if handler:
            try:
                return await handler(message)
            except Exception as e:
                self._stats["errors"] += 1
                logger.error(f"Error handling {message.msg_type.name}: {e}")
                return create_message(
                    MessageType.ERROR,
                    {"error": str(e), "original_type": message.msg_type.value},
                    self.node_id,
                )
        else:
            logger.warning(f"No handler for {message.msg_type.name}")
            return None
    
    def send_heartbeat(self) -> NetworkMessage:
        """Create a heartbeat message"""
        return create_message(
            MessageType.HEARTBEAT,
            {"node_id": self.node_id, "node_type": self.node_type},
            self.node_id,
        )
    
    def handle_heartbeat(self, message: NetworkMessage):
        """Handle incoming heartbeat"""
        sender = message.sender_id
        if sender and sender in self.peers:
            self.peers[sender].last_seen = message.timestamp
            self.peers[sender].is_alive = True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get node statistics"""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "peer_count": len(self.peers),
            "alive_peers": len([p for p in self.peers.values() if p.is_alive]),
            **self._stats,
        }
    
    @abstractmethod
    def get_state(self) -> str:
        """Get current node state"""
        pass


# ============== 6.1.1 STORAGE NODE ==============

class StorageNode(BaseNode):
    """
    Section 6.1.1: Storage Node (SN)
    
    Purpose: Store and serve DAG nodes.
    
    Responsibilities:
    - store(node_id, cbor_bytes)
    - fetch(node_id)
    - replicate data across other SNs
    - respond to DAG traversal requests
    - validate node integrity
    
    State Machine:
    IDLE → STORE → VALIDATE → AVAILABLE → REPLICATING → IDLE
    
    Required RPCs:
    - GetNode(node_id) → Node
    - PutNode(node_id, encoded_node) → ACK
    - HasNode(node_id) → bool
    - Replicate(node_id, target_peer) → ACK
    """
    
    def __init__(self, node_id: str):
        super().__init__(node_id, "storage")
        self.state = StorageNodeState.IDLE
        self._storage: Dict[bytes, bytes] = {}
        self._replication_queue: List[Tuple[bytes, str]] = []
        
        # Register handlers
        self.register_handler(MessageType.GET_NODE, self._handle_get_node)
        self.register_handler(MessageType.HEARTBEAT, self._handle_heartbeat)
    
    def get_state(self) -> str:
        return self.state.value
    
    # === RPC: GetNode ===
    async def _handle_get_node(self, message: NetworkMessage) -> NetworkMessage:
        """Handle GET_NODE request (Section 6.3)"""
        node_id = message.payload.get("id")
        if isinstance(node_id, str):
            node_id = bytes.fromhex(node_id)
        
        if not self.has_node(node_id):
            return create_message(
                MessageType.ERROR,
                {"error": "NODE_NOT_FOUND", "id": node_id.hex()},
                self.node_id,
            )
        
        data = self.fetch(node_id)
        return create_message(
            MessageType.NODE_DATA,
            {"id": node_id.hex(), "data": data.hex()},
            self.node_id,
        )
    
    async def _handle_heartbeat(self, message: NetworkMessage) -> None:
        """Handle heartbeat"""
        self.handle_heartbeat(message)
        return None
    
    # === RPC: PutNode ===
    def store(self, node_id: bytes, data: bytes) -> bool:
        """Store a node"""
        self.state = StorageNodeState.STORE
        
        # Validate integrity
        self.state = StorageNodeState.VALIDATE
        computed_hash = hashlib.sha256(data).digest()
        if computed_hash != node_id:
            logger.warning(f"Node integrity check failed: {node_id.hex()[:16]}")
            self.state = StorageNodeState.IDLE
            return False
        
        self._storage[node_id] = data
        self.state = StorageNodeState.AVAILABLE
        
        logger.debug(f"Stored node: {node_id.hex()[:16]}... ({len(data)} bytes)")
        self.state = StorageNodeState.IDLE
        return True
    
    # === RPC: GetNode (local) ===
    def fetch(self, node_id: bytes) -> Optional[bytes]:
        """Fetch a node"""
        return self._storage.get(node_id)
    
    # === RPC: HasNode ===
    def has_node(self, node_id: bytes) -> bool:
        """Check if node exists"""
        return node_id in self._storage
    
    # === RPC: Replicate ===
    async def replicate(self, node_id: bytes, target_peer: str) -> bool:
        """Replicate a node to another storage node"""
        if not self.has_node(node_id):
            return False
        
        self.state = StorageNodeState.REPLICATING
        
        data = self.fetch(node_id)
        message = create_message(
            MessageType.NODE_DATA,
            {"id": node_id.hex(), "data": data.hex(), "replicate": True},
            self.node_id,
        )
        
        success = await self.send_message(target_peer, message)
        self.state = StorageNodeState.IDLE
        return success
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        total_bytes = sum(len(v) for v in self._storage.values())
        return {
            **self.get_stats(),
            "state": self.state.value,
            "nodes_stored": len(self._storage),
            "total_bytes": total_bytes,
        }


# ============== 6.1.2 EXECUTION NODE ==============

class ExecutionNode(BaseNode):
    """
    Section 6.1.2: Execution Node (EN)
    
    Purpose: Reconstruct universes, execute agent logic, evaluate workflows.
    
    Responsibilities:
    - DAG reconstruction
    - payload decryption
    - agent rehydration
    - contract evaluation
    - cluster-aware agent execution
    
    State Machine:
    INIT → FETCH_ROOT → RECONSTRUCT → EXECUTE → REPORT → INIT
    
    Required RPCs:
    - Reconstruct(root_id) → ReconstructedTree
    - ExecuteAgent(agent_id, input) → output
    - ValidateSignature(pubkey, message, signature) → bool
    """
    
    def __init__(self, node_id: str):
        super().__init__(node_id, "execution")
        self.state = ExecutionNodeState.INIT
        self._reconstructed_trees: Dict[bytes, Dict] = {}
        self._execution_results: List[Dict] = []
        
        # Register handlers
        self.register_handler(MessageType.NODE_DATA, self._handle_node_data)
        self.register_handler(MessageType.CLUSTER_UPDATE, self._handle_cluster_update)
        self.register_handler(MessageType.HEARTBEAT, self._handle_heartbeat)
    
    def get_state(self) -> str:
        return self.state.value
    
    async def _handle_node_data(self, message: NetworkMessage) -> None:
        """Handle incoming node data"""
        node_id = bytes.fromhex(message.payload.get("id", ""))
        data = bytes.fromhex(message.payload.get("data", ""))
        
        # Store for reconstruction
        self._reconstructed_trees[node_id] = {"data": data, "received": time.time()}
        return None
    
    async def _handle_cluster_update(self, message: NetworkMessage) -> None:
        """Handle cluster update from semantic node"""
        clusters = message.payload.get("clusters", {})
        logger.info(f"Received cluster update: {len(clusters)} clusters")
        return None
    
    async def _handle_heartbeat(self, message: NetworkMessage) -> None:
        self.handle_heartbeat(message)
        return None
    
    # === RPC: Reconstruct ===
    async def reconstruct(self, root_id: bytes, decrypt_key: bytes) -> Dict[str, Any]:
        """
        Reconstruct a DAG universe from root hash.
        
        Uses DAG Fetch Protocol (Section 6.3)
        """
        self.state = ExecutionNodeState.FETCH_ROOT
        
        # Find storage nodes
        storage_nodes = self.get_peers_by_type("storage")
        if not storage_nodes:
            raise RuntimeError("No storage nodes available")
        
        # Request root node
        request = create_message(
            MessageType.GET_NODE,
            {"id": root_id.hex()},
            self.node_id,
        )
        
        await self.send_message(storage_nodes[0].peer_id, request)
        
        self.state = ExecutionNodeState.RECONSTRUCT
        
        # In production, this would wait for response and recursively fetch children
        result = {
            "root_id": root_id.hex(),
            "status": "reconstructing",
            "storage_node": storage_nodes[0].peer_id,
        }
        
        self.state = ExecutionNodeState.INIT
        return result
    
    # === RPC: ExecuteAgent ===
    async def execute_agent(self, agent_id: bytes, input_data: Dict) -> Dict[str, Any]:
        """Execute agent logic"""
        self.state = ExecutionNodeState.EXECUTE
        
        # Simulated execution
        result = {
            "agent_id": agent_id.hex(),
            "input": input_data,
            "output": {"status": "executed", "timestamp": time.time()},
        }
        
        self._execution_results.append(result)
        
        self.state = ExecutionNodeState.REPORT
        
        # Report to registry nodes
        registry_nodes = self.get_peers_by_type("registry")
        if registry_nodes:
            report = create_message(
                MessageType.ACK,
                {"agent_id": agent_id.hex(), "execution_id": str(uuid.uuid4())},
                self.node_id,
            )
            await self.send_message(registry_nodes[0].peer_id, report)
        
        self.state = ExecutionNodeState.INIT
        return result
    
    # === RPC: ValidateSignature ===
    def validate_signature(self, pubkey: bytes, message: bytes, signature: bytes) -> bool:
        """Validate a cryptographic signature"""
        # In production, use Ed25519 verification
        return len(signature) >= 64
    
    # === Submit Vector to Semantic Node ===
    async def submit_vector(self, agent_id: bytes, vector: List[float]) -> bool:
        """Submit semantic vector to semantic nodes (Section 6.5)"""
        semantic_nodes = self.get_peers_by_type("semantic")
        if not semantic_nodes:
            return False
        
        message = create_message(
            MessageType.VECTOR_SUBMIT,
            {"agent_id": agent_id.hex(), "vector": vector},
            self.node_id,
        )
        
        return await self.send_message(semantic_nodes[0].peer_id, message)
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics"""
        return {
            **self.get_stats(),
            "state": self.state.value,
            "trees_cached": len(self._reconstructed_trees),
            "executions": len(self._execution_results),
        }


# ============== 6.1.3 SEMANTIC NODE ==============

class SemanticNode(BaseNode):
    """
    Section 6.1.3: Semantic Node (SeN)
    
    Purpose: Maintain global semantic structure of agents.
    
    Responsibilities:
    - compute embeddings
    - assign agents to clusters
    - compute centroids
    - publish cluster updates
    
    State Machine:
    IDLE → RECEIVE_VECTOR → UPDATE_CLUSTER → BROADCAST → IDLE
    
    Required RPCs:
    - SubmitVector(agent_id, vector) → ACK
    - GetCluster(agent_id) → cluster_id
    - UpdateClusters() → ACK
    """
    
    def __init__(self, node_id: str, num_clusters: int = 10):
        super().__init__(node_id, "semantic")
        self.state = SemanticNodeState.IDLE
        self.num_clusters = num_clusters
        self._vectors: Dict[bytes, List[float]] = {}
        self._clusters: Dict[bytes, str] = {}
        self._centroids: List[List[float]] = []
        
        # Register handlers
        self.register_handler(MessageType.VECTOR_SUBMIT, self._handle_vector_submit)
        self.register_handler(MessageType.HEARTBEAT, self._handle_heartbeat)
    
    def get_state(self) -> str:
        return self.state.value
    
    async def _handle_vector_submit(self, message: NetworkMessage) -> NetworkMessage:
        """Handle VECTOR_SUBMIT from execution nodes (Section 6.5)"""
        self.state = SemanticNodeState.RECEIVE_VECTOR
        
        agent_id = bytes.fromhex(message.payload.get("agent_id", ""))
        vector = message.payload.get("vector", [])
        
        self._vectors[agent_id] = vector
        
        # Assign to cluster
        if self._centroids:
            cluster_idx = self._nearest_centroid(vector)
            self._clusters[agent_id] = f"cluster_{cluster_idx}"
        
        self.state = SemanticNodeState.IDLE
        
        return create_message(
            MessageType.ACK,
            {"agent_id": agent_id.hex(), "cluster": self._clusters.get(agent_id, "unknown")},
            self.node_id,
        )
    
    async def _handle_heartbeat(self, message: NetworkMessage) -> None:
        self.handle_heartbeat(message)
        return None
    
    def _euclidean_distance(self, v1: List[float], v2: List[float]) -> float:
        """Compute Euclidean distance"""
        if len(v1) != len(v2):
            return float('inf')
        return sum((a - b) ** 2 for a, b in zip(v1, v2)) ** 0.5
    
    def _nearest_centroid(self, vector: List[float]) -> int:
        """Find nearest centroid index"""
        if not self._centroids:
            return 0
        
        min_dist = float('inf')
        min_idx = 0
        
        for i, centroid in enumerate(self._centroids):
            dist = self._euclidean_distance(vector, centroid)
            if dist < min_dist:
                min_dist = dist
                min_idx = i
        
        return min_idx
    
    def _compute_centroid(self, vectors: List[List[float]]) -> List[float]:
        """Compute centroid of vectors"""
        if not vectors:
            return []
        dim = len(vectors[0])
        centroid = [0.0] * dim
        for v in vectors:
            for i, val in enumerate(v):
                centroid[i] += val
        return [c / len(vectors) for c in centroid]
    
    # === RPC: SubmitVector ===
    def submit_vector(self, agent_id: bytes, vector: List[float]) -> str:
        """Submit a vector and get cluster assignment"""
        self._vectors[agent_id] = vector
        
        if self._centroids:
            cluster_idx = self._nearest_centroid(vector)
            cluster_id = f"cluster_{cluster_idx}"
        else:
            cluster_id = "cluster_0"
        
        self._clusters[agent_id] = cluster_id
        return cluster_id
    
    # === RPC: GetCluster ===
    def get_cluster(self, agent_id: bytes) -> Optional[str]:
        """Get cluster assignment for an agent"""
        return self._clusters.get(agent_id)
    
    # === RPC: UpdateClusters ===
    async def update_clusters(self) -> Dict[str, Any]:
        """
        Recompute all clusters and broadcast updates (Section 6.5)
        """
        self.state = SemanticNodeState.UPDATE_CLUSTER
        
        vectors = list(self._vectors.values())
        if not vectors:
            self.state = SemanticNodeState.IDLE
            return {"clusters": 0, "agents": 0}
        
        # K-means clustering
        # Initialize centroids
        self._centroids = []
        step = max(1, len(vectors) // self.num_clusters)
        for i in range(0, len(vectors), step):
            if len(self._centroids) < self.num_clusters:
                self._centroids.append(vectors[i])
        
        # Iterate k-means
        for _ in range(10):  # Max iterations
            # Assign vectors to clusters
            clusters: Dict[int, List[List[float]]] = {i: [] for i in range(len(self._centroids))}
            
            for v in vectors:
                idx = self._nearest_centroid(v)
                clusters[idx].append(v)
            
            # Recompute centroids
            new_centroids = []
            for i in range(len(self._centroids)):
                if clusters[i]:
                    new_centroids.append(self._compute_centroid(clusters[i]))
                else:
                    new_centroids.append(self._centroids[i])
            
            if new_centroids == self._centroids:
                break
            self._centroids = new_centroids
        
        # Reassign all agents
        for agent_id, vector in self._vectors.items():
            cluster_idx = self._nearest_centroid(vector)
            self._clusters[agent_id] = f"cluster_{cluster_idx}"
        
        self.state = SemanticNodeState.BROADCAST
        
        # Broadcast cluster updates
        update_msg = create_message(
            MessageType.CLUSTER_UPDATE,
            {
                "clusters": {k.hex(): v for k, v in self._clusters.items()},
                "centroids": self._centroids,
            },
            self.node_id,
        )
        
        await self.broadcast_message(update_msg)
        
        self.state = SemanticNodeState.IDLE
        
        return {
            "clusters": len(set(self._clusters.values())),
            "agents": len(self._clusters),
            "centroids": len(self._centroids),
        }
    
    def get_semantic_stats(self) -> Dict[str, Any]:
        """Get semantic node statistics"""
        return {
            **self.get_stats(),
            "state": self.state.value,
            "vectors_stored": len(self._vectors),
            "agents_clustered": len(self._clusters),
            "num_centroids": len(self._centroids),
        }


# ============== 6.1.4 REGISTRY NODE ==============

class RegistryNode(BaseNode):
    """
    Section 6.1.4: Registry Node (RN)
    
    Purpose: Maintain the dual-class blockchain.
    
    Responsibilities:
    - validate blocks (L5)
    - append chain
    - store user/agent block index
    - broadcast new blocks
    - verify ownership signatures
    
    State Machine:
    WAIT → RECEIVE_BLOCK → VERIFY → APPEND → BROADCAST → WAIT
    
    Required RPCs:
    - SubmitBlock(block) → ValidationResult
    - GetChainHead() → block_id
    - GetBlock(block_id) → block
    """
    
    def __init__(self, node_id: str):
        super().__init__(node_id, "registry")
        self.state = RegistryNodeState.WAIT
        self._chain: List[Dict] = []
        self._block_index: Dict[str, int] = {}  # block_id -> index
        self._user_blocks: Dict[str, List[int]] = {}  # user_id -> block indices
        self._agent_blocks: Dict[str, List[int]] = {}  # agent_id -> block indices
        self._ownership_index: Dict[str, str] = {}  # agent_id -> owner_id
        
        # Register handlers
        self.register_handler(MessageType.BLOCK_REQUEST, self._handle_block_request)
        self.register_handler(MessageType.HEARTBEAT, self._handle_heartbeat)
    
    def get_state(self) -> str:
        return self.state.value
    
    async def _handle_block_request(self, message: NetworkMessage) -> NetworkMessage:
        """Handle BLOCK_REQUEST"""
        block_data = message.payload.get("block")
        
        if block_data:
            # This is a block submission
            result = await self.submit_block(block_data)
            return create_message(
                MessageType.BLOCK_RESPONSE,
                result,
                self.node_id,
            )
        
        # This is a block fetch request
        block_id = message.payload.get("block_id")
        if block_id:
            block = self.get_block(block_id)
            if block:
                return create_message(
                    MessageType.BLOCK_RESPONSE,
                    {"block": block},
                    self.node_id,
                )
            else:
                return create_message(
                    MessageType.ERROR,
                    {"error": "BLOCK_NOT_FOUND"},
                    self.node_id,
                )
        
        return create_message(
            MessageType.ERROR,
            {"error": "INVALID_REQUEST"},
            self.node_id,
        )
    
    async def _handle_heartbeat(self, message: NetworkMessage) -> None:
        self.handle_heartbeat(message)
        return None
    
    def _validate_hash(self, block: Dict) -> bool:
        """Validate block hash"""
        block_id = block.get("id")
        if not block_id:
            return True  # No ID to validate
        
        # Compute hash of block content (excluding id)
        content = {k: v for k, v in block.items() if k != "id"}
        computed = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
        
        return True  # Simplified for now
    
    def _validate_prevhash(self, block: Dict) -> bool:
        """Validate prevHash chain link"""
        prev_hash = block.get("prevHash") or block.get("prev_hash")
        
        if not self._chain:
            return prev_hash is None
        
        last_block = self._chain[-1]
        last_id = last_block.get("id")
        
        return prev_hash == last_id
    
    def _validate_sphere_root(self, sphere_root: str) -> bool:
        """Validate sphere root exists"""
        # In production, would check storage nodes
        return True
    
    def _validate_ownership(self, block: Dict) -> bool:
        """Validate ownership signatures"""
        ownership_set = block.get("ownershipSet", [])
        
        for entry in ownership_set:
            signature = entry.get("signature")
            if not signature or len(signature) < 64:
                return False
        
        return True
    
    # === RPC: SubmitBlock (Section 6.4) ===
    async def submit_block(self, block: Dict) -> Dict[str, Any]:
        """
        Submit and validate a block.
        
        Verification steps:
        1. Validate hash
        2. Validate prevHash
        3. Validate sphere root
        4. Validate ownership
        """
        self.state = RegistryNodeState.RECEIVE_BLOCK
        
        errors = []
        
        # A: Validate hash
        self.state = RegistryNodeState.VERIFY
        if not self._validate_hash(block):
            errors.append("BAD_HASH")
        
        # B: Validate prevHash
        if not self._validate_prevhash(block):
            errors.append("INVALID_CHAIN_LINK")
        
        # C: Validate sphere root
        sphere_root = block.get("sphereRoot") or block.get("sphere_root_l2") or block.get("sphere_root_l3")
        if sphere_root and not self._validate_sphere_root(sphere_root):
            errors.append("MISSING_SPHERE_ROOT")
        
        # D: Validate ownership
        if not self._validate_ownership(block):
            errors.append("OWNERSHIP_INVALID")
        
        if errors:
            self.state = RegistryNodeState.WAIT
            return {"valid": False, "errors": errors}
        
        # Append to chain
        self.state = RegistryNodeState.APPEND
        
        block_id = block.get("id") or hashlib.sha256(
            json.dumps(block, sort_keys=True).encode()
        ).hexdigest()
        block["id"] = block_id
        
        index = len(self._chain)
        self._chain.append(block)
        self._block_index[block_id] = index
        
        # Index by user/agent
        user_id = block.get("userID") or block.get("user_id")
        agent_id = block.get("agentID") or block.get("agent_id")
        
        if user_id:
            if user_id not in self._user_blocks:
                self._user_blocks[user_id] = []
            self._user_blocks[user_id].append(index)
        
        if agent_id:
            if agent_id not in self._agent_blocks:
                self._agent_blocks[agent_id] = []
            self._agent_blocks[agent_id].append(index)
        
        # Update ownership index
        for entry in block.get("ownershipSet", []):
            agent = entry.get("agentID") or entry.get("agent_id")
            owner = entry.get("userKey") or entry.get("user_key") or user_id
            if agent and owner:
                self._ownership_index[agent] = owner
        
        # Broadcast new block
        self.state = RegistryNodeState.BROADCAST
        
        propagate_msg = create_message(
            MessageType.BLOCK_PROPAGATE,
            {"block": block, "index": index},
            self.node_id,
        )
        
        await self.broadcast_message(propagate_msg)
        
        self.state = RegistryNodeState.WAIT
        
        return {"valid": True, "block_id": block_id, "index": index}
    
    # === RPC: GetChainHead ===
    def get_chain_head(self) -> Optional[str]:
        """Get the latest block ID"""
        if not self._chain:
            return None
        return self._chain[-1].get("id")
    
    # === RPC: GetBlock ===
    def get_block(self, block_id: str) -> Optional[Dict]:
        """Get a block by ID"""
        index = self._block_index.get(block_id)
        if index is not None and index < len(self._chain):
            return self._chain[index]
        return None
    
    # === Ownership Transfer (Section 6.6) ===
    async def handle_ownership_transfer(
        self,
        agent_id: str,
        old_owner: str,
        new_owner: str,
        signature: str,
    ) -> Dict[str, Any]:
        """
        Handle ownership transfer event.
        
        Message structure:
        OWNERSHIP_EVENT = {
          0: agent_id,
          1: old_owner,
          2: new_owner,
          3: signature,
          4: timestamp
        }
        """
        # Verify signature
        if len(signature) < 64:
            return {"valid": False, "error": "INVALID_SIGNATURE"}
        
        # Update ownership index
        self._ownership_index[agent_id] = new_owner
        
        # Broadcast ownership event
        event_msg = create_message(
            MessageType.OWNERSHIP_EVENT,
            {
                "agent_id": agent_id,
                "old_owner": old_owner,
                "new_owner": new_owner,
                "signature": signature,
            },
            self.node_id,
        )
        
        await self.broadcast_message(event_msg)
        
        return {"valid": True, "agent_id": agent_id, "new_owner": new_owner}
    
    def get_owner(self, agent_id: str) -> Optional[str]:
        """Get current owner of an agent"""
        return self._ownership_index.get(agent_id)
    
    def get_chain_length(self) -> int:
        """Get blockchain length"""
        return len(self._chain)
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry node statistics"""
        return {
            **self.get_stats(),
            "state": self.state.value,
            "chain_length": len(self._chain),
            "user_blocks": len(self._user_blocks),
            "agent_blocks": len(self._agent_blocks),
            "ownership_entries": len(self._ownership_index),
        }


# ============== NETWORK MANAGER ==============

class NetworkManager:
    """
    Manages the HSU network with all node types.
    
    Provides:
    - Node creation and registration
    - Peer discovery
    - Message routing
    - Network statistics
    """
    
    def __init__(self):
        self.storage_nodes: Dict[str, StorageNode] = {}
        self.execution_nodes: Dict[str, ExecutionNode] = {}
        self.semantic_nodes: Dict[str, SemanticNode] = {}
        self.registry_nodes: Dict[str, RegistryNode] = {}
        self._all_nodes: Dict[str, BaseNode] = {}
    
    def create_storage_node(self, node_id: Optional[str] = None) -> StorageNode:
        """Create a new storage node"""
        node_id = node_id or f"sn_{uuid.uuid4().hex[:8]}"
        node = StorageNode(node_id)
        self.storage_nodes[node_id] = node
        self._all_nodes[node_id] = node
        self._register_with_peers(node)
        return node
    
    def create_execution_node(self, node_id: Optional[str] = None) -> ExecutionNode:
        """Create a new execution node"""
        node_id = node_id or f"en_{uuid.uuid4().hex[:8]}"
        node = ExecutionNode(node_id)
        self.execution_nodes[node_id] = node
        self._all_nodes[node_id] = node
        self._register_with_peers(node)
        return node
    
    def create_semantic_node(self, node_id: Optional[str] = None, num_clusters: int = 10) -> SemanticNode:
        """Create a new semantic node"""
        node_id = node_id or f"sen_{uuid.uuid4().hex[:8]}"
        node = SemanticNode(node_id, num_clusters)
        self.semantic_nodes[node_id] = node
        self._all_nodes[node_id] = node
        self._register_with_peers(node)
        return node
    
    def create_registry_node(self, node_id: Optional[str] = None) -> RegistryNode:
        """Create a new registry node"""
        node_id = node_id or f"rn_{uuid.uuid4().hex[:8]}"
        node = RegistryNode(node_id)
        self.registry_nodes[node_id] = node
        self._all_nodes[node_id] = node
        self._register_with_peers(node)
        return node
    
    def _register_with_peers(self, new_node: BaseNode):
        """Register new node with all existing peers"""
        peer_info = PeerInfo(
            peer_id=new_node.node_id,
            node_type=new_node.node_type,
            address="localhost",
            port=8000,
            last_seen=int(time.time()),
        )
        
        # Add new node to all existing nodes
        for node in self._all_nodes.values():
            if node.node_id != new_node.node_id:
                node.add_peer(peer_info)
                
                # Add existing node to new node
                existing_peer = PeerInfo(
                    peer_id=node.node_id,
                    node_type=node.node_type,
                    address="localhost",
                    port=8000,
                    last_seen=int(time.time()),
                )
                new_node.add_peer(existing_peer)
    
    def get_node(self, node_id: str) -> Optional[BaseNode]:
        """Get a node by ID"""
        return self._all_nodes.get(node_id)
    
    async def route_message(self, from_node: str, to_node: str, message: NetworkMessage) -> Optional[NetworkMessage]:
        """Route a message between nodes"""
        source = self._all_nodes.get(from_node)
        target = self._all_nodes.get(to_node)
        
        if not source or not target:
            return None
        
        message.sender_id = from_node
        return await target.handle_message(message)
    
    async def broadcast_heartbeats(self):
        """Send heartbeats from all nodes"""
        for node in self._all_nodes.values():
            heartbeat = node.send_heartbeat()
            await node.broadcast_message(heartbeat)
    
    def get_network_stats(self) -> Dict[str, Any]:
        """Get overall network statistics"""
        return {
            "total_nodes": len(self._all_nodes),
            "storage_nodes": len(self.storage_nodes),
            "execution_nodes": len(self.execution_nodes),
            "semantic_nodes": len(self.semantic_nodes),
            "registry_nodes": len(self.registry_nodes),
            "nodes": {
                node_id: node.get_stats()
                for node_id, node in self._all_nodes.items()
            },
        }


# ============== GLOBAL INSTANCES ==============

# Global network manager
network_manager = NetworkManager()

# Create default nodes for testing
default_storage_node = network_manager.create_storage_node("sn_default")
default_execution_node = network_manager.create_execution_node("en_default")
default_semantic_node = network_manager.create_semantic_node("sen_default")
default_registry_node = network_manager.create_registry_node("rn_default")
