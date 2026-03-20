"""DSID-P (Decentralized Secure Identity with Provenance) management."""

import hashlib
import logging
import secrets
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DSID, HashNode
from .config import settings

logger = logging.getLogger(__name__)

# DSID-P Section 68: Ed25519 Cryptographic Signatures
try:
    from nacl.signing import SigningKey, VerifyKey
    from nacl.exceptions import CryptoError
    BadSignature = CryptoError  # BadSignature is alias for CryptoError in newer versions
    ED25519_AVAILABLE = True
except ImportError:
    ED25519_AVAILABLE = False
    SigningKey = None
    VerifyKey = None
    BadSignature = None


class Ed25519Signer:
    """
    DSID-P Section 68.2: Ed25519 Signature Implementation.
    
    Provides cryptographic identity signing and verification
    as specified in the DSID-P Implementation Blueprint.
    """
    
    def __init__(self):
        if not ED25519_AVAILABLE:
            raise ImportError("PyNaCl required for Ed25519. Install with: pip install pynacl")
    
    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """
        Generate Ed25519 keypair.
        
        Returns:
            (private_key, public_key) as bytes
        """
        signing_key = SigningKey.generate()
        verify_key = signing_key.verify_key
        return bytes(signing_key), bytes(verify_key)
    
    def sign(self, message: bytes, private_key: bytes) -> bytes:
        """
        Sign a message with Ed25519 private key.
        
        Args:
            message: The message to sign
            private_key: 32-byte Ed25519 private key
            
        Returns:
            64-byte signature
        """
        signing_key = SigningKey(private_key)
        signed = signing_key.sign(message)
        return signed.signature
    
    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """
        Verify Ed25519 signature.
        
        Args:
            message: The original message
            signature: 64-byte signature
            public_key: 32-byte Ed25519 public key
            
        Returns:
            True if valid, False otherwise
        """
        try:
            verify_key = VerifyKey(public_key)
            verify_key.verify(message, signature)
            return True
        except BadSignature:
            return False
        except Exception:
            return False
    
    def sign_dsid(self, dsid_data: dict, private_key: bytes) -> str:
        """Sign a DSID object and return hex signature."""
        message = str(sorted(dsid_data.items())).encode()
        signature = self.sign(message, private_key)
        return signature.hex()
    
    def verify_dsid(self, dsid_data: dict, signature_hex: str, public_key: bytes) -> bool:
        """Verify a DSID signature."""
        message = str(sorted(dsid_data.items())).encode()
        signature = bytes.fromhex(signature_hex)
        return self.verify(message, signature, public_key)


# Global signer instance
try:
    ed25519_signer = Ed25519Signer()
except ImportError:
    ed25519_signer = None


