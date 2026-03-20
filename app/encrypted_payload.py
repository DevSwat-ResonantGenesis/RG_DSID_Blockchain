"""
Encrypted Payload System (HSU-Spec Layer 2-3)
==============================================

Implements AES-256 encryption for node payloads:
- User data encryption (Layer 2)
- Agent state encryption (Layer 3)
- Key derivation from wallet keys
- Secure payload storage

Formula:
Enc_k(x) → ciphertext
Dec_k(ciphertext) → x
"""

import hashlib
import secrets
import base64
import json
import logging
from typing import Any, Dict, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime

# Try to import cryptography for AES
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logging.warning("cryptography library not available for AES encryption")

logger = logging.getLogger(__name__)


@dataclass
class EncryptedPayload:
    """An encrypted payload with metadata"""
    ciphertext: bytes
    iv: bytes  # Initialization vector
    salt: bytes  # Key derivation salt
    algorithm: str = "AES-256-CBC"
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ciphertext": base64.b64encode(self.ciphertext).decode(),
            "iv": base64.b64encode(self.iv).decode(),
            "salt": base64.b64encode(self.salt).decode(),
            "algorithm": self.algorithm,
            "created_at": self.created_at.isoformat(),
        }
    
    def to_bytes(self) -> bytes:
        """Serialize to bytes for storage"""
        return json.dumps(self.to_dict()).encode()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EncryptedPayload":
        return cls(
            ciphertext=base64.b64decode(data["ciphertext"]),
            iv=base64.b64decode(data["iv"]),
            salt=base64.b64decode(data["salt"]),
            algorithm=data.get("algorithm", "AES-256-CBC"),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "EncryptedPayload":
        return cls.from_dict(json.loads(data.decode()))


@dataclass
class DecryptedPayload:
    """A decrypted payload with verification"""
    plaintext: bytes
    content_hash: str  # Hash of plaintext for verification
    decrypted_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_string(self) -> str:
        return self.plaintext.decode('utf-8')
    
    def to_json(self) -> Any:
        return json.loads(self.plaintext.decode('utf-8'))


class PayloadEncryptor:
    """
    AES-256 Payload Encryption System
    
    Implements secure encryption for node payloads in the Hash-Sphere Universe.
    
    Features:
    - AES-256-CBC encryption
    - PBKDF2 key derivation
    - Random IV per encryption
    - Content hash verification
    """
    
    KEY_SIZE = 32  # 256 bits
    IV_SIZE = 16   # 128 bits
    SALT_SIZE = 16
    ITERATIONS = 100000  # PBKDF2 iterations
    
    def __init__(self):
        self._key_cache: Dict[str, bytes] = {}  # Cache derived keys
    
    def _derive_key(self, password: Union[str, bytes], salt: bytes) -> bytes:
        """
        Derive encryption key from password using PBKDF2.
        
        This allows using wallet private keys or passwords as encryption keys.
        """
        if isinstance(password, str):
            password = password.encode('utf-8')
        
        # Check cache
        cache_key = hashlib.sha256(password + salt).hexdigest()
        if cache_key in self._key_cache:
            return self._key_cache[cache_key]
        
        # PBKDF2 key derivation
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password,
            salt,
            self.ITERATIONS,
            dklen=self.KEY_SIZE
        )
        
        # Cache for performance
        self._key_cache[cache_key] = key
        return key
    
    def _pad(self, data: bytes) -> bytes:
        """PKCS7 padding for AES block size"""
        if CRYPTO_AVAILABLE:
            padder = padding.PKCS7(128).padder()
            return padder.update(data) + padder.finalize()
        else:
            # Manual PKCS7 padding
            block_size = 16
            pad_len = block_size - (len(data) % block_size)
            return data + bytes([pad_len] * pad_len)
    
    def _unpad(self, data: bytes) -> bytes:
        """Remove PKCS7 padding"""
        if CRYPTO_AVAILABLE:
            unpadder = padding.PKCS7(128).unpadder()
            return unpadder.update(data) + unpadder.finalize()
        else:
            # Manual PKCS7 unpadding
            pad_len = data[-1]
            return data[:-pad_len]
    
    def encrypt(
        self,
        plaintext: Union[str, bytes, Dict, Any],
        key: Union[str, bytes],
    ) -> EncryptedPayload:
        """
        Encrypt plaintext with AES-256-CBC.
        
        Args:
            plaintext: Data to encrypt (string, bytes, or JSON-serializable)
            key: Encryption key (password or wallet key)
        
        Returns:
            EncryptedPayload with ciphertext, IV, and salt
        """
        # Convert plaintext to bytes
        if isinstance(plaintext, str):
            plaintext_bytes = plaintext.encode('utf-8')
        elif isinstance(plaintext, bytes):
            plaintext_bytes = plaintext
        else:
            plaintext_bytes = json.dumps(plaintext, sort_keys=True).encode('utf-8')
        
        # Generate random IV and salt
        iv = secrets.token_bytes(self.IV_SIZE)
        salt = secrets.token_bytes(self.SALT_SIZE)
        
        # Derive encryption key
        derived_key = self._derive_key(key, salt)
        
        # Pad plaintext
        padded = self._pad(plaintext_bytes)
        
        if CRYPTO_AVAILABLE:
            # Real AES encryption
            cipher = Cipher(
                algorithms.AES(derived_key),
                modes.CBC(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(padded) + encryptor.finalize()
        else:
            # Fallback: XOR-based encryption (NOT secure for production!)
            logger.warning("Using fallback encryption - NOT secure for production!")
            key_stream = (derived_key * ((len(padded) // len(derived_key)) + 1))[:len(padded)]
            ciphertext = bytes(a ^ b for a, b in zip(padded, key_stream))
        
        return EncryptedPayload(
            ciphertext=ciphertext,
            iv=iv,
            salt=salt,
            algorithm="AES-256-CBC" if CRYPTO_AVAILABLE else "XOR-FALLBACK",
        )
    
    def decrypt(
        self,
        encrypted: EncryptedPayload,
        key: Union[str, bytes],
    ) -> DecryptedPayload:
        """
        Decrypt ciphertext with AES-256-CBC.
        
        Args:
            encrypted: EncryptedPayload to decrypt
            key: Decryption key (same as encryption key)
        
        Returns:
            DecryptedPayload with plaintext and content hash
        """
        # Derive decryption key
        derived_key = self._derive_key(key, encrypted.salt)
        
        if CRYPTO_AVAILABLE and encrypted.algorithm == "AES-256-CBC":
            # Real AES decryption
            cipher = Cipher(
                algorithms.AES(derived_key),
                modes.CBC(encrypted.iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            padded = decryptor.update(encrypted.ciphertext) + decryptor.finalize()
        else:
            # Fallback: XOR-based decryption
            key_stream = (derived_key * ((len(encrypted.ciphertext) // len(derived_key)) + 1))[:len(encrypted.ciphertext)]
            padded = bytes(a ^ b for a, b in zip(encrypted.ciphertext, key_stream))
        
        # Remove padding
        plaintext = self._unpad(padded)
        
        # Compute content hash for verification
        content_hash = hashlib.sha256(plaintext).hexdigest()
        
        return DecryptedPayload(
            plaintext=plaintext,
            content_hash=content_hash,
        )
    
    def encrypt_node(
        self,
        payload: Any,
        links: list,
        owner_key: Union[str, bytes],
    ) -> Tuple[EncryptedPayload, str]:
        """
        Encrypt a DAG node's payload.
        
        Returns:
            Tuple of (encrypted_payload, node_hash)
        """
        node_data = {
            "payload": payload,
            "links": links,
        }
        
        encrypted = self.encrypt(node_data, owner_key)
        
        # Compute node hash from encrypted content
        node_hash = hashlib.sha256(encrypted.ciphertext).hexdigest()
        
        return encrypted, node_hash
    
    def decrypt_node(
        self,
        encrypted: EncryptedPayload,
        owner_key: Union[str, bytes],
    ) -> Tuple[Any, list]:
        """
        Decrypt a DAG node's payload.
        
        Returns:
            Tuple of (payload, links)
        """
        decrypted = self.decrypt(encrypted, owner_key)
        node_data = decrypted.to_json()
        
        return node_data.get("payload"), node_data.get("links", [])


class EncryptedNodeStore:
    """
    Encrypted Node Storage
    
    Manages encrypted DAG nodes with:
    - Encryption on write
    - Decryption on read
    - Hash-based addressing
    """
    
    def __init__(self):
        self._encryptor = PayloadEncryptor()
        self._nodes: Dict[str, EncryptedPayload] = {}  # node_hash -> encrypted
        self._metadata: Dict[str, Dict[str, Any]] = {}  # node_hash -> metadata
    
    def store_node(
        self,
        payload: Any,
        links: list,
        owner_key: Union[str, bytes],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Store an encrypted node.
        
        Returns:
            Node hash (content-addressable ID)
        """
        encrypted, node_hash = self._encryptor.encrypt_node(payload, links, owner_key)
        
        self._nodes[node_hash] = encrypted
        self._metadata[node_hash] = {
            "links": links,
            "created_at": datetime.utcnow().isoformat(),
            **(metadata or {}),
        }
        
        logger.info(f"🔒 Stored encrypted node: {node_hash[:16]}...")
        
        return node_hash
    
    def fetch_node(
        self,
        node_hash: str,
        owner_key: Union[str, bytes],
    ) -> Optional[Tuple[Any, list]]:
        """
        Fetch and decrypt a node.
        
        Returns:
            Tuple of (payload, links) or None if not found
        """
        if node_hash not in self._nodes:
            return None
        
        encrypted = self._nodes[node_hash]
        
        try:
            payload, links = self._encryptor.decrypt_node(encrypted, owner_key)
            logger.info(f"🔓 Decrypted node: {node_hash[:16]}...")
            return payload, links
        except Exception as e:
            logger.error(f"Decryption failed for {node_hash[:16]}...: {e}")
            return None
    
    def get_metadata(self, node_hash: str) -> Optional[Dict[str, Any]]:
        """Get node metadata without decryption"""
        return self._metadata.get(node_hash)
    
    def get_links(self, node_hash: str) -> list:
        """Get node links without decryption"""
        meta = self._metadata.get(node_hash, {})
        return meta.get("links", [])
    
    def node_exists(self, node_hash: str) -> bool:
        """Check if node exists"""
        return node_hash in self._nodes


class UniverseReconstructor:
    """
    Universe Reconstruction System
    
    Implements the HSU-Spec reconstruction algorithm:
    
    function RECONSTRUCT(rootID, key):
        node := fetchNode(rootID)
        payload := Dec_key(node.payload)
        for c in node.links:
             child := RECONSTRUCT(c, key)
        return assemble(payload, child[])
    """
    
    def __init__(self, node_store: EncryptedNodeStore):
        self._store = node_store
        self._reconstruction_cache: Dict[str, Any] = {}
    
    def reconstruct(
        self,
        root_hash: str,
        owner_key: Union[str, bytes],
        max_depth: int = 100,
    ) -> Optional[Dict[str, Any]]:
        """
        Recursively reconstruct a data universe from root hash.
        
        Args:
            root_hash: Root node hash
            owner_key: Decryption key
            max_depth: Maximum recursion depth (prevents infinite loops)
        
        Returns:
            Reconstructed data structure
        """
        return self._reconstruct_node(root_hash, owner_key, 0, max_depth)
    
    def _reconstruct_node(
        self,
        node_hash: str,
        owner_key: Union[str, bytes],
        depth: int,
        max_depth: int,
    ) -> Optional[Dict[str, Any]]:
        """Recursive node reconstruction"""
        # Check cache
        if node_hash in self._reconstruction_cache:
            return self._reconstruction_cache[node_hash]
        
        # Check depth limit
        if depth >= max_depth:
            logger.warning(f"Max depth reached at {node_hash[:16]}...")
            return {"_truncated": True, "_hash": node_hash}
        
        # Fetch and decrypt node
        result = self._store.fetch_node(node_hash, owner_key)
        if result is None:
            return None
        
        payload, links = result
        
        # Recursively reconstruct children
        children = []
        for link_hash in links:
            child = self._reconstruct_node(link_hash, owner_key, depth + 1, max_depth)
            if child is not None:
                children.append(child)
        
        # Assemble result
        reconstructed = {
            "_hash": node_hash,
            "_depth": depth,
            "payload": payload,
            "children": children,
        }
        
        # Cache result
        self._reconstruction_cache[node_hash] = reconstructed
        
        return reconstructed
    
    def clear_cache(self):
        """Clear reconstruction cache"""
        self._reconstruction_cache.clear()
    
    def get_reconstruction_stats(self) -> Dict[str, Any]:
        """Get reconstruction statistics"""
        return {
            "cached_nodes": len(self._reconstruction_cache),
            "store_nodes": len(self._store._nodes),
        }


# Global instances
payload_encryptor = PayloadEncryptor()
encrypted_node_store = EncryptedNodeStore()
universe_reconstructor = UniverseReconstructor(encrypted_node_store)


# Convenience functions
def encrypt_payload(plaintext: Any, key: Union[str, bytes]) -> EncryptedPayload:
    """Encrypt a payload"""
    return payload_encryptor.encrypt(plaintext, key)


def decrypt_payload(encrypted: EncryptedPayload, key: Union[str, bytes]) -> DecryptedPayload:
    """Decrypt a payload"""
    return payload_encryptor.decrypt(encrypted, key)


def store_encrypted_node(payload: Any, links: list, key: Union[str, bytes]) -> str:
    """Store an encrypted node"""
    return encrypted_node_store.store_node(payload, links, key)


def fetch_encrypted_node(node_hash: str, key: Union[str, bytes]) -> Optional[Tuple[Any, list]]:
    """Fetch and decrypt a node"""
    return encrypted_node_store.fetch_node(node_hash, key)


def reconstruct_universe(root_hash: str, key: Union[str, bytes]) -> Optional[Dict[str, Any]]:
    """Reconstruct a data universe from root hash"""
    return universe_reconstructor.reconstruct(root_hash, key)
