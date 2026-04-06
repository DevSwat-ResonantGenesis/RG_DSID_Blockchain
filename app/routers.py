"""Blockchain Service API routers."""

import logging
import httpx
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import (
    DSID, HashNode, Block, BlockTransaction, TransactionGraph,
    AuditEntry, AnchorRecord
)
from .dsid import dsid_manager, hash_lineage_manager
from .chain import blockchain_manager, transaction_manager, graph_manager
from .audit import audit_manager, compliance_reporter

logger = logging.getLogger(__name__)

# Credit costs from pricing.yaml
CREDIT_COSTS = {
    "audit_entry": 100,
    "verification": 10,
    "compliance_report": 500,
    "smart_contract_deploy": 1000,
}

BILLING_SERVICE_URL = "http://billing_service:8000"

async def deduct_credits(user_id: str, amount: int, reference_type: str, description: str) -> dict:
    """Deduct credits from user's balance via billing service."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BILLING_SERVICE_URL}/billing/credits/deduct",
                json={
                    "amount": amount,
                    "reference_type": reference_type,
                    "description": description,
                },
                headers={"X-User-Id": user_id},
                timeout=5.0,
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.warning(f"Credit deduction failed: {e}")
        return {"error": str(e)}

router = APIRouter(prefix="/blockchain", tags=["blockchain"])


# ============== Request/Response Models ==============

class DSIDCreateRequest(BaseModel):
    entity_type: str
    entity_id: str
    content: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    parent_dsid: Optional[str] = None
    public_key: Optional[str] = None


class DSIDResponse(BaseModel):
    id: str
    dsid: str
    entity_type: str
    entity_id: str
    content_hash: str
    version: int
    status: str
    lineage_depth: int
    anchored: bool


class TransactionCreateRequest(BaseModel):
    tx_type: str
    payload: Dict[str, Any]
    from_dsid: Optional[str] = None
    to_dsid: Optional[str] = None
    signature: Optional[str] = None


class TransactionResponse(BaseModel):
    tx_hash: str
    tx_type: str
    status: str
    block_number: Optional[int] = None
    from_dsid: Optional[str] = None
    to_dsid: Optional[str] = None


class BlockResponse(BaseModel):
    block_number: int
    block_hash: str
    previous_block_hash: Optional[str]
    merkle_root: str
    transaction_count: int
    timestamp: str


class AuditEntryResponse(BaseModel):
    entry_hash: str
    sequence_number: int
    event_type: str
    event_category: str
    action: str
    actor_dsid: Optional[str]
    success: bool
    timestamp: str


class AuditLogListResponse(BaseModel):
    """Compatibility response for AI audit log listing."""

    items: List[AuditEntryResponse]
    total: int
    page: int
    limit: int
    anchored: bool


class AuditEntryCreate(BaseModel):
    event_type: str
    event_category: str
    action: str
    actor_dsid: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    description: Optional[str] = None
    changes: Optional[Dict[str, Any]] = None
    success: bool = True
    compliance_tags: Optional[List[str]] = None


class GraphEdgeCreate(BaseModel):
    from_tx_hash: str
    to_tx_hash: str
    relationship: str
    weight: float = 1.0
    metadata: Optional[Dict[str, Any]] = None


# ============== DSID Endpoints ==============

@router.post("/dsid", response_model=DSIDResponse, status_code=status.HTTP_201_CREATED)
async def create_dsid(
    payload: DSIDCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new DSID for an entity."""
    dsid = await dsid_manager.create_dsid(
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        content=payload.content,
        metadata=payload.metadata,
        parent_dsid=payload.parent_dsid,
        public_key=payload.public_key,
        db_session=session,
    )

    return DSIDResponse(
        id=str(dsid.id),
        dsid=dsid.dsid,
        entity_type=dsid.entity_type,
        entity_id=str(dsid.entity_id),
        content_hash=dsid.content_hash,
        version=dsid.version,
        status=dsid.status,
        lineage_depth=dsid.lineage_depth,
        anchored=dsid.anchored,
    )


