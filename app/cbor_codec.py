"""
CBOR Block Format & Byte-Level Structures (HSU-Spec Section 4)
===============================================================

Implements canonical CBOR encoding for all HSU-Spec structures:
- Layer 1: Identity Nodes (Tag 60000)
- Layer 2: User Data Nodes (Tag 60001)
- Layer 3: Agent Data Nodes (Tag 60002)
- Layer 4: Coordination Nodes (Tag 60003)
- Layer 5: User Blocks (Tag 60004), Agent Blocks (Tag 60005)
- Smart Contracts (Tag 60006)
- Semantic Vectors (Tag 60007)
- Cluster Metadata (Tag 60008)

Encoding Format: CBOR (RFC 7049 / RFC 8949 Canonical Mode)
"""

import hashlib
import json
import struct
import logging
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum

logger = logging.getLogger(__name__)


# ============== CBOR TAGS ==============

class CBORTag(IntEnum):
    """CBOR tags for HSU-Spec structures (private use range > 55000)"""
    IDENTITY_NODE = 60000      # Layer 1
    USER_DATA_NODE = 60001     # Layer 2
    AGENT_DATA_NODE = 60002    # Layer 3
    COORDINATION_NODE = 60003  # Layer 4
    USER_BLOCK = 60004         # Layer 5 Class U
    AGENT_BLOCK = 60005        # Layer 5 Class A
    SMART_CONTRACT = 60006
    SEMANTIC_VECTOR = 60007
    CLUSTER_METADATA = 60008


# ============== INTERACTION TYPES ==============

class InteractionType(IntEnum):
    """Interaction types for Layer 4"""
    USER_TO_AGENT = 0
    AGENT_TO_AGENT = 1
    AGENT_TO_SYSTEM = 2
    SYSTEM_TO_USER = 3


# ============== CBOR ENCODER ==============

class CBOREncoder:
    """
    Canonical CBOR Encoder (RFC 8949)
    
    Rules:
    1. Map keys sorted lexicographically by byte encoding
    2. Minimal-length encoding for integers
    3. No redundant fields
    4. Byte strings as raw binary
    5. Tags for typed structures
    """
    
    # CBOR major types
    UNSIGNED_INT = 0
    NEGATIVE_INT = 1
    BYTE_STRING = 2
    TEXT_STRING = 3
    ARRAY = 4
    MAP = 5
    TAG = 6
    SIMPLE = 7
    
    def __init__(self):
        self._buffer = bytearray()
    
    def _write_byte(self, b: int):
        self._buffer.append(b & 0xFF)
    
    def _write_bytes(self, data: bytes):
        self._buffer.extend(data)
    
    def _encode_head(self, major_type: int, value: int):
        """Encode CBOR head with minimal length"""
        mt = major_type << 5
        
        if value < 24:
            self._write_byte(mt | value)
        elif value < 256:
            self._write_byte(mt | 24)
            self._write_byte(value)
        elif value < 65536:
            self._write_byte(mt | 25)
            self._write_bytes(struct.pack(">H", value))
        elif value < 4294967296:
            self._write_byte(mt | 26)
            self._write_bytes(struct.pack(">I", value))
        else:
            self._write_byte(mt | 27)
            self._write_bytes(struct.pack(">Q", value))
    
    def encode_unsigned(self, value: int):
        """Encode unsigned integer"""
        self._encode_head(self.UNSIGNED_INT, value)
    
    def encode_negative(self, value: int):
        """Encode negative integer"""
        self._encode_head(self.NEGATIVE_INT, -1 - value)
    
    def encode_int(self, value: int):
        """Encode any integer"""
        if value >= 0:
            self.encode_unsigned(value)
        else:
            self.encode_negative(value)
    
    def encode_bytes(self, data: bytes):
        """Encode byte string"""
        self._encode_head(self.BYTE_STRING, len(data))
        self._write_bytes(data)
    
    def encode_string(self, value: str):
        """Encode text string"""
        encoded = value.encode('utf-8')
        self._encode_head(self.TEXT_STRING, len(encoded))
        self._write_bytes(encoded)
    
    def encode_array(self, items: List[Any]):
        """Encode array"""
        self._encode_head(self.ARRAY, len(items))
        for item in items:
            self.encode_value(item)
    
    def encode_map(self, data: Dict[Any, Any]):
        """Encode map with canonical key ordering"""
        # Sort keys by their CBOR encoding
        sorted_items = sorted(
            data.items(),
            key=lambda x: self._key_sort_value(x[0])
        )
        
        self._encode_head(self.MAP, len(sorted_items))
        for key, value in sorted_items:
            self.encode_value(key)
            self.encode_value(value)
    
    def _key_sort_value(self, key: Any) -> bytes:
        """Get sort value for map key"""
        encoder = CBOREncoder()
        encoder.encode_value(key)
        return bytes(encoder._buffer)
    
    def encode_tag(self, tag: int, value: Any):
        """Encode tagged value"""
        self._encode_head(self.TAG, tag)
        self.encode_value(value)
    
    def encode_float(self, value: float):
        """Encode float (IEEE 754 double)"""
        self._write_byte((self.SIMPLE << 5) | 27)
        self._write_bytes(struct.pack(">d", value))
    
    def encode_bool(self, value: bool):
        """Encode boolean"""
        self._write_byte((self.SIMPLE << 5) | (21 if value else 20))
    
    def encode_null(self):
        """Encode null"""
        self._write_byte((self.SIMPLE << 5) | 22)
    
    def encode_value(self, value: Any):
        """Encode any value"""
        if value is None:
            self.encode_null()
        elif isinstance(value, bool):
            self.encode_bool(value)
        elif isinstance(value, int):
            self.encode_int(value)
        elif isinstance(value, float):
            self.encode_float(value)
        elif isinstance(value, bytes):
            self.encode_bytes(value)
        elif isinstance(value, str):
            self.encode_string(value)
        elif isinstance(value, list):
            self.encode_array(value)
        elif isinstance(value, dict):
            self.encode_map(value)
        elif isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], int):
            # Tagged value: (tag, value)
            self.encode_tag(value[0], value[1])
        else:
            # Fallback: convert to string
            self.encode_string(str(value))
    
    def get_bytes(self) -> bytes:
        """Get encoded bytes"""
        return bytes(self._buffer)
    
    def reset(self):
        """Reset buffer"""
        self._buffer = bytearray()


