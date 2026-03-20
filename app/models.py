"""Blockchain Service database models."""

from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, Boolean, JSON, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func

from .db import Base


class DSID(Base):
    """Decentralized Secure Identity with Provenance (DSID-P)."""
    __tablename__ = "dsids"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # DSID identifier
    dsid = Column(String(128), unique=True, index=True, nullable=False)  # dsid:v1:entity_type:hash
    
    # Entity reference
    entity_type = Column(String(32), nullable=False)  # user, agent, content, transaction, etc.
    entity_id = Column(UUID(as_uuid=True), index=True, nullable=False)
    
    # Cryptographic identity
    public_key = Column(Text, nullable=True)  # Public key for verification
    key_algorithm = Column(String(32), default="ed25519")
    
    # Content hash
    content_hash = Column(String(64), nullable=False)  # SHA-256 of entity content
    metadata_hash = Column(String(64), nullable=True)  # Hash of metadata
    
    # Provenance chain
    parent_dsid = Column(String(128), nullable=True)  # Parent DSID for lineage
    root_dsid = Column(String(128), nullable=True)  # Root of the lineage chain
    lineage_depth = Column(Integer, default=0)
    
    # Version tracking
    version = Column(Integer, default=1)
    previous_version_dsid = Column(String(128), nullable=True)
    
    # Status
    status = Column(String(32), default="active")  # active, revoked, superseded
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(Text, nullable=True)
    
    # Blockchain anchoring
    anchored = Column(Boolean, default=False)
    anchor_tx_hash = Column(String(128), nullable=True)
    anchor_block_number = Column(BigInteger, nullable=True)
    anchor_chain = Column(String(32), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class HashNode(Base):
    """Node in the hash lineage tree."""
    __tablename__ = "hash_nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Hash identity
    hash_value = Column(String(64), unique=True, index=True, nullable=False)
    hash_algorithm = Column(String(16), default="sha256")
    
    # Content reference
    content_type = Column(String(32), nullable=False)  # message, file, transaction, state
    content_id = Column(UUID(as_uuid=True), index=True, nullable=True)
    content_preview = Column(Text, nullable=True)  # First 256 chars for quick reference
    
    # Lineage
    parent_hash = Column(String(64), index=True, nullable=True)
    children_hashes = Column(ARRAY(String), nullable=True)
    depth = Column(Integer, default=0)
    
    # Merkle tree position
    merkle_root = Column(String(64), nullable=True)
    merkle_proof = Column(JSON, nullable=True)  # Proof path to root
    
    # Metadata
    extra_metadata = Column(JSON, nullable=True)
    
    # Block reference
    block_id = Column(UUID(as_uuid=True), index=True, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Block(Base):
    """Block in the internal blockchain."""
    __tablename__ = "blocks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Block identity
    block_number = Column(BigInteger, unique=True, index=True, nullable=False)
    block_hash = Column(String(64), unique=True, index=True, nullable=False)
    
    # Chain linkage
    previous_block_hash = Column(String(64), index=True, nullable=True)
    
    # Merkle root of transactions
    merkle_root = Column(String(64), nullable=False)
    
    # Block data
    transaction_count = Column(Integer, default=0)
    transactions_hash = Column(String(64), nullable=False)  # Hash of all tx hashes
    
    # State
    state_root = Column(String(64), nullable=True)  # Root of state trie
    
    # Timestamps
    timestamp = Column(DateTime(timezone=True), nullable=False)
    
    # Validation
    validator = Column(String(128), nullable=True)  # Who created this block
    signature = Column(Text, nullable=True)
    
    # External anchoring
    anchored = Column(Boolean, default=False)
    anchor_tx_hash = Column(String(128), nullable=True)
    anchor_chain = Column(String(32), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BlockTransaction(Base):
    """Transaction in a block."""
    __tablename__ = "block_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Transaction identity
    tx_hash = Column(String(64), unique=True, index=True, nullable=False)
    
    # Block reference
    block_id = Column(UUID(as_uuid=True), index=True, nullable=True)
    block_number = Column(BigInteger, index=True, nullable=True)
    tx_index = Column(Integer, nullable=True)  # Position in block
    
    # Transaction type
    tx_type = Column(String(32), nullable=False)  # transfer, anchor, register, update, revoke
    
    # Parties
    from_dsid = Column(String(128), index=True, nullable=True)
    to_dsid = Column(String(128), index=True, nullable=True)
    
    # Content
    payload = Column(JSON, nullable=True)
    payload_hash = Column(String(64), nullable=False)
    
    # Signature
    signature = Column(Text, nullable=True)
    
    # Status
    status = Column(String(32), default="pending")  # pending, confirmed, failed
    
    # Gas/fees
    fee = Column(BigInteger, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)


class TransactionGraph(Base):
    """Graph edges for transaction relationships."""
    __tablename__ = "transaction_graph"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Edge definition
    from_tx_hash = Column(String(64), index=True, nullable=False)
    to_tx_hash = Column(String(64), index=True, nullable=False)
    
    # Relationship type
    relationship = Column(String(32), nullable=False)  # input, output, reference, depends_on
    
    # Weight/value
    weight = Column(Float, default=1.0)
    
    # Metadata
    extra_metadata = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuditEntry(Base):
    """Audit chain entry for compliance and tracking."""
    __tablename__ = "audit_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Entry identity
    entry_hash = Column(String(64), unique=True, index=True, nullable=False)
    sequence_number = Column(BigInteger, index=True, nullable=False)
    
    # Chain linkage
    previous_entry_hash = Column(String(64), index=True, nullable=True)
    
    # Audit event
    event_type = Column(String(64), nullable=False)  # create, update, delete, access, transfer, etc.
    event_category = Column(String(32), nullable=False)  # user, agent, data, financial, security
    
    # Actor
    actor_dsid = Column(String(128), index=True, nullable=True)
    actor_ip = Column(String(45), nullable=True)  # IPv4 or IPv6
    actor_user_agent = Column(String(512), nullable=True)
    
    # Target
    target_type = Column(String(32), nullable=True)
    target_id = Column(UUID(as_uuid=True), index=True, nullable=True)
    target_dsid = Column(String(128), nullable=True)
    
    # Event details
    action = Column(String(64), nullable=False)
    description = Column(Text, nullable=True)
    
    # Before/after state
    before_state_hash = Column(String(64), nullable=True)
    after_state_hash = Column(String(64), nullable=True)
    changes = Column(JSON, nullable=True)  # Diff of changes
    
    # Result
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    # Compliance tags
    compliance_tags = Column(ARRAY(String), nullable=True)  # GDPR, SOC2, HIPAA, etc.
    
    # Signature
    signature = Column(Text, nullable=True)
    
    # Block reference
    block_id = Column(UUID(as_uuid=True), index=True, nullable=True)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StateSnapshot(Base):
    """State snapshots for point-in-time recovery."""
    __tablename__ = "state_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Snapshot identity
    snapshot_hash = Column(String(64), unique=True, index=True, nullable=False)
    
    # Block reference
    block_number = Column(BigInteger, index=True, nullable=False)
    block_hash = Column(String(64), nullable=False)
    
    # State data
    state_root = Column(String(64), nullable=False)
    account_count = Column(Integer, default=0)
    
    # Storage reference
    storage_path = Column(String(512), nullable=True)  # Path to snapshot file
    storage_size_bytes = Column(BigInteger, nullable=True)
    
    # Metadata
    extra_metadata = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AnchorRecord(Base):
    """Records of external blockchain anchoring."""
    __tablename__ = "anchor_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # What was anchored
    anchor_type = Column(String(32), nullable=False)  # block, merkle_root, state_root
    internal_hash = Column(String(64), index=True, nullable=False)
    internal_block_number = Column(BigInteger, nullable=True)
    
    # External chain details
    external_chain = Column(String(32), nullable=False)  # ethereum, polygon, solana
    external_tx_hash = Column(String(128), unique=True, index=True, nullable=False)
    external_block_number = Column(BigInteger, nullable=True)
    external_block_hash = Column(String(128), nullable=True)
    
    # Contract details
    contract_address = Column(String(128), nullable=True)
    
    # Status
    status = Column(String(32), default="pending")  # pending, confirmed, failed
    confirmations = Column(Integer, default=0)
    
    # Cost
    gas_used = Column(BigInteger, nullable=True)
    gas_price = Column(BigInteger, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