@router.get("/dsid/{dsid_str}", response_model=DSIDResponse)
async def get_dsid(
    dsid_str: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a DSID by its identifier."""
    dsid = await dsid_manager.get_dsid(dsid_str, session)
    if not dsid:
        raise HTTPException(status_code=404, detail="DSID not found")

    return DSIDResponse(
        id=str(dsid.id),
        dsid=dsid.dsid,
        entity_type=dsid.entity_type,
        entity_id=str(dsid.entity_id),
        content_hash=dsid.content_hash,
        version=dsid.version,
        status=dsid.status,
        lineage_depth=dsid.lineage_depth,
        anchored=dsid.anchored,
    )


@router.get("/dsid/{dsid_str}/lineage", response_model=List[DSIDResponse])
async def get_dsid_lineage(
    dsid_str: str,
    session: AsyncSession = Depends(get_session),
):
    """Get the full lineage chain for a DSID."""
    lineage = await dsid_manager.get_lineage(dsid_str, session)

    return [
        DSIDResponse(
            id=str(d.id),
            dsid=d.dsid,
            entity_type=d.entity_type,
            entity_id=str(d.entity_id),
            content_hash=d.content_hash,
            version=d.version,
            status=d.status,
            lineage_depth=d.lineage_depth,
            anchored=d.anchored,
        )
        for d in lineage
    ]


@router.post("/dsid/{dsid_str}/verify")
async def verify_dsid(
    dsid_str: str,
    content: Dict[str, Any],
    session: AsyncSession = Depends(get_session),
):
    """Verify content against a DSID."""
    is_valid, message = await dsid_manager.verify_dsid(dsid_str, content, session)
    return {"valid": is_valid, "message": message}


@router.post("/dsid/{dsid_str}/revoke")
async def revoke_dsid(
    dsid_str: str,
    reason: str,
    session: AsyncSession = Depends(get_session),
):
    """Revoke a DSID."""
    try:
        dsid = await dsid_manager.revoke_dsid(dsid_str, reason, session)
        return {"status": "revoked", "dsid": dsid.dsid}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== Hash Lineage Endpoints ==============

@router.get("/hash/{hash_value}/lineage")
async def get_hash_lineage(
    hash_value: str,
    session: AsyncSession = Depends(get_session),
):
    """Get the lineage chain for a hash."""
    lineage = await hash_lineage_manager.get_hash_lineage(hash_value, session)

    return [
        {
            "hash": node.hash_value,
            "content_type": node.content_type,
            "depth": node.depth,
            "parent_hash": node.parent_hash,
        }
        for node in lineage
    ]


@router.get("/hash/{hash_value}/tree")
async def get_hash_tree(
    hash_value: str,
    max_depth: int = 10,
    session: AsyncSession = Depends(get_session),
):
    """Get the hash tree starting from a root."""
    tree = await hash_lineage_manager.get_hash_tree(hash_value, session, max_depth)
    return tree


@router.post("/merkle/root")
async def compute_merkle_root(
    hashes: List[str],
):
    """Compute Merkle root from a list of hashes."""
    root = hash_lineage_manager.compute_merkle_root(hashes)
    return {"merkle_root": root, "leaf_count": len(hashes)}


@router.post("/merkle/proof")
async def compute_merkle_proof(
    target_hash: str,
    all_hashes: List[str],
):
    """Compute Merkle proof for a hash."""
    proof = hash_lineage_manager.compute_merkle_proof(target_hash, all_hashes)
    root = hash_lineage_manager.compute_merkle_root(all_hashes)
    return {"proof": proof, "merkle_root": root}


@router.post("/merkle/verify")
async def verify_merkle_proof(
    target_hash: str,
    merkle_root: str,
    proof: List[Dict[str, str]],
):
    """Verify a Merkle proof."""
    is_valid = hash_lineage_manager.verify_merkle_proof(target_hash, merkle_root, proof)
    return {"valid": is_valid}


# ============== Block Endpoints ==============

@router.get("/blocks/latest", response_model=BlockResponse)
async def get_latest_block(
    session: AsyncSession = Depends(get_session),
):
    """Get the latest block."""
    block = await blockchain_manager.get_latest_block(session)
    if not block:
        raise HTTPException(status_code=404, detail="No blocks found")

    return BlockResponse(
        block_number=block.block_number,
        block_hash=block.block_hash,
        previous_block_hash=block.previous_block_hash,
        merkle_root=block.merkle_root,
        transaction_count=block.transaction_count,
        timestamp=block.timestamp.isoformat(),
        anchored=block.anchored,
    )


@router.get("/blocks/{block_number}", response_model=BlockResponse)
async def get_block(
    block_number: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a block by number."""
    block = await blockchain_manager.get_block_by_number(block_number, session)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")

    return BlockResponse(
        block_number=block.block_number,
        block_hash=block.block_hash,
        previous_block_hash=block.previous_block_hash,
        merkle_root=block.merkle_root,
        transaction_count=block.transaction_count,
        timestamp=block.timestamp.isoformat(),
        anchored=block.anchored,
    )


@router.get("/blocks/{block_number}/transactions", response_model=List[TransactionResponse])
async def get_block_transactions(
    block_number: int,
    session: AsyncSession = Depends(get_session),
):
    """Get transactions in a block."""
    block = await blockchain_manager.get_block_by_number(block_number, session)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")

    result = await session.execute(
        select(BlockTransaction)
        .where(BlockTransaction.block_id == block.id)
        .order_by(BlockTransaction.tx_index)
    )
    transactions = result.scalars().all()

    return [
        TransactionResponse(
            tx_hash=tx.tx_hash,
            tx_type=tx.tx_type,
            status=tx.status,
            block_number=tx.block_number,
            from_dsid=tx.from_dsid,
            to_dsid=tx.to_dsid,
        )
        for tx in transactions
    ]


@router.post("/blocks/mine")
async def mine_block(
    validator: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """Mine a new block with pending transactions."""
    block = await blockchain_manager.mine_block(validator=validator, db_session=session)
    if not block:
        return {"status": "no_transactions", "message": "No pending transactions to mine"}

    return {
        "status": "mined",
        "block_number": block.block_number,
        "block_hash": block.block_hash,
        "transaction_count": block.transaction_count,
    }


@router.get("/chain/stats")
async def get_chain_stats(
    session: AsyncSession = Depends(get_session),
):
    """Get blockchain statistics."""
    return await blockchain_manager.get_chain_stats(session)


@router.post("/chain/verify")
async def verify_chain(
    from_block: int = 0,
    to_block: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
):
    """Verify blockchain integrity."""
    return await blockchain_manager.verify_chain(from_block, to_block, session)


# ============== Transaction Endpoints ==============

@router.post("/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    payload: TransactionCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new transaction."""
    tx = await transaction_manager.create_transaction(
        tx_type=payload.tx_type,
        payload=payload.payload,
        from_dsid=payload.from_dsid,
        to_dsid=payload.to_dsid,
        signature=payload.signature,
        db_session=session,
    )

    return TransactionResponse(
        tx_hash=tx.tx_hash,
        tx_type=tx.tx_type,
        status=tx.status,
        block_number=tx.block_number,
        from_dsid=tx.from_dsid,
        to_dsid=tx.to_dsid,
    )


@router.get("/transactions/{tx_hash}", response_model=TransactionResponse)
async def get_transaction(
    tx_hash: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a transaction by hash."""
    tx = await transaction_manager.get_transaction(tx_hash, session)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return TransactionResponse(
        tx_hash=tx.tx_hash,
        tx_type=tx.tx_type,
        status=tx.status,
        block_number=tx.block_number,
        from_dsid=tx.from_dsid,
        to_dsid=tx.to_dsid,
    )


@router.get("/transactions/dsid/{dsid}", response_model=List[TransactionResponse])
async def get_transactions_by_dsid(
    dsid: str,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    """Get transactions involving a DSID."""
    transactions = await transaction_manager.get_transactions_by_dsid(
        dsid, limit=limit, db_session=session
    )

    return [
        TransactionResponse(
            tx_hash=tx.tx_hash,
            tx_type=tx.tx_type,
            status=tx.status,
            block_number=tx.block_number,
            from_dsid=tx.from_dsid,
            to_dsid=tx.to_dsid,
        )
        for tx in transactions
    ]


# ============== Transaction Graph Endpoints ==============

@router.post("/graph/edge")
async def add_graph_edge(
    payload: GraphEdgeCreate,
    session: AsyncSession = Depends(get_session),
):
    """Add an edge to the transaction graph."""
    edge = await graph_manager.add_edge(
        from_tx_hash=payload.from_tx_hash,
        to_tx_hash=payload.to_tx_hash,
        relationship=payload.relationship,
        weight=payload.weight,
        metadata=payload.metadata,
        db_session=session,
    )
    return {"id": str(edge.id), "status": "created"}


@router.get("/graph/{tx_hash}/connected")
async def get_connected_transactions(
    tx_hash: str,
    direction: str = "both",
    relationship: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """Get connected transactions in the graph."""
    edges = await graph_manager.get_connected_transactions(
        tx_hash, direction=direction, relationship=relationship, db_session=session
    )

    return [
        {
            "from": e.from_tx_hash,
            "to": e.to_tx_hash,
            "relationship": e.relationship,
            "weight": e.weight,
        }
        for e in edges
    ]


@router.get("/graph/path")
async def find_transaction_path(
    from_tx: str,
    to_tx: str,
    max_depth: int = 10,
    session: AsyncSession = Depends(get_session),
):
    """Find path between two transactions."""
    path = await graph_manager.get_transaction_path(
        from_tx, to_tx, max_depth=max_depth, db_session=session
    )
    return {"path": path, "length": len(path)}


@router.get("/graph/stats")
async def get_graph_stats(
    session: AsyncSession = Depends(get_session),
):
    """Get transaction graph statistics."""
    return await graph_manager.get_graph_stats(session)


# ============== Audit Chain Endpoints ==============

@router.post("/audit", response_model=AuditEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_audit_entry(
    payload: AuditEntryCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Create a new audit entry with credit deduction."""
    actor_ip = request.client.host if request.client else None
    user_id = request.headers.get("x-user-id")
    
    # Deduct credits for audit entry
    if user_id:
        await deduct_credits(user_id, CREDIT_COSTS["audit_entry"], "blockchain_audit", f"Audit entry: {payload.action}")
        logger.info(f"💳 Deducted {CREDIT_COSTS['audit_entry']} credits for audit entry")

    entry = await audit_manager.create_entry(
        event_type=payload.event_type,
        event_category=payload.event_category,
        action=payload.action,
        actor_dsid=payload.actor_dsid,
        actor_ip=actor_ip,
        target_type=payload.target_type,
        target_id=payload.target_id,
        description=payload.description,
        changes=payload.changes,
        success=payload.success,
        compliance_tags=payload.compliance_tags,
        db_session=session,
    )

    return AuditEntryResponse(
        entry_hash=entry.entry_hash,
        sequence_number=entry.sequence_number,
        event_type=entry.event_type,
        event_category=entry.event_category,
        action=entry.action,
        actor_dsid=entry.actor_dsid,
        success=entry.success,
        timestamp=entry.timestamp.isoformat(),
    )


@router.get("/audit/{entry_hash}", response_model=AuditEntryResponse)
async def get_audit_entry(
    entry_hash: str,
    session: AsyncSession = Depends(get_session),
):
    """Get an audit entry by hash."""
    entry = await audit_manager.get_entry(entry_hash, session)
    if not entry:
        raise HTTPException(status_code=404, detail="Audit entry not found")

    return AuditEntryResponse(
        entry_hash=entry.entry_hash,
        sequence_number=entry.sequence_number,
        event_type=entry.event_type,
        event_category=entry.event_category,
        action=entry.action,
        actor_dsid=entry.actor_dsid,
        success=entry.success,
        timestamp=entry.timestamp.isoformat(),
    )


@router.get("/audit/actor/{actor_dsid}", response_model=List[AuditEntryResponse])
async def get_audit_by_actor(
    actor_dsid: str,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    """Get audit entries for an actor."""
    entries = await audit_manager.get_entries_by_actor(
        actor_dsid, limit=limit, db_session=session
    )

    return [
        AuditEntryResponse(
            entry_hash=e.entry_hash,
            sequence_number=e.sequence_number,
            event_type=e.event_type,
            event_category=e.event_category,
            action=e.action,
            actor_dsid=e.actor_dsid,
            success=e.success,
            timestamp=e.timestamp.isoformat(),
        )
        for e in entries
    ]


@router.get("/audit/category/{category}", response_model=List[AuditEntryResponse])
async def get_audit_by_category(
    category: str,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    """Get audit entries by category."""
    entries = await audit_manager.get_entries_by_category(
        category, limit=limit, db_session=session
    )

    return [
        AuditEntryResponse(
            entry_hash=e.entry_hash,
            sequence_number=e.sequence_number,
            event_type=e.event_type,
            event_category=e.event_category,
            action=e.action,
            actor_dsid=e.actor_dsid,
            success=e.success,
            timestamp=e.timestamp.isoformat(),
        )
        for e in entries
    ]


@router.post("/audit/verify")
async def verify_audit_chain(
    from_sequence: int = 0,
    to_sequence: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
):
    """Verify audit chain integrity."""
    return await audit_manager.verify_chain(from_sequence, to_sequence, session)


@router.get("/audit/stats")
async def get_audit_stats(
    session: AsyncSession = Depends(get_session),
):
    """Get audit chain statistics."""
    return await audit_manager.get_audit_stats(session)


@router.get("/audit/export")
async def export_audit_log(
    from_sequence: int,
    to_sequence: int,
    session: AsyncSession = Depends(get_session),
):
    """Export audit entries for compliance reporting."""
    return await audit_manager.export_audit_log(from_sequence, to_sequence, session)


# ============== AI Audit Compatibility Endpoints ==============

@router.get("/ai-audit/logs", response_model=AuditLogListResponse)
async def list_ai_audit_logs(
    page: int = 1,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    """List audit entries in a format compatible with the old /ai-audit/logs API."""

    if page < 1:
        page = 1
    if limit <= 0 or limit > 100:
        limit = 50

    total_result = await session.execute(select(func.count()).select_from(AuditEntry))
    total = total_result.scalar_one() or 0

    stmt = (
        select(AuditEntry)
        .order_by(AuditEntry.timestamp.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    result = await session.execute(stmt)
    entries = result.scalars().all()

    items = [
        AuditEntryResponse(
            entry_hash=e.entry_hash,
            sequence_number=e.sequence_number,
            event_type=e.event_type,
            event_category=e.event_category,
            action=e.action,
            actor_dsid=e.actor_dsid,
            success=e.success,
            timestamp=e.timestamp.isoformat(),
        )
        for e in entries
    ]

    return AuditLogListResponse(items=items, total=total, page=page, limit=limit, anchored=False)


@router.get("/ai-audit/logs/{entry_hash}", response_model=AuditEntryResponse)
async def get_ai_audit_log(
    entry_hash: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a single AI audit log entry by hash (compat with old API)."""

    entry = await audit_manager.get_entry(entry_hash, session)
    if not entry:
        raise HTTPException(status_code=404, detail="Audit entry not found")

    return AuditEntryResponse(
        entry_hash=entry.entry_hash,
        sequence_number=entry.sequence_number,
        event_type=entry.event_type,
        event_category=entry.event_category,
        action=entry.action,
        actor_dsid=entry.actor_dsid,
        success=entry.success,
        timestamp=entry.timestamp.isoformat(),
    )


# ============== Compliance Endpoints ==============

@router.get("/compliance/gdpr/{user_dsid}")
async def get_gdpr_report(
    user_dsid: str,
    session: AsyncSession = Depends(get_session),
):
    """Generate GDPR compliance report for a user."""
    return await compliance_reporter.generate_gdpr_report(user_dsid, session)


@router.get("/compliance/soc2")
async def get_soc2_report(
    from_date: str,
    to_date: str,
    session: AsyncSession = Depends(get_session),
):
    """Generate SOC2 compliance report."""
    from_dt = datetime.fromisoformat(from_date)
    to_dt = datetime.fromisoformat(to_date)
    return await compliance_reporter.generate_soc2_report(from_dt, to_dt, session)


# ============== Policies Compatibility Endpoints ==============

class PolicyCreateRequest(BaseModel):
    """Policy creation request - compatibility with old backend."""
    name: str
    description: Optional[str] = None
    policy_type: str = "custom"
    rules: Optional[Dict[str, Any]] = None
    is_active: bool = True


class PolicyResponse(BaseModel):
    """Policy response - compatibility with old backend."""
    id: str
    name: str
    description: Optional[str] = None
    policy_type: str
    rules: Dict[str, Any] = {}
    is_active: bool
    created_at: str
    updated_at: str


class PolicyUpdateRequest(BaseModel):
    """Policy update request."""
    name: Optional[str] = None
    description: Optional[str] = None
    rules: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


@router.get("/policies", response_model=List[PolicyResponse])
async def list_policies(
    request: Request,
    policy_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    """List policies - compatibility with old backend.
    
    Policies are stored as audit entries with event_type='policy'.
    """
    user_id = request.headers.get("x-user-id")
    org_id = request.headers.get("x-org-id")
    
    # Query audit entries that represent policies
    stmt = select(AuditEntry).where(
        AuditEntry.event_type == "policy"
    ).order_by(AuditEntry.timestamp.desc()).limit(limit)
    
    if policy_type:
        stmt = stmt.where(AuditEntry.event_category == policy_type)
    
    result = await session.execute(stmt)
    entries = result.scalars().all()
    
    return [
        PolicyResponse(
            id=str(e.entry_hash),
            name=e.action or "Unnamed Policy",
            description=e.event_data.get("description") if e.event_data else None,
            policy_type=e.event_category or "custom",
            rules=e.event_data.get("rules", {}) if e.event_data else {},
            is_active=e.success,
            created_at=e.timestamp.isoformat(),
            updated_at=e.timestamp.isoformat(),
        )
        for e in entries
    ]


@router.post("/policies", response_model=PolicyResponse, status_code=201)
async def create_policy(
    payload: PolicyCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Create a policy - compatibility with old backend.
    
    Stores policy as an audit entry with event_type='policy'.
    """
    user_id = request.headers.get("x-user-id")
    org_id = request.headers.get("x-org-id")
    
    # Create audit entry representing the policy
    entry = await audit_manager.create_entry(
        event_type="policy",
        event_category=payload.policy_type,
        action=payload.name,
        actor_dsid=user_id or "system",
        target_dsid=org_id,
        event_data={
            "description": payload.description,
            "rules": payload.rules or {},
            "is_active": payload.is_active,
        },
        success=payload.is_active,
        db_session=session,
    )
    
    return PolicyResponse(
        id=str(entry.entry_hash),
        name=payload.name,
        description=payload.description,
        policy_type=payload.policy_type,
        rules=payload.rules or {},
        is_active=payload.is_active,
        created_at=entry.timestamp.isoformat(),
        updated_at=entry.timestamp.isoformat(),
    )


@router.get("/policies/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific policy - compatibility with old backend."""
    entry = await audit_manager.get_entry(policy_id, session)
    
    if not entry or entry.event_type != "policy":
        raise HTTPException(status_code=404, detail="Policy not found")
    
    return PolicyResponse(
        id=str(entry.entry_hash),
        name=entry.action or "Unnamed Policy",
        description=entry.event_data.get("description") if entry.event_data else None,
        policy_type=entry.event_category or "custom",
        rules=entry.event_data.get("rules", {}) if entry.event_data else {},
        is_active=entry.success,
        created_at=entry.timestamp.isoformat(),
        updated_at=entry.timestamp.isoformat(),
    )


@router.put("/policies/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: str,
    payload: PolicyUpdateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Update a policy - compatibility with old backend.
    
    Creates a new audit entry representing the updated policy.
    """
    user_id = request.headers.get("x-user-id")
    org_id = request.headers.get("x-org-id")
    
    # Get existing policy
    existing = await audit_manager.get_entry(policy_id, session)
    if not existing or existing.event_type != "policy":
        raise HTTPException(status_code=404, detail="Policy not found")
    
    # Create new entry with updated values
    name = payload.name or existing.action
    policy_type = existing.event_category
    existing_data = existing.event_data or {}
    
    new_data = {
        "description": payload.description if payload.description is not None else existing_data.get("description"),
        "rules": payload.rules if payload.rules is not None else existing_data.get("rules", {}),
        "is_active": payload.is_active if payload.is_active is not None else existing_data.get("is_active", True),
        "previous_version": policy_id,
    }
    
    entry = await audit_manager.create_entry(
        event_type="policy",
        event_category=policy_type,
        action=name,
        actor_dsid=user_id or "system",
        target_dsid=org_id,
        event_data=new_data,
        success=new_data["is_active"],
        db_session=session,
    )
    
    return PolicyResponse(
        id=str(entry.entry_hash),
        name=name,
        description=new_data["description"],
        policy_type=policy_type or "custom",
        rules=new_data["rules"],
        is_active=new_data["is_active"],
        created_at=entry.timestamp.isoformat(),
        updated_at=entry.timestamp.isoformat(),
    )


@router.delete("/policies/{policy_id}")
async def delete_policy(
    policy_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Delete a policy - compatibility with old backend.
    
    Creates an audit entry marking the policy as deleted.
    """
    user_id = request.headers.get("x-user-id")
    
    # Get existing policy
    existing = await audit_manager.get_entry(policy_id, session)
    if not existing or existing.event_type != "policy":
        raise HTTPException(status_code=404, detail="Policy not found")
    
    # Create deletion audit entry
    await audit_manager.create_entry(
        event_type="policy_deleted",
        event_category=existing.event_category,
        action=f"Deleted: {existing.action}",
        actor_dsid=user_id or "system",
        target_dsid=policy_id,
        event_data={"deleted_policy_hash": policy_id},
        success=True,
        db_session=session,
    )
    
    return {"status": "deleted", "id": policy_id}


# ============== Health Endpoint ==============

@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"service": "blockchain", "status": "ok"}


@router.get("/status")
async def status_endpoint():
    """Status endpoint for blockchain service."""
    return {
        "service": "blockchain",
        "status": "operational",
        "version": "0.1.0",
        "features": ["dsid", "hash_lineage", "transactions", "audit", "dual_class_blocks"]
    }


# ============== DUAL-CLASS BLOCKCHAIN ENDPOINTS (HSU-Spec Layer 5) ==============

from .dual_class_blocks import (
    dual_class_blockchain, create_user_block, create_agent_block,
    get_user_block, get_agent_block, get_chain_stats,
    UserBlock, AgentBlock
)
from .crypto_wallet import (
    crypto_wallet_service, create_user_wallet, create_agent_wallet,
    get_wallet, get_wallet_by_entity, sign_message, verify_message,
    transfer_ownership, CryptoWallet, WalletType
)


class CreateUserBlockRequest(BaseModel):
    user_id: str
    public_key: Optional[str] = None
    initial_data: Optional[Dict[str, Any]] = None


class CreateAgentBlockRequest(BaseModel):
    agent_id: str
    agent_hash: str
    owner_id: str
    cluster_id: str
    cluster_name: Optional[str] = ""
    capabilities: Optional[Dict[str, Any]] = None


class TransferAgentRequest(BaseModel):
    agent_id: str
    new_owner_id: str
    transfer_type: str = "permanent"  # permanent, rental, delegation
    rental_duration_hours: Optional[int] = None


class CreateWalletRequest(BaseModel):
    entity_id: str
    wallet_type: str = "user"  # user, agent
    entity_dsid: Optional[str] = None


class SignMessageRequest(BaseModel):
    address: str
    message: str


class VerifyMessageRequest(BaseModel):
    message: str
    signature: str
    signer_address: str


class TransferOwnershipRequest(BaseModel):
    from_address: str
    to_address: str
    asset_type: str
    asset_id: str
    transfer_type: str = "permanent"
    expiry_hours: Optional[int] = None


# ---- User Block Endpoints ----

@router.post("/blocks/user")
async def create_user_block_endpoint(
    payload: CreateUserBlockRequest,
    request: Request,
):
    """Create a User Block (Class U) for a new user."""
    try:
        block = create_user_block(
            user_id=payload.user_id,
            public_key=payload.public_key,
        )
        return {
            "status": "ok",
            "block": block.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blocks/user/{user_id}")
async def get_user_block_endpoint(user_id: str, request: Request):
    """Get the User Block for a user."""
    block = get_user_block(user_id)
    if not block:
        raise HTTPException(status_code=404, detail="User block not found")
    return {"status": "ok", "block": block.to_dict()}


@router.put("/blocks/user/{user_id}")
async def update_user_block_endpoint(
    user_id: str,
    request: Request,
):
    """Update a User Block with new state."""
    try:
        body = await request.json()
        block = dual_class_blockchain.update_user_block(
            user_id=user_id,
            new_sphere_root=body.get("sphere_root"),
            new_agent_dsids=body.get("agent_dsids"),
            transaction_hash=body.get("transaction_hash"),
        )
        if not block:
            raise HTTPException(status_code=404, detail="User block not found")
        return {"status": "ok", "block": block.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Agent Block Endpoints ----

@router.post("/blocks/agent")
async def create_agent_block_endpoint(
    payload: CreateAgentBlockRequest,
    request: Request,
):
    """Create an Agent Block (Class A) for a new agent."""
    try:
        block = create_agent_block(
            agent_id=payload.agent_id,
            agent_hash=payload.agent_hash,
            owner_id=payload.owner_id,
            cluster_id=payload.cluster_id,
            cluster_name=payload.cluster_name or "",
        )
        return {
            "status": "ok",
            "block": block.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blocks/agent/{agent_id}")
async def get_agent_block_endpoint(agent_id: str, request: Request):
    """Get the Agent Block for an agent."""
    block = get_agent_block(agent_id)
    if not block:
        raise HTTPException(status_code=404, detail="Agent block not found")
    return {"status": "ok", "block": block.to_dict()}


@router.put("/blocks/agent/{agent_id}")
async def update_agent_block_endpoint(
    agent_id: str,
    request: Request,
):
    """Update an Agent Block with new state."""
    try:
        body = await request.json()
        block = dual_class_blockchain.update_agent_block(
            agent_id=agent_id,
            new_state_root=body.get("state_root"),
            new_memory_root=body.get("memory_root"),
            interaction_count=body.get("interaction_count", 0),
            success_count=body.get("success_count", 0),
            response_time_ms=body.get("response_time_ms", 0),
            transaction_hash=body.get("transaction_hash"),
        )
        if not block:
            raise HTTPException(status_code=404, detail="Agent block not found")
        return {"status": "ok", "block": block.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/blocks/agent/transfer")
async def transfer_agent_endpoint(
    payload: TransferAgentRequest,
    request: Request,
):
    """Transfer agent ownership to a new user."""
    try:
        block = dual_class_blockchain.transfer_agent_ownership(
            agent_id=payload.agent_id,
            new_owner_id=payload.new_owner_id,
            transfer_type=payload.transfer_type,
            rental_duration_hours=payload.rental_duration_hours,
        )
        if not block:
            raise HTTPException(status_code=404, detail="Agent block not found")
        return {"status": "ok", "block": block.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Chain Stats ----

@router.get("/blocks/stats")
async def get_blockchain_stats(request: Request):
    """Get dual-class blockchain statistics."""
    return {
        "status": "ok",
        "stats": get_chain_stats(),
    }


@router.get("/blocks/verify")
async def verify_blockchain(request: Request):
    """Verify the integrity of the blockchain."""
    is_valid, message = dual_class_blockchain.verify_chain()
    return {
        "status": "ok",
        "valid": is_valid,
        "message": message,
    }


@router.get("/blocks/user/{user_id}/all")
async def get_all_user_blocks(user_id: str, request: Request):
    """Get all blocks related to a user (user block + owned agent blocks)."""
    blocks = dual_class_blockchain.get_blocks_by_user(user_id)
    return {
        "status": "ok",
        "blocks": blocks,
        "count": len(blocks),
    }


# ============== CRYPTO WALLET ENDPOINTS (HSU-Spec Layer 1) ==============

@router.post("/wallet/create")
async def create_wallet_endpoint(
    payload: CreateWalletRequest,
    request: Request,
):
    """Create a new crypto wallet for a user or agent."""
    try:
        wallet_type = WalletType.USER if payload.wallet_type == "user" else WalletType.AGENT
        wallet = crypto_wallet_service.create_wallet(
            entity_id=payload.entity_id,
            wallet_type=wallet_type,
            entity_dsid=payload.entity_dsid,
        )
        return {
            "status": "ok",
            "wallet": wallet.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wallet/{address}")
async def get_wallet_endpoint(address: str, request: Request):
    """Get wallet by address."""
    wallet = get_wallet(address)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return {"status": "ok", "wallet": wallet.to_dict()}


@router.get("/wallet/entity/{entity_id}")
async def get_wallet_by_entity_endpoint(entity_id: str, request: Request):
    """Get wallet by entity ID (user or agent)."""
    wallet = get_wallet_by_entity(entity_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found for entity")
    return {"status": "ok", "wallet": wallet.to_dict()}


@router.post("/wallet/sign")
async def sign_message_endpoint(
    payload: SignMessageRequest,
    request: Request,
):
    """Sign a message with wallet's private key."""
    try:
        signed = sign_message(payload.address, payload.message)
        if not signed:
            raise HTTPException(status_code=400, detail="Failed to sign message")
        return {
            "status": "ok",
            "signed": signed.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wallet/verify")
async def verify_message_endpoint(
    payload: VerifyMessageRequest,
    request: Request,
):
    """Verify a signed message."""
    try:
        is_valid = verify_message(
            payload.message,
            payload.signature,
            payload.signer_address,
        )
        return {
            "status": "ok",
            "verified": is_valid,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wallet/transfer")
async def transfer_ownership_endpoint(
    payload: TransferOwnershipRequest,
    request: Request,
):
    """Create a signed ownership transfer."""
    try:
        transfer = crypto_wallet_service.create_transfer(
            from_address=payload.from_address,
            to_address=payload.to_address,
            asset_type=payload.asset_type,
            asset_id=payload.asset_id,
            transfer_type=payload.transfer_type,
            expiry_hours=payload.expiry_hours,
        )
        if not transfer:
            raise HTTPException(status_code=400, detail="Failed to create transfer")
        return {
            "status": "ok",
            "transfer": transfer.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wallet/{address}/transfers")
async def get_wallet_transfers(address: str, request: Request):
    """Get all transfers involving a wallet."""
    transfers = crypto_wallet_service.get_transfers_by_address(address)
    return {
        "status": "ok",
        "transfers": [t.to_dict() for t in transfers],
        "count": len(transfers),
    }


@router.post("/wallet/{address}/lock")
async def lock_wallet_endpoint(address: str, request: Request):
    """Lock a wallet (prevent transactions)."""
    success = crypto_wallet_service.lock_wallet(address)
    if not success:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return {"status": "ok", "message": "Wallet locked"}


@router.post("/wallet/{address}/unlock")
async def unlock_wallet_endpoint(address: str, request: Request):
    """Unlock a wallet."""
    success = crypto_wallet_service.unlock_wallet(address)
    if not success:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return {"status": "ok", "message": "Wallet unlocked"}


@router.get("/wallet/stats")
async def get_wallet_stats(request: Request):
    """Get wallet service statistics."""
    return {
        "status": "ok",
        "stats": crypto_wallet_service.get_stats(),
    }


# ============== DOMAIN-SEPARATED HASHING ENDPOINTS (HSU-Spec Section 3) ==============

from .domain_hasher import (
    domain_hasher, DomainHasher, HashDomain,
    hash_l1_user, hash_l1_agent, hash_l2_sphere, hash_l3_sphere,
    hash_l4_interaction, hash_l5_ublock, hash_l5_ablock
)
from .encrypted_payload import (
    payload_encryptor, encrypted_node_store, universe_reconstructor,
    encrypt_payload, decrypt_payload, store_encrypted_node,
    fetch_encrypted_node, reconstruct_universe, EncryptedPayload
)


class DomainHashRequest(BaseModel):
    domain: str  # L1_USER, L2_USER_SPHERE, etc.
    data: Any


class EncryptPayloadRequest(BaseModel):
    plaintext: Any
    key: str


class DecryptPayloadRequest(BaseModel):
    encrypted: Dict[str, Any]
    key: str


class StoreNodeRequest(BaseModel):
    payload: Any
    links: List[str] = []
    key: str
    metadata: Optional[Dict[str, Any]] = None


class ReconstructRequest(BaseModel):
    root_hash: str
    key: str
    max_depth: int = 100


@router.post("/hash/domain")
async def compute_domain_hash(payload: DomainHashRequest, request: Request):
    """
    Compute domain-separated hash: H_d(x) = H(d ∥ x)
    
    Domains: L1_USER, L1_AGENT, L2_USER_SPHERE, L3_AGENT_SPHERE, L4_COORD, L5_UBLOCK, L5_ABLOCK
    """
    try:
        domain = HashDomain[payload.domain]
        result = domain_hasher.hash(domain, payload.data)
        return {
            "status": "ok",
            "hash": result.to_dict(),
        }
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid domain: {payload.domain}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hash/user-identity")
async def hash_user_identity_endpoint(request: Request):
    """H_1(x) = H("L1-USER" ∥ public_key)"""
    try:
        body = await request.json()
        public_key = body.get("public_key", "")
        result = domain_hasher.hash_user_identity(public_key)
        return {"status": "ok", "hash": result.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hash/agent-identity")
async def hash_agent_identity_endpoint(request: Request):
    """H_1A(x) = H("L1-AGENT" ∥ public_key)"""
    try:
        body = await request.json()
        public_key = body.get("public_key", "")
        result = domain_hasher.hash_agent_identity(public_key)
        return {"status": "ok", "hash": result.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hash/user-sphere")
async def hash_user_sphere_endpoint(request: Request):
    """H_2(x) = H("L2-USER-SPHERE" ∥ payload ∥ children)"""
    try:
        body = await request.json()
        payload = body.get("payload", {})
        children = body.get("children", [])
        result = domain_hasher.hash_user_sphere(payload, children)
        return {"status": "ok", "hash": result.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hash/agent-sphere")
async def hash_agent_sphere_endpoint(request: Request):
    """H_3(x) = H("L3-AGENT-SPHERE" ∥ payload ∥ semantic ∥ children)"""
    try:
        body = await request.json()
        payload = body.get("payload", {})
        semantic = body.get("semantic", [])
        children = body.get("children", [])
        result = domain_hasher.hash_agent_sphere(payload, semantic, children)
        return {"status": "ok", "hash": result.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hash/interaction")
async def hash_interaction_endpoint(request: Request):
    """H_4(x) = H("L4-COORD" ∥ interaction)"""
    try:
        body = await request.json()
        result = domain_hasher.hash_interaction(
            sender_id=body.get("sender_id", ""),
            receiver_id=body.get("receiver_id", ""),
            timestamp=body.get("timestamp", 0),
            payload=body.get("payload", {}),
        )
        return {"status": "ok", "hash": result.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hash/global-fingerprint")
async def compute_global_fingerprint_endpoint(request: Request):
    """
    Compute global fingerprint: h_final = H(h1 ∥ h2 ∥ h3 ∥ h4 ∥ h5)
    """
    try:
        body = await request.json()
        result = domain_hasher.compute_global_fingerprint(
            h1_identity=body.get("h1", ""),
            h2_user_sphere=body.get("h2", ""),
            h3_agent_sphere=body.get("h3", ""),
            h4_coordination=body.get("h4", ""),
            h5_blockchain=body.get("h5", ""),
        )
        return {"status": "ok", "fingerprint": result.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hash/merkle-root")
async def compute_merkle_root_endpoint(request: Request):
    """Compute Merkle root from list of hashes"""
    try:
        body = await request.json()
        hashes = body.get("hashes", [])
        root = domain_hasher.compute_merkle_root(hashes)
        return {"status": "ok", "merkle_root": root}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== ENCRYPTED PAYLOAD ENDPOINTS (HSU-Spec Layer 2-3) ==============

@router.post("/encrypt/payload")
async def encrypt_payload_endpoint(payload: EncryptPayloadRequest, request: Request):
    """Encrypt a payload with AES-256"""
    try:
        encrypted = encrypt_payload(payload.plaintext, payload.key)
        return {
            "status": "ok",
            "encrypted": encrypted.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decrypt/payload")
async def decrypt_payload_endpoint(payload: DecryptPayloadRequest, request: Request):
    """Decrypt a payload"""
    try:
        encrypted = EncryptedPayload.from_dict(payload.encrypted)
        decrypted = decrypt_payload(encrypted, payload.key)
        return {
            "status": "ok",
            "plaintext": decrypted.to_string(),
            "content_hash": decrypted.content_hash,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/nodes/store")
async def store_node_endpoint(payload: StoreNodeRequest, request: Request):
    """Store an encrypted DAG node"""
    try:
        node_hash = store_encrypted_node(
            payload=payload.payload,
            links=payload.links,
            key=payload.key,
        )
        return {
            "status": "ok",
            "node_hash": node_hash,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/nodes/fetch")
async def fetch_node_endpoint(request: Request):
    """Fetch and decrypt a DAG node"""
    try:
        body = await request.json()
        node_hash = body.get("node_hash", "")
        key = body.get("key", "")
        
        result = fetch_encrypted_node(node_hash, key)
        if result is None:
            raise HTTPException(status_code=404, detail="Node not found or decryption failed")
        
        payload, links = result
        return {
            "status": "ok",
            "payload": payload,
            "links": links,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/universe/reconstruct")
async def reconstruct_universe_endpoint(payload: ReconstructRequest, request: Request):
    """
    Reconstruct a data universe from root hash.
    
    Implements HSU-Spec reconstruction algorithm:
    RECONSTRUCT(rootID, key) → full data structure
    """
    try:
        result = reconstruct_universe(payload.root_hash, payload.key)
        if result is None:
            raise HTTPException(status_code=404, detail="Root node not found")
        
        return {
            "status": "ok",
            "universe": result,
            "stats": universe_reconstructor.get_reconstruction_stats(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/universe/stats")
async def get_universe_stats(request: Request):
    """Get universe reconstruction statistics"""
    return {
        "status": "ok",
        "stats": universe_reconstructor.get_reconstruction_stats(),
    }


# ============== SMART CONTRACT ENDPOINTS (HSU-Spec Section 3.9) ==============

from .smart_contract import (
    parse_contract, validate_contract, contract_engine,
    Contract, ActionType, ParseError
)


class ContractParseRequest(BaseModel):
    source: str


class ContractEvaluateRequest(BaseModel):
    contract_id: str
    agent_hash: str
    action: str  # read, write, execute


@router.post("/contract/parse")
async def parse_contract_endpoint(payload: ContractParseRequest, request: Request):
    """
    Parse a smart contract from DSL source code.
    
    Grammar:
    contract <name> {
        allow agent:<hash> to <action>
        limit <action> to <integer>
        delegate <action> to agent:<hash>
    }
    """
    try:
        contract = parse_contract(payload.source)
        return {
            "status": "ok",
            "contract": contract.to_dict(),
        }
    except ParseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contract/validate")
async def validate_contract_endpoint(payload: ContractParseRequest, request: Request):
    """Validate contract syntax without registering"""
    valid, error = validate_contract(payload.source)
    return {
        "status": "ok",
        "valid": valid,
        "error": error,
    }


@router.post("/contract/register")
async def register_contract_endpoint(payload: ContractParseRequest, request: Request):
    """Parse and register a contract for enforcement"""
    try:
        contract = parse_contract(payload.source)
        contract_engine.register_contract(contract)
        return {
            "status": "ok",
            "contract_id": contract.contract_id,
            "name": contract.name,
            "rules_count": len(contract.rules),
        }
    except ParseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contract/evaluate")
async def evaluate_contract_endpoint(payload: ContractEvaluateRequest, request: Request):
    """
    Evaluate if an action is allowed by a contract.
    
    Checks permission, limit, and delegation rules.
    """
    try:
        action = ActionType.from_string(payload.action)
        result = contract_engine.evaluate(
            contract_id=payload.contract_id,
            agent_hash=payload.agent_hash,
            action=action,
        )
        return {
            "status": "ok",
            "allowed": result.allowed,
            "reason": result.reason,
            "rule_matched": result.rule_matched.to_dict() if result.rule_matched else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contract/{contract_id}")
async def get_contract_endpoint(contract_id: str, request: Request):
    """Get a registered contract by ID"""
    contract = contract_engine.get_contract(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return {
        "status": "ok",
        "contract": contract.to_dict(),
    }


@router.post("/contract/{contract_id}/reset")
async def reset_contract_counts_endpoint(contract_id: str, request: Request):
    """Reset action counts for a contract (for limit rules)"""
    contract_engine.reset_counts(contract_id)
    return {"status": "ok", "message": "Counts reset"}


@router.get("/contract/stats")
async def get_contract_stats_endpoint(request: Request):
    """Get contract engine statistics"""
    return {
        "status": "ok",
        "stats": contract_engine.get_stats(),
    }


# ============== CBOR CODEC ENDPOINTS (HSU-Spec Section 4) ==============

from .cbor_codec import (
    cbor_codec, CBORCodec, CBORTag, InteractionType,
    encode_to_cbor, decode_from_cbor, compute_canonical_hash
)
import base64


class CBOREncodeRequest(BaseModel):
    value: Any


class CBORDecodeRequest(BaseModel):
    data: str  # Base64 encoded


class IdentityNodeRequest(BaseModel):
    public_key: str  # Hex encoded
    signature: Optional[str] = None
    owner_id: Optional[str] = None


class UserDataNodeRequest(BaseModel):
    encrypted_payload: str  # Base64
    links: List[str] = []  # Hex hashes
    timestamp: int


class AgentDataNodeRequest(BaseModel):
    encrypted_payload: str
    links: List[str] = []
    semantic_vector: Optional[List[float]] = None
    cluster_id: Optional[str] = None


class CoordinationNodeRequest(BaseModel):
    encrypted_record: str
    links: List[str] = []
    sender_id: str
    receiver_id: str
    timestamp: int
    interaction_type: int  # 0-3


class UserBlockRequest(BaseModel):
    version: int = 1
    prev_hash: str  # Hex
    user_id: str
    sphere_root: str
    ownership_set: List[Dict[str, str]] = []  # [{agent_id, signature}]
    timestamp: int


class AgentBlockRequest(BaseModel):
    version: int = 1
    prev_hash: str
    agent_id: str
    cluster_id: str
    sphere_root: str
    contracts: List[str] = []
    timestamp: int


@router.post("/cbor/encode")
async def cbor_encode_endpoint(payload: CBOREncodeRequest, request: Request):
    """Encode value to canonical CBOR"""
    try:
        cbor_bytes = encode_to_cbor(payload.value)
        return {
            "status": "ok",
            "cbor": base64.b64encode(cbor_bytes).decode(),
            "size": len(cbor_bytes),
            "hash": compute_canonical_hash(payload.value).hex(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cbor/decode")
async def cbor_decode_endpoint(payload: CBORDecodeRequest, request: Request):
    """Decode CBOR to value"""
    try:
        cbor_bytes = base64.b64decode(payload.data)
        value = decode_from_cbor(cbor_bytes)
        return {
            "status": "ok",
            "value": value,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cbor/node/identity")
async def cbor_identity_node_endpoint(payload: IdentityNodeRequest, request: Request):
    """Encode Layer 1 Identity Node (Tag 60000)"""
    try:
        public_key = bytes.fromhex(payload.public_key)
        signature = bytes.fromhex(payload.signature) if payload.signature else None
        owner_id = bytes.fromhex(payload.owner_id) if payload.owner_id else None
        
        node_id, cbor_bytes = cbor_codec.encode_identity_node(
            public_key=public_key,
            signature=signature,
            owner_id=owner_id,
        )
        return {
            "status": "ok",
            "node_id": node_id.hex(),
            "cbor": base64.b64encode(cbor_bytes).decode(),
            "size": len(cbor_bytes),
            "tag": CBORTag.IDENTITY_NODE,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cbor/node/user-data")
async def cbor_user_data_node_endpoint(payload: UserDataNodeRequest, request: Request):
    """Encode Layer 2 User Data Node (Tag 60001)"""
    try:
        encrypted_payload = base64.b64decode(payload.encrypted_payload)
        links = [bytes.fromhex(h) for h in payload.links]
        
        node_id, cbor_bytes = cbor_codec.encode_user_data_node(
            encrypted_payload=encrypted_payload,
            links=links,
            timestamp=payload.timestamp,
        )
        return {
            "status": "ok",
            "node_id": node_id.hex(),
            "cbor": base64.b64encode(cbor_bytes).decode(),
            "size": len(cbor_bytes),
            "tag": CBORTag.USER_DATA_NODE,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cbor/node/agent-data")
async def cbor_agent_data_node_endpoint(payload: AgentDataNodeRequest, request: Request):
    """Encode Layer 3 Agent Data Node (Tag 60002)"""
    try:
        encrypted_payload = base64.b64decode(payload.encrypted_payload)
        links = [bytes.fromhex(h) for h in payload.links]
        cluster_id = bytes.fromhex(payload.cluster_id) if payload.cluster_id else None
        
        node_id, cbor_bytes = cbor_codec.encode_agent_data_node(
            encrypted_payload=encrypted_payload,
            links=links,
            semantic_vector=payload.semantic_vector,
            cluster_id=cluster_id,
        )
        return {
            "status": "ok",
            "node_id": node_id.hex(),
            "cbor": base64.b64encode(cbor_bytes).decode(),
            "size": len(cbor_bytes),
            "tag": CBORTag.AGENT_DATA_NODE,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cbor/node/coordination")
async def cbor_coordination_node_endpoint(payload: CoordinationNodeRequest, request: Request):
    """Encode Layer 4 Coordination Node (Tag 60003)"""
    try:
        encrypted_record = base64.b64decode(payload.encrypted_record)
        links = [bytes.fromhex(h) for h in payload.links]
        sender_id = bytes.fromhex(payload.sender_id)
        receiver_id = bytes.fromhex(payload.receiver_id)
        interaction_type = InteractionType(payload.interaction_type)
        
        node_id, cbor_bytes = cbor_codec.encode_coordination_node(
            encrypted_record=encrypted_record,
            links=links,
            sender_id=sender_id,
            receiver_id=receiver_id,
            timestamp=payload.timestamp,
            interaction_type=interaction_type,
        )
        return {
            "status": "ok",
            "node_id": node_id.hex(),
            "cbor": base64.b64encode(cbor_bytes).decode(),
            "size": len(cbor_bytes),
            "tag": CBORTag.COORDINATION_NODE,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cbor/block/user")
async def cbor_user_block_endpoint(payload: UserBlockRequest, request: Request):
    """Encode Layer 5 User Block (Tag 60004)"""
    try:
        prev_hash = bytes.fromhex(payload.prev_hash)
        user_id = bytes.fromhex(payload.user_id)
        sphere_root = bytes.fromhex(payload.sphere_root)
        ownership_set = [
            (bytes.fromhex(o["agent_id"]), bytes.fromhex(o["signature"]))
            for o in payload.ownership_set
        ]
        
        block_hash, cbor_bytes = cbor_codec.encode_user_block(
            version=payload.version,
            prev_hash=prev_hash,
            user_id=user_id,
            sphere_root=sphere_root,
            ownership_set=ownership_set,
            timestamp=payload.timestamp,
        )
        return {
            "status": "ok",
            "block_hash": block_hash.hex(),
            "cbor": base64.b64encode(cbor_bytes).decode(),
            "size": len(cbor_bytes),
            "tag": CBORTag.USER_BLOCK,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cbor/block/agent")
async def cbor_agent_block_endpoint(payload: AgentBlockRequest, request: Request):
    """Encode Layer 5 Agent Block (Tag 60005)"""
    try:
        prev_hash = bytes.fromhex(payload.prev_hash)
        agent_id = bytes.fromhex(payload.agent_id)
        cluster_id = bytes.fromhex(payload.cluster_id)
        sphere_root = bytes.fromhex(payload.sphere_root)
        contracts = [bytes.fromhex(c) for c in payload.contracts]
        
        block_hash, cbor_bytes = cbor_codec.encode_agent_block(
            version=payload.version,
            prev_hash=prev_hash,
            agent_id=agent_id,
            cluster_id=cluster_id,
            sphere_root=sphere_root,
            contracts=contracts,
            timestamp=payload.timestamp,
        )
        return {
            "status": "ok",
            "block_hash": block_hash.hex(),
            "cbor": base64.b64encode(cbor_bytes).decode(),
            "size": len(cbor_bytes),
            "tag": CBORTag.AGENT_BLOCK,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cbor/tags")
async def get_cbor_tags_endpoint(request: Request):
    """Get all CBOR tags used in HSU-Spec"""
    return {
        "status": "ok",
        "tags": {
            "IDENTITY_NODE": CBORTag.IDENTITY_NODE,
            "USER_DATA_NODE": CBORTag.USER_DATA_NODE,
            "AGENT_DATA_NODE": CBORTag.AGENT_DATA_NODE,
            "COORDINATION_NODE": CBORTag.COORDINATION_NODE,
            "USER_BLOCK": CBORTag.USER_BLOCK,
            "AGENT_BLOCK": CBORTag.AGENT_BLOCK,
            "SMART_CONTRACT": CBORTag.SMART_CONTRACT,
            "SEMANTIC_VECTOR": CBORTag.SEMANTIC_VECTOR,
            "CLUSTER_METADATA": CBORTag.CLUSTER_METADATA,
        },
        "interaction_types": {
            "USER_TO_AGENT": InteractionType.USER_TO_AGENT,
            "AGENT_TO_AGENT": InteractionType.AGENT_TO_AGENT,
            "AGENT_TO_SYSTEM": InteractionType.AGENT_TO_SYSTEM,
            "SYSTEM_TO_USER": InteractionType.SYSTEM_TO_USER,
        },
    }


# ============== SECTION 5: RECONSTRUCTION & PROOF-OF-EXISTENCE ==============

from .reconstruction import (
    dag_reconstructor, proof_validator, ownership_verifier,
    cluster_rebuilder, system_recovery, default_storage,
    DAGReconstructor, ProofOfExistence, OwnershipVerifier,
    SemanticClusterRebuilder, SystemRecovery, InMemoryStorage,
    ReconstructionError, IntegrityError, ValidationError,
)


class StoreNodeForReconstructionRequest(BaseModel):
    node_id: str  # Hex
    data: str  # Base64 encoded CBOR/JSON


class ReconstructRequest(BaseModel):
    root_id: str  # Hex
    decrypt_key: str  # Hex
    max_depth: int = 1000


class ValidateChainRequest(BaseModel):
    chain: List[Dict[str, Any]]


class VerifyOwnershipRequest(BaseModel):
    agent_id: str  # Hex
    owner_public_key: str  # Hex
    signature: str  # Hex


class RebuildClustersRequest(BaseModel):
    agent_nodes: List[Dict[str, Any]]
    num_clusters: int = 10


class SystemRecoveryRequest(BaseModel):
    user_root_id: str  # Hex
    user_key: str  # Hex
    agent_roots: List[Dict[str, str]]  # [{id, key}]
    blockchain: List[Dict[str, Any]]


@router.post("/reconstruction/store-node")
async def store_node_for_reconstruction(payload: StoreNodeForReconstructionRequest, request: Request):
    """Store a node for later reconstruction"""
    try:
        node_id = bytes.fromhex(payload.node_id)
        data = base64.b64decode(payload.data)
        default_storage.store(node_id, data)
        return {
            "status": "ok",
            "node_id": payload.node_id,
            "size": len(data),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reconstruction/reconstruct")
async def reconstruct_dag(payload: ReconstructRequest, request: Request):
    """
    Section 5.1: Recursive DAG Reconstruction
    
    Reconstruct entire universe from root hash.
    """
    try:
        root_id = bytes.fromhex(payload.root_id)
        decrypt_key = bytes.fromhex(payload.decrypt_key)
        
        result = dag_reconstructor.reconstruct_universe(
            root_id=root_id,
            decrypt_key=decrypt_key,
            max_depth=payload.max_depth,
        )
        
        return {
            "status": "ok",
            "universe": result.to_dict(),
            "stats": dag_reconstructor.get_stats(),
        }
    except ReconstructionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reconstruction/stats")
async def get_reconstruction_stats(request: Request):
    """Get reconstruction statistics"""
    return {
        "status": "ok",
        "stats": dag_reconstructor.get_stats(),
    }


@router.post("/reconstruction/clear-cache")
async def clear_reconstruction_cache(request: Request):
    """Clear reconstruction cache"""
    dag_reconstructor.clear_cache()
    return {"status": "ok", "message": "Cache cleared"}


@router.post("/proof/validate-chain")
async def validate_blockchain_chain(payload: ValidateChainRequest, request: Request):
    """
    Section 5.3: Blockchain Proof-of-Existence Validation
    
    Validates:
    1. Hash(block) == blockID
    2. prevHash links are correct
    3. Ownership signatures
    4. Sphere roots exist
    """
    try:
        result = proof_validator.validate_chain(payload.chain)
        return {
            "status": "ok",
            "valid": result.valid,
            "blocks_validated": result.blocks_validated,
            "errors": result.errors,
            "block_results": [
                {
                    "block_id": r.block_id.hex() if isinstance(r.block_id, bytes) else r.block_id,
                    "valid": r.valid,
                    "errors": r.errors,
                    "warnings": r.warnings,
                }
                for r in result.block_results
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proof/validate-block")
async def validate_single_block(request: Request):
    """Validate a single block"""
    try:
        body = await request.json()
        result = proof_validator.validate_block(body)
        return {
            "status": "ok",
            "valid": result.valid,
            "block_id": result.block_id.hex() if isinstance(result.block_id, bytes) else result.block_id,
            "errors": result.errors,
            "warnings": result.warnings,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proof/existence")
async def generate_existence_proof(request: Request):
    """Generate proof-of-existence for a node"""
    try:
        body = await request.json()
        node_id = bytes.fromhex(body.get("node_id", ""))
        chain = body.get("chain", [])
        
        proof = proof_validator.generate_existence_proof(node_id, chain)
        
        if proof:
            return {"status": "ok", "proof": proof}
        else:
            return {"status": "ok", "proof": None, "message": "Node not found in chain"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ownership/verify")
async def verify_ownership_endpoint(payload: VerifyOwnershipRequest, request: Request):
    """
    Section 5.4: Ownership Transfer Verification
    
    Verify that owner signed the agent_id.
    """
    try:
        agent_id = bytes.fromhex(payload.agent_id)
        owner_key = bytes.fromhex(payload.owner_public_key)
        signature = bytes.fromhex(payload.signature)
        
        valid = ownership_verifier.verify_ownership(agent_id, owner_key, signature)
        
        return {
            "status": "ok",
            "valid": valid,
            "agent_id": payload.agent_id,
            "owner": payload.owner_public_key[:32] + "...",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ownership/create-proof")
async def create_ownership_proof_endpoint(request: Request):
    """Create an ownership proof object"""
    try:
        body = await request.json()
        
        proof = ownership_verifier.create_ownership_proof(
            agent_id=bytes.fromhex(body.get("agent_id", "")),
            owner_id=bytes.fromhex(body.get("owner_id", "")),
            signature=bytes.fromhex(body.get("signature", "")),
            timestamp=body.get("timestamp", 0),
            transfer_type=body.get("transfer_type", "permanent"),
        )
        
        return {
            "status": "ok",
            "proof": proof.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clusters/rebuild")
async def rebuild_semantic_clusters(payload: RebuildClustersRequest, request: Request):
    """
    Section 5.5: Semantic Cluster Rebuild
    
    Rebuild cluster assignments for all agents.
    """
    try:
        rebuilder = SemanticClusterRebuilder(num_clusters=payload.num_clusters)
        assignments = rebuilder.rebuild_clusters(payload.agent_nodes)
        
        return {
            "status": "ok",
            "assignments": [
                {
                    "agent_id": a.agent_id.hex() if isinstance(a.agent_id, bytes) else a.agent_id,
                    "cluster_id": a.cluster_id,
                    "centroid_distance": a.centroid_distance,
                }
                for a in assignments
            ],
            "centroids": rebuilder.get_centroids(),
            "num_clusters": len(set(a.cluster_id for a in assignments)),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recovery/full")
async def full_system_recovery(payload: SystemRecoveryRequest, request: Request):
    """
    Section 5.7: Full System Recovery
    
    Orchestrates complete recovery of:
    - User universe (Layer 2)
    - Agent universes (Layer 3)
    - Blockchain validation (Layer 5)
    - Semantic cluster rebuild
    """
    try:
        user_root_id = bytes.fromhex(payload.user_root_id)
        user_key = bytes.fromhex(payload.user_key)
        
        agent_roots = [
            (bytes.fromhex(a["id"]), bytes.fromhex(a["key"]))
            for a in payload.agent_roots
        ]
        
        result = system_recovery.recover_system(
            user_root_id=user_root_id,
            user_key=user_key,
            agent_root_ids=agent_roots,
            blockchain=payload.blockchain,
        )
        
        return {
            "status": "ok",
            "result": result.to_dict(),
        }
    except ReconstructionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recovery/stats")
async def get_recovery_stats(request: Request):
    """Get system recovery statistics"""
    return {
        "status": "ok",
        "reconstruction_stats": dag_reconstructor.get_stats(),
        "storage_nodes": len(default_storage._nodes),
    }


# Sections 6-43 deleted: 5,200+ lines of HSU-Spec documentation-as-Python endpoints
# (network_protocol, benchmarking, interoperability, agent_lifecycle, security_threat_model,
#  compliance_audit, semantic_taxonomy, economic_model, reputation_trust, infrastructure_deployment,
#  federation_sovereignty, protocol_roadmap, workforce_simulation, adoption_strategy,
#  ethical_governance, agent_economy, technical_specification, legal_regulatory,
#  security_architecture, implementation_guide, strategic_partnerships, commercialization,
#  standards_positioning, scaling_performance)
# All backing .py files deleted — they were spec documents, not executable blockchain code.


# ============== On-Chain Registration Endpoints ==============

@router.post("/register-on-chain")
async def register_agent_on_chain(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    Register an agent on the Base Sepolia blockchain.
    
    Requires:
    - agent_id: The platform agent ID
    - The agent must have a DSID already
    
    This creates a blockchain transaction internally and,
    if ANCHOR_PRIVATE_KEY is configured, writes to Base Sepolia AgentRegistry.
    """
    import os
    import httpx as httpx_client

    body = await request.json()
    agent_id = body.get("agent_id")
    
    if not agent_id:
        return {"error": "agent_id is required"}, 400

    # 1. Look up the DSID for this agent
    from .dsid import dsid_manager
    dsid = await dsid_manager.get_dsid_by_entity("agent", agent_id, session)
    
    if not dsid:
        return {"status": "error", "message": "Agent has no DSID. Create agent first."}

    # 2. Create internal blockchain transaction
    tx = await transaction_manager.create_transaction(
        tx_type="agent_on_chain_register",
        payload={
            "dsid": dsid.dsid,
            "agent_id": agent_id,
            "content_hash": dsid.content_hash,
            "entity_type": dsid.entity_type,
            "action": "register_on_chain",
        },
        from_dsid=dsid.dsid,
        to_dsid=dsid.dsid,
        db_session=session,
    )

    result = {
        "status": "registered_internal",
        "dsid": dsid.dsid,
        "content_hash": dsid.content_hash,
        "internal_tx_hash": tx.tx_hash,
        "chain_id": "resonant-genesis-1",
        "external_chain": None,
        "external_tx_hash": None,
        "basescan_url": None,
    }

    # 3. If private key is configured, also write to Base Sepolia
    anchor_private_key = os.getenv("ANCHOR_PRIVATE_KEY", "")
    agent_contract = os.getenv("BASE_AGENT_CONTRACT", "")
    rpc_url = os.getenv("BASE_RPC_URL", "") or os.getenv("ANCHOR_RPC_URL", "")

    if anchor_private_key and agent_contract and rpc_url:
        try:
            from web3 import Web3
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            if w3.is_connected():
                abi = [{
                    "inputs": [
                        {"name": "manifestHash", "type": "bytes32"},
                        {"name": "metadataUri", "type": "string"},
                    ],
                    "name": "registerAgent",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                }]
                contract = w3.eth.contract(
                    address=Web3.to_checksum_address(agent_contract),
                    abi=abi,
                )
                manifest_bytes = bytes.fromhex(dsid.content_hash[:64])
                metadata_uri = f"resonant://agent/{agent_id}/dsid/{dsid.dsid}"
                account = w3.eth.account.from_key(anchor_private_key)
                
                tx_on_chain = contract.functions.registerAgent(
                    manifest_bytes, metadata_uri
                ).build_transaction({
                    "from": account.address,
                    "nonce": w3.eth.get_transaction_count(account.address),
                    "gas": 200000,
                    "gasPrice": w3.eth.gas_price,
                })
                signed = account.sign_transaction(tx_on_chain)
                tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

                chain_id = os.getenv("BASE_CHAIN_ID", "84532")
                basescan_base = "https://sepolia.basescan.org" if "sepolia" in rpc_url.lower() else "https://basescan.org"

                result["status"] = "registered_on_chain"
                result["external_chain"] = f"base-sepolia (chain {chain_id})"
                result["external_tx_hash"] = tx_hash.hex()
                result["basescan_url"] = f"{basescan_base}/tx/0x{tx_hash.hex()}"
        except Exception as e:
            result["external_error"] = str(e)

    return result


@router.get("/agent-chain-status/{agent_id}")
async def get_agent_chain_status(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get the on-chain registration status for an agent."""
    import os
    from .dsid import dsid_manager
    from sqlalchemy import select

    dsid = await dsid_manager.get_dsid_by_entity("agent", agent_id, session)
    
    if not dsid:
        return {
            "agent_id": agent_id,
            "has_dsid": False,
            "dsid": None,
            "internal_chain": {"registered": False},
            "external_chain": {"registered": False},
        }

    # Check for internal blockchain transactions
    result = await session.execute(
        select(BlockTransaction)
        .where(BlockTransaction.tx_type == "agent_on_chain_register")
        .where(BlockTransaction.from_dsid == dsid.dsid)
        .order_by(BlockTransaction.created_at.desc())
        .limit(1)
    )
    on_chain_tx = result.scalar_one_or_none()

    # Check for any DSID registration tx (from backfill or creation)
    result2 = await session.execute(
        select(BlockTransaction)
        .where(BlockTransaction.tx_type == "dsid_register")
        .where(BlockTransaction.to_dsid == dsid.dsid)
        .order_by(BlockTransaction.created_at.desc())
        .limit(1)
    )
    dsid_tx = result2.scalar_one_or_none()

    # Build block info
    block_info = None
    tx_for_block = on_chain_tx or dsid_tx
    if tx_for_block and tx_for_block.block_number is not None:
        from .models import Block
        block_result = await session.execute(
            select(Block).where(Block.block_number == tx_for_block.block_number)
        )
        block = block_result.scalar_one_or_none()
        if block:
            block_info = {
                "block_number": block.block_number,
                "block_hash": block.block_hash,
                "merkle_root": block.merkle_root,
                "timestamp": block.timestamp.isoformat() if block.timestamp else None,
                "validator": block.validator,
            }

    agent_contract = os.getenv("BASE_AGENT_CONTRACT", "")
    rpc_url = os.getenv("BASE_RPC_URL", "") or os.getenv("ANCHOR_RPC_URL", "")
    chain_id = os.getenv("BASE_CHAIN_ID", "84532")

    return {
        "agent_id": agent_id,
        "has_dsid": True,
        "dsid": dsid.dsid,
        "content_hash": dsid.content_hash,
        "created_at": dsid.created_at.isoformat() if dsid.created_at else None,
        "lineage_depth": dsid.lineage_depth,
        "internal_chain": {
            "chain_id": "resonant-genesis-1",
            "registered": dsid_tx is not None,
            "tx_hash": dsid_tx.tx_hash if dsid_tx else None,
            "block_number": dsid_tx.block_number if dsid_tx else None,
            "status": dsid_tx.status if dsid_tx else None,
            "block": block_info,
        },
        "external_chain": {
            "chain": f"Base Sepolia (chain {chain_id})",
            "registered": on_chain_tx is not None and "external_tx_hash" in (on_chain_tx.payload or {}),
            "agent_contract": agent_contract,
            "rpc_url": rpc_url[:50] + "..." if rpc_url else None,
            "on_chain_tx_hash": on_chain_tx.tx_hash if on_chain_tx else None,
        },
    }


@router.get("/chain/overview")
async def get_chain_overview(
    session: AsyncSession = Depends(get_session),
):
    """Get a comprehensive overview of the internal blockchain."""
    from sqlalchemy import select, func
    from .models import Block, DSID, HashNode, AuditEntry, AnchorRecord
    from .config import settings as bc_settings

    blocks = (await session.execute(select(func.count(Block.id)))).scalar() or 0
    txs = (await session.execute(select(func.count(BlockTransaction.id)))).scalar() or 0
    pending = (await session.execute(
        select(func.count(BlockTransaction.id)).where(BlockTransaction.status == "pending")
    )).scalar() or 0
    confirmed = (await session.execute(
        select(func.count(BlockTransaction.id)).where(BlockTransaction.status == "confirmed")
    )).scalar() or 0
    dsids = (await session.execute(select(func.count(DSID.id)))).scalar() or 0
    hash_nodes = (await session.execute(select(func.count(HashNode.id)))).scalar() or 0
    audit_entries = (await session.execute(select(func.count(AuditEntry.id)))).scalar() or 0
    anchors = (await session.execute(select(func.count(AnchorRecord.id)))).scalar() or 0

    latest_block = (await session.execute(
        select(Block).order_by(Block.block_number.desc()).limit(1)
    )).scalar_one_or_none()

    # TX type breakdown
    tx_types = dict((await session.execute(
        select(BlockTransaction.tx_type, func.count(BlockTransaction.id))
        .group_by(BlockTransaction.tx_type)
    )).all())

    return {
        "chain_id": bc_settings.CHAIN_ID,
        "status": "active",
        "miner": "resonant-genesis-node-0",
        "mine_interval_seconds": 10,
        "blocks": blocks,
        "transactions": {
            "total": txs,
            "pending": pending,
            "confirmed": confirmed,
            "by_type": tx_types,
        },
        "dsids": dsids,
        "hash_nodes": hash_nodes,
        "audit_entries": audit_entries,
        "anchor_records": anchors,
        "latest_block": {
            "number": latest_block.block_number if latest_block else -1,
            "hash": latest_block.block_hash if latest_block else None,
            "merkle_root": latest_block.merkle_root if latest_block else None,
            "tx_count": latest_block.transaction_count if latest_block else 0,
            "timestamp": latest_block.timestamp.isoformat() if latest_block and latest_block.timestamp else None,
        } if latest_block else None,
    }