class DSIDManager:
    """Manages DSID-P identities and provenance."""

    def generate_dsid(
        self,
        entity_type: str,
        content_hash: str,
        version: int = 1,
    ) -> str:
        """Generate a DSID identifier."""
        # Format: dsid:v{version}:{entity_type}:{content_hash[:16]}:{random}
        random_suffix = secrets.token_hex(4)
        return f"{settings.DSID_PREFIX}:v{version}:{entity_type}:{content_hash[:16]}:{random_suffix}"

    def hash_content(self, content: Any) -> str:
        """Generate SHA-256 hash of content."""
        if isinstance(content, dict):
            content_str = str(sorted(content.items()))
        elif isinstance(content, bytes):
            content_str = content.decode('utf-8', errors='ignore')
        else:
            content_str = str(content)
        
        return hashlib.sha256(content_str.encode()).hexdigest()

    async def create_dsid(
        self,
        entity_type: str,
        entity_id: str,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
        parent_dsid: Optional[str] = None,
        public_key: Optional[str] = None,
        db_session: AsyncSession = None,
    ) -> DSID:
        """Create a new DSID for an entity."""
        content_hash = self.hash_content(content)
        metadata_hash = self.hash_content(metadata) if metadata else None
        
        dsid_str = self.generate_dsid(entity_type, content_hash)
        
        # Determine lineage
        root_dsid = None
        lineage_depth = 0
        
        if parent_dsid:
            parent = await self.get_dsid(parent_dsid, db_session)
            if parent:
                root_dsid = parent.root_dsid or parent.dsid
                lineage_depth = parent.lineage_depth + 1
        
        dsid = DSID(
            dsid=dsid_str,
            entity_type=entity_type,
            entity_id=entity_id,
            public_key=public_key,
            content_hash=content_hash,
            metadata_hash=metadata_hash,
            parent_dsid=parent_dsid,
            root_dsid=root_dsid or dsid_str,
            lineage_depth=lineage_depth,
        )
        db_session.add(dsid)
        await db_session.commit()
        await db_session.refresh(dsid)
        
        # Create hash node for lineage tracking
        await self._create_hash_node(
            hash_value=content_hash,
            content_type=entity_type,
            content_id=entity_id,
            parent_hash=parent.content_hash if parent_dsid else None,
            db_session=db_session,
        )

        # Record DSID creation as a blockchain transaction
        try:
            from .chain import transaction_manager
            await transaction_manager.create_transaction(
                tx_type='dsid_register',
                payload={
                    'dsid': dsid_str,
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'content_hash': content_hash,
                    'metadata_hash': metadata_hash,
                    'lineage_depth': lineage_depth,
                    'parent_dsid': parent_dsid,
                    'root_dsid': root_dsid or dsid_str,
                },
                from_dsid=parent_dsid,
                to_dsid=dsid_str,
                db_session=db_session,
            )
            logger.info(f'Blockchain TX created for DSID {dsid_str}')
        except Exception as e:
            logger.warning(f'Failed to create blockchain TX for DSID {dsid_str}: {e}')

        return dsid

    async def get_dsid(
        self,
        dsid_str: str,
        db_session: AsyncSession,
    ) -> Optional[DSID]:
        """Get a DSID by its identifier."""
        result = await db_session.execute(
            select(DSID).where(DSID.dsid == dsid_str)
        )
        return result.scalar_one_or_none()

    async def get_dsid_by_entity(
        self,
        entity_type: str,
        entity_id: str,
        db_session: AsyncSession,
    ) -> Optional[DSID]:
        """Get the current DSID for an entity."""
        result = await db_session.execute(
            select(DSID)
            .where(DSID.entity_type == entity_type)
            .where(DSID.entity_id == entity_id)
            .where(DSID.status == "active")
            .order_by(DSID.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_dsid(
        self,
        dsid_str: str,
        new_content: Any,
        new_metadata: Optional[Dict[str, Any]] = None,
        db_session: AsyncSession = None,
    ) -> DSID:
        """Create a new version of a DSID."""
        current = await self.get_dsid(dsid_str, db_session)
        if not current:
            raise ValueError("DSID not found")
        
        if current.status != "active":
            raise ValueError("Cannot update non-active DSID")
        
        # Mark current as superseded
        current.status = "superseded"
        
        # Create new version
        new_dsid = await self.create_dsid(
            entity_type=current.entity_type,
            entity_id=str(current.entity_id),
            content=new_content,
            metadata=new_metadata,
            parent_dsid=current.dsid,
            public_key=current.public_key,
            db_session=db_session,
        )
        new_dsid.version = current.version + 1
        new_dsid.previous_version_dsid = current.dsid
        
        await db_session.commit()
        return new_dsid

    async def revoke_dsid(
        self,
        dsid_str: str,
        reason: str,
        db_session: AsyncSession,
    ) -> DSID:
        """Revoke a DSID."""
        dsid = await self.get_dsid(dsid_str, db_session)
        if not dsid:
            raise ValueError("DSID not found")
        
        dsid.status = "revoked"
        dsid.revoked_at = datetime.utcnow()
        dsid.revocation_reason = reason
        
        await db_session.commit()
        return dsid

    async def verify_dsid(
        self,
        dsid_str: str,
        content: Any,
        db_session: AsyncSession,
    ) -> Tuple[bool, str]:
        """Verify content against a DSID."""
        dsid = await self.get_dsid(dsid_str, db_session)
        if not dsid:
            return False, "DSID not found"
        
        if dsid.status != "active":
            return False, f"DSID is {dsid.status}"
        
        content_hash = self.hash_content(content)
        if content_hash != dsid.content_hash:
            return False, "Content hash mismatch"
        
        return True, "Verified"

    async def get_lineage(
        self,
        dsid_str: str,
        db_session: AsyncSession,
    ) -> List[DSID]:
        """Get the full lineage chain for a DSID."""
        lineage = []
        current_dsid = dsid_str
        
        while current_dsid:
            dsid = await self.get_dsid(current_dsid, db_session)
            if not dsid:
                break
            lineage.append(dsid)
            current_dsid = dsid.parent_dsid
        
        return lineage

    async def get_descendants(
        self,
        dsid_str: str,
        db_session: AsyncSession,
        max_depth: int = 10,
    ) -> List[DSID]:
        """Get all descendants of a DSID."""
        result = await db_session.execute(
            select(DSID)
            .where(DSID.root_dsid == dsid_str)
            .where(DSID.lineage_depth <= max_depth)
            .order_by(DSID.lineage_depth)
        )
        return list(result.scalars().all())

    async def _create_hash_node(
        self,
        hash_value: str,
        content_type: str,
        content_id: str,
        parent_hash: Optional[str] = None,
        db_session: AsyncSession = None,
    ) -> HashNode:
        """Create a hash node for lineage tracking."""
        # Check if node exists
        result = await db_session.execute(
            select(HashNode).where(HashNode.hash_value == hash_value)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        
        # Get parent depth
        depth = 0
        if parent_hash:
            parent_result = await db_session.execute(
                select(HashNode).where(HashNode.hash_value == parent_hash)
            )
            parent = parent_result.scalar_one_or_none()
            if parent:
                depth = parent.depth + 1
                # Update parent's children
                if parent.children_hashes:
                    parent.children_hashes = parent.children_hashes + [hash_value]
                else:
                    parent.children_hashes = [hash_value]
        
        node = HashNode(
            hash_value=hash_value,
            content_type=content_type,
            content_id=content_id,
            parent_hash=parent_hash,
            depth=depth,
        )
        db_session.add(node)
        await db_session.commit()
        await db_session.refresh(node)
        return node


class HashLineageManager:
    """Manages hash lineage and Merkle trees."""

    def compute_merkle_root(self, hashes: List[str]) -> str:
        """Compute Merkle root from a list of hashes."""
        if not hashes:
            return hashlib.sha256(b"").hexdigest()
        
        if len(hashes) == 1:
            return hashes[0]
        
        # Build tree level by level
        while len(hashes) > 1:
            # Pad to even number at each level
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])
            new_level = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                new_hash = hashlib.sha256(combined.encode()).hexdigest()
                new_level.append(new_hash)
            hashes = new_level
        
        return hashes[0]

    def compute_merkle_proof(
        self,
        target_hash: str,
        all_hashes: List[str],
    ) -> List[Dict[str, str]]:
        """Compute Merkle proof for a hash."""
        if target_hash not in all_hashes:
            return []
        
        proof = []
        hashes = all_hashes.copy()
        
        # Pad to even number
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])
        
        target_idx = hashes.index(target_hash)
        
        while len(hashes) > 1:
            new_level = []
            for i in range(0, len(hashes), 2):
                if i == target_idx or i + 1 == target_idx:
                    # Add sibling to proof
                    sibling_idx = i + 1 if i == target_idx else i
                    proof.append({
                        "hash": hashes[sibling_idx],
                        "position": "right" if sibling_idx > target_idx else "left",
                    })
                    target_idx = i // 2
                
                combined = hashes[i] + hashes[i + 1]
                new_hash = hashlib.sha256(combined.encode()).hexdigest()
                new_level.append(new_hash)
            
            hashes = new_level
        
        return proof

    def verify_merkle_proof(
        self,
        target_hash: str,
        merkle_root: str,
        proof: List[Dict[str, str]],
    ) -> bool:
        """Verify a Merkle proof."""
        current = target_hash
        
        for step in proof:
            sibling = step["hash"]
            if step["position"] == "left":
                combined = sibling + current
            else:
                combined = current + sibling
            current = hashlib.sha256(combined.encode()).hexdigest()
        
        return current == merkle_root

    async def get_hash_lineage(
        self,
        hash_value: str,
        db_session: AsyncSession,
    ) -> List[HashNode]:
        """Get the lineage chain for a hash."""
        lineage = []
        current_hash = hash_value
        
        while current_hash:
            result = await db_session.execute(
                select(HashNode).where(HashNode.hash_value == current_hash)
            )
            node = result.scalar_one_or_none()
            if not node:
                break
            lineage.append(node)
            current_hash = node.parent_hash
        
        return lineage

    async def get_hash_tree(
        self,
        root_hash: str,
        db_session: AsyncSession,
        max_depth: int = 10,
    ) -> Dict[str, Any]:
        """Get the hash tree starting from a root."""
        result = await db_session.execute(
            select(HashNode).where(HashNode.hash_value == root_hash)
        )
        root = result.scalar_one_or_none()
        if not root:
            return {}
        
        async def build_tree(node: HashNode, depth: int) -> Dict[str, Any]:
            if depth >= max_depth:
                return {"hash": node.hash_value, "truncated": True}
            
            tree = {
                "hash": node.hash_value,
                "content_type": node.content_type,
                "depth": node.depth,
                "children": [],
            }
            
            if node.children_hashes:
                for child_hash in node.children_hashes:
                    child_result = await db_session.execute(
                        select(HashNode).where(HashNode.hash_value == child_hash)
                    )
                    child = child_result.scalar_one_or_none()
                    if child:
                        tree["children"].append(await build_tree(child, depth + 1))
            
            return tree
        
        return await build_tree(root, 0)


dsid_manager = DSIDManager()
hash_lineage_manager = HashLineageManager()