# ============== CBOR DECODER ==============

class CBORDecoder:
    """Canonical CBOR Decoder"""
    
    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0
    
    def _read_byte(self) -> int:
        if self._pos >= len(self._data):
            raise ValueError("Unexpected end of data")
        b = self._data[self._pos]
        self._pos += 1
        return b
    
    def _read_bytes(self, n: int) -> bytes:
        if self._pos + n > len(self._data):
            raise ValueError("Unexpected end of data")
        data = self._data[self._pos:self._pos + n]
        self._pos += n
        return data
    
    def _decode_head(self) -> Tuple[int, int]:
        """Decode CBOR head, return (major_type, value)"""
        b = self._read_byte()
        major_type = b >> 5
        additional = b & 0x1F
        
        if additional < 24:
            value = additional
        elif additional == 24:
            value = self._read_byte()
        elif additional == 25:
            value = struct.unpack(">H", self._read_bytes(2))[0]
        elif additional == 26:
            value = struct.unpack(">I", self._read_bytes(4))[0]
        elif additional == 27:
            value = struct.unpack(">Q", self._read_bytes(8))[0]
        else:
            raise ValueError(f"Invalid additional info: {additional}")
        
        return major_type, value
    
    def decode(self) -> Any:
        """Decode next value"""
        major_type, value = self._decode_head()
        
        if major_type == 0:  # Unsigned int
            return value
        elif major_type == 1:  # Negative int
            return -1 - value
        elif major_type == 2:  # Byte string
            return self._read_bytes(value)
        elif major_type == 3:  # Text string
            return self._read_bytes(value).decode('utf-8')
        elif major_type == 4:  # Array
            return [self.decode() for _ in range(value)]
        elif major_type == 5:  # Map
            result = {}
            for _ in range(value):
                k = self.decode()
                v = self.decode()
                result[k] = v
            return result
        elif major_type == 6:  # Tag
            tag = value
            content = self.decode()
            return (tag, content)
        elif major_type == 7:  # Simple/float
            if value == 20:
                return False
            elif value == 21:
                return True
            elif value == 22:
                return None
            elif value == 27:
                # Rewind and read float
                self._pos -= 1
                self._read_byte()  # Skip the head byte we already read
                return struct.unpack(">d", self._read_bytes(8))[0]
            else:
                raise ValueError(f"Unknown simple value: {value}")
        else:
            raise ValueError(f"Unknown major type: {major_type}")


