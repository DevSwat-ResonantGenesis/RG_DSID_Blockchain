"""
Domain-Separated Hashing System (HSU-Spec Section 3)
=====================================================

Implements cryptographic domain separation for all 5 layers:
- L1: Cryptographic Identity (User + Agent)
- L2: User Data Sphere
- L3: Agent Sphere
- L4: Coordination Layer
- L5: Blockchain Registry (User + Agent blocks)

Formula: H_d(x) = H(d ∥ x)
Where d is a unique domain constant ensuring independence of layers.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum


class HashDomain(Enum):
    """Domain prefixes for layer-separated hashing"""
    # Layer 1 - Cryptographic Identity
    L1_USER = "L1-USER"
    L1_AGENT = "L1-AGENT"
    
    # Layer 2 - User Data Sphere
    L2_USER_SPHERE = "L2-USER-SPHERE"
    L2_USER_NODE = "L2-USER-NODE"
    
    # Layer 3 - Agent Sphere
    L3_AGENT_SPHERE = "L3-AGENT-SPHERE"
    L3_AGENT_NODE = "L3-AGENT-NODE"
    L3_CLUSTER = "L3-CLUSTER"
    
    # Layer 4 - Coordination
    L4_COORD = "L4-COORD"
    L4_INTERACTION = "L4-INTERACTION"
    L4_DELEGATION = "L4-DELEGATION"
    
    # Layer 5 - Blockchain Registry
    L5_UBLOCK = "L5-UBLOCK"
    L5_ABLOCK = "L5-ABLOCK"
    L5_TRANSACTION = "L5-TRANSACTION"
    
    # Special domains
    OWNERSHIP = "OWNERSHIP"
    CONTRACT = "CONTRACT"
    MERKLE = "MERKLE"
    GLOBAL = "GLOBAL"


@dataclass
class DomainHash:
    """Result of a domain-separated hash operation"""
    domain: str
    input_hash: str  # Hash of input data only
    domain_hash: str  # H(domain ∥ input)
    layer: int
    
    def __str__(self) -> str:
        return self.domain_hash
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "input_hash": self.input_hash,
            "domain_hash": self.domain_hash,
            "layer": self.layer,
        }


class DomainHasher:
    """
    Domain-Separated Hasher
    
    Implements H_d(x) = H(d ∥ x) for cryptographic domain separation.
    This ensures hashes from different layers cannot collide.
    
    HSU-Spec Section 3 compliance:
    - H_1(x) = H("L1-USER" ∥ x)
    - H_1A(x) = H("L1-AGENT" ∥ x)
    - H_2(x) = H("L2-USER-SPHERE" ∥ x)
    - H_3(x) = H("L3-AGENT-SPHERE" ∥ x)
    - H_4(x) = H("L4-COORD" ∥ x)
    - H_5U(x) = H("L5-UBLOCK" ∥ x)
    - H_5A(x) = H("L5-ABLOCK" ∥ x)
    """
    
    LAYER_MAP = {
        HashDomain.L1_USER: 1,
        HashDomain.L1_AGENT: 1,
        HashDomain.L2_USER_SPHERE: 2,
        HashDomain.L2_USER_NODE: 2,
        HashDomain.L3_AGENT_SPHERE: 3,
        HashDomain.L3_AGENT_NODE: 3,
        HashDomain.L3_CLUSTER: 3,
        HashDomain.L4_COORD: 4,
        HashDomain.L4_INTERACTION: 4,
        HashDomain.L4_DELEGATION: 4,
        HashDomain.L5_UBLOCK: 5,
        HashDomain.L5_ABLOCK: 5,
        HashDomain.L5_TRANSACTION: 5,
        HashDomain.OWNERSHIP: 1,
        HashDomain.CONTRACT: 3,
        HashDomain.MERKLE: 0,
        HashDomain.GLOBAL: 0,
    }
    
    @staticmethod
    def _to_bytes(data: Any) -> bytes:
        """Convert any data to bytes for hashing"""
        if isinstance(data, bytes):
            return data
        elif isinstance(data, str):
            return data.encode('utf-8')
        elif isinstance(data, dict):
            return json.dumps(data, sort_keys=True).encode('utf-8')
        elif isinstance(data, (list, tuple)):
            return json.dumps(list(data), sort_keys=True).encode('utf-8')
        else:
            return str(data).encode('utf-8')
    
    @staticmethod
    def hash(domain: HashDomain, data: Any) -> DomainHash:
        """
        Compute domain-separated hash: H_d(x) = H(d ∥ x)
        
        Args:
            domain: The hash domain (layer identifier)
            data: Data to hash (bytes, str, dict, or any serializable)
        
        Returns:
            DomainHash with both input hash and domain-separated hash
        """
        data_bytes = DomainHasher._to_bytes(data)
        domain_prefix = domain.value.encode('utf-8')
        
        # Input hash (without domain)
        input_hash = hashlib.sha256(data_bytes).hexdigest()
        
        # Domain-separated hash: H(domain ∥ data)
        domain_hash = hashlib.sha256(domain_prefix + data_bytes).hexdigest()
        
        layer = DomainHasher.LAYER_MAP.get(domain, 0)
        
        return DomainHash(
            domain=domain.value,
            input_hash=input_hash,
            domain_hash=domain_hash,
            layer=layer,
        )
    
    @staticmethod
    def hash_raw(domain: HashDomain, data: Any) -> str:
        """
        Compute domain-separated hash and return just the hash string.
        
        Convenience method for when you only need the hash value.
        """
        return DomainHasher.hash(domain, data).domain_hash
    
    # ==========================================
    # LAYER 1 - CRYPTOGRAPHIC IDENTITY
    # ==========================================
    
    @staticmethod
    def hash_user_identity(public_key: Union[str, bytes]) -> DomainHash:
        """
        H_1(x) = H("L1-USER" ∥ public_key)
        
        Generate user identity hash from public key.
        """
        return DomainHasher.hash(HashDomain.L1_USER, public_key)
    
    @staticmethod
    def hash_agent_identity(public_key: Union[str, bytes]) -> DomainHash:
        """
        H_1A(x) = H("L1-AGENT" ∥ public_key)
        
        Generate agent identity hash from public key.
        """
        return DomainHasher.hash(HashDomain.L1_AGENT, public_key)
    
    @staticmethod
    def hash_ownership(user_id: str, agent_id: str, signature: str) -> DomainHash:
        """
        Hash ownership binding: H("OWNERSHIP" ∥ user_id ∥ agent_id ∥ signature)
        """
        data = f"{user_id}:{agent_id}:{signature}"
        return DomainHasher.hash(HashDomain.OWNERSHIP, data)
    
    # ==========================================
    # LAYER 2 - USER DATA SPHERE
    # ==========================================
    
    @staticmethod
    def hash_user_sphere(payload: Any, child_hashes: List[str]) -> DomainHash:
        """
        H_2(x) = H("L2-USER-SPHERE" ∥ payload ∥ children)
        
        Generate user sphere root hash.
        SphereRoot_U = H_2(payload_U0 ∥ ID_U1 ∥ ID_U2 ∥ ... ∥ ID_Un)
        """
        payload_bytes = DomainHasher._to_bytes(payload)
        children_bytes = "".join(child_hashes).encode('utf-8')
        combined = payload_bytes + children_bytes
        return DomainHasher.hash(HashDomain.L2_USER_SPHERE, combined)
    
    @staticmethod
    def hash_user_node(payload: Any, links: List[str] = None) -> DomainHash:
        """
        Hash a user data node.
        Node_Ui := <payload_i, links_i[]>
        ID_Ui := H_2(encode(Node_Ui))
        """
        node_data = {
            "payload": DomainHasher._to_bytes(payload).hex(),
            "links": links or [],
        }
        return DomainHasher.hash(HashDomain.L2_USER_NODE, node_data)
    
    # ==========================================
    # LAYER 3 - AGENT SPHERE
    # ==========================================
    
    @staticmethod
    def hash_agent_sphere(
        payload: Any,
        semantic_vector: Optional[List[float]] = None,
        child_hashes: List[str] = None,
    ) -> DomainHash:
        """
        H_3(x) = H("L3-AGENT-SPHERE" ∥ payload ∥ semantic ∥ children)
        
        Generate agent sphere root hash with semantic embedding.
        """
        data = {
            "payload": DomainHasher._to_bytes(payload).hex(),
            "semantic": semantic_vector or [],
            "children": child_hashes or [],
        }
        return DomainHasher.hash(HashDomain.L3_AGENT_SPHERE, data)
    
    @staticmethod
    def hash_cluster(cluster_id: str, agent_hashes: List[str]) -> DomainHash:
        """
        Hash a cluster of agents.
        """
        data = {
            "cluster_id": cluster_id,
            "agents": sorted(agent_hashes),
        }
        return DomainHasher.hash(HashDomain.L3_CLUSTER, data)
    
    # ==========================================
    # LAYER 4 - COORDINATION
    # ==========================================
    
    @staticmethod
    def hash_interaction(
        sender_id: str,
        receiver_id: str,
        timestamp: int,
        payload: Any,
    ) -> DomainHash:
        """
        H_4(x) = H("L4-COORD" ∥ interaction)
        
        Hash an interaction record.
        Record := <senderID, receiverID, timestamp, payload_interaction>
        """
        data = {
            "sender": sender_id,
            "receiver": receiver_id,
            "timestamp": timestamp,
            "payload": DomainHasher._to_bytes(payload).hex(),
        }
        return DomainHasher.hash(HashDomain.L4_INTERACTION, data)
    
    @staticmethod
    def hash_delegation(
        from_agent: str,
        to_agent: str,
        task_hash: str,
        timestamp: int,
    ) -> DomainHash:
        """
        Hash an agent-to-agent delegation.
        """
        data = {
            "from": from_agent,
            "to": to_agent,
            "task": task_hash,
            "timestamp": timestamp,
        }
        return DomainHasher.hash(HashDomain.L4_DELEGATION, data)
    
    @staticmethod
    def hash_coordination_root(interaction_hashes: List[str]) -> DomainHash:
        """
        InteractionRoot = H_4(Node_I0 ∥ Node_I1 ∥ ... ∥ Node_Ik)
        """
        combined = "".join(interaction_hashes)
        return DomainHasher.hash(HashDomain.L4_COORD, combined)
    
    # ==========================================
    # LAYER 5 - BLOCKCHAIN REGISTRY
    # ==========================================
    
    @staticmethod
    def hash_user_block(
        version: int,
        prev_hash: Optional[str],
        user_id: str,
        sphere_root: str,
        ownership_set: List[str],
        timestamp: int,
    ) -> DomainHash:
        """
        H_5U(x) = H("L5-UBLOCK" ∥ encode(UserBlock))
        
        Hash a User Block (Class U).
        """
        block_data = {
            "version": version,
            "prev_hash": prev_hash or "genesis",
            "user_id": user_id,
            "sphere_root": sphere_root,
            "ownership_set": sorted(ownership_set),
            "timestamp": timestamp,
        }
        return DomainHasher.hash(HashDomain.L5_UBLOCK, block_data)
    
    @staticmethod
    def hash_agent_block(
        version: int,
        prev_hash: Optional[str],
        agent_id: str,
        cluster_id: str,
        sphere_root: str,
        contracts: List[str],
        timestamp: int,
    ) -> DomainHash:
        """
        H_5A(x) = H("L5-ABLOCK" ∥ encode(AgentBlock))
        
        Hash an Agent Block (Class A).
        """
        block_data = {
            "version": version,
            "prev_hash": prev_hash or "genesis",
            "agent_id": agent_id,
            "cluster_id": cluster_id,
            "sphere_root": sphere_root,
            "contracts": sorted(contracts),
            "timestamp": timestamp,
        }
        return DomainHasher.hash(HashDomain.L5_ABLOCK, block_data)
    
    @staticmethod
    def hash_transaction(
        tx_type: str,
        from_id: str,
        to_id: str,
        payload: Any,
        timestamp: int,
    ) -> DomainHash:
        """
        Hash a blockchain transaction.
        """
        tx_data = {
            "type": tx_type,
            "from": from_id,
            "to": to_id,
            "payload": DomainHasher._to_bytes(payload).hex(),
            "timestamp": timestamp,
        }
        return DomainHasher.hash(HashDomain.L5_TRANSACTION, tx_data)
    
    # ==========================================
    # GLOBAL FINGERPRINT
    # ==========================================
    
    @staticmethod
    def compute_global_fingerprint(
        h1_identity: str,
        h2_user_sphere: str,
        h3_agent_sphere: str,
        h4_coordination: str,
        h5_blockchain: str,
    ) -> DomainHash:
        """
        Compute global cryptographic fingerprint of entire user-agent universe.
        
        h_final = H(h1 ∥ h2 ∥ h3 ∥ h4 ∥ h5)
        
        This is the ultimate proof of the complete state.
        """
        combined = f"{h1_identity}{h2_user_sphere}{h3_agent_sphere}{h4_coordination}{h5_blockchain}"
        return DomainHasher.hash(HashDomain.GLOBAL, combined)
    
    # ==========================================
    # MERKLE OPERATIONS
    # ==========================================
    
    @staticmethod
    def compute_merkle_root(hashes: List[str]) -> str:
        """
        Compute Merkle root from a list of hashes.
        Uses domain separation for Merkle nodes.
        """
        if not hashes:
            return DomainHasher.hash_raw(HashDomain.MERKLE, "empty")
        
        if len(hashes) == 1:
            return hashes[0]
        
        # Pad to even number
        working = hashes.copy()
        if len(working) % 2 == 1:
            working.append(working[-1])
        
        # Build tree
        while len(working) > 1:
            new_level = []
            for i in range(0, len(working), 2):
                combined = working[i] + working[i + 1]
                new_hash = DomainHasher.hash_raw(HashDomain.MERKLE, combined)
                new_level.append(new_hash)
            working = new_level
        
        return working[0]
    
    @staticmethod
    def compute_merkle_proof(
        hashes: List[str],
        target_index: int,
    ) -> List[Dict[str, str]]:
        """
        Compute Merkle proof for a specific hash.
        """
        if not hashes or target_index >= len(hashes):
            return []
        
        proof = []
        working = hashes.copy()
        
        if len(working) % 2 == 1:
            working.append(working[-1])
        
        idx = target_index
        
        while len(working) > 1:
            new_level = []
            for i in range(0, len(working), 2):
                if i == idx or i + 1 == idx:
                    sibling_idx = i + 1 if i == idx else i
                    proof.append({
                        "hash": working[sibling_idx],
                        "position": "right" if sibling_idx > idx else "left",
                    })
                    idx = i // 2
                
                combined = working[i] + working[i + 1]
                new_hash = DomainHasher.hash_raw(HashDomain.MERKLE, combined)
                new_level.append(new_hash)
            
            working = new_level
        
        return proof
    
    @staticmethod
    def verify_merkle_proof(
        target_hash: str,
        merkle_root: str,
        proof: List[Dict[str, str]],
    ) -> bool:
        """
        Verify a Merkle proof.
        """
        current = target_hash
        
        for step in proof:
            sibling = step["hash"]
            if step["position"] == "left":
                combined = sibling + current
            else:
                combined = current + sibling
            current = DomainHasher.hash_raw(HashDomain.MERKLE, combined)
        
        return current == merkle_root


# Global instance
domain_hasher = DomainHasher()


# Convenience functions
def hash_l1_user(public_key: Union[str, bytes]) -> str:
    """H_1(x) = H("L1-USER" ∥ x)"""
    return domain_hasher.hash_user_identity(public_key).domain_hash


def hash_l1_agent(public_key: Union[str, bytes]) -> str:
    """H_1A(x) = H("L1-AGENT" ∥ x)"""
    return domain_hasher.hash_agent_identity(public_key).domain_hash


def hash_l2_sphere(payload: Any, children: List[str] = None) -> str:
    """H_2(x) = H("L2-USER-SPHERE" ∥ x)"""
    return domain_hasher.hash_user_sphere(payload, children or []).domain_hash


def hash_l3_sphere(payload: Any, semantic: List[float] = None, children: List[str] = None) -> str:
    """H_3(x) = H("L3-AGENT-SPHERE" ∥ x)"""
    return domain_hasher.hash_agent_sphere(payload, semantic, children).domain_hash


def hash_l4_interaction(sender: str, receiver: str, timestamp: int, payload: Any) -> str:
    """H_4(x) = H("L4-COORD" ∥ x)"""
    return domain_hasher.hash_interaction(sender, receiver, timestamp, payload).domain_hash


def hash_l5_ublock(version: int, prev: str, user_id: str, sphere: str, ownership: List[str], ts: int) -> str:
    """H_5U(x) = H("L5-UBLOCK" ∥ x)"""
    return domain_hasher.hash_user_block(version, prev, user_id, sphere, ownership, ts).domain_hash


def hash_l5_ablock(version: int, prev: str, agent_id: str, cluster: str, sphere: str, contracts: List[str], ts: int) -> str:
    """H_5A(x) = H("L5-ABLOCK" ∥ x)"""
    return domain_hasher.hash_agent_block(version, prev, agent_id, cluster, sphere, contracts, ts).domain_hash


# ============== FINGERPRINT (H_final) ==============

@dataclass
class UniverseFingerprint:
    """
    Hash Universe Fingerprint
    
    Global hash representing the combined identity of all layers:
    H_final = H(H1 ∥ H2 ∥ H3 ∥ H4 ∥ H5)
    
    Equivalent to a root-of-roots.
    """
    h1: str  # Layer 1 identity hash
    h2: str  # Layer 2 user sphere hash
    h3: str  # Layer 3 agent sphere hash
    h4: str  # Layer 4 coordination hash
    h5: str  # Layer 5 blockchain hash
    fingerprint: str  # H_final
    timestamp: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "h1": self.h1,
            "h2": self.h2,
            "h3": self.h3,
            "h4": self.h4,
            "h5": self.h5,
            "fingerprint": self.fingerprint,
            "timestamp": self.timestamp,
        }


def compute_fingerprint(
    h1: str,
    h2: str,
    h3: str,
    h4: str,
    h5: str,
) -> UniverseFingerprint:
    """
    Compute the Hash Universe Fingerprint.
    
    H_final = H(H1 ∥ H2 ∥ H3 ∥ H4 ∥ H5)
    
    This is the root-of-roots representing the entire universe state.
    
    Args:
        h1: Layer 1 identity hash (user or agent)
        h2: Layer 2 user sphere root hash
        h3: Layer 3 agent sphere root hash
        h4: Layer 4 coordination root hash
        h5: Layer 5 blockchain head hash
    
    Returns:
        UniverseFingerprint with all layer hashes and final fingerprint
    """
    import time
    
    # Concatenate all layer hashes
    combined = h1 + h2 + h3 + h4 + h5
    
    # Compute H_final = H("FINGERPRINT" ∥ H1 ∥ H2 ∥ H3 ∥ H4 ∥ H5)
    domain = "FINGERPRINT"
    data = domain.encode() + combined.encode()
    fingerprint = hashlib.sha256(data).hexdigest()
    
    return UniverseFingerprint(
        h1=h1,
        h2=h2,
        h3=h3,
        h4=h4,
        h5=h5,
        fingerprint=fingerprint,
        timestamp=int(time.time()),
    )


def compute_user_fingerprint(
    user_public_key: Union[str, bytes],
    user_sphere_root: str,
    agent_sphere_roots: List[str],
    coordination_root: str,
    blockchain_head: str,
) -> UniverseFingerprint:
    """
    Compute fingerprint for a user's entire universe.
    
    Args:
        user_public_key: User's public key
        user_sphere_root: Root hash of user's L2 sphere
        agent_sphere_roots: List of agent L3 sphere roots owned by user
        coordination_root: Root hash of L4 coordination layer
        blockchain_head: Current blockchain head hash
    
    Returns:
        UniverseFingerprint for the user's universe
    """
    # H1: User identity
    h1 = hash_l1_user(user_public_key)
    
    # H2: User sphere
    h2 = user_sphere_root
    
    # H3: Combined agent spheres (Merkle root of all agent roots)
    if agent_sphere_roots:
        combined_agents = "".join(sorted(agent_sphere_roots))
        h3 = hashlib.sha256(("L3-COMBINED" + combined_agents).encode()).hexdigest()
    else:
        h3 = hashlib.sha256(b"L3-EMPTY").hexdigest()
    
    # H4: Coordination
    h4 = coordination_root
    
    # H5: Blockchain
    h5 = blockchain_head
    
    return compute_fingerprint(h1, h2, h3, h4, h5)


def compute_agent_fingerprint(
    agent_public_key: Union[str, bytes],
    owner_sphere_root: str,
    agent_sphere_root: str,
    coordination_root: str,
    blockchain_head: str,
) -> UniverseFingerprint:
    """
    Compute fingerprint for an agent's universe.
    
    Args:
        agent_public_key: Agent's public key
        owner_sphere_root: Root hash of owner's L2 sphere
        agent_sphere_root: Root hash of agent's L3 sphere
        coordination_root: Root hash of L4 coordination layer
        blockchain_head: Current blockchain head hash
    
    Returns:
        UniverseFingerprint for the agent's universe
    """
    # H1: Agent identity
    h1 = hash_l1_agent(agent_public_key)
    
    # H2: Owner's sphere (agent inherits owner context)
    h2 = owner_sphere_root
    
    # H3: Agent sphere
    h3 = agent_sphere_root
    
    # H4: Coordination
    h4 = coordination_root
    
    # H5: Blockchain
    h5 = blockchain_head
    
    return compute_fingerprint(h1, h2, h3, h4, h5)


def verify_fingerprint(
    fingerprint: UniverseFingerprint,
    expected_hash: str,
) -> bool:
    """
    Verify a fingerprint matches expected hash.
    
    Args:
        fingerprint: The fingerprint to verify
        expected_hash: Expected H_final value
    
    Returns:
        True if fingerprint matches
    """
    return fingerprint.fingerprint == expected_hash


def compare_fingerprints(
    fp1: UniverseFingerprint,
    fp2: UniverseFingerprint,
) -> Dict[str, Any]:
    """
    Compare two fingerprints and identify differences.
    
    Args:
        fp1: First fingerprint
        fp2: Second fingerprint
    
    Returns:
        Dict with comparison results
    """
    differences = []
    
    if fp1.h1 != fp2.h1:
        differences.append("L1_identity")
    if fp1.h2 != fp2.h2:
        differences.append("L2_user_sphere")
    if fp1.h3 != fp2.h3:
        differences.append("L3_agent_sphere")
    if fp1.h4 != fp2.h4:
        differences.append("L4_coordination")
    if fp1.h5 != fp2.h5:
        differences.append("L5_blockchain")
    
    return {
        "match": fp1.fingerprint == fp2.fingerprint,
        "fingerprint_match": fp1.fingerprint == fp2.fingerprint,
        "differences": differences,
        "layers_changed": len(differences),
    }
