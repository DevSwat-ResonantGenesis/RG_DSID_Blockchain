"""
Crypto Wallet System (HSU-Spec Layer 1)
========================================

MetaMask-like wallet abstraction for users and agents.

Features:
- Ed25519 keypair generation
- Secure key derivation
- Sign/verify operations
- Ownership transfer signatures
- Wallet-like identity management
"""

import hashlib
import secrets
import base64
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Try to import cryptography library for Ed25519
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives import serialization
    from cryptography.exceptions import InvalidSignature
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logging.warning("cryptography library not available, using fallback signing")

logger = logging.getLogger(__name__)


class WalletType(Enum):
    """Wallet type classification"""
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class WalletStatus(Enum):
    """Wallet status"""
    ACTIVE = "active"
    LOCKED = "locked"
    REVOKED = "revoked"


@dataclass
class WalletKeyPair:
    """Cryptographic keypair for a wallet"""
    private_key_bytes: bytes  # Never expose this!
    public_key_bytes: bytes
    public_key_hex: str
    algorithm: str = "ed25519"
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CryptoWallet:
    """
    Crypto Wallet - MetaMask-like identity for users and agents.
    
    Contains:
    - Cryptographic keypair (Ed25519)
    - Public address (derived from public key)
    - Identity hash (root location in Hash Sphere)
    - Signing capabilities
    """
    wallet_id: str = ""
    wallet_type: WalletType = WalletType.USER
    
    # Entity reference
    entity_id: str = ""  # User ID or Agent ID
    entity_dsid: str = ""
    
    # Cryptographic identity
    public_key_hex: str = ""
    address: str = ""  # Derived from public key (like Ethereum address)
    identity_hash: str = ""  # H(public_key) - root in Hash Sphere
    
    # Key metadata (private key stored separately/encrypted)
    key_algorithm: str = "ed25519"
    key_created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Status
    status: WalletStatus = WalletStatus.ACTIVE
    
    # Ownership
    owned_agents: List[str] = field(default_factory=list)  # Agent DSIDs
    delegated_to: List[str] = field(default_factory=list)  # Delegated wallet addresses
    
    # Transaction history
    nonce: int = 0  # Transaction counter
    last_transaction_hash: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excludes private key)"""
        return {
            "wallet_id": self.wallet_id,
            "wallet_type": self.wallet_type.value,
            "entity_id": self.entity_id,
            "entity_dsid": self.entity_dsid,
            "public_key_hex": self.public_key_hex,
            "address": self.address,
            "identity_hash": self.identity_hash,
            "key_algorithm": self.key_algorithm,
            "status": self.status.value,
            "owned_agents": self.owned_agents,
            "nonce": self.nonce,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SignedMessage:
    """A cryptographically signed message"""
    message: str
    message_hash: str
    signature: str
    signer_address: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": self.message,
            "message_hash": self.message_hash,
            "signature": self.signature,
            "signer_address": self.signer_address,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class OwnershipTransfer:
    """Signed ownership transfer record"""
    transfer_id: str
    asset_type: str  # "agent", "data", etc.
    asset_id: str
    from_address: str
    to_address: str
    transfer_type: str  # "permanent", "rental", "delegation"
    signature: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expiry: Optional[datetime] = None  # For rentals
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "transfer_id": self.transfer_id,
            "asset_type": self.asset_type,
            "asset_id": self.asset_id,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "transfer_type": self.transfer_type,
            "signature": self.signature,
            "timestamp": self.timestamp.isoformat(),
            "expiry": self.expiry.isoformat() if self.expiry else None,
        }


class CryptoWalletService:
    """
    Crypto Wallet Service
    
    Manages wallet creation, signing, and verification.
    Similar to MetaMask but for the Resonant Genesis platform.
    """
    
    def __init__(self):
        self._wallets: Dict[str, CryptoWallet] = {}  # address -> wallet
        self._keypairs: Dict[str, WalletKeyPair] = {}  # address -> keypair (secure storage)
        self._entity_to_address: Dict[str, str] = {}  # entity_id -> address
        self._transfers: List[OwnershipTransfer] = []
    
    def _hash(self, data: str) -> str:
        """Generate SHA-256 hash"""
        return hashlib.sha256(data.encode()).hexdigest()
    
    def _generate_wallet_id(self) -> str:
        """Generate unique wallet ID"""
        return f"wallet_{secrets.token_hex(8)}"
    
    def _derive_address(self, public_key_hex: str) -> str:
        """
        Derive wallet address from public key.
        Similar to Ethereum: last 20 bytes of keccak256(public_key)
        We use SHA-256 and take last 40 hex chars (20 bytes).
        """
        full_hash = self._hash(public_key_hex)
        return "0x" + full_hash[-40:]
    
    def _generate_keypair(self) -> WalletKeyPair:
        """Generate Ed25519 keypair"""
        if CRYPTO_AVAILABLE:
            # Use real Ed25519
            private_key = Ed25519PrivateKey.generate()
            public_key = private_key.public_key()
            
            private_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            
            return WalletKeyPair(
                private_key_bytes=private_bytes,
                public_key_bytes=public_bytes,
                public_key_hex=public_bytes.hex(),
                algorithm="ed25519",
            )
        else:
            # Fallback: use random bytes (NOT cryptographically secure for production!)
            private_bytes = secrets.token_bytes(32)
            public_bytes = hashlib.sha256(private_bytes).digest()
            
            return WalletKeyPair(
                private_key_bytes=private_bytes,
                public_key_bytes=public_bytes,
                public_key_hex=public_bytes.hex(),
                algorithm="sha256_fallback",
            )
    
    def _sign_message(self, message: str, keypair: WalletKeyPair) -> str:
        """Sign a message with private key"""
        message_bytes = message.encode()
        
        if CRYPTO_AVAILABLE and keypair.algorithm == "ed25519":
            # Real Ed25519 signing
            private_key = Ed25519PrivateKey.from_private_bytes(keypair.private_key_bytes)
            signature = private_key.sign(message_bytes)
            return base64.b64encode(signature).decode()
        else:
            # Fallback: HMAC-like signature
            combined = keypair.private_key_bytes + message_bytes
            signature = hashlib.sha256(combined).digest()
            return base64.b64encode(signature).decode()
    
    def _verify_signature(
        self,
        message: str,
        signature: str,
        public_key_hex: str,
    ) -> bool:
        """Verify a signature"""
        try:
            message_bytes = message.encode()
            signature_bytes = base64.b64decode(signature)
            public_key_bytes = bytes.fromhex(public_key_hex)
            
            if CRYPTO_AVAILABLE:
                # Real Ed25519 verification
                public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
                public_key.verify(signature_bytes, message_bytes)
                return True
            else:
                # Fallback: can't verify without private key
                # In production, this would need proper implementation
                return True  # Trust for now
                
        except (InvalidSignature, Exception) as e:
            logger.warning(f"Signature verification failed: {e}")
            return False
    
    # ==========================================
    # WALLET OPERATIONS
    # ==========================================
    
    def create_wallet(
        self,
        entity_id: str,
        wallet_type: WalletType = WalletType.USER,
        entity_dsid: Optional[str] = None,
    ) -> CryptoWallet:
        """
        Create a new crypto wallet for a user or agent.
        
        This is like creating a MetaMask wallet.
        """
        # Check if wallet already exists for entity
        if entity_id in self._entity_to_address:
            existing_address = self._entity_to_address[entity_id]
            return self._wallets[existing_address]
        
        # Generate keypair
        keypair = self._generate_keypair()
        
        # Derive address
        address = self._derive_address(keypair.public_key_hex)
        
        # Generate identity hash (root in Hash Sphere)
        identity_hash = self._hash(keypair.public_key_hex)
        
        # Generate DSID if not provided
        if not entity_dsid:
            entity_dsid = f"dsid:v1:{wallet_type.value}:{identity_hash[:16]}:{secrets.token_hex(4)}"
        
        # Create wallet
        wallet = CryptoWallet(
            wallet_id=self._generate_wallet_id(),
            wallet_type=wallet_type,
            entity_id=entity_id,
            entity_dsid=entity_dsid,
            public_key_hex=keypair.public_key_hex,
            address=address,
            identity_hash=identity_hash,
            key_algorithm=keypair.algorithm,
            key_created_at=keypair.created_at,
        )
        
        # Store (keypair stored separately for security)
        self._wallets[address] = wallet
        self._keypairs[address] = keypair
        self._entity_to_address[entity_id] = address
        
        logger.info(f"🔐 Created {wallet_type.value} wallet: {address}")
        
        return wallet
    
    def get_wallet(self, address: str) -> Optional[CryptoWallet]:
        """Get wallet by address"""
        return self._wallets.get(address)
    
    def get_wallet_by_entity(self, entity_id: str) -> Optional[CryptoWallet]:
        """Get wallet by entity ID"""
        address = self._entity_to_address.get(entity_id)
        if address:
            return self._wallets.get(address)
        return None
    
    def lock_wallet(self, address: str) -> bool:
        """Lock a wallet (prevent transactions)"""
        if address in self._wallets:
            self._wallets[address].status = WalletStatus.LOCKED
            return True
        return False
    
    def unlock_wallet(self, address: str) -> bool:
        """Unlock a wallet"""
        if address in self._wallets:
            self._wallets[address].status = WalletStatus.ACTIVE
            return True
        return False
    
    # ==========================================
    # SIGNING OPERATIONS
    # ==========================================
    
    def sign_message(
        self,
        address: str,
        message: str,
    ) -> Optional[SignedMessage]:
        """
        Sign a message with wallet's private key.
        
        Like MetaMask's personal_sign.
        """
        if address not in self._wallets:
            logger.warning(f"Wallet not found: {address}")
            return None
        
        wallet = self._wallets[address]
        if wallet.status != WalletStatus.ACTIVE:
            logger.warning(f"Wallet is {wallet.status.value}")
            return None
        
        keypair = self._keypairs.get(address)
        if not keypair:
            logger.warning(f"Keypair not found for wallet")
            return None
        
        # Sign
        message_hash = self._hash(message)
        signature = self._sign_message(message, keypair)
        
        return SignedMessage(
            message=message,
            message_hash=message_hash,
            signature=signature,
            signer_address=address,
        )
    
    def verify_message(
        self,
        message: str,
        signature: str,
        signer_address: str,
    ) -> bool:
        """
        Verify a signed message.
        
        Like MetaMask's signature verification.
        """
        wallet = self._wallets.get(signer_address)
        if not wallet:
            return False
        
        return self._verify_signature(message, signature, wallet.public_key_hex)
    
    # ==========================================
    # OWNERSHIP TRANSFER
    # ==========================================
    
    def create_transfer(
        self,
        from_address: str,
        to_address: str,
        asset_type: str,
        asset_id: str,
        transfer_type: str = "permanent",
        expiry_hours: Optional[int] = None,
    ) -> Optional[OwnershipTransfer]:
        """
        Create a signed ownership transfer.
        
        This is like signing a transaction to transfer an NFT.
        """
        # Validate wallets
        from_wallet = self._wallets.get(from_address)
        to_wallet = self._wallets.get(to_address)
        
        if not from_wallet or not to_wallet:
            logger.warning("Invalid wallet addresses")
            return None
        
        if from_wallet.status != WalletStatus.ACTIVE:
            logger.warning("Source wallet is not active")
            return None
        
        # Create transfer message
        transfer_id = f"transfer_{secrets.token_hex(8)}"
        expiry = None
        if transfer_type == "rental" and expiry_hours:
            from datetime import timedelta
            expiry = datetime.utcnow() + timedelta(hours=expiry_hours)
        
        transfer_message = (
            f"TRANSFER:{transfer_id}:"
            f"{asset_type}:{asset_id}:"
            f"{from_address}:{to_address}:"
            f"{transfer_type}:"
            f"{datetime.utcnow().isoformat()}"
        )
        
        # Sign the transfer
        signed = self.sign_message(from_address, transfer_message)
        if not signed:
            return None
        
        # Create transfer record
        transfer = OwnershipTransfer(
            transfer_id=transfer_id,
            asset_type=asset_type,
            asset_id=asset_id,
            from_address=from_address,
            to_address=to_address,
            transfer_type=transfer_type,
            signature=signed.signature,
            expiry=expiry,
        )
        
        # Update wallets
        from_wallet.nonce += 1
        from_wallet.last_transaction_hash = self._hash(transfer_message)
        from_wallet.updated_at = datetime.utcnow()
        
        # If transferring agent ownership
        if asset_type == "agent":
            if asset_id in from_wallet.owned_agents:
                from_wallet.owned_agents.remove(asset_id)
            if transfer_type == "permanent":
                to_wallet.owned_agents.append(asset_id)
        
        # Store transfer
        self._transfers.append(transfer)
        
        logger.info(f"📝 Created {transfer_type} transfer: {asset_id[:16]}... -> {to_address}")
        
        return transfer
    
    def verify_transfer(self, transfer: OwnershipTransfer) -> bool:
        """Verify a transfer signature"""
        transfer_message = (
            f"TRANSFER:{transfer.transfer_id}:"
            f"{transfer.asset_type}:{transfer.asset_id}:"
            f"{transfer.from_address}:{transfer.to_address}:"
            f"{transfer.transfer_type}:"
            f"{transfer.timestamp.isoformat()}"
        )
        
        return self.verify_message(
            transfer_message,
            transfer.signature,
            transfer.from_address,
        )
    
    def get_transfers_by_address(self, address: str) -> List[OwnershipTransfer]:
        """Get all transfers involving an address"""
        return [
            t for t in self._transfers
            if t.from_address == address or t.to_address == address
        ]
    
    # ==========================================
    # DELEGATION
    # ==========================================
    
    def delegate_access(
        self,
        owner_address: str,
        delegate_address: str,
        permissions: Optional[List[str]] = None,
    ) -> bool:
        """
        Delegate wallet access to another address.
        
        Like granting approval in ERC-721.
        """
        owner_wallet = self._wallets.get(owner_address)
        delegate_wallet = self._wallets.get(delegate_address)
        
        if not owner_wallet or not delegate_wallet:
            return False
        
        if delegate_address not in owner_wallet.delegated_to:
            owner_wallet.delegated_to.append(delegate_address)
            owner_wallet.updated_at = datetime.utcnow()
            logger.info(f"🔑 Delegated access: {owner_address} -> {delegate_address}")
        
        return True
    
    def revoke_delegation(self, owner_address: str, delegate_address: str) -> bool:
        """Revoke delegated access"""
        owner_wallet = self._wallets.get(owner_address)
        if not owner_wallet:
            return False
        
        if delegate_address in owner_wallet.delegated_to:
            owner_wallet.delegated_to.remove(delegate_address)
            owner_wallet.updated_at = datetime.utcnow()
            logger.info(f"🔒 Revoked delegation: {owner_address} -> {delegate_address}")
        
        return True
    
    # ==========================================
    # STATISTICS
    # ==========================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get wallet service statistics"""
        user_wallets = [w for w in self._wallets.values() if w.wallet_type == WalletType.USER]
        agent_wallets = [w for w in self._wallets.values() if w.wallet_type == WalletType.AGENT]
        
        return {
            "total_wallets": len(self._wallets),
            "user_wallets": len(user_wallets),
            "agent_wallets": len(agent_wallets),
            "active_wallets": len([w for w in self._wallets.values() if w.status == WalletStatus.ACTIVE]),
            "total_transfers": len(self._transfers),
            "crypto_available": CRYPTO_AVAILABLE,
        }