# ============== HSU-SPEC NODE STRUCTURES ==============

@dataclass
class IdentityNode:
    """Layer 1 - Identity Node (Tag 60000)"""
    id: bytes  # 32-byte hash
    public_key: bytes
    signature: Optional[bytes] = None
    owner_id: Optional[bytes] = None  # For agents
    
    def to_cbor(self) -> bytes:
        encoder = CBOREncoder()
        data = {
            0: self.id,
            1: self.public_key,
        }
        if self.signature:
            data[2] = self.signature
        if self.owner_id:
            data[3] = self.owner_id
        
        encoder.encode_tag(CBORTag.IDENTITY_NODE, data)
        return encoder.get_bytes()
    
    @classmethod
    def from_cbor(cls, data: bytes) -> "IdentityNode":
        decoder = CBORDecoder(data)
        tag, content = decoder.decode()
        assert tag == CBORTag.IDENTITY_NODE
        return cls(
            id=content[0],
            public_key=content[1],
            signature=content.get(2),
            owner_id=content.get(3),
        )


@dataclass
class UserDataNode:
    """Layer 2 - User Data Sphere Node (Tag 60001)"""
    id: bytes  # 32-byte hash
    encrypted_payload: bytes
    links: List[bytes]  # Child node IDs
    timestamp: int
    user_version: int = 1
    schema_version: int = 1
    
    def to_cbor(self) -> bytes:
        encoder = CBOREncoder()
        data = {
            0: self.id,
            1: self.encrypted_payload,
            2: self.links,
            3: {
                0: self.timestamp,
                1: self.user_version,
                2: self.schema_version,
            }
        }
        encoder.encode_tag(CBORTag.USER_DATA_NODE, data)
        return encoder.get_bytes()
    
    @classmethod
    def from_cbor(cls, data: bytes) -> "UserDataNode":
        decoder = CBORDecoder(data)
        tag, content = decoder.decode()
        assert tag == CBORTag.USER_DATA_NODE
        meta = content[3]
        return cls(
            id=content[0],
            encrypted_payload=content[1],
            links=content[2],
            timestamp=meta[0],
            user_version=meta.get(1, 1),
            schema_version=meta.get(2, 1),
        )


@dataclass
class SemanticVector:
    """Semantic Vector (Tag 60007)"""
    values: List[float]
    
    def to_cbor(self) -> bytes:
        encoder = CBOREncoder()
        encoder.encode_tag(CBORTag.SEMANTIC_VECTOR, self.values)
        return encoder.get_bytes()


@dataclass
class ClusterMetadata:
    """Cluster Metadata (Tag 60008)"""
    centroid_id: bytes
    cluster_neighbors: List[bytes]
    
    def to_cbor(self) -> bytes:
        encoder = CBOREncoder()
        data = {
            0: self.centroid_id,
            1: self.cluster_neighbors,
        }
        encoder.encode_tag(CBORTag.CLUSTER_METADATA, data)
        return encoder.get_bytes()


@dataclass
class AgentDataNode:
    """Layer 3 - Agent Sphere Node (Tag 60002)"""
    id: bytes
    encrypted_agent_payload: bytes
    links: List[bytes]
    semantic_vector: Optional[List[float]] = None
    cluster_id: Optional[bytes] = None
    agent_version: int = 1
    permissions: Optional[Dict[str, Any]] = None
    
    def to_cbor(self) -> bytes:
        encoder = CBOREncoder()
        meta = {
            2: self.agent_version,
        }
        if self.semantic_vector:
            # Embed semantic vector with tag
            meta[0] = (CBORTag.SEMANTIC_VECTOR, self.semantic_vector)
        if self.cluster_id:
            meta[1] = self.cluster_id
        if self.permissions:
            meta[3] = self.permissions
        
        data = {
            0: self.id,
            1: self.encrypted_agent_payload,
            2: self.links,
            3: meta,
        }
        encoder.encode_tag(CBORTag.AGENT_DATA_NODE, data)
        return encoder.get_bytes()


@dataclass
class CoordinationNode:
    """Layer 4 - Coordination Node (Tag 60003)"""
    id: bytes
    encrypted_interaction_record: bytes
    links: List[bytes]
    sender_id: bytes
    receiver_id: bytes
    timestamp: int
    interaction_type: InteractionType
    
    def to_cbor(self) -> bytes:
        encoder = CBOREncoder()
        data = {
            0: self.id,
            1: self.encrypted_interaction_record,
            2: self.links,
            3: {
                0: self.sender_id,
                1: self.receiver_id,
                2: self.timestamp,
                3: int(self.interaction_type),
            }
        }
        encoder.encode_tag(CBORTag.COORDINATION_NODE, data)
        return encoder.get_bytes()


@dataclass
class OwnershipEntry:
    """Ownership entry for User Block"""
    agent_id: bytes
    signature: bytes
    
    def to_dict(self) -> Dict[int, bytes]:
        return {0: self.agent_id, 1: self.signature}


@dataclass
class UserBlock:
    """Layer 5 - User Block Class U (Tag 60004)"""
    version: int
    prev_hash: bytes  # 32 bytes
    user_id: bytes
    sphere_root_l2: bytes
    ownership_set: List[OwnershipEntry]
    timestamp: int
    
    def to_cbor(self) -> bytes:
        encoder = CBOREncoder()
        data = {
            0: self.version,
            1: self.prev_hash,
            2: self.user_id,
            3: self.sphere_root_l2,
            4: [o.to_dict() for o in self.ownership_set],
            5: self.timestamp,
        }
        encoder.encode_tag(CBORTag.USER_BLOCK, data)
        return encoder.get_bytes()
    
    def compute_hash(self) -> bytes:
        """Compute block hash: SHA256(canonical CBOR)"""
        return hashlib.sha256(self.to_cbor()).digest()


@dataclass
class AgentBlock:
    """Layer 5 - Agent Block Class A (Tag 60005)"""
    version: int
    prev_hash: bytes
    agent_id: bytes
    cluster_id: bytes
    sphere_root_l3: bytes
    contracts: List[bytes]  # Contract node IDs
    timestamp: int
    
    def to_cbor(self) -> bytes:
        encoder = CBOREncoder()
        data = {
            0: self.version,
            1: self.prev_hash,
            2: self.agent_id,
            3: self.cluster_id,
            4: self.sphere_root_l3,
            5: self.contracts,
            6: self.timestamp,
        }
        encoder.encode_tag(CBORTag.AGENT_BLOCK, data)
        return encoder.get_bytes()
    
    def compute_hash(self) -> bytes:
        """Compute block hash: SHA256(canonical CBOR)"""
        return hashlib.sha256(self.to_cbor()).digest()


@dataclass
class SmartContractNode:
    """Smart Contract Object (Tag 60006)"""
    contract_id: bytes
    rules: List[Dict[int, Any]]
    signatures: List[bytes]
    
    def to_cbor(self) -> bytes:
        encoder = CBOREncoder()
        data = {
            0: self.contract_id,
            1: self.rules,
            2: self.signatures,
        }
        encoder.encode_tag(CBORTag.SMART_CONTRACT, data)
        return encoder.get_bytes()


# ============== NODE ID COMPUTATION ==============

def compute_node_id(node_cbor: bytes) -> bytes:
    """
    Compute NodeID from canonical CBOR encoding.
    
    function ComputeNodeID(node):
        bytes := CanonicalCBOR(node)
        return SHA256(bytes)
    """
    return hashlib.sha256(node_cbor).digest()


# ============== CODEC MANAGER ==============