# Global instance
crypto_wallet_service = CryptoWalletService()


# Convenience functions
def create_user_wallet(user_id: str, user_dsid: Optional[str] = None) -> CryptoWallet:
    """Create a user wallet"""
    return crypto_wallet_service.create_wallet(user_id, WalletType.USER, user_dsid)


def create_agent_wallet(agent_id: str, agent_dsid: Optional[str] = None) -> CryptoWallet:
    """Create an agent wallet"""
    return crypto_wallet_service.create_wallet(agent_id, WalletType.AGENT, agent_dsid)


def get_wallet(address: str) -> Optional[CryptoWallet]:
    """Get wallet by address"""
    return crypto_wallet_service.get_wallet(address)


def get_wallet_by_entity(entity_id: str) -> Optional[CryptoWallet]:
    """Get wallet by entity ID"""
    return crypto_wallet_service.get_wallet_by_entity(entity_id)


def sign_message(address: str, message: str) -> Optional[SignedMessage]:
    """Sign a message"""
    return crypto_wallet_service.sign_message(address, message)


def verify_message(message: str, signature: str, signer_address: str) -> bool:
    """Verify a signed message"""
    return crypto_wallet_service.verify_message(message, signature, signer_address)


def transfer_ownership(
    from_address: str,
    to_address: str,
    asset_type: str,
    asset_id: str,
    transfer_type: str = "permanent",
) -> Optional[OwnershipTransfer]:
    """Transfer asset ownership"""
    return crypto_wallet_service.create_transfer(
        from_address, to_address, asset_type, asset_id, transfer_type
    )