class CBORCodec:
    """
    CBOR Codec Manager
    
    Provides high-level encoding/decoding for all HSU-Spec structures.
    """
    
    @staticmethod
    def encode(value: Any) -> bytes:
        """Encode any value to CBOR"""
        encoder = CBOREncoder()
        encoder.encode_value(value)
        return encoder.get_bytes()
    
    @staticmethod
    def decode(data: bytes) -> Any:
        """Decode CBOR to value"""
        decoder = CBORDecoder(data)
        return decoder.decode()
    
    @staticmethod
    def encode_identity_node(
        public_key: bytes,
        signature: Optional[bytes] = None,
        owner_id: Optional[bytes] = None,
    ) -> Tuple[bytes, bytes]:
        """
        Encode Layer 1 Identity Node.
        Returns (node_id, cbor_bytes)
        """
        # Compute ID from public key
        node_id = hashlib.sha256(b"L1-IDENTITY" + public_key).digest()
        
        node = IdentityNode(
            id=node_id,
            public_key=public_key,
            signature=signature,
            owner_id=owner_id,
        )
        cbor_bytes = node.to_cbor()
        return node_id, cbor_bytes
    
    @staticmethod
    def encode_user_data_node(
        encrypted_payload: bytes,
        links: List[bytes],
        timestamp: int,
    ) -> Tuple[bytes, bytes]:
        """
        Encode Layer 2 User Data Node.
        Returns (node_id, cbor_bytes)
        """
        # Compute ID from payload and links
        content = encrypted_payload + b"".join(links)
        node_id = hashlib.sha256(b"L2-USER-DATA" + content).digest()
        
        node = UserDataNode(
            id=node_id,
            encrypted_payload=encrypted_payload,
            links=links,
            timestamp=timestamp,
        )
        cbor_bytes = node.to_cbor()
        return node_id, cbor_bytes
    
    @staticmethod
    def encode_agent_data_node(
        encrypted_payload: bytes,
        links: List[bytes],
        semantic_vector: Optional[List[float]] = None,
        cluster_id: Optional[bytes] = None,
    ) -> Tuple[bytes, bytes]:
        """
        Encode Layer 3 Agent Data Node.
        Returns (node_id, cbor_bytes)
        """
        content = encrypted_payload + b"".join(links)
        node_id = hashlib.sha256(b"L3-AGENT-DATA" + content).digest()
        
        node = AgentDataNode(
            id=node_id,
            encrypted_agent_payload=encrypted_payload,
            links=links,
            semantic_vector=semantic_vector,
            cluster_id=cluster_id,
        )
        cbor_bytes = node.to_cbor()
        return node_id, cbor_bytes
    
    @staticmethod
    def encode_coordination_node(
        encrypted_record: bytes,
        links: List[bytes],
        sender_id: bytes,
        receiver_id: bytes,
        timestamp: int,
        interaction_type: InteractionType,
    ) -> Tuple[bytes, bytes]:
        """
        Encode Layer 4 Coordination Node.
        Returns (node_id, cbor_bytes)
        """
        content = encrypted_record + sender_id + receiver_id
        node_id = hashlib.sha256(b"L4-COORD" + content).digest()
        
        node = CoordinationNode(
            id=node_id,
            encrypted_interaction_record=encrypted_record,
            links=links,
            sender_id=sender_id,
            receiver_id=receiver_id,
            timestamp=timestamp,
            interaction_type=interaction_type,
        )
        cbor_bytes = node.to_cbor()
        return node_id, cbor_bytes
    
    @staticmethod
    def encode_user_block(
        version: int,
        prev_hash: bytes,
        user_id: bytes,
        sphere_root: bytes,
        ownership_set: List[Tuple[bytes, bytes]],
        timestamp: int,
    ) -> Tuple[bytes, bytes]:
        """
        Encode Layer 5 User Block.
        Returns (block_hash, cbor_bytes)
        """
        ownership_entries = [
            OwnershipEntry(agent_id=a, signature=s)
            for a, s in ownership_set
        ]
        
        block = UserBlock(
            version=version,
            prev_hash=prev_hash,
            user_id=user_id,
            sphere_root_l2=sphere_root,
            ownership_set=ownership_entries,
            timestamp=timestamp,
        )
        cbor_bytes = block.to_cbor()
        block_hash = block.compute_hash()
        return block_hash, cbor_bytes
    
    @staticmethod
    def encode_agent_block(
        version: int,
        prev_hash: bytes,
        agent_id: bytes,
        cluster_id: bytes,
        sphere_root: bytes,
        contracts: List[bytes],
        timestamp: int,
    ) -> Tuple[bytes, bytes]:
        """
        Encode Layer 5 Agent Block.
        Returns (block_hash, cbor_bytes)
        """
        block = AgentBlock(
            version=version,
            prev_hash=prev_hash,
            agent_id=agent_id,
            cluster_id=cluster_id,
            sphere_root_l3=sphere_root,
            contracts=contracts,
            timestamp=timestamp,
        )
        cbor_bytes = block.to_cbor()
        block_hash = block.compute_hash()
        return block_hash, cbor_bytes


# Global codec instance
cbor_codec = CBORCodec()


# ============== CONVENIENCE FUNCTIONS ==============

def encode_to_cbor(value: Any) -> bytes:
    """Encode value to CBOR"""
    return cbor_codec.encode(value)


def decode_from_cbor(data: bytes) -> Any:
    """Decode CBOR to value"""
    return cbor_codec.decode(data)


def compute_canonical_hash(value: Any) -> bytes:
    """Compute SHA-256 hash of canonical CBOR encoding"""
    cbor_bytes = encode_to_cbor(value)
    return hashlib.sha256(cbor_bytes).digest()
