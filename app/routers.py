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


# ============== SECTION 6: NODE ROLES & NETWORK PROTOCOL ==============

from .network_protocol import (
    network_manager, NetworkManager, NetworkMessage, MessageType,
    StorageNode, ExecutionNode, SemanticNode, RegistryNode,
    PeerInfo, create_message,
    default_storage_node, default_execution_node,
    default_semantic_node, default_registry_node,
)


class CreateNodeRequest(BaseModel):
    node_type: str  # storage, execution, semantic, registry
    node_id: Optional[str] = None
    num_clusters: int = 10  # For semantic nodes


class StoreNodeRequest(BaseModel):
    node_id: str  # Hex - the DAG node ID
    data: str  # Hex - the CBOR data


class SendMessageRequest(BaseModel):
    from_node: str
    to_node: str
    msg_type: int
    payload: Dict[str, Any]


class SubmitBlockRequest(BaseModel):
    block: Dict[str, Any]


class SubmitVectorRequest(BaseModel):
    agent_id: str  # Hex
    vector: List[float]


class OwnershipTransferRequest(BaseModel):
    agent_id: str
    old_owner: str
    new_owner: str
    signature: str


@router.post("/network/node/create")
async def create_network_node(payload: CreateNodeRequest, request: Request):
    """
    Section 6.1: Create a new network node
    
    Node types:
    - storage: Store and serve DAG nodes
    - execution: Reconstruct universes, execute agents
    - semantic: Maintain semantic clusters
    - registry: Maintain dual-class blockchain
    """
    try:
        if payload.node_type == "storage":
            node = network_manager.create_storage_node(payload.node_id)
        elif payload.node_type == "execution":
            node = network_manager.create_execution_node(payload.node_id)
        elif payload.node_type == "semantic":
            node = network_manager.create_semantic_node(payload.node_id, payload.num_clusters)
        elif payload.node_type == "registry":
            node = network_manager.create_registry_node(payload.node_id)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown node type: {payload.node_type}")
        
        return {
            "status": "ok",
            "node_id": node.node_id,
            "node_type": node.node_type,
            "peers": len(node.peers),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/network/nodes")
async def list_network_nodes(request: Request):
    """List all network nodes"""
    return {
        "status": "ok",
        "nodes": {
            "storage": list(network_manager.storage_nodes.keys()),
            "execution": list(network_manager.execution_nodes.keys()),
            "semantic": list(network_manager.semantic_nodes.keys()),
            "registry": list(network_manager.registry_nodes.keys()),
        },
        "total": len(network_manager._all_nodes),
    }


@router.get("/network/node/{node_id}")
async def get_network_node(node_id: str, request: Request):
    """Get details of a specific node"""
    node = network_manager.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    return {
        "status": "ok",
        "node_id": node.node_id,
        "node_type": node.node_type,
        "state": node.get_state(),
        "stats": node.get_stats(),
        "peers": [p.to_dict() for p in node.peers.values()],
    }


@router.get("/network/stats")
async def get_network_stats(request: Request):
    """Get overall network statistics"""
    return {
        "status": "ok",
        "stats": network_manager.get_network_stats(),
    }


# === Storage Node RPCs (Section 6.1.1) ===

@router.post("/network/storage/store")
async def storage_node_store(payload: StoreNodeRequest, request: Request):
    """
    Storage Node RPC: PutNode
    
    Store a DAG node in the storage network.
    """
    try:
        node_id = bytes.fromhex(payload.node_id)
        data = bytes.fromhex(payload.data)
        
        success = default_storage_node.store(node_id, data)
        
        return {
            "status": "ok" if success else "error",
            "node_id": payload.node_id,
            "stored": success,
            "size": len(data),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/network/storage/fetch/{node_id}")
async def storage_node_fetch(node_id: str, request: Request):
    """
    Storage Node RPC: GetNode
    
    Fetch a DAG node from storage.
    """
    try:
        node_id_bytes = bytes.fromhex(node_id)
        data = default_storage_node.fetch(node_id_bytes)
        
        if data is None:
            raise HTTPException(status_code=404, detail="Node not found")
        
        return {
            "status": "ok",
            "node_id": node_id,
            "data": data.hex(),
            "size": len(data),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/network/storage/has/{node_id}")
async def storage_node_has(node_id: str, request: Request):
    """
    Storage Node RPC: HasNode
    
    Check if a node exists in storage.
    """
    try:
        node_id_bytes = bytes.fromhex(node_id)
        exists = default_storage_node.has_node(node_id_bytes)
        
        return {
            "status": "ok",
            "node_id": node_id,
            "exists": exists,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/network/storage/stats")
async def storage_node_stats(request: Request):
    """Get storage node statistics"""
    return {
        "status": "ok",
        "stats": default_storage_node.get_storage_stats(),
    }


# === Execution Node RPCs (Section 6.1.2) ===

@router.post("/network/execution/reconstruct")
async def execution_node_reconstruct(request: Request):
    """
    Execution Node RPC: Reconstruct
    
    Reconstruct a DAG universe from root hash.
    """
    try:
        body = await request.json()
        root_id = bytes.fromhex(body.get("root_id", ""))
        decrypt_key = bytes.fromhex(body.get("decrypt_key", "00" * 32))
        
        result = await default_execution_node.reconstruct(root_id, decrypt_key)
        
        return {
            "status": "ok",
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/network/execution/execute")
async def execution_node_execute(request: Request):
    """
    Execution Node RPC: ExecuteAgent
    
    Execute agent logic.
    """
    try:
        body = await request.json()
        agent_id = bytes.fromhex(body.get("agent_id", ""))
        input_data = body.get("input", {})
        
        result = await default_execution_node.execute_agent(agent_id, input_data)
        
        return {
            "status": "ok",
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/network/execution/stats")
async def execution_node_stats(request: Request):
    """Get execution node statistics"""
    return {
        "status": "ok",
        "stats": default_execution_node.get_execution_stats(),
    }


# === Semantic Node RPCs (Section 6.1.3) ===

@router.post("/network/semantic/submit-vector")
async def semantic_node_submit_vector(payload: SubmitVectorRequest, request: Request):
    """
    Semantic Node RPC: SubmitVector
    
    Submit an agent's semantic vector for clustering.
    """
    try:
        agent_id = bytes.fromhex(payload.agent_id)
        cluster_id = default_semantic_node.submit_vector(agent_id, payload.vector)
        
        return {
            "status": "ok",
            "agent_id": payload.agent_id,
            "cluster_id": cluster_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/network/semantic/cluster/{agent_id}")
async def semantic_node_get_cluster(agent_id: str, request: Request):
    """
    Semantic Node RPC: GetCluster
    
    Get cluster assignment for an agent.
    """
    try:
        agent_id_bytes = bytes.fromhex(agent_id)
        cluster_id = default_semantic_node.get_cluster(agent_id_bytes)
        
        return {
            "status": "ok",
            "agent_id": agent_id,
            "cluster_id": cluster_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/network/semantic/update-clusters")
async def semantic_node_update_clusters(request: Request):
    """
    Semantic Node RPC: UpdateClusters
    
    Recompute all clusters and broadcast updates.
    """
    try:
        result = await default_semantic_node.update_clusters()
        
        return {
            "status": "ok",
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/network/semantic/stats")
async def semantic_node_stats(request: Request):
    """Get semantic node statistics"""
    return {
        "status": "ok",
        "stats": default_semantic_node.get_semantic_stats(),
    }


# === Registry Node RPCs (Section 6.1.4) ===

@router.post("/network/registry/submit-block")
async def registry_node_submit_block(payload: SubmitBlockRequest, request: Request):
    """
    Registry Node RPC: SubmitBlock
    
    Submit and validate a block for the blockchain.
    """
    try:
        result = await default_registry_node.submit_block(payload.block)
        
        return {
            "status": "ok",
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/network/registry/chain-head")
async def registry_node_chain_head(request: Request):
    """
    Registry Node RPC: GetChainHead
    
    Get the latest block ID.
    """
    head = default_registry_node.get_chain_head()
    
    return {
        "status": "ok",
        "chain_head": head,
        "chain_length": default_registry_node.get_chain_length(),
    }


@router.get("/network/registry/block/{block_id}")
async def registry_node_get_block(block_id: str, request: Request):
    """
    Registry Node RPC: GetBlock
    
    Get a block by ID.
    """
    block = default_registry_node.get_block(block_id)
    
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    
    return {
        "status": "ok",
        "block": block,
    }


@router.post("/network/registry/ownership-transfer")
async def registry_node_ownership_transfer(payload: OwnershipTransferRequest, request: Request):
    """
    Section 6.6: Ownership Transfer Event
    
    Handle ownership transfer of an agent.
    """
    try:
        result = await default_registry_node.handle_ownership_transfer(
            agent_id=payload.agent_id,
            old_owner=payload.old_owner,
            new_owner=payload.new_owner,
            signature=payload.signature,
        )
        
        return {
            "status": "ok",
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/network/registry/owner/{agent_id}")
async def registry_node_get_owner(agent_id: str, request: Request):
    """Get current owner of an agent"""
    owner = default_registry_node.get_owner(agent_id)
    
    return {
        "status": "ok",
        "agent_id": agent_id,
        "owner": owner,
    }


@router.get("/network/registry/stats")
async def registry_node_stats(request: Request):
    """Get registry node statistics"""
    return {
        "status": "ok",
        "stats": default_registry_node.get_registry_stats(),
    }


# === Network Messaging (Section 6.2-6.7) ===

@router.post("/network/message/send")
async def send_network_message(payload: SendMessageRequest, request: Request):
    """
    Send a message between nodes.
    
    Message types (Section 6.2):
    0: GET_NODE
    1: NODE_DATA
    2: BLOCK_PROPAGATE
    3: BLOCK_REQUEST
    4: BLOCK_RESPONSE
    5: VECTOR_SUBMIT
    6: CLUSTER_UPDATE
    7: OWNERSHIP_EVENT
    8: HEARTBEAT
    """
    try:
        message = create_message(
            MessageType(payload.msg_type),
            payload.payload,
            payload.from_node,
        )
        
        response = await network_manager.route_message(
            payload.from_node,
            payload.to_node,
            message,
        )
        
        return {
            "status": "ok",
            "message_id": message.message_id,
            "response": response.to_dict() if response else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/network/heartbeat")
async def broadcast_heartbeats(request: Request):
    """
    Section 6.7: Broadcast heartbeats from all nodes
    """
    try:
        await network_manager.broadcast_heartbeats()
        
        return {
            "status": "ok",
            "message": "Heartbeats broadcast",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/network/message-types")
async def get_message_types(request: Request):
    """Get all network message types"""
    return {
        "status": "ok",
        "message_types": {
            "GET_NODE": MessageType.GET_NODE.value,
            "NODE_DATA": MessageType.NODE_DATA.value,
            "BLOCK_PROPAGATE": MessageType.BLOCK_PROPAGATE.value,
            "BLOCK_REQUEST": MessageType.BLOCK_REQUEST.value,
            "BLOCK_RESPONSE": MessageType.BLOCK_RESPONSE.value,
            "VECTOR_SUBMIT": MessageType.VECTOR_SUBMIT.value,
            "CLUSTER_UPDATE": MessageType.CLUSTER_UPDATE.value,
            "OWNERSHIP_EVENT": MessageType.OWNERSHIP_EVENT.value,
            "HEARTBEAT": MessageType.HEARTBEAT.value,
            "ERROR": MessageType.ERROR.value,
            "ACK": MessageType.ACK.value,
        },
    }


# ============== FINGERPRINT (H_final) ==============

from .domain_hasher import (
    compute_fingerprint, compute_user_fingerprint, compute_agent_fingerprint,
    verify_fingerprint, compare_fingerprints, UniverseFingerprint,
)


class ComputeFingerprintRequest(BaseModel):
    h1: str  # Layer 1 identity hash
    h2: str  # Layer 2 user sphere hash
    h3: str  # Layer 3 agent sphere hash
    h4: str  # Layer 4 coordination hash
    h5: str  # Layer 5 blockchain hash


class UserFingerprintRequest(BaseModel):
    user_public_key: str
    user_sphere_root: str
    agent_sphere_roots: List[str]
    coordination_root: str
    blockchain_head: str


class AgentFingerprintRequest(BaseModel):
    agent_public_key: str
    owner_sphere_root: str
    agent_sphere_root: str
    coordination_root: str
    blockchain_head: str


@router.post("/fingerprint/compute")
async def compute_universe_fingerprint(payload: ComputeFingerprintRequest, request: Request):
    """
    Compute Hash Universe Fingerprint.
    
    H_final = H(H1 ∥ H2 ∥ H3 ∥ H4 ∥ H5)
    
    This is the root-of-roots representing the entire universe state.
    """
    try:
        fingerprint = compute_fingerprint(
            h1=payload.h1,
            h2=payload.h2,
            h3=payload.h3,
            h4=payload.h4,
            h5=payload.h5,
        )
        
        return {
            "status": "ok",
            "fingerprint": fingerprint.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fingerprint/user")
async def compute_user_universe_fingerprint(payload: UserFingerprintRequest, request: Request):
    """Compute fingerprint for a user's entire universe."""
    try:
        fingerprint = compute_user_fingerprint(
            user_public_key=payload.user_public_key,
            user_sphere_root=payload.user_sphere_root,
            agent_sphere_roots=payload.agent_sphere_roots,
            coordination_root=payload.coordination_root,
            blockchain_head=payload.blockchain_head,
        )
        
        return {
            "status": "ok",
            "fingerprint": fingerprint.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fingerprint/agent")
async def compute_agent_universe_fingerprint(payload: AgentFingerprintRequest, request: Request):
    """Compute fingerprint for an agent's universe."""
    try:
        fingerprint = compute_agent_fingerprint(
            agent_public_key=payload.agent_public_key,
            owner_sphere_root=payload.owner_sphere_root,
            agent_sphere_root=payload.agent_sphere_root,
            coordination_root=payload.coordination_root,
            blockchain_head=payload.blockchain_head,
        )
        
        return {
            "status": "ok",
            "fingerprint": fingerprint.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== SECTION 21: MULTI-AGENT GOVERNANCE ==============

from .governance import (
    governance_engine, GovernanceEngine,
    GovernancePolicy, OwnershipGovernance, ContractGovernance,
    SemanticGovernance, BehavioralGovernance,
    AgentClass, AGENT_CLASSIFICATIONS,
    GovernanceLayer, ValidationResult,
)


class AddPolicyRequest(BaseModel):
    name: str
    description: str
    source: str  # human, enterprise, government
    constraints: List[str]
    applies_to: List[str]
    priority: int = 50


class SetOwnershipRequest(BaseModel):
    agent_id: str
    owner_id: str
    manager_ids: List[str] = []
    permissions: List[str] = []


class AddContractRequest(BaseModel):
    agent_id: str
    allowed_actions: List[str] = []
    forbidden_actions: List[str] = []
    resource_budgets: Dict[str, int] = {}
    escalation_rules: List[Dict[str, Any]] = []
    logging_requirements: List[str] = []


class AddSemanticRuleRequest(BaseModel):
    cluster_id: str
    cluster_name: str
    rules: List[Dict[str, Any]] = []
    audit_requirements: List[str] = []
    supervision_required: bool = False
    self_modification_allowed: bool = True
    output_logging_required: bool = False


class ValidateActionRequest(BaseModel):
    agent_id: str
    action: str
    context: Dict[str, Any] = {}


class ClassifyAgentRequest(BaseModel):
    agent_id: str
    agent_class: str  # autonomous_worker, supervisor, coordinator, advisory, critical


class EscalateRequest(BaseModel):
    agent_id: str
    violation_type: str
    severity: str  # low, medium, high, critical
    details: Dict[str, Any] = {}


class RevokeRequest(BaseModel):
    agent_id: str
    revocation_type: str  # permissions, memory_access, actions, full_freeze, archive
    reason: str
    revoked_by: str
    reversible: bool = True


class EnterpriseGovernanceRequest(BaseModel):
    agent_id: str
    enterprise_id: str
    department: str


class GovernmentComplianceRequest(BaseModel):
    agent_id: str
    jurisdiction: str
    compliance_level: str
    ministry: str


class HumanApprovalRequest(BaseModel):
    agent_id: str
    action: str
    context: Dict[str, Any] = {}


class ApproveActionRequest(BaseModel):
    approval_id: str
    approver_id: str


class DenyActionRequest(BaseModel):
    approval_id: str
    denier_id: str
    reason: str


class KillSwitchRequest(BaseModel):
    agent_id: str
    operator_id: str
    reason: str


# === Governance Policy Endpoints (L0) ===

@router.post("/governance/policy/add")
async def add_governance_policy(payload: AddPolicyRequest, request: Request):
    """Add a governance policy (L0 - External policies)"""
    try:
        import uuid
        policy = GovernancePolicy(
            policy_id=str(uuid.uuid4()),
            name=payload.name,
            description=payload.description,
            source=payload.source,
            constraints=payload.constraints,
            applies_to=payload.applies_to,
            priority=payload.priority,
        )
        
        policy_id = governance_engine.add_policy(policy)
        
        return {
            "status": "ok",
            "policy_id": policy_id,
            "policy": policy.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/governance/policy/list")
async def list_governance_policies(request: Request):
    """List all governance policies"""
    return {
        "status": "ok",
        "policies": [p.to_dict() for p in governance_engine._policies.values()],
    }


# === Ownership Governance Endpoints (L1) ===

@router.post("/governance/ownership/set")
async def set_ownership_governance(payload: SetOwnershipRequest, request: Request):
    """Set ownership governance for an agent (L1)"""
    try:
        ownership = OwnershipGovernance(
            agent_id=payload.agent_id,
            owner_id=payload.owner_id,
            manager_ids=payload.manager_ids,
            permissions=payload.permissions,
        )
        
        governance_engine.set_ownership(ownership)
        
        return {
            "status": "ok",
            "ownership": ownership.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/governance/ownership/{agent_id}")
async def get_ownership_governance(agent_id: str, request: Request):
    """Get ownership governance for an agent"""
    ownership = governance_engine._ownership.get(agent_id)
    if not ownership:
        raise HTTPException(status_code=404, detail="Ownership not found")
    
    return {
        "status": "ok",
        "ownership": ownership.to_dict(),
    }


# === Contract Governance Endpoints (L2) ===

@router.post("/governance/contract/add")
async def add_contract_governance(payload: AddContractRequest, request: Request):
    """Add contract governance for an agent (L2)"""
    try:
        import uuid
        contract = ContractGovernance(
            contract_id=str(uuid.uuid4()),
            agent_id=payload.agent_id,
            allowed_actions=payload.allowed_actions,
            forbidden_actions=payload.forbidden_actions,
            resource_budgets=payload.resource_budgets,
            escalation_rules=payload.escalation_rules,
            logging_requirements=payload.logging_requirements,
        )
        
        contract_id = governance_engine.add_contract(contract)
        
        return {
            "status": "ok",
            "contract_id": contract_id,
            "contract": contract.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Semantic Governance Endpoints (L3) ===

@router.post("/governance/semantic/add")
async def add_semantic_governance(payload: AddSemanticRuleRequest, request: Request):
    """Add semantic governance rules for a cluster (L3)"""
    try:
        rule = SemanticGovernance(
            cluster_id=payload.cluster_id,
            cluster_name=payload.cluster_name,
            rules=payload.rules,
            audit_requirements=payload.audit_requirements,
            supervision_required=payload.supervision_required,
            self_modification_allowed=payload.self_modification_allowed,
            output_logging_required=payload.output_logging_required,
        )
        
        cluster_id = governance_engine.add_semantic_rule(rule)
        
        return {
            "status": "ok",
            "cluster_id": cluster_id,
            "rule": rule.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Governance Operations (21.4) ===

@router.post("/governance/validate")
async def validate_agent_action(payload: ValidateActionRequest, request: Request):
    """
    Full governance validation before execution.
    
    Checks:
    1. Identity verification
    2. Contract check
    3. Semantic rule check
    4. Cluster constraints
    5. Registry compliance
    """
    try:
        validation = governance_engine.validate_action(
            agent_id=payload.agent_id,
            action=payload.action,
            context=payload.context,
        )
        
        return {
            "status": "ok",
            "validation": validation.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/governance/classify")
async def classify_agent(payload: ClassifyAgentRequest, request: Request):
    """Classify an agent (Classes A-E)"""
    try:
        agent_class = AgentClass(payload.agent_class)
        governance_engine.classify_agent(payload.agent_id, agent_class)
        
        classification = governance_engine.get_classification(payload.agent_id)
        
        return {
            "status": "ok",
            "agent_id": payload.agent_id,
            "classification": classification.to_dict() if classification else None,
        }
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid agent class: {payload.agent_class}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/governance/escalate")
async def escalate_violation(payload: EscalateRequest, request: Request):
    """Escalate a governance violation"""
    try:
        escalation = governance_engine.escalate(
            agent_id=payload.agent_id,
            violation_type=payload.violation_type,
            severity=payload.severity,
            details=payload.details,
        )
        
        return {
            "status": "ok",
            "escalation": escalation.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/governance/revoke")
async def revoke_permissions(payload: RevokeRequest, request: Request):
    """Revoke agent permissions"""
    try:
        revocation = governance_engine.revoke(
            agent_id=payload.agent_id,
            revocation_type=payload.revocation_type,
            reason=payload.reason,
            revoked_by=payload.revoked_by,
            reversible=payload.reversible,
        )
        
        return {
            "status": "ok",
            "revocation": revocation.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Enterprise & Government Governance (21.6, 21.7) ===

@router.post("/governance/enterprise/apply")
async def apply_enterprise_governance(payload: EnterpriseGovernanceRequest, request: Request):
    """Apply enterprise governance to an agent (21.6)"""
    try:
        result = governance_engine.apply_enterprise_governance(
            agent_id=payload.agent_id,
            enterprise_id=payload.enterprise_id,
            department=payload.department,
        )
        
        return {
            "status": "ok",
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/governance/government/compliance")
async def create_government_compliance(payload: GovernmentComplianceRequest, request: Request):
    """Create government compliance requirements (21.7)"""
    try:
        result = governance_engine.create_government_compliance(
            agent_id=payload.agent_id,
            jurisdiction=payload.jurisdiction,
            compliance_level=payload.compliance_level,
            ministry=payload.ministry,
        )
        
        return {
            "status": "ok",
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Human-in-the-Loop (21.9) ===

@router.post("/governance/human/request-approval")
async def request_human_approval(payload: HumanApprovalRequest, request: Request):
    """Request human approval for an action (21.9)"""
    try:
        approval_id = governance_engine.request_human_approval(
            agent_id=payload.agent_id,
            action=payload.action,
            context=payload.context,
        )
        
        return {
            "status": "ok",
            "approval_id": approval_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/governance/human/approve")
async def approve_action(payload: ApproveActionRequest, request: Request):
    """Approve a pending action"""
    try:
        success = governance_engine.approve_action(
            approval_id=payload.approval_id,
            approver_id=payload.approver_id,
        )
        
        return {
            "status": "ok" if success else "error",
            "approved": success,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/governance/human/deny")
async def deny_action(payload: DenyActionRequest, request: Request):
    """Deny a pending action"""
    try:
        success = governance_engine.deny_action(
            approval_id=payload.approval_id,
            denier_id=payload.denier_id,
            reason=payload.reason,
        )
        
        return {
            "status": "ok" if success else "error",
            "denied": success,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/governance/human/kill-switch")
async def kill_switch(payload: KillSwitchRequest, request: Request):
    """Emergency kill switch - immediately freeze agent"""
    try:
        revocation = governance_engine.kill_switch(
            agent_id=payload.agent_id,
            operator_id=payload.operator_id,
            reason=payload.reason,
        )
        
        return {
            "status": "ok",
            "revocation": revocation.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/governance/pending-approvals")
async def get_pending_approvals(request: Request):
    """Get all pending human approvals"""
    return {
        "status": "ok",
        "pending_approvals": governance_engine._pending_approvals,
    }


# === Governance Stats & Events ===

@router.get("/governance/stats")
async def get_governance_stats(request: Request):
    """Get governance engine statistics"""
    return {
        "status": "ok",
        "stats": governance_engine.get_stats(),
    }


@router.get("/governance/events")
async def get_governance_events(agent_id: Optional[str] = None, limit: int = 100, request: Request = None):
    """Get governance events"""
    return {
        "status": "ok",
        "events": governance_engine.get_events(agent_id, limit),
    }


@router.get("/governance/agent-classes")
async def get_agent_classes(request: Request):
    """Get all agent classification types"""
    return {
        "status": "ok",
        "classes": {
            k.value: v.to_dict() for k, v in AGENT_CLASSIFICATIONS.items()
        },
    }


@router.get("/governance/layers")
async def get_governance_layers(request: Request):
    """Get governance layer definitions"""
    return {
        "status": "ok",
        "layers": {
            "L0_POLICY": "Human/Enterprise/Government Policies (External)",
            "L1_OWNERSHIP": "Ownership & Identity Governance",
            "L2_CONTRACT": "Contract-Level Governance",
            "L3_SEMANTIC": "Semantic Governance (Cluster-based)",
            "L4_BEHAVIORAL": "Behavioral & Coordination Governance",
            "L5_REGISTRY": "Registry Enforcement Layer",
        },
    }


# ============== SECTION 22: PERFORMANCE BENCHMARKING ==============

from .benchmarking import benchmark_engine, BenchmarkDomain, BenchmarkType


@router.post("/benchmark/run/identity")
async def run_identity_benchmarks(iterations: int = 1000, request: Request = None):
    """Run L1 Identity layer benchmarks"""
    results = []
    results.append((await benchmark_engine.benchmark_identity_creation(iterations)).to_dict())
    results.append((await benchmark_engine.benchmark_signature_verification(iterations)).to_dict())
    return {"status": "ok", "domain": "identity", "results": results}


@router.post("/benchmark/run/user-dag")
async def run_user_dag_benchmarks(iterations: int = 1000, request: Request = None):
    """Run L2 User DAG benchmarks"""
    results = []
    results.append((await benchmark_engine.benchmark_dag_node_creation(iterations)).to_dict())
    results.append((await benchmark_engine.benchmark_dag_rehydration(500)).to_dict())
    return {"status": "ok", "domain": "user_dag", "results": results}


@router.post("/benchmark/run/agent-dag")
async def run_agent_dag_benchmarks(iterations: int = 1000, request: Request = None):
    """Run L3 Agent DAG benchmarks"""
    results = []
    results.append((await benchmark_engine.benchmark_memory_append(iterations)).to_dict())
    results.append((await benchmark_engine.benchmark_embedding_update(iterations)).to_dict())
    return {"status": "ok", "domain": "agent_dag", "results": results}


@router.post("/benchmark/run/coordination")
async def run_coordination_benchmarks(iterations: int = 1000, request: Request = None):
    """Run L4 Coordination layer benchmarks"""
    results = []
    results.append((await benchmark_engine.benchmark_event_append(iterations)).to_dict())
    return {"status": "ok", "domain": "coordination", "results": results}


@router.post("/benchmark/run/registry")
async def run_registry_benchmarks(iterations: int = 100, request: Request = None):
    """Run L5 Registry blockchain benchmarks"""
    results = []
    results.append((await benchmark_engine.benchmark_block_anchoring(iterations)).to_dict())
    return {"status": "ok", "domain": "registry", "results": results}


@router.post("/benchmark/run/semantic")
async def run_semantic_benchmarks(vector_count: int = 5000, request: Request = None):
    """Run Semantic subsystem benchmarks"""
    results = []
    results.append((await benchmark_engine.benchmark_vector_ingestion(vector_count)).to_dict())
    results.append((await benchmark_engine.benchmark_cluster_recalculation(500, 5)).to_dict())
    return {"status": "ok", "domain": "semantic", "results": results}


@router.post("/benchmark/run/network")
async def run_network_benchmarks(iterations: int = 1000, request: Request = None):
    """Run Network & Transport benchmarks"""
    results = []
    results.append((await benchmark_engine.benchmark_cbor_encoding(iterations)).to_dict())
    return {"status": "ok", "domain": "network", "results": results}


@router.post("/benchmark/run/end-to-end")
async def run_end_to_end_benchmarks(iterations: int = 50, request: Request = None):
    """Run End-to-End agent workflow benchmarks"""
    results = []
    results.append((await benchmark_engine.benchmark_full_agent_workflow(iterations)).to_dict())
    return {"status": "ok", "domain": "end_to_end", "results": results}


@router.post("/benchmark/run/full-suite")
async def run_full_benchmark_suite(request: Request):
    """Run complete DSID-P benchmark suite"""
    suite = await benchmark_engine.run_full_benchmark_suite()
    return {"status": "ok", "suite": suite.to_dict()}


@router.get("/benchmark/results")
async def get_benchmark_results(request: Request):
    """Get all benchmark results"""
    return {"status": "ok", "results": benchmark_engine.get_results()}


@router.get("/benchmark/summary")
async def get_benchmark_summary(request: Request):
    """Get benchmark summary"""
    return {"status": "ok", "summary": benchmark_engine.get_summary()}


@router.get("/benchmark/domains")
async def get_benchmark_domains(request: Request):
    """Get benchmark domain definitions"""
    return {
        "status": "ok",
        "domains": {
            "L1_IDENTITY": "Identity creation, signature verification, lookup",
            "L2_USER_DAG": "Node creation, root recalculation, rehydration",
            "L3_AGENT_DAG": "Memory append, behavior mutation, embedding update",
            "L4_COORDINATION": "Event append, causality chain query",
            "L5_REGISTRY": "Block anchoring, propagation, proof verification",
            "SEMANTIC": "Vector ingestion, cluster recalculation, drift detection",
            "NETWORK": "CBOR encoding, node fetch latency",
            "END_TO_END": "Full agent workflow, audit reconstruction",
        },
    }


# ============== SECTION 23: INTEROPERABILITY LAYER ==============

from .interoperability import (
    interop_manager, ExternalIdentityType, ExternalModelType,
    ExternalAgentType, ExternalRegistryType, TransportType,
)


class CreateIdentityMappingRequest(BaseModel):
    external_id: str
    external_type: str
    provider: str
    metadata: Dict[str, Any] = {}


class TranslateEmbeddingRequest(BaseModel):
    source_vector: List[float]
    source_model: str


class ProposeMemoryRequest(BaseModel):
    agent_id: str
    content: Dict[str, Any]
    source_system: str
    requires_approval: bool = True


class ImportAgentRequest(BaseModel):
    external_type: str
    external_agent_id: str
    capabilities: List[str] = []
    initial_cluster: Optional[str] = None


class RegisterModelRequest(BaseModel):
    model_type: str
    model_name: str
    endpoint: Optional[str] = None
    capabilities: List[str] = []


class AnchorToExternalRequest(BaseModel):
    dsidp_block_id: str
    registry_type: str


class RegisterTransportRequest(BaseModel):
    transport_type: str
    endpoint: str
    auth_type: str = "none"


# Identity Bridge endpoints
@router.post("/interop/identity/create-mapping")
async def create_identity_mapping(payload: CreateIdentityMappingRequest, request: Request):
    """Create DSID-P identity from external identity"""
    try:
        ext_type = ExternalIdentityType(payload.external_type)
        mapping = interop_manager.identity_bridge.create_dsidp_identity_from_external(
            external_id=payload.external_id,
            external_type=ext_type,
            provider=payload.provider,
            metadata=payload.metadata,
        )
        return {"status": "ok", "mapping": mapping.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/interop/identity/resolve/{external_id}")
async def resolve_identity(external_id: str, request: Request):
    """Resolve external ID to DSID-P identity"""
    dsidp_id = interop_manager.identity_bridge.resolve_identity(external_id)
    return {"status": "ok", "external_id": external_id, "dsidp_identity": dsidp_id}


# Semantic Translation endpoints
@router.post("/interop/semantic/translate")
async def translate_embedding(payload: TranslateEmbeddingRequest, request: Request):
    """Translate external embedding to DSID-P space"""
    try:
        model_type = ExternalModelType(payload.source_model)
        translation = interop_manager.semantic_translator.translate_embedding(
            source_vector=payload.source_vector,
            source_model=model_type,
        )
        return {
            "status": "ok",
            "source_model": payload.source_model,
            "source_dimension": len(payload.source_vector),
            "translated_dimension": len(translation.translated_vector),
            "translated_vector": translation.translated_vector[:10],  # First 10 for brevity
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Memory Gateway endpoints
@router.post("/interop/memory/propose")
async def propose_memory(payload: ProposeMemoryRequest, request: Request):
    """Propose memory update from external system"""
    proposal = interop_manager.memory_gateway.propose_memory(
        agent_id=payload.agent_id,
        content=payload.content,
        source_system=payload.source_system,
        requires_approval=payload.requires_approval,
    )
    return {"status": "ok", "proposal": proposal.to_dict()}


@router.post("/interop/memory/approve/{proposal_id}")
async def approve_memory_proposal(proposal_id: str, request: Request):
    """Approve a memory proposal"""
    success = interop_manager.memory_gateway.approve_proposal(proposal_id)
    return {"status": "ok" if success else "error", "approved": success}


@router.get("/interop/memory/pending")
async def get_pending_memory_proposals(agent_id: Optional[str] = None, request: Request = None):
    """Get pending memory proposals"""
    proposals = interop_manager.memory_gateway.get_pending_proposals(agent_id)
    return {"status": "ok", "proposals": [p.to_dict() for p in proposals]}


# External Agent Adapter endpoints
@router.post("/interop/agent/import")
async def import_external_agent(payload: ImportAgentRequest, request: Request):
    """Import external agent into DSID-P"""
    try:
        agent_type = ExternalAgentType(payload.external_type)
        imported = interop_manager.agent_adapter.import_agent(
            external_type=agent_type,
            external_agent_id=payload.external_agent_id,
            capabilities=payload.capabilities,
            initial_cluster=payload.initial_cluster,
        )
        return {"status": "ok", "imported_agent": imported.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/interop/agent/list")
async def list_imported_agents(external_type: Optional[str] = None, request: Request = None):
    """List imported agents"""
    agent_type = ExternalAgentType(external_type) if external_type else None
    agents = interop_manager.agent_adapter.list_imported_agents(agent_type)
    return {"status": "ok", "agents": [a.to_dict() for a in agents]}


# External Model Adapter endpoints
@router.post("/interop/model/register")
async def register_external_model(payload: RegisterModelRequest, request: Request):
    """Register external AI model"""
    try:
        model_type = ExternalModelType(payload.model_type)
        connection = interop_manager.model_adapter.register_model(
            model_type=model_type,
            model_name=payload.model_name,
            endpoint=payload.endpoint,
            capabilities=payload.capabilities,
        )
        return {"status": "ok", "model": connection.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/interop/model/list")
async def list_registered_models(model_type: Optional[str] = None, request: Request = None):
    """List registered models"""
    m_type = ExternalModelType(model_type) if model_type else None
    models = interop_manager.model_adapter.list_models(m_type)
    return {"status": "ok", "models": [m.to_dict() for m in models]}


# Registry Bridge endpoints
@router.post("/interop/registry/anchor")
async def anchor_to_external_registry(payload: AnchorToExternalRequest, request: Request):
    """Anchor DSID-P block to external registry"""
    try:
        reg_type = ExternalRegistryType(payload.registry_type)
        anchor = interop_manager.registry_bridge.anchor_to_external(
            dsidp_block_id=payload.dsidp_block_id,
            registry_type=reg_type,
        )
        return {"status": "ok", "anchor": anchor.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/interop/registry/anchors")
async def list_external_anchors(registry_type: Optional[str] = None, request: Request = None):
    """List external anchors"""
    reg_type = ExternalRegistryType(registry_type) if registry_type else None
    anchors = interop_manager.registry_bridge.list_anchors(reg_type)
    return {"status": "ok", "anchors": [a.to_dict() for a in anchors]}


# Transport endpoints
@router.post("/interop/transport/register")
async def register_transport(payload: RegisterTransportRequest, request: Request):
    """Register transport adapter"""
    try:
        t_type = TransportType(payload.transport_type)
        config = interop_manager.transport_manager.register_transport(
            transport_type=t_type,
            endpoint=payload.endpoint,
            auth_type=payload.auth_type,
        )
        return {"status": "ok", "transport": config.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/interop/transport/list")
async def list_transports(transport_type: Optional[str] = None, request: Request = None):
    """List transport configs"""
    t_type = TransportType(transport_type) if transport_type else None
    configs = interop_manager.transport_manager.list_transports(t_type)
    return {"status": "ok", "transports": [c.to_dict() for c in configs]}


@router.get("/interop/stats")
async def get_interop_stats(request: Request):
    """Get interoperability statistics"""
    return {"status": "ok", "stats": interop_manager.get_stats()}


@router.get("/interop/supported-types")
async def get_supported_types(request: Request):
    """Get all supported external types"""
    return {
        "status": "ok",
        "identity_types": [t.value for t in ExternalIdentityType],
        "model_types": [t.value for t in ExternalModelType],
        "agent_types": [t.value for t in ExternalAgentType],
        "registry_types": [t.value for t in ExternalRegistryType],
        "transport_types": [t.value for t in TransportType],
    }


# ============== SECTION 24: AGENT LIFECYCLE ==============

from .agent_lifecycle import (
    lifecycle_manager, LifecycleStage, SuspensionReason, RetirementReason,
    AgentCreationSpec,
)


class CreateAgentRequest(BaseModel):
    purpose: str
    owner_id: str
    initial_capabilities: List[str] = []
    cluster_hints: List[str] = []
    initial_policies: List[str] = []


class InitializeAgentRequest(BaseModel):
    agent_id: str
    initial_memory: List[Dict[str, Any]] = []
    semantic_vector: List[float] = []


class ActivateAgentRequest(BaseModel):
    agent_id: str
    cluster_id: str
    ownership_signature: str


class AppendMemoryRequest(BaseModel):
    agent_id: str
    memory_content: Dict[str, Any]


class UpdateSemanticRequest(BaseModel):
    agent_id: str
    new_vector: List[float]


class CoordinationEventRequest(BaseModel):
    agent_id: str
    event_type: str
    target_agent_id: Optional[str] = None
    event_data: Dict[str, Any] = {}


class UpgradeAgentRequest(BaseModel):
    agent_id: str
    new_capabilities: List[str]
    new_contracts: List[str] = []
    new_semantic_vector: List[float] = []


class TransferOwnershipRequest(BaseModel):
    agent_id: str
    new_owner_id: str
    new_ownership_signature: str
    prune_memory: bool = False


class SuspendAgentRequest(BaseModel):
    agent_id: str
    reason: str


class RetireAgentRequest(BaseModel):
    agent_id: str
    reason: str


@router.post("/lifecycle/create")
async def create_agent(payload: CreateAgentRequest, request: Request):
    """Stage 1: Create agent"""
    spec = AgentCreationSpec(
        purpose=payload.purpose,
        initial_capabilities=payload.initial_capabilities,
        cluster_hints=payload.cluster_hints,
        initial_policies=payload.initial_policies,
        owner_id=payload.owner_id,
    )
    agent = lifecycle_manager.create_agent(spec, triggered_by="api")
    return {"status": "ok", "agent": agent.to_dict()}


@router.post("/lifecycle/initialize")
async def initialize_agent(payload: InitializeAgentRequest, request: Request):
    """Stage 2: Initialize agent sphere"""
    try:
        agent = lifecycle_manager.initialize_agent(
            agent_id=payload.agent_id,
            initial_memory=payload.initial_memory,
            semantic_vector=payload.semantic_vector,
            triggered_by="api",
        )
        return {"status": "ok", "agent": agent.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/lifecycle/activate")
async def activate_agent(payload: ActivateAgentRequest, request: Request):
    """Stage 3: Activate agent with registry block"""
    try:
        agent = lifecycle_manager.activate_agent(
            agent_id=payload.agent_id,
            cluster_id=payload.cluster_id,
            ownership_signature=payload.ownership_signature,
            triggered_by="api",
        )
        return {"status": "ok", "agent": agent.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/lifecycle/start-operation/{agent_id}")
async def start_agent_operation(agent_id: str, request: Request):
    """Stage 4: Start operational phase"""
    try:
        agent = lifecycle_manager.start_operation(agent_id, triggered_by="api")
        return {"status": "ok", "agent": agent.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/lifecycle/append-memory")
async def append_agent_memory(payload: AppendMemoryRequest, request: Request):
    """Stage 5: Append memory"""
    try:
        node_id = lifecycle_manager.append_memory(
            agent_id=payload.agent_id,
            memory_content=payload.memory_content,
            triggered_by="api",
        )
        return {"status": "ok", "memory_node_id": node_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/lifecycle/update-semantic")
async def update_agent_semantic(payload: UpdateSemanticRequest, request: Request):
    """Stage 6: Update semantic vector"""
    try:
        result = lifecycle_manager.update_semantic_vector(
            agent_id=payload.agent_id,
            new_vector=payload.new_vector,
            triggered_by="api",
        )
        return {"status": "ok", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/lifecycle/coordination-event")
async def record_coordination(payload: CoordinationEventRequest, request: Request):
    """Stage 7: Record coordination event"""
    try:
        event_id = lifecycle_manager.record_coordination_event(
            agent_id=payload.agent_id,
            event_type=payload.event_type,
            target_agent_id=payload.target_agent_id,
            event_data=payload.event_data,
            triggered_by="api",
        )
        return {"status": "ok", "event_id": event_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/lifecycle/upgrade")
async def upgrade_agent(payload: UpgradeAgentRequest, request: Request):
    """Stage 9: Upgrade agent"""
    try:
        agent = lifecycle_manager.upgrade_agent(
            agent_id=payload.agent_id,
            new_capabilities=payload.new_capabilities,
            new_contracts=payload.new_contracts if payload.new_contracts else None,
            new_semantic_vector=payload.new_semantic_vector if payload.new_semantic_vector else None,
            triggered_by="api",
        )
        return {"status": "ok", "agent": agent.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/lifecycle/transfer")
async def transfer_agent_ownership(payload: TransferOwnershipRequest, request: Request):
    """Stage 10: Transfer ownership"""
    try:
        agent = lifecycle_manager.transfer_ownership(
            agent_id=payload.agent_id,
            new_owner_id=payload.new_owner_id,
            new_ownership_signature=payload.new_ownership_signature,
            prune_memory=payload.prune_memory,
            triggered_by="api",
        )
        return {"status": "ok", "agent": agent.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/lifecycle/suspend")
async def suspend_agent(payload: SuspendAgentRequest, request: Request):
    """Stage 11: Suspend agent"""
    try:
        reason = SuspensionReason(payload.reason)
        agent = lifecycle_manager.suspend_agent(
            agent_id=payload.agent_id,
            reason=reason,
            triggered_by="api",
        )
        return {"status": "ok", "agent": agent.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/lifecycle/unsuspend/{agent_id}")
async def unsuspend_agent(agent_id: str, request: Request):
    """Unsuspend agent"""
    try:
        agent = lifecycle_manager.unsuspend_agent(agent_id, triggered_by="api")
        return {"status": "ok", "agent": agent.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/lifecycle/retire")
async def retire_agent(payload: RetireAgentRequest, request: Request):
    """Stage 12: Retire agent"""
    try:
        reason = RetirementReason(payload.reason)
        agent = lifecycle_manager.retire_agent(
            agent_id=payload.agent_id,
            reason=reason,
            triggered_by="api",
        )
        return {"status": "ok", "agent": agent.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/lifecycle/agent/{agent_id}")
async def get_agent(agent_id: str, request: Request):
    """Get agent by ID"""
    agent = lifecycle_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "ok", "agent": agent.to_dict()}


@router.get("/lifecycle/agent/{agent_id}/history")
async def get_agent_history(agent_id: str, request: Request):
    """Get agent lifecycle history"""
    history = lifecycle_manager.get_agent_history(agent_id)
    return {"status": "ok", "history": history}


@router.get("/lifecycle/agent/{agent_id}/ownership-history")
async def get_agent_ownership_history(agent_id: str, request: Request):
    """Get agent ownership history"""
    history = lifecycle_manager.get_ownership_history(agent_id)
    return {"status": "ok", "ownership_history": history}


@router.get("/lifecycle/agents")
async def list_agents(
    stage: Optional[str] = None,
    owner_id: Optional[str] = None,
    cluster_id: Optional[str] = None,
    request: Request = None,
):
    """List agents with filters"""
    stage_enum = LifecycleStage(stage) if stage else None
    agents = lifecycle_manager.list_agents(stage_enum, owner_id, cluster_id)
    return {"status": "ok", "agents": [a.to_dict() for a in agents]}


@router.get("/lifecycle/stats")
async def get_lifecycle_stats(request: Request):
    """Get lifecycle statistics"""
    return {"status": "ok", "stats": lifecycle_manager.get_stats()}


@router.get("/lifecycle/stages")
async def get_lifecycle_stages(request: Request):
    """Get lifecycle stage definitions"""
    return {
        "status": "ok",
        "stages": {
            "created": "Stage 1: Identity defined, pre-activation",
            "initialized": "Stage 2: Agent DAG built",
            "activated": "Stage 3: Registry block written, legal entity",
            "operational": "Stage 4: Active execution",
            "evolving": "Stage 5-6: Memory/semantic evolution",
            "coordinating": "Stage 7: Multi-agent collaboration",
            "governed": "Stage 8: Under governance enforcement",
            "upgrading": "Stage 9: Capability upgrade in progress",
            "transferring": "Stage 10: Ownership transfer in progress",
            "suspended": "Stage 11: Temporarily frozen",
            "retired": "Stage 12: Permanently archived",
        },
        "suspension_reasons": [r.value for r in SuspensionReason],
        "retirement_reasons": [r.value for r in RetirementReason],
    }


# ============== SECTION 26: SECURITY THREAT MODEL ==============

from .security_threat_model import (
    threat_catalog, threat_engine, security_assessor,
    ThreatDomain, ThreatSeverity, ThreatStatus,
)


class DetectThreatRequest(BaseModel):
    threat_id: str
    source_entity: str
    target_entity: Optional[str] = None
    details: Dict[str, Any] = {}


class MitigateThreatRequest(BaseModel):
    event_id: str
    mitigation_applied: str


@router.get("/security/threats")
async def list_threats(domain: Optional[str] = None, request: Request = None):
    """List all defined threats"""
    domain_enum = ThreatDomain(domain) if domain else None
    threats = threat_catalog.list_threats(domain_enum)
    return {"status": "ok", "threats": [t.to_dict() for t in threats]}


@router.get("/security/threats/{threat_id}")
async def get_threat(threat_id: str, request: Request):
    """Get threat definition by ID"""
    threat = threat_catalog.get_threat(threat_id)
    if not threat:
        raise HTTPException(status_code=404, detail="Threat not found")
    return {"status": "ok", "threat": threat.to_dict()}


@router.get("/security/threats/severity/{severity}")
async def get_threats_by_severity(severity: str, request: Request):
    """Get threats by severity level"""
    try:
        sev = ThreatSeverity(severity)
        threats = threat_catalog.get_threats_by_severity(sev)
        return {"status": "ok", "threats": [t.to_dict() for t in threats]}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid severity level")


@router.get("/security/threat-matrix")
async def get_threat_matrix(request: Request):
    """Get threat matrix summary"""
    return {"status": "ok", "matrix": threat_catalog.get_threat_matrix()}


@router.post("/security/detect")
async def detect_threat(payload: DetectThreatRequest, request: Request):
    """Record a detected threat"""
    try:
        event = threat_engine.detect_threat(
            threat_id=payload.threat_id,
            source_entity=payload.source_entity,
            target_entity=payload.target_entity,
            details=payload.details,
        )
        return {"status": "ok", "event": event.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/security/mitigate")
async def mitigate_threat(payload: MitigateThreatRequest, request: Request):
    """Mark a threat as mitigated"""
    try:
        event = threat_engine.mitigate_threat(
            event_id=payload.event_id,
            mitigation_applied=payload.mitigation_applied,
        )
        return {"status": "ok", "event": event.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/security/escalate/{event_id}")
async def escalate_threat(event_id: str, request: Request):
    """Escalate a threat for human review"""
    try:
        event = threat_engine.escalate_threat(event_id)
        return {"status": "ok", "event": event.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/security/resolve/{event_id}")
async def resolve_threat(event_id: str, request: Request):
    """Mark a threat as resolved"""
    try:
        event = threat_engine.resolve_threat(event_id)
        return {"status": "ok", "event": event.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/security/false-positive/{event_id}")
async def mark_false_positive(event_id: str, request: Request):
    """Mark a threat as false positive"""
    try:
        event = threat_engine.mark_false_positive(event_id)
        return {"status": "ok", "event": event.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/security/events/active")
async def get_active_threats(entity: Optional[str] = None, request: Request = None):
    """Get active (unresolved) threats"""
    events = threat_engine.get_active_threats(entity)
    return {"status": "ok", "events": [e.to_dict() for e in events]}


@router.get("/security/events/history")
async def get_threat_history(
    entity: Optional[str] = None,
    domain: Optional[str] = None,
    request: Request = None,
):
    """Get threat event history"""
    domain_enum = ThreatDomain(domain) if domain else None
    events = threat_engine.get_threat_history(entity, domain_enum)
    return {"status": "ok", "events": [e.to_dict() for e in events]}


@router.get("/security/stats")
async def get_security_stats(request: Request):
    """Get threat detection statistics"""
    return {"status": "ok", "stats": threat_engine.get_stats()}


@router.get("/security/posture")
async def assess_security_posture(request: Request):
    """Assess overall security posture"""
    posture = security_assessor.assess()
    return {"status": "ok", "posture": posture.to_dict()}


@router.get("/security/domains")
async def get_threat_domains(request: Request):
    """Get threat domain definitions"""
    return {
        "status": "ok",
        "domains": {
            "identity": "L1 Identity threats (spoofing, tampering, hijacking)",
            "dag_integrity": "L2+L3 DAG threats (mutation, corruption, injection)",
            "semantic": "Semantic threats (poisoning, mis-clustering)",
            "coordination": "L4 Coordination threats (workflow manipulation, delegation abuse)",
            "registry": "L5 Registry threats (block rewriting, forking)",
            "network": "Network threats (node spoofing, transport manipulation)",
            "human_governance": "Human threats (misconfiguration, insider, over-permissive)",
            "sovereign": "Sovereign threats (compliance failure, cross-ministry contamination)",
        },
        "severities": [s.value for s in ThreatSeverity],
        "statuses": [s.value for s in ThreatStatus],
    }


# ============== SECTION 27: COMPLIANCE & AUDIT ==============

from .compliance_audit import (
    control_catalog, audit_engine, scenario_manager,
    residency_manager, report_generator,
    ComplianceFramework, ComplianceLayer, AuditType,
    ComplianceStatus, ComplianceMaturityLevel,
)


class RunComplianceCheckRequest(BaseModel):
    control_id: str
    evidence: List[Dict[str, Any]]
    checked_by: str = "system"


class GenerateIdentityArtifactRequest(BaseModel):
    identity_hash: str
    signature_verified: bool
    ownership_changes: List[Dict[str, Any]] = []
    permission_scopes: List[str] = []


class GenerateDAGArtifactRequest(BaseModel):
    layer: str
    node_hashes: List[str]
    relationships: List[Dict[str, str]] = []
    versions: List[Dict[str, Any]] = []
    root_hash: str


class GenerateSemanticArtifactRequest(BaseModel):
    agent_id: str
    vector_changes: List[Dict[str, Any]] = []
    cluster_assignments: List[Dict[str, Any]] = []
    drift_logs: List[Dict[str, Any]] = []


class GenerateCoordinationArtifactRequest(BaseModel):
    event_lineage: List[Dict[str, Any]] = []
    causality_graphs: List[Dict[str, Any]] = []
    delegation_chains: List[Dict[str, Any]] = []


class GenerateRegistryArtifactRequest(BaseModel):
    block_metadata: List[Dict[str, Any]] = []
    anchoring_proofs: List[Dict[str, Any]] = []
    block_signatures: List[Dict[str, Any]] = []


class AddResidencyConfigRequest(BaseModel):
    region: str
    jurisdiction: str
    allowed_data_types: List[str]
    restricted_data_types: List[str] = []
    node_requirements: Dict[str, Any] = {}


class GenerateReportRequest(BaseModel):
    framework: str
    check_ids: List[str]
    artifact_ids: List[str]
    generated_by: str = "system"


# Compliance Controls
@router.get("/compliance/controls")
async def list_compliance_controls(
    framework: Optional[str] = None,
    layer: Optional[str] = None,
    request: Request = None,
):
    """List compliance controls"""
    fw = ComplianceFramework(framework) if framework else None
    ly = ComplianceLayer(layer) if layer else None
    controls = control_catalog.list_controls(fw, ly)
    return {"status": "ok", "controls": [c.to_dict() for c in controls]}


@router.get("/compliance/controls/{control_id}")
async def get_compliance_control(control_id: str, request: Request):
    """Get compliance control by ID"""
    control = control_catalog.get_control(control_id)
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")
    return {"status": "ok", "control": control.to_dict()}


@router.post("/compliance/check")
async def run_compliance_check(payload: RunComplianceCheckRequest, request: Request):
    """Run a compliance check"""
    try:
        result = audit_engine.run_compliance_check(
            control_id=payload.control_id,
            evidence=payload.evidence,
            checked_by=payload.checked_by,
        )
        return {"status": "ok", "result": result.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/compliance/check/{check_id}")
async def get_compliance_check_result(check_id: str, request: Request):
    """Get compliance check result"""
    result = audit_engine.get_check_result(check_id)
    if not result:
        raise HTTPException(status_code=404, detail="Check result not found")
    return {"status": "ok", "result": result.to_dict()}


# Audit Artifacts
@router.post("/audit/artifact/identity")
async def generate_identity_artifact(payload: GenerateIdentityArtifactRequest, request: Request):
    """Generate identity audit artifact"""
    artifact = audit_engine.generate_identity_artifact(
        identity_hash=payload.identity_hash,
        signature_verified=payload.signature_verified,
        ownership_changes=payload.ownership_changes,
        permission_scopes=payload.permission_scopes,
    )
    return {"status": "ok", "artifact": artifact.to_dict()}


@router.post("/audit/artifact/dag")
async def generate_dag_artifact(payload: GenerateDAGArtifactRequest, request: Request):
    """Generate DAG audit artifact"""
    artifact = audit_engine.generate_dag_artifact(
        layer=payload.layer,
        node_hashes=payload.node_hashes,
        relationships=payload.relationships,
        versions=payload.versions,
        root_hash=payload.root_hash,
    )
    return {"status": "ok", "artifact": artifact.to_dict()}


@router.post("/audit/artifact/semantic")
async def generate_semantic_artifact(payload: GenerateSemanticArtifactRequest, request: Request):
    """Generate semantic audit artifact"""
    artifact = audit_engine.generate_semantic_artifact(
        agent_id=payload.agent_id,
        vector_changes=payload.vector_changes,
        cluster_assignments=payload.cluster_assignments,
        drift_logs=payload.drift_logs,
    )
    return {"status": "ok", "artifact": artifact.to_dict()}


@router.post("/audit/artifact/coordination")
async def generate_coordination_artifact(payload: GenerateCoordinationArtifactRequest, request: Request):
    """Generate coordination audit artifact"""
    artifact = audit_engine.generate_coordination_artifact(
        event_lineage=payload.event_lineage,
        causality_graphs=payload.causality_graphs,
        delegation_chains=payload.delegation_chains,
    )
    return {"status": "ok", "artifact": artifact.to_dict()}


@router.post("/audit/artifact/registry")
async def generate_registry_artifact(payload: GenerateRegistryArtifactRequest, request: Request):
    """Generate registry audit artifact"""
    artifact = audit_engine.generate_registry_artifact(
        block_metadata=payload.block_metadata,
        anchoring_proofs=payload.anchoring_proofs,
        block_signatures=payload.block_signatures,
    )
    return {"status": "ok", "artifact": artifact.to_dict()}


@router.get("/audit/artifact/{artifact_id}")
async def get_audit_artifact(artifact_id: str, request: Request):
    """Get audit artifact by ID"""
    artifact = audit_engine.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return {"status": "ok", "artifact": artifact.to_dict()}


@router.get("/audit/artifacts/export")
async def export_audit_artifacts(artifact_ids: Optional[str] = None, request: Request = None):
    """Export audit artifacts for external review"""
    ids = artifact_ids.split(",") if artifact_ids else None
    artifacts = audit_engine.export_artifacts(ids)
    return {"status": "ok", "artifacts": artifacts}


# Compliance Scenarios
@router.get("/compliance/scenarios")
async def list_compliance_scenarios(framework: Optional[str] = None, request: Request = None):
    """List compliance scenarios"""
    fw = ComplianceFramework(framework) if framework else None
    scenarios = scenario_manager.list_scenarios(fw)
    return {"status": "ok", "scenarios": [s.to_dict() for s in scenarios]}


@router.get("/compliance/scenarios/{scenario_id}")
async def get_compliance_scenario(scenario_id: str, request: Request):
    """Get compliance scenario by ID"""
    scenario = scenario_manager.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {"status": "ok", "scenario": scenario.to_dict()}


# Data Residency
@router.post("/compliance/residency/config")
async def add_residency_config(payload: AddResidencyConfigRequest, request: Request):
    """Add data residency configuration"""
    config = residency_manager.add_config(
        region=payload.region,
        jurisdiction=payload.jurisdiction,
        allowed_data_types=payload.allowed_data_types,
        restricted_data_types=payload.restricted_data_types,
        node_requirements=payload.node_requirements,
    )
    return {"status": "ok", "config": config.to_dict()}


@router.get("/compliance/residency/configs")
async def list_residency_configs(request: Request):
    """List data residency configurations"""
    configs = residency_manager.list_configs()
    return {"status": "ok", "configs": [c.to_dict() for c in configs]}


@router.get("/compliance/residency/check")
async def check_data_residency(data_type: str, target_region: str, request: Request = None):
    """Check if data type can be stored in target region"""
    result = residency_manager.check_residency(data_type, target_region)
    return {"status": "ok", "result": result}


# Compliance Reports
@router.post("/compliance/report/generate")
async def generate_compliance_report(payload: GenerateReportRequest, request: Request):
    """Generate compliance report"""
    try:
        fw = ComplianceFramework(payload.framework)
        report = report_generator.generate_report(
            framework=fw,
            check_ids=payload.check_ids,
            artifact_ids=payload.artifact_ids,
            generated_by=payload.generated_by,
        )
        return {"status": "ok", "report": report.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/compliance/frameworks")
async def get_compliance_frameworks(request: Request):
    """Get supported compliance frameworks"""
    return {
        "status": "ok",
        "frameworks": [f.value for f in ComplianceFramework],
        "layers": [l.value for l in ComplianceLayer],
        "audit_types": [t.value for t in AuditType],
        "statuses": [s.value for s in ComplianceStatus],
        "maturity_levels": {
            "level_1": "Basic audit logging",
            "level_2": "Full lineage tracking",
            "level_3": "Semantic drift monitoring",
            "level_4": "Permissioned governance",
            "level_5": "Sovereign-grade compliance",
            "level_6": "AI Act + multi-framework certifications",
        },
    }


@router.get("/compliance/layer-mapping")
async def get_compliance_layer_mapping(request: Request):
    """Get compliance layer mapping"""
    return {
        "status": "ok",
        "mapping": {
            "L1_identity": {
                "description": "Identity Compliance",
                "enforces": ["strict identity binding", "ownership proof", "permission scopes"],
                "supports": ["NIST SP 800-63", "Zero Trust", "EU AI Act identity traceability"],
            },
            "L2_data": {
                "description": "Data Compliance (User DAG)",
                "enforces": ["encryption", "structured DAG", "full lineage", "retention policies"],
                "supports": ["GDPR", "HIPAA", "CCPA"],
            },
            "L3_agent": {
                "description": "Agent Compliance (Agent DAG)",
                "enforces": ["behavior graphs", "semantic vectors", "policy contracts"],
                "supports": ["EU AI Act High-Risk", "Digital Government", "Banking/Finance"],
            },
            "L4_workflow": {
                "description": "Workflow/Behavior Compliance",
                "enforces": ["event logging", "causality chains", "workflow traceability"],
                "supports": ["SOX", "FedRAMP High", "ISO 42001"],
            },
            "L5_registry": {
                "description": "Registry Compliance (Anchoring & Proof)",
                "enforces": ["ownership proof", "identity proof", "DAG root proof", "temporal integrity"],
                "supports": ["Cross-border ledger trust", "Chain-of-custody", "Sovereign audits"],
            },
        },
    }


# ============== SECTION 28: SEMANTIC CLUSTER TAXONOMY ==============

from .semantic_taxonomy import (
    taxonomy_catalog, drift_monitor, confidence_calculator, governance_manager,
    DomainCluster, SemanticRiskRating,
)


class RecordVectorRequest(BaseModel):
    agent_id: str
    vector: List[float]
    cluster: str


class CalculateConfidenceRequest(BaseModel):
    agent_id: str
    vector: List[float]
    cluster_centroids: Dict[str, List[float]]


class CheckActionRequest(BaseModel):
    cluster_code: str
    action: str


# Taxonomy endpoints
@router.get("/taxonomy/domains")
async def list_taxonomy_domains(request: Request):
    """List all Tier 1 domain clusters"""
    domains = taxonomy_catalog.list_domains()
    return {"status": "ok", "domains": [d.to_dict() for d in domains]}


@router.get("/taxonomy/domains/{code}")
async def get_taxonomy_domain(code: str, request: Request):
    """Get domain cluster by code"""
    domain = taxonomy_catalog.get_domain(code)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return {"status": "ok", "domain": domain.to_dict()}


@router.get("/taxonomy/functional-clusters")
async def list_functional_clusters(domain: Optional[str] = None, request: Request = None):
    """List Tier 2 functional clusters"""
    clusters = taxonomy_catalog.list_functional_clusters(domain)
    return {"status": "ok", "clusters": [c.to_dict() for c in clusters]}


@router.get("/taxonomy/functional-clusters/{code}")
async def get_functional_cluster(code: str, request: Request):
    """Get functional cluster by code"""
    cluster = taxonomy_catalog.get_functional_cluster(code)
    if not cluster:
        raise HTTPException(status_code=404, detail="Functional cluster not found")
    return {"status": "ok", "cluster": cluster.to_dict()}


@router.get("/taxonomy/specialist-subclusters")
async def list_specialist_subclusters(functional: Optional[str] = None, request: Request = None):
    """List Tier 3 specialist subclusters"""
    subclusters = taxonomy_catalog.list_specialist_subclusters(functional)
    return {"status": "ok", "subclusters": [s.to_dict() for s in subclusters]}


@router.get("/taxonomy/specialist-subclusters/{code}")
async def get_specialist_subcluster(code: str, request: Request):
    """Get specialist subcluster by code"""
    subcluster = taxonomy_catalog.get_specialist_subcluster(code)
    if not subcluster:
        raise HTTPException(status_code=404, detail="Specialist subcluster not found")
    return {"status": "ok", "subcluster": subcluster.to_dict()}


@router.get("/taxonomy/marketplace-categories")
async def get_marketplace_categories(request: Request):
    """Get marketplace category mapping"""
    return {"status": "ok", "categories": taxonomy_catalog.get_marketplace_categories()}


@router.get("/taxonomy/risk-ratings")
async def get_risk_ratings(request: Request):
    """Get Semantic Risk Rating (SRR) definitions"""
    return {
        "status": "ok",
        "ratings": {
            "SRR-1": "Minimal risk (summarization, semantic search)",
            "SRR-2": "Low risk (creative generation, basic communication)",
            "SRR-3": "Medium risk (workflow execution, planning)",
            "SRR-4": "High risk (finance, system control, engineering)",
            "SRR-5": "Critical risk (legal, medical, governance, planning other agents)",
        },
    }


# Semantic Drift endpoints
@router.post("/taxonomy/drift/record")
async def record_semantic_vector(payload: RecordVectorRequest, request: Request):
    """Record a semantic vector and check for drift"""
    record = drift_monitor.record_vector(
        agent_id=payload.agent_id,
        vector=payload.vector,
        cluster=payload.cluster,
    )
    if record:
        return {"status": "ok", "drift_detected": True, "record": record.to_dict()}
    return {"status": "ok", "drift_detected": False, "message": "First vector recorded"}


@router.get("/taxonomy/drift/history/{agent_id}")
async def get_drift_history(agent_id: str, request: Request):
    """Get drift history for an agent"""
    history = drift_monitor.get_drift_history(agent_id)
    return {"status": "ok", "history": [r.to_dict() for r in history]}


@router.get("/taxonomy/drift/stats/{agent_id}")
async def get_drift_stats(agent_id: str, request: Request):
    """Get drift statistics for an agent"""
    return {"status": "ok", "stats": drift_monitor.get_drift_stats(agent_id)}


# Semantic Confidence endpoints
@router.post("/taxonomy/confidence/calculate")
async def calculate_semantic_confidence(payload: CalculateConfidenceRequest, request: Request):
    """Calculate Semantic Confidence Interval (SCI)"""
    score = confidence_calculator.calculate_confidence(
        agent_id=payload.agent_id,
        vector=payload.vector,
        cluster_centroids=payload.cluster_centroids,
    )
    return {"status": "ok", "confidence": score.to_dict()}


@router.get("/taxonomy/confidence/{agent_id}")
async def get_semantic_confidence(agent_id: str, request: Request):
    """Get SCI for an agent"""
    score = confidence_calculator.get_score(agent_id)
    if not score:
        raise HTTPException(status_code=404, detail="No confidence score found")
    return {"status": "ok", "confidence": score.to_dict()}


@router.get("/taxonomy/confidence/reassignment/{agent_id}")
async def check_reassignment_needed(agent_id: str, request: Request):
    """Check if agent needs cluster reassignment"""
    needs = confidence_calculator.needs_reassignment(agent_id)
    return {"status": "ok", "needs_reassignment": needs}


# Cluster Governance endpoints
@router.get("/taxonomy/governance/rules")
async def list_governance_rules(request: Request):
    """List cluster governance rules"""
    rules = governance_manager.list_rules()
    return {"status": "ok", "rules": [r.to_dict() for r in rules]}


@router.get("/taxonomy/governance/rules/{cluster_code}")
async def get_governance_rules(cluster_code: str, request: Request):
    """Get governance rules for a cluster"""
    rules = governance_manager.get_rules(cluster_code)
    if not rules:
        raise HTTPException(status_code=404, detail="No rules found for cluster")
    return {"status": "ok", "rules": rules.to_dict()}


@router.post("/taxonomy/governance/check-action")
async def check_action_allowed(payload: CheckActionRequest, request: Request):
    """Check if an action is allowed for a cluster"""
    result = governance_manager.check_action_allowed(payload.cluster_code, payload.action)
    return {"status": "ok", "result": result}


# ============== SECTION 29: ECONOMIC FORECASTING MODEL ==============

from .economic_model import (
    forecast_engine, network_effect_calc, get_tam_analysis,
    MarketplaceRevenueCalculator, EnterpriseRevenueCalculator,
    GovernmentRevenueCalculator, PlatformUsageCalculator,
)


class GenerateForecastRequest(BaseModel):
    periods: int = 10
    initial_users: int = 1000
    user_growth_rate: float = 1.5
    agent_creation_rate: float = 0.5
    max_enterprises: int = 500
    enterprise_k: float = 0.6
    enterprise_midpoint: int = 4
    max_governments: int = 50
    government_k: float = 0.4
    government_midpoint: int = 6


class MarketplaceRevenueRequest(BaseModel):
    period: int
    agents_minted: int
    agents_sold: int
    rental_transactions: int
    skills_sold: int
    a2a_interactions: int


class NetworkEffectRequest(BaseModel):
    users: int
    agents: int
    enterprises: int
    governments: int
    marketplace_revenue: float


@router.post("/economics/forecast/generate")
async def generate_economic_forecast(payload: GenerateForecastRequest, request: Request):
    """Generate multi-period economic forecast"""
    forecasts = forecast_engine.generate_forecast(
        periods=payload.periods,
        initial_users=payload.initial_users,
        user_growth_rate=payload.user_growth_rate,
        agent_creation_rate=payload.agent_creation_rate,
        max_enterprises=payload.max_enterprises,
        enterprise_k=payload.enterprise_k,
        enterprise_midpoint=payload.enterprise_midpoint,
        max_governments=payload.max_governments,
        government_k=payload.government_k,
        government_midpoint=payload.government_midpoint,
    )
    return {"status": "ok", "forecasts": [f.to_dict() for f in forecasts]}


@router.get("/economics/forecast/summary")
async def get_forecast_summary(request: Request):
    """Get forecast summary"""
    return {"status": "ok", "summary": forecast_engine.get_summary()}


@router.get("/economics/forecast/period/{period}")
async def get_period_forecast(period: int, request: Request):
    """Get forecast for a specific period"""
    forecast = forecast_engine.get_forecast(period)
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast not found for period")
    return {"status": "ok", "forecast": forecast.to_dict()}


@router.post("/economics/marketplace/calculate")
async def calculate_marketplace_revenue(payload: MarketplaceRevenueRequest, request: Request):
    """Calculate marketplace revenue for a period"""
    calc = MarketplaceRevenueCalculator()
    revenue = calc.calculate(
        period=payload.period,
        agents_minted=payload.agents_minted,
        agents_sold=payload.agents_sold,
        rental_transactions=payload.rental_transactions,
        skills_sold=payload.skills_sold,
        a2a_interactions=payload.a2a_interactions,
    )
    return {"status": "ok", "revenue": revenue.to_dict()}


@router.get("/economics/enterprise/calculate/{num_enterprises}")
async def calculate_enterprise_revenue(num_enterprises: int, period: int = 1, request: Request = None):
    """Calculate enterprise revenue"""
    calc = EnterpriseRevenueCalculator()
    revenue = calc.calculate(period, num_enterprises)
    return {"status": "ok", "revenue": revenue.to_dict()}


@router.get("/economics/government/calculate/{num_deployments}")
async def calculate_government_revenue(num_deployments: int, period: int = 1, request: Request = None):
    """Calculate government revenue"""
    calc = GovernmentRevenueCalculator()
    revenue = calc.calculate(period, num_deployments)
    return {"status": "ok", "revenue": revenue.to_dict()}


@router.get("/economics/platform/calculate/{active_agents}")
async def calculate_platform_revenue(active_agents: int, period: int = 1, request: Request = None):
    """Calculate platform usage revenue"""
    calc = PlatformUsageCalculator()
    revenue = calc.calculate(period, active_agents)
    return {"status": "ok", "revenue": revenue.to_dict()}


@router.post("/economics/network-effects")
async def calculate_network_effects(payload: NetworkEffectRequest, request: Request):
    """Calculate network effect metrics"""
    metrics = network_effect_calc.calculate(
        users=payload.users,
        agents=payload.agents,
        enterprises=payload.enterprises,
        governments=payload.governments,
        marketplace_revenue=payload.marketplace_revenue,
    )
    return {"status": "ok", "metrics": metrics.to_dict()}


@router.get("/economics/tam")
async def get_tam_analysis_endpoint(request: Request):
    """Get Total Addressable Market analysis"""
    tam = get_tam_analysis()
    return {"status": "ok", "tam": [t.to_dict() for t in tam]}


@router.get("/economics/revenue-engines")
async def get_revenue_engines(request: Request):
    """Get revenue engine descriptions"""
    return {
        "status": "ok",
        "engines": {
            "marketplace": {
                "name": "Agent Marketplace Revenue",
                "components": ["minting", "sales", "rentals", "skills", "agent-to-agent"],
            },
            "enterprise": {
                "name": "Enterprise Deployment Revenue",
                "components": ["license_fee", "agent_fleet", "usage_fees"],
            },
            "government": {
                "name": "Government Sovereign Infrastructure Revenue",
                "components": ["sovereign_license", "ministry_deployment", "agent_workforce", "infrastructure"],
            },
            "platform": {
                "name": "Platform Usage/API Revenue",
                "components": ["dag_operations", "anchoring", "coordination", "semantic", "interactions"],
            },
        },
    }


# ============== SECTION 30: AGENT REPUTATION & TRUST SYSTEM ==============

from .reputation_trust import (
    trust_calculator, decay_engine, recovery_engine, enforcement_engine,
    marketplace_integration, history_manager,
    TrustTier, TrustRecoveryAction, WEIGHT_PROFILES,
    PerformanceReputation, BehavioralReputation, SemanticReliability,
    GovernanceComplianceScore, SocialInteractionScore,
)


class CalculateTrustScoreRequest(BaseModel):
    agent_id: str
    weight_profile: str = "medium_risk"
    performance: Dict[str, Any]
    behavioral: Dict[str, Any]
    semantic: Dict[str, Any]
    governance: Dict[str, Any]
    social: Dict[str, Any]


class ApplyDecayRequest(BaseModel):
    current_score: float
    days_inactive: int = 0
    behavior_graph_age_days: int = 0
    drift_events: int = 0
    is_gov_certified: bool = False
    is_enterprise_verified: bool = False


class ApplyRecoveryRequest(BaseModel):
    agent_id: str
    current_score: float
    action: str
    verified_by: Optional[str] = None


class CheckTrustAccessRequest(BaseModel):
    agent_tier: str
    cluster_code: str


class RecordTrustEventRequest(BaseModel):
    agent_id: str
    event_type: str
    details: Dict[str, Any]


@router.post("/trust/score/calculate")
async def calculate_trust_score(payload: CalculateTrustScoreRequest, request: Request):
    """Calculate Agent Trust Score (ATS)"""
    
    pr = PerformanceReputation(
        agent_id=payload.agent_id,
        task_success_rate=payload.performance.get("task_success_rate", 0.8),
        error_frequency=payload.performance.get("error_frequency", 2.0),
        output_quality_score=payload.performance.get("output_quality_score", 75.0),
        latency_consistency=payload.performance.get("latency_consistency", 0.9),
        successful_interactions=payload.performance.get("successful_interactions", 100),
        enterprise_satisfaction=payload.performance.get("enterprise_satisfaction", 80.0),
    )
    
    br = BehavioralReputation(
        agent_id=payload.agent_id,
        behavior_consistency=payload.behavioral.get("behavior_consistency", 0.85),
        deviation_score=payload.behavioral.get("deviation_score", 10.0),
        anomaly_count=payload.behavioral.get("anomaly_count", 1),
        cooperation_quality=payload.behavioral.get("cooperation_quality", 80.0),
        conflict_rate=payload.behavioral.get("conflict_rate", 1.0),
        governance_warnings=payload.behavioral.get("governance_warnings", 0),
    )
    
    sr = SemanticReliability(
        agent_id=payload.agent_id,
        drift_velocity=payload.semantic.get("drift_velocity", 0.05),
        cluster_consistency=payload.semantic.get("cluster_consistency", 0.9),
        vector_coherence=payload.semantic.get("vector_coherence", 0.85),
        domain_alignment=payload.semantic.get("domain_alignment", 80.0),
        misalignment_recoveries=payload.semantic.get("misalignment_recoveries", 2),
    )
    
    gcs = GovernanceComplianceScore(
        agent_id=payload.agent_id,
        policy_violations=payload.governance.get("policy_violations", 0),
        permission_breaches=payload.governance.get("permission_breaches", 0),
        unauthorized_writes=payload.governance.get("unauthorized_writes", 0),
        delegation_misuse=payload.governance.get("delegation_misuse", 0),
        compliance_audits_passed=payload.governance.get("compliance_audits_passed", 5),
        compliance_audits_failed=payload.governance.get("compliance_audits_failed", 0),
        supervisory_interventions=payload.governance.get("supervisory_interventions", 1),
    )
    
    sis = SocialInteractionScore(
        agent_id=payload.agent_id,
        peer_evaluations_positive=payload.social.get("peer_evaluations_positive", 20),
        peer_evaluations_negative=payload.social.get("peer_evaluations_negative", 2),
        enterprise_ratings_sum=payload.social.get("enterprise_ratings_sum", 400.0),
        enterprise_ratings_count=payload.social.get("enterprise_ratings_count", 5),
        conflict_resolutions_success=payload.social.get("conflict_resolutions_success", 8),
        conflict_resolutions_failed=payload.social.get("conflict_resolutions_failed", 1),
        cooperation_frequency=payload.social.get("cooperation_frequency", 50),
        legitimate_refusals=payload.social.get("legitimate_refusals", 10),
        incorrect_refusals=payload.social.get("incorrect_refusals", 1),
    )
    
    score = trust_calculator.calculate(
        agent_id=payload.agent_id,
        pr=pr, br=br, sr=sr, gcs=gcs, sis=sis,
        weight_profile=payload.weight_profile,
    )
    
    return {"status": "ok", "score": score.to_dict()}


@router.get("/trust/score/{agent_id}")
async def get_trust_score(agent_id: str, request: Request):
    """Get trust score for an agent"""
    score = trust_calculator.get_score(agent_id)
    if not score:
        raise HTTPException(status_code=404, detail="Trust score not found")
    return {"status": "ok", "score": score.to_dict()}


@router.get("/trust/history/{agent_id}")
async def get_trust_history(agent_id: str, request: Request):
    """Get trust score history for an agent"""
    history = trust_calculator.get_history(agent_id)
    return {"status": "ok", "history": [s.to_dict() for s in history]}


@router.post("/trust/decay/apply")
async def apply_trust_decay(payload: ApplyDecayRequest, request: Request):
    """Apply trust decay to a score"""
    new_score, breakdown = decay_engine.apply_decay(
        current_score=payload.current_score,
        days_inactive=payload.days_inactive,
        behavior_graph_age_days=payload.behavior_graph_age_days,
        drift_events=payload.drift_events,
        is_gov_certified=payload.is_gov_certified,
        is_enterprise_verified=payload.is_enterprise_verified,
    )
    return {
        "status": "ok",
        "original_score": payload.current_score,
        "new_score": round(new_score, 2),
        "breakdown": breakdown,
    }


@router.post("/trust/recovery/apply")
async def apply_trust_recovery(payload: ApplyRecoveryRequest, request: Request):
    """Apply trust recovery action"""
    try:
        action = TrustRecoveryAction(payload.action)
        event = recovery_engine.apply_recovery(
            agent_id=payload.agent_id,
            current_score=payload.current_score,
            action=action,
            verified_by=payload.verified_by,
        )
        return {"status": "ok", "event": event.to_dict()}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid recovery action")


@router.get("/trust/recovery/history/{agent_id}")
async def get_recovery_history(agent_id: str, request: Request):
    """Get recovery history for an agent"""
    history = recovery_engine.get_recovery_history(agent_id)
    return {"status": "ok", "history": [e.to_dict() for e in history]}


@router.post("/trust/enforcement/check")
async def check_trust_access(payload: CheckTrustAccessRequest, request: Request):
    """Check if agent has access based on trust tier"""
    try:
        tier = TrustTier(payload.agent_tier)
        result = enforcement_engine.check_access(tier, payload.cluster_code)
        return {"status": "ok", "result": result}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid trust tier")


@router.get("/trust/enforcement/rules")
async def list_enforcement_rules(request: Request):
    """List trust enforcement rules"""
    rules = enforcement_engine.list_rules()
    return {"status": "ok", "rules": [r.to_dict() for r in rules]}


@router.get("/trust/marketplace/multiplier/{ats}")
async def get_price_multiplier(ats: float, request: Request):
    """Get marketplace price multiplier for ATS"""
    multiplier = marketplace_integration.calculate_price_multiplier(ats)
    return {"status": "ok", "ats": ats, "price_multiplier": round(multiplier, 2)}


@router.get("/trust/marketplace/visibility/{tier}")
async def get_marketplace_visibility(tier: str, request: Request):
    """Get marketplace visibility level for tier"""
    try:
        trust_tier = TrustTier(tier)
        visibility = marketplace_integration.get_visibility_level(trust_tier)
        badge = marketplace_integration.get_marketplace_badge(trust_tier)
        return {"status": "ok", "tier": tier, "visibility": visibility, "badge": badge}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid trust tier")


@router.post("/trust/events/record")
async def record_trust_event(payload: RecordTrustEventRequest, request: Request):
    """Record a trust event"""
    event = history_manager.record_event(
        agent_id=payload.agent_id,
        event_type=payload.event_type,
        details=payload.details,
    )
    return {"status": "ok", "event": event.to_dict()}


@router.get("/trust/events/{agent_id}")
async def get_trust_events(agent_id: str, event_type: Optional[str] = None, request: Request = None):
    """Get trust events for an agent"""
    events = history_manager.get_history(agent_id, event_type)
    return {"status": "ok", "events": [e.to_dict() for e in events]}


@router.get("/trust/audit/{agent_id}")
async def get_trust_audit_report(agent_id: str, request: Request):
    """Get trust audit report for an agent"""
    report = history_manager.get_audit_report(agent_id)
    return {"status": "ok", "report": report}


@router.get("/trust/tiers")
async def get_trust_tiers(request: Request):
    """Get trust tier definitions"""
    return {
        "status": "ok",
        "tiers": {
            "T5": {"name": "Platinum", "range": "90-100", "description": "Enterprise/Gov-grade reliability"},
            "T4": {"name": "Gold", "range": "75-89", "description": "High-performing, trusted"},
            "T3": {"name": "Silver", "range": "60-74", "description": "Stable, general-purpose"},
            "T2": {"name": "Bronze", "range": "40-59", "description": "Limited trust, supervised"},
            "T1": {"name": "Restricted", "range": "0-39", "description": "Heavily supervised or suspended"},
        },
    }


@router.get("/trust/weight-profiles")
async def get_weight_profiles(request: Request):
    """Get trust weight profiles"""
    return {
        "status": "ok",
        "profiles": {k: v.to_dict() for k, v in WEIGHT_PROFILES.items()},
    }


@router.get("/trust/recovery-actions")
async def get_recovery_actions(request: Request):
    """Get available trust recovery actions"""
    return {
        "status": "ok",
        "actions": [a.value for a in TrustRecoveryAction],
    }


@router.get("/trust/pillars")
async def get_trust_pillars(request: Request):
    """Get trust pillar definitions"""
    return {
        "status": "ok",
        "pillars": {
            "PR": {
                "name": "Performance Reputation",
                "description": "How reliably the agent completes tasks",
                "factors": ["task_success_rate", "error_frequency", "output_quality", "latency_consistency"],
            },
            "BR": {
                "name": "Behavioral Reputation",
                "description": "How predictable, stable, and safe the agent's behavior is",
                "factors": ["behavior_consistency", "deviation_score", "anomaly_count", "cooperation_quality"],
            },
            "SR": {
                "name": "Semantic Reliability",
                "description": "How stable the agent is within its semantic cluster",
                "factors": ["drift_velocity", "cluster_consistency", "vector_coherence", "domain_alignment"],
            },
            "GCS": {
                "name": "Governance Compliance Score",
                "description": "How well the agent follows governance contracts",
                "factors": ["policy_violations", "permission_breaches", "compliance_audits", "supervisory_interventions"],
            },
            "SIS": {
                "name": "Social/Interaction Score",
                "description": "How trustworthy the agent is as a collaborator",
                "factors": ["peer_evaluations", "enterprise_ratings", "conflict_resolution", "cooperation_frequency"],
            },
        },
    }


# ============== SECTION 31: INFRASTRUCTURE DEPLOYMENT MODEL ==============

from .infrastructure_deployment import (
    deployment_catalog, deployment_manager, blueprint_generator,
    DeploymentMode, DeploymentMaturityLevel, NodeType, DeploymentPhase,
    HighAvailabilityConfig,
)


class CreateDeploymentRequest(BaseModel):
    name: str
    mode: str
    region: str
    maturity_level: int = 1
    ha_config: Optional[Dict[str, Any]] = None


class AddNodeRequest(BaseModel):
    deployment_id: str
    node_type: str
    region: str
    zone: str
    replicas: int = 1


class UpdatePhaseRequest(BaseModel):
    deployment_id: str
    phase: str


# Deployment Mode endpoints
@router.get("/deployment/modes")
async def list_deployment_modes(request: Request):
    """List deployment mode configurations"""
    configs = deployment_catalog.list_mode_configs()
    return {"status": "ok", "modes": [c.to_dict() for c in configs]}


@router.get("/deployment/modes/{mode}")
async def get_deployment_mode(mode: str, request: Request):
    """Get deployment mode configuration"""
    config = deployment_catalog.get_mode_config(mode)
    if not config:
        raise HTTPException(status_code=404, detail="Mode not found")
    return {"status": "ok", "mode": config.to_dict()}


# Node Definition endpoints
@router.get("/deployment/node-types")
async def list_node_types(request: Request):
    """List node type definitions"""
    definitions = deployment_catalog.list_node_definitions()
    return {"status": "ok", "node_types": [d.to_dict() for d in definitions]}


@router.get("/deployment/node-types/{node_type}")
async def get_node_type(node_type: str, request: Request):
    """Get node type definition"""
    definition = deployment_catalog.get_node_definition(node_type)
    if not definition:
        raise HTTPException(status_code=404, detail="Node type not found")
    return {"status": "ok", "node_type": definition.to_dict()}


# Deployment Management endpoints
@router.post("/deployment/create")
async def create_deployment(payload: CreateDeploymentRequest, request: Request):
    """Create a new deployment"""
    try:
        mode = DeploymentMode(payload.mode)
        maturity = DeploymentMaturityLevel(payload.maturity_level)
        
        ha_config = None
        if payload.ha_config:
            ha_config = HighAvailabilityConfig(
                storage_replicas=payload.ha_config.get("storage_replicas", 3),
                compute_redundancy=payload.ha_config.get("compute_redundancy", "active-active"),
                identity_replicas=payload.ha_config.get("identity_replicas", 3),
                registry_signers=payload.ha_config.get("registry_signers", 5),
                failover_mode=payload.ha_config.get("failover_mode", "automatic"),
            )
        
        deployment = deployment_manager.create_deployment(
            name=payload.name,
            mode=mode,
            region=payload.region,
            maturity_level=maturity,
            ha_config=ha_config,
        )
        return {"status": "ok", "deployment": deployment}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/deployment/list")
async def list_deployments(request: Request):
    """List all deployments"""
    deployments = deployment_manager.list_deployments()
    return {"status": "ok", "deployments": deployments}


@router.get("/deployment/{deployment_id}")
async def get_deployment(deployment_id: str, request: Request):
    """Get deployment details"""
    deployment = deployment_manager.get_deployment(deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return {"status": "ok", "deployment": deployment}


@router.post("/deployment/node/add")
async def add_deployment_node(payload: AddNodeRequest, request: Request):
    """Add a node to a deployment"""
    try:
        node_type = NodeType(payload.node_type)
        node = deployment_manager.add_node(
            deployment_id=payload.deployment_id,
            node_type=node_type,
            region=payload.region,
            zone=payload.zone,
            replicas=payload.replicas,
        )
        return {"status": "ok", "node": node.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/deployment/{deployment_id}/nodes")
async def list_deployment_nodes(deployment_id: str, request: Request):
    """List nodes in a deployment"""
    nodes = deployment_manager.list_nodes(deployment_id)
    return {"status": "ok", "nodes": [n.to_dict() for n in nodes]}


@router.get("/deployment/{deployment_id}/health")
async def get_deployment_health(deployment_id: str, request: Request):
    """Get deployment health summary"""
    health = deployment_manager.get_deployment_health(deployment_id)
    return {"status": "ok", "health": health}


@router.post("/deployment/phase/update")
async def update_deployment_phase(payload: UpdatePhaseRequest, request: Request):
    """Update deployment phase"""
    try:
        phase = DeploymentPhase(payload.phase)
        deployment = deployment_manager.update_deployment_phase(
            deployment_id=payload.deployment_id,
            phase=phase,
        )
        if not deployment:
            raise HTTPException(status_code=404, detail="Deployment not found")
        return {"status": "ok", "deployment": deployment}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Blueprint endpoints
@router.get("/deployment/blueprint/enterprise")
async def get_enterprise_blueprint(request: Request):
    """Get enterprise deployment blueprint"""
    blueprint = blueprint_generator.generate_enterprise_blueprint()
    return {"status": "ok", "blueprint": blueprint.to_dict()}


@router.get("/deployment/blueprint/government")
async def get_government_blueprint(request: Request):
    """Get government deployment blueprint"""
    blueprint = blueprint_generator.generate_government_blueprint()
    return {"status": "ok", "blueprint": blueprint.to_dict()}


@router.get("/deployment/maturity-levels")
async def get_maturity_levels(request: Request):
    """Get deployment maturity level definitions"""
    return {
        "status": "ok",
        "levels": {
            "L1": "Local development",
            "L2": "Single-cluster deploy",
            "L3": "Multi-cluster enterprise",
            "L4": "High-availability + governance",
            "L5": "Federated enterprise",
            "L6": "Sovereign national infrastructure",
            "L7": "Global federated deployment",
        },
    }


@router.get("/deployment/phases")
async def get_deployment_phases(request: Request):
    """Get deployment phase definitions"""
    return {
        "status": "ok",
        "phases": {
            "foundation": "Phase 1: Identity, Registry, Storage",
            "dag_infrastructure": "Phase 2: User/Agent Sphere, Coordination",
            "semantics": "Phase 3: Semantic clusters, Drift, Governance",
            "marketplace": "Phase 4: Marketplace, Apps, Multi-agent",
        },
    }


# ============== SECTION 32: FEDERATION & MULTI-TENANT SOVEREIGNTY ==============

from .federation_sovereignty import (
    tenant_manager, federation_manager, sovereignty_validator,
    FederationScope, FederationMaturityLevel, IsolationLevel,
)


class CreateTenantRequest(BaseModel):
    name: str
    tenant_type: str
    region: str
    jurisdiction: str
    federation_scope: str = "intra_tenant"
    maturity_level: int = 1


class CreatePartitionRequest(BaseModel):
    tenant_id: str
    name: str
    partition_type: str
    governance_policy_id: str


class EstablishTrustBridgeRequest(BaseModel):
    tenant_a_id: str
    tenant_b_id: str
    scope: str
    trust_level: str = "limited"
    expires_in_days: Optional[int] = None


class IssueCredentialRequest(BaseModel):
    issuer_tenant_id: str
    subject_tenant_id: str
    agent_id: str
    trust_tier: str
    semantic_cluster: str
    risk_classification: str
    governance_contract_hash: str
    valid_days: int = 365


class CreateSemanticAlignmentRequest(BaseModel):
    source_tenant_id: str
    target_tenant_id: str
    cluster_mappings: Dict[str, str]
    drift_mappings: Dict[str, float]
    risk_mappings: Dict[str, str]


class CreateInteractionRequest(BaseModel):
    source_tenant_id: str
    target_tenant_id: str
    source_agent_id: str
    interaction_type: str
    target_agent_id: Optional[str] = None


class ApproveInteractionRequest(BaseModel):
    interaction_id: str
    tenant_id: str


class ValidateCrossBoundaryRequest(BaseModel):
    source_tenant_id: str
    target_tenant_id: str
    trust_bridge_id: Optional[str] = None
    agent_trust_tier: str
    semantic_cluster: str
    risk_level: int


# Tenant Management endpoints
@router.post("/federation/tenant/create")
async def create_tenant(payload: CreateTenantRequest, request: Request):
    """Create a new tenant"""
    try:
        scope = FederationScope(payload.federation_scope)
        maturity = FederationMaturityLevel(payload.maturity_level)
        
        tenant = tenant_manager.create_tenant(
            name=payload.name,
            tenant_type=payload.tenant_type,
            region=payload.region,
            jurisdiction=payload.jurisdiction,
            federation_scope=scope,
            maturity_level=maturity,
        )
        return {"status": "ok", "tenant": tenant.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/federation/tenant/list")
async def list_tenants(tenant_type: Optional[str] = None, request: Request = None):
    """List all tenants"""
    tenants = tenant_manager.list_tenants(tenant_type)
    return {"status": "ok", "tenants": [t.to_dict() for t in tenants]}


@router.get("/federation/tenant/{tenant_id}")
async def get_tenant(tenant_id: str, request: Request):
    """Get tenant details"""
    tenant = tenant_manager.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"status": "ok", "tenant": tenant.to_dict()}


@router.post("/federation/partition/create")
async def create_partition(payload: CreatePartitionRequest, request: Request):
    """Create a partition within a tenant"""
    partition = tenant_manager.create_partition(
        tenant_id=payload.tenant_id,
        name=payload.name,
        partition_type=payload.partition_type,
        governance_policy_id=payload.governance_policy_id,
    )
    if not partition:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"status": "ok", "partition": partition.to_dict()}


@router.get("/federation/tenant/{tenant_id}/partitions")
async def list_tenant_partitions(tenant_id: str, request: Request):
    """List partitions in a tenant"""
    partitions = tenant_manager.list_partitions(tenant_id)
    return {"status": "ok", "partitions": [p.to_dict() for p in partitions]}


# Trust Bridge endpoints
@router.post("/federation/trust-bridge/establish")
async def establish_trust_bridge(payload: EstablishTrustBridgeRequest, request: Request):
    """Establish a trust bridge between tenants"""
    try:
        scope = FederationScope(payload.scope)
        bridge = federation_manager.establish_trust_bridge(
            tenant_a_id=payload.tenant_a_id,
            tenant_b_id=payload.tenant_b_id,
            scope=scope,
            trust_level=payload.trust_level,
            expires_in_days=payload.expires_in_days,
        )
        if not bridge:
            raise HTTPException(status_code=404, detail="One or both tenants not found")
        return {"status": "ok", "bridge": bridge.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/federation/trust-bridge/list")
async def list_trust_bridges(tenant_id: Optional[str] = None, request: Request = None):
    """List trust bridges"""
    bridges = federation_manager.list_trust_bridges(tenant_id)
    return {"status": "ok", "bridges": [b.to_dict() for b in bridges]}


@router.get("/federation/trust-bridge/{bridge_id}")
async def get_trust_bridge(bridge_id: str, request: Request):
    """Get trust bridge details"""
    bridge = federation_manager.get_trust_bridge(bridge_id)
    if not bridge:
        raise HTTPException(status_code=404, detail="Trust bridge not found")
    return {"status": "ok", "bridge": bridge.to_dict()}


# Credential endpoints
@router.post("/federation/credential/issue")
async def issue_credential(payload: IssueCredentialRequest, request: Request):
    """Issue a federated identity credential"""
    credential = federation_manager.issue_credential(
        issuer_tenant_id=payload.issuer_tenant_id,
        subject_tenant_id=payload.subject_tenant_id,
        agent_id=payload.agent_id,
        trust_tier=payload.trust_tier,
        semantic_cluster=payload.semantic_cluster,
        risk_classification=payload.risk_classification,
        governance_contract_hash=payload.governance_contract_hash,
        valid_days=payload.valid_days,
    )
    return {"status": "ok", "credential": credential.to_dict()}


@router.get("/federation/credential/{credential_id}")
async def get_credential(credential_id: str, request: Request):
    """Get credential details"""
    credential = federation_manager.get_credential(credential_id)
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"status": "ok", "credential": credential.to_dict()}


# Semantic Alignment endpoints
@router.post("/federation/semantic-alignment/create")
async def create_semantic_alignment(payload: CreateSemanticAlignmentRequest, request: Request):
    """Create a semantic alignment map between tenants"""
    alignment = federation_manager.create_semantic_alignment(
        source_tenant_id=payload.source_tenant_id,
        target_tenant_id=payload.target_tenant_id,
        cluster_mappings=payload.cluster_mappings,
        drift_mappings=payload.drift_mappings,
        risk_mappings=payload.risk_mappings,
    )
    return {"status": "ok", "alignment": alignment.to_dict()}


# Cross-Boundary Interaction endpoints
@router.post("/federation/interaction/create")
async def create_interaction(payload: CreateInteractionRequest, request: Request):
    """Create a cross-boundary interaction"""
    interaction = federation_manager.create_interaction(
        source_tenant_id=payload.source_tenant_id,
        target_tenant_id=payload.target_tenant_id,
        source_agent_id=payload.source_agent_id,
        interaction_type=payload.interaction_type,
        target_agent_id=payload.target_agent_id,
    )
    return {"status": "ok", "interaction": interaction.to_dict()}


@router.post("/federation/interaction/approve")
async def approve_interaction(payload: ApproveInteractionRequest, request: Request):
    """Approve an interaction from a tenant's governance"""
    interaction = federation_manager.approve_interaction(
        interaction_id=payload.interaction_id,
        tenant_id=payload.tenant_id,
    )
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")
    return {"status": "ok", "interaction": interaction.to_dict()}


@router.get("/federation/interaction/{interaction_id}")
async def get_interaction(interaction_id: str, request: Request):
    """Get interaction details"""
    interaction = federation_manager.get_interaction(interaction_id)
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")
    return {"status": "ok", "interaction": interaction.to_dict()}


@router.get("/federation/interaction/list")
async def list_interactions(
    tenant_id: Optional[str] = None,
    status: Optional[str] = None,
    request: Request = None,
):
    """List cross-boundary interactions"""
    interactions = federation_manager.list_interactions(tenant_id, status)
    return {"status": "ok", "interactions": [i.to_dict() for i in interactions]}


# Sovereignty Validation endpoints
@router.post("/federation/validate/cross-boundary")
async def validate_cross_boundary(payload: ValidateCrossBoundaryRequest, request: Request):
    """Validate a cross-boundary request"""
    source_tenant = tenant_manager.get_tenant(payload.source_tenant_id)
    target_tenant = tenant_manager.get_tenant(payload.target_tenant_id)
    
    if not source_tenant or not target_tenant:
        raise HTTPException(status_code=404, detail="One or both tenants not found")
    
    trust_bridge = None
    if payload.trust_bridge_id:
        trust_bridge = federation_manager.get_trust_bridge(payload.trust_bridge_id)
    
    result = sovereignty_validator.validate_cross_boundary_request(
        source_tenant=source_tenant,
        target_tenant=target_tenant,
        trust_bridge=trust_bridge,
        agent_trust_tier=payload.agent_trust_tier,
        semantic_cluster=payload.semantic_cluster,
        risk_level=payload.risk_level,
    )
    return {"status": "ok", "validation": result}


@router.get("/federation/scopes")
async def get_federation_scopes(request: Request):
    """Get federation scope definitions"""
    return {
        "status": "ok",
        "scopes": {
            "intra_tenant": "Scope 1: Within a single tenant (departments, environments)",
            "inter_enterprise": "Scope 2: Between enterprises (supplier-manufacturer, bank-fintech)",
            "inter_ministry": "Scope 3: Between government ministries",
            "inter_nation": "Scope 4: Between nations (highest level)",
        },
    }


@router.get("/federation/maturity-levels")
async def get_federation_maturity_levels(request: Request):
    """Get federation maturity level definitions"""
    return {
        "status": "ok",
        "levels": {
            "FM-1": "Single-tenant isolation",
            "FM-2": "Intra-enterprise federation",
            "FM-3": "Cross-enterprise federation",
            "FM-4": "Inter-ministry federation",
            "FM-5": "National sovereign federation",
            "FM-6": "Multi-nation federation",
            "FM-7": "Global, semantic-governed federation",
        },
    }


@router.get("/federation/isolation-levels")
async def get_isolation_levels(request: Request):
    """Get isolation level definitions"""
    return {
        "status": "ok",
        "levels": [l.value for l in IsolationLevel],
        "descriptions": {
            "identity": "Tenants cannot read or impersonate each other's identities",
            "memory": "User/Agent DAGs remain inside the tenant",
            "semantic": "Each tenant has its own vectors, clusters, risk ratings",
            "coordination": "Workflow logs never cross boundaries unless allowed",
            "registry": "Each tenant has its own registry chain",
            "network": "Network-level isolation",
        },
    }


# ============== SECTION 33: PROTOCOL ROADMAP ==============

from .protocol_roadmap import (
    roadmap_catalog, roadmap_tracker, get_long_term_vision,
    RoadmapEra, MilestoneCategory, MilestoneStatus,
)


class UpdateProgressRequest(BaseModel):
    milestone_id: str
    progress_percent: float
    notes: str
    updated_by: str = "system"


# Era endpoints
@router.get("/roadmap/eras")
async def list_roadmap_eras(request: Request):
    """List all roadmap eras"""
    eras = roadmap_catalog.list_eras()
    return {"status": "ok", "eras": [e.to_dict() for e in eras]}


@router.get("/roadmap/eras/{era}")
async def get_roadmap_era(era: str, request: Request):
    """Get roadmap era details"""
    era_def = roadmap_catalog.get_era(era)
    if not era_def:
        raise HTTPException(status_code=404, detail="Era not found")
    return {"status": "ok", "era": era_def.to_dict()}


@router.get("/roadmap/current-era")
async def get_current_era(request: Request):
    """Get the current roadmap era"""
    era = roadmap_catalog.get_current_era()
    return {"status": "ok", "era": era.to_dict()}


# Milestone endpoints
@router.get("/roadmap/milestones")
async def list_milestones(
    era: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    request: Request = None,
):
    """List roadmap milestones"""
    milestones = roadmap_catalog.list_milestones(era, category, status)
    return {"status": "ok", "milestones": [m.to_dict() for m in milestones]}


@router.get("/roadmap/milestones/{milestone_id}")
async def get_milestone(milestone_id: str, request: Request):
    """Get milestone details"""
    milestone = roadmap_catalog.get_milestone(milestone_id)
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return {"status": "ok", "milestone": milestone.to_dict()}


# Progress Tracking endpoints
@router.post("/roadmap/progress/update")
async def update_milestone_progress(payload: UpdateProgressRequest, request: Request):
    """Update progress on a milestone"""
    update = roadmap_tracker.update_progress(
        milestone_id=payload.milestone_id,
        progress_percent=payload.progress_percent,
        notes=payload.notes,
        updated_by=payload.updated_by,
    )
    if not update:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return {"status": "ok", "update": update.to_dict()}


@router.get("/roadmap/progress/{milestone_id}")
async def get_milestone_progress(milestone_id: str, request: Request):
    """Get progress for a milestone"""
    progress = roadmap_tracker.get_milestone_progress(milestone_id)
    history = roadmap_tracker.get_progress_history(milestone_id)
    return {
        "status": "ok",
        "milestone_id": milestone_id,
        "progress": progress,
        "history": [h.to_dict() for h in history],
    }


@router.get("/roadmap/era-progress/{era}")
async def get_era_progress(era: str, request: Request):
    """Get overall progress for an era"""
    progress = roadmap_tracker.get_era_progress(era)
    return {"status": "ok", "progress": progress}


@router.get("/roadmap/summary")
async def get_roadmap_summary(request: Request):
    """Get overall roadmap summary"""
    summary = roadmap_tracker.get_roadmap_summary()
    return {"status": "ok", "summary": summary}


@router.get("/roadmap/vision")
async def get_long_term_vision_endpoint(request: Request):
    """Get the long-term vision for DSID-P (2035)"""
    vision = get_long_term_vision()
    return {"status": "ok", "vision": vision}


@router.get("/roadmap/categories")
async def get_milestone_categories(request: Request):
    """Get milestone category definitions"""
    return {
        "status": "ok",
        "categories": [c.value for c in MilestoneCategory],
        "descriptions": {
            "protocol": "Core protocol development milestones",
            "ecosystem": "Ecosystem and tooling milestones",
            "adoption": "Adoption and deployment milestones",
            "standardization": "Standardization and compliance milestones",
            "technical": "Technical infrastructure milestones",
        },
    }


@router.get("/roadmap/statuses")
async def get_milestone_statuses(request: Request):
    """Get milestone status definitions"""
    return {
        "status": "ok",
        "statuses": [s.value for s in MilestoneStatus],
    }


@router.get("/roadmap/timeline")
async def get_roadmap_timeline(request: Request):
    """Get roadmap timeline overview"""
    return {
        "status": "ok",
        "timeline": {
            "2025-2026": {
                "era": "Era I",
                "name": "Foundation & Local Autonomy",
                "agent_scale": "250-1,000 agents per tenant",
            },
            "2027-2028": {
                "era": "Era II",
                "name": "Enterprise Multi-Agent Infrastructure",
                "agent_scale": "10,000-100,000 agents per enterprise",
            },
            "2029-2030": {
                "era": "Era III",
                "name": "National Sovereign AI Systems",
                "agent_scale": "500,000-3,000,000 agents per nation",
            },
            "2031-2032": {
                "era": "Era IV",
                "name": "Global Federation & Interoperability",
                "agent_scale": "10,000,000-50,000,000 active agents globally",
            },
            "2033-2035": {
                "era": "Era V",
                "name": "Fully Autonomous Semantic Ecosystems",
                "agent_scale": "Billions of agents globally",
            },
        },
    }


# ============== SECTION 34: GLOBAL AGENT WORKFORCE SIMULATION ==============

from .workforce_simulation import (
    population_model, demand_model, supply_model, performance_model,
    governance_risk_model, equilibrium_model, scenario_simulator,
    get_global_growth_projections,
)


class SimulatePopulationRequest(BaseModel):
    periods: int = 10
    initial_agents: int = 1000
    initial_users: int = 500
    initial_orgs: int = 10
    creation_rate: float = 0.5
    auto_generation_rate: float = 0.1


class CalculateDemandRequest(BaseModel):
    users: int
    organizations: int
    industry_multiplier: float = 1.0
    government_scale: float = 0.0


class CalculateSupplyRequest(BaseModel):
    cluster_distribution: Dict[str, int]
    trust_distribution: Optional[Dict[str, float]] = None


class SimulateDriftRequest(BaseModel):
    agent_id: str
    initial_drift: float = 0.05
    drift_velocity: float = 0.01
    risk_level: str = "medium_risk"
    periods: int = 10


class SimulateTrustRequest(BaseModel):
    agent_id: str
    initial_ats: float = 75.0
    decay_rate: float = 0.001
    reinforcement: float = 0.5
    periods: int = 30


class RunScenarioRequest(BaseModel):
    name: str
    agent_count: int
    user_count: int
    org_count: int
    government_scale: float = 0.0
    industry_multiplier: float = 1.0


# Population Model endpoints
@router.post("/simulation/population/simulate")
async def simulate_population(payload: SimulatePopulationRequest, request: Request):
    """Simulate population growth over time"""
    from .workforce_simulation import PopulationModel
    model = PopulationModel(
        initial_agents=payload.initial_agents,
        initial_users=payload.initial_users,
        initial_orgs=payload.initial_orgs,
        creation_rate=payload.creation_rate,
        auto_generation_rate=payload.auto_generation_rate,
    )
    history = model.simulate(payload.periods)
    return {"status": "ok", "history": [h.to_dict() for h in history]}


@router.get("/simulation/population/projections")
async def get_population_projections(
    max_agents: int = 1000000000,
    k: float = 0.5,
    midpoint: int = 5,
    years: int = 10,
    request: Request = None,
):
    """Get population growth projections"""
    projections = population_model.project_growth(max_agents, k, midpoint, years)
    return {"status": "ok", "projections": projections}


# Demand Model endpoints
@router.post("/simulation/demand/calculate")
async def calculate_demand(payload: CalculateDemandRequest, request: Request):
    """Calculate task demand"""
    demand = demand_model.calculate_demand(
        users=payload.users,
        organizations=payload.organizations,
        industry_multiplier=payload.industry_multiplier,
        government_scale=payload.government_scale,
    )
    return {"status": "ok", "demand": demand.to_dict()}


# Supply Model endpoints
@router.post("/simulation/supply/calculate")
async def calculate_supply(payload: CalculateSupplyRequest, request: Request):
    """Calculate agent supply capacity"""
    supply = supply_model.calculate_supply(
        cluster_distribution=payload.cluster_distribution,
        trust_distribution=payload.trust_distribution,
    )
    return {"status": "ok", "supply": supply.to_dict()}


# Performance Model endpoints
@router.get("/simulation/performance/calculate/{agents}")
async def calculate_performance(
    agents: int,
    avg_throughput: float = 100.0,
    avg_success_rate: float = 0.92,
    avg_compliance_factor: float = 0.95,
    request: Request = None,
):
    """Calculate workforce productivity"""
    performance = performance_model.calculate_productivity(
        agents=agents,
        avg_throughput=avg_throughput,
        avg_success_rate=avg_success_rate,
        avg_compliance_factor=avg_compliance_factor,
    )
    return {"status": "ok", "performance": performance.to_dict()}


@router.get("/simulation/performance/cluster-loads")
async def get_cluster_load_profiles(request: Request):
    """Get cluster load profiles"""
    profiles = performance_model.list_cluster_load_profiles()
    return {"status": "ok", "profiles": [p.to_dict() for p in profiles]}


# Governance & Risk Model endpoints
@router.post("/simulation/drift/simulate")
async def simulate_drift(payload: SimulateDriftRequest, request: Request):
    """Simulate semantic drift over time"""
    result = governance_risk_model.simulate_drift(
        agent_id=payload.agent_id,
        initial_drift=payload.initial_drift,
        drift_velocity=payload.drift_velocity,
        risk_level=payload.risk_level,
        periods=payload.periods,
    )
    return {"status": "ok", "simulation": result.to_dict()}


@router.post("/simulation/trust/simulate")
async def simulate_trust_dynamics(payload: SimulateTrustRequest, request: Request):
    """Simulate trust dynamics over time"""
    result = governance_risk_model.simulate_trust_dynamics(
        agent_id=payload.agent_id,
        initial_ats=payload.initial_ats,
        decay_rate=payload.decay_rate,
        reinforcement=payload.reinforcement,
        periods=payload.periods,
    )
    return {"status": "ok", "simulation": result.to_dict()}


# Equilibrium Model endpoints
@router.get("/simulation/equilibrium/calculate")
async def calculate_equilibrium(supply: float, demand: float, request: Request = None):
    """Calculate supply-demand equilibrium"""
    equilibrium = equilibrium_model.calculate_equilibrium(supply, demand)
    return {"status": "ok", "equilibrium": equilibrium.to_dict()}


# Scenario Simulator endpoints
@router.get("/simulation/scenarios/predefined")
async def list_predefined_scenarios(request: Request):
    """List predefined simulation scenarios"""
    scenarios = scenario_simulator.list_predefined_scenarios()
    return {"status": "ok", "scenarios": [s.to_dict() for s in scenarios]}


@router.get("/simulation/scenarios/predefined/{name}")
async def run_predefined_scenario(name: str, request: Request):
    """Run a predefined scenario"""
    scenario = scenario_simulator.get_predefined_scenario(name)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    result = scenario_simulator.run_scenario(scenario)
    return {"status": "ok", "result": result.to_dict()}


@router.post("/simulation/scenarios/custom")
async def run_custom_scenario(payload: RunScenarioRequest, request: Request):
    """Run a custom simulation scenario"""
    from .workforce_simulation import SimulationScenario
    scenario = SimulationScenario(
        scenario_id=str(uuid.uuid4()),
        name=payload.name,
        description="Custom scenario",
        agent_count=payload.agent_count,
        user_count=payload.user_count,
        org_count=payload.org_count,
        government_scale=payload.government_scale,
        industry_multiplier=payload.industry_multiplier,
    )
    result = scenario_simulator.run_scenario(scenario)
    return {"status": "ok", "result": result.to_dict()}


@router.get("/simulation/global-projections")
async def get_global_projections(request: Request):
    """Get global agent workforce growth projections"""
    projections = get_global_growth_projections()
    return {"status": "ok", "projections": projections}


# ============== SECTION 35: ADOPTION STRATEGY ==============

from .adoption_strategy import (
    adoption_catalog, risk_catalog, adoption_tracker,
    AdoptionTrack, ACCELERATORS, PARTNER_CATEGORIES, get_adoption_timeline,
)


class StartAdoptionRequest(BaseModel):
    organization_name: str
    track: str


class UpdateAdoptionRequest(BaseModel):
    adoption_id: str
    phase_progress: float
    current_phase: Optional[str] = None


# Phase endpoints
@router.get("/adoption/phases")
async def list_adoption_phases(track: Optional[str] = None, request: Request = None):
    """List adoption phases"""
    phases = adoption_catalog.list_phases(track)
    return {"status": "ok", "phases": [p.to_dict() for p in phases]}


@router.get("/adoption/phases/{phase_id}")
async def get_adoption_phase(phase_id: str, request: Request):
    """Get adoption phase details"""
    phase = adoption_catalog.get_phase(phase_id)
    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found")
    return {"status": "ok", "phase": phase.to_dict()}


# Risk endpoints
@router.get("/adoption/risks")
async def list_adoption_risks(track: Optional[str] = None, request: Request = None):
    """List adoption risks"""
    risks = risk_catalog.list_risks(track)
    return {"status": "ok", "risks": [r.to_dict() for r in risks]}


@router.get("/adoption/risks/{risk_id}")
async def get_adoption_risk(risk_id: str, request: Request):
    """Get adoption risk details"""
    risk = risk_catalog.get_risk(risk_id)
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")
    return {"status": "ok", "risk": risk.to_dict()}


# Accelerator endpoints
@router.get("/adoption/accelerators")
async def list_accelerators(request: Request):
    """List adoption accelerators"""
    return {"status": "ok", "accelerators": [a.to_dict() for a in ACCELERATORS]}


# Partner endpoints
@router.get("/adoption/partners")
async def list_partner_categories(request: Request):
    """List strategic partner categories"""
    return {"status": "ok", "categories": [p.to_dict() for p in PARTNER_CATEGORIES]}


# Timeline endpoints
@router.get("/adoption/timeline")
async def get_timeline(request: Request):
    """Get full adoption timeline"""
    return {"status": "ok", "timeline": get_adoption_timeline()}


# Adoption Tracking endpoints
@router.post("/adoption/start")
async def start_adoption(payload: StartAdoptionRequest, request: Request):
    """Start tracking an adoption"""
    try:
        track = AdoptionTrack(payload.track)
        adoption = adoption_tracker.start_adoption(
            organization_name=payload.organization_name,
            track=track,
        )
        return {"status": "ok", "adoption": adoption.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/adoption/update")
async def update_adoption(payload: UpdateAdoptionRequest, request: Request):
    """Update adoption progress"""
    adoption = adoption_tracker.update_progress(
        adoption_id=payload.adoption_id,
        phase_progress=payload.phase_progress,
        current_phase=payload.current_phase,
    )
    if not adoption:
        raise HTTPException(status_code=404, detail="Adoption not found")
    return {"status": "ok", "adoption": adoption.to_dict()}


@router.get("/adoption/{adoption_id}")
async def get_adoption(adoption_id: str, request: Request):
    """Get adoption details"""
    adoption = adoption_tracker.get_adoption(adoption_id)
    if not adoption:
        raise HTTPException(status_code=404, detail="Adoption not found")
    return {"status": "ok", "adoption": adoption.to_dict()}


@router.get("/adoption/list")
async def list_adoptions(track: Optional[str] = None, request: Request = None):
    """List all adoptions"""
    adoptions = adoption_tracker.list_adoptions(track)
    return {"status": "ok", "adoptions": [a.to_dict() for a in adoptions]}


@router.get("/adoption/tracks")
async def get_adoption_tracks(request: Request):
    """Get adoption track definitions"""
    return {
        "status": "ok",
        "tracks": {
            "enterprise": {
                "name": "Enterprise Adoption Framework",
                "phases": ["A1", "A2", "A3", "A4", "A5"],
                "duration": "1-36 months",
            },
            "government": {
                "name": "Government/Sovereign Adoption Framework",
                "phases": ["B1", "B2", "B3", "B4"],
                "duration": "1-10 years",
            },
        },
    }


# ============== SECTION 36: ETHICAL GOVERNANCE & OVERSIGHT ==============

from .ethical_governance import (
    ethical_catalog, red_flag_monitor, certification_manager,
    RedFlagType,
)


class DetectRedFlagRequest(BaseModel):
    flag_type: str
    agent_id: str
    description: str
    severity: str = "medium"


class UpdateRedFlagRequest(BaseModel):
    flag_id: str
    status: str
    enforcement_action: Optional[str] = None


class IssueCertificationRequest(BaseModel):
    agent_id: str
    certification_type: str
    issued_by: str
    valid_days: int = 365
    audit_summary: Optional[Dict[str, Any]] = None


# Ethical Pillars endpoints
@router.get("/ethics/pillars")
async def list_ethical_pillars(request: Request):
    """List ethical pillars"""
    pillars = ethical_catalog.list_pillars()
    return {"status": "ok", "pillars": [p.to_dict() for p in pillars]}


@router.get("/ethics/pillars/{pillar}")
async def get_ethical_pillar(pillar: str, request: Request):
    """Get ethical pillar details"""
    p = ethical_catalog.get_pillar(pillar)
    if not p:
        raise HTTPException(status_code=404, detail="Pillar not found")
    return {"status": "ok", "pillar": p.to_dict()}


# Governance Layers endpoints
@router.get("/ethics/layers")
async def list_governance_layers(request: Request):
    """List governance layers"""
    layers = ethical_catalog.list_layers()
    return {"status": "ok", "layers": [l.to_dict() for l in layers]}


@router.get("/ethics/layers/{layer}")
async def get_governance_layer(layer: str, request: Request):
    """Get governance layer details"""
    l = ethical_catalog.get_layer(layer)
    if not l:
        raise HTTPException(status_code=404, detail="Layer not found")
    return {"status": "ok", "layer": l.to_dict()}


# Governance Roles endpoints
@router.get("/ethics/roles")
async def list_governance_roles(request: Request):
    """List governance roles"""
    roles = ethical_catalog.list_roles()
    return {"status": "ok", "roles": [r.to_dict() for r in roles]}


@router.get("/ethics/roles/{role}")
async def get_governance_role(role: str, request: Request):
    """Get governance role details"""
    r = ethical_catalog.get_role(role)
    if not r:
        raise HTTPException(status_code=404, detail="Role not found")
    return {"status": "ok", "role": r.to_dict()}


# Safeguards endpoints
@router.get("/ethics/safeguards")
async def list_safeguards(request: Request):
    """List ethical safeguards"""
    safeguards = ethical_catalog.list_safeguards()
    return {"status": "ok", "safeguards": [s.to_dict() for s in safeguards]}


@router.get("/ethics/safeguards/{safeguard_id}")
async def get_safeguard(safeguard_id: str, request: Request):
    """Get safeguard details"""
    s = ethical_catalog.get_safeguard(safeguard_id)
    if not s:
        raise HTTPException(status_code=404, detail="Safeguard not found")
    return {"status": "ok", "safeguard": s.to_dict()}


# Red Flag endpoints
@router.post("/ethics/red-flags/detect")
async def detect_red_flag(payload: DetectRedFlagRequest, request: Request):
    """Detect and record a red flag"""
    try:
        flag_type = RedFlagType(payload.flag_type)
        flag = red_flag_monitor.detect_flag(
            flag_type=flag_type,
            agent_id=payload.agent_id,
            description=payload.description,
            severity=payload.severity,
        )
        return {"status": "ok", "flag": flag.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ethics/red-flags/update")
async def update_red_flag(payload: UpdateRedFlagRequest, request: Request):
    """Update red flag status"""
    flag = red_flag_monitor.update_flag_status(
        flag_id=payload.flag_id,
        status=payload.status,
        enforcement_action=payload.enforcement_action,
    )
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    return {"status": "ok", "flag": flag.to_dict()}


@router.get("/ethics/red-flags/{flag_id}")
async def get_red_flag(flag_id: str, request: Request):
    """Get red flag details"""
    flag = red_flag_monitor.get_flag(flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    return {"status": "ok", "flag": flag.to_dict()}


@router.get("/ethics/red-flags")
async def list_red_flags(
    agent_id: Optional[str] = None,
    status: Optional[str] = None,
    flag_type: Optional[str] = None,
    request: Request = None,
):
    """List red flags"""
    flags = red_flag_monitor.list_flags(agent_id, status, flag_type)
    return {"status": "ok", "flags": [f.to_dict() for f in flags]}


@router.get("/ethics/enforcement-workflow")
async def get_enforcement_workflow(request: Request):
    """Get the enforcement workflow"""
    return {"status": "ok", "workflow": red_flag_monitor.get_enforcement_workflow()}


# Certification endpoints
@router.post("/ethics/certifications/issue")
async def issue_certification(payload: IssueCertificationRequest, request: Request):
    """Issue an ethical certification"""
    cert = certification_manager.issue_certification(
        agent_id=payload.agent_id,
        certification_type=payload.certification_type,
        issued_by=payload.issued_by,
        valid_days=payload.valid_days,
        audit_summary=payload.audit_summary,
    )
    return {"status": "ok", "certification": cert.to_dict()}


@router.get("/ethics/certifications/{certification_id}")
async def get_certification(certification_id: str, request: Request):
    """Get certification details"""
    cert = certification_manager.get_certification(certification_id)
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found")
    return {"status": "ok", "certification": cert.to_dict()}


@router.get("/ethics/certifications")
async def list_certifications(agent_id: Optional[str] = None, request: Request = None):
    """List certifications"""
    certs = certification_manager.list_certifications(agent_id)
    return {"status": "ok", "certifications": [c.to_dict() for c in certs]}


@router.get("/ethics/red-flag-types")
async def get_red_flag_types(request: Request):
    """Get red flag type definitions"""
    return {
        "status": "ok",
        "types": [t.value for t in RedFlagType],
        "descriptions": {
            "behavioral_deviation": "Sudden changes in pattern",
            "semantic_drift": "Cross-cluster misalignment",
            "governance_violation": "Unauthorized actions",
            "risk_escalation": "Operating outside trust tier",
            "procedural_failure": "Not following prescribed processes",
        },
    }


# ============== SECTION 37: AGENT ECONOMY INCENTIVE & PRICING ==============

from .agent_economy import (
    dynamic_pricing_engine, task_revenue_calculator,
    enterprise_billing_engine, sovereign_licensing_engine,
    PRICING_TIERS, REVENUE_STREAMS, INCENTIVE_LOOPS,
    PricingTier, EnterpriseBillingMode,
)


class CalculatePriceRequest(BaseModel):
    base_price: float
    quality_score: float
    trust_score: float
    semantic_risk_class: int
    demand_factor: float = 1.0
    complexity_multiplier: float = 1.0


class CalculateTaskRevenueRequest(BaseModel):
    agent_id: str
    task_complexity: float = 1.0
    trust_tier: str = "T3"


class CalculateWorkflowRevenueRequest(BaseModel):
    agent_ids: List[str]
    task_complexities: List[float]
    trust_tiers: List[str]


class CalculateSeatBillingRequest(BaseModel):
    enterprise_id: str
    agent_count: int
    seat_price: float = 1.0
    period: str = "monthly"


class CalculateUsageBillingRequest(BaseModel):
    enterprise_id: str
    agent_count: int
    dag_writes: int
    semantic_ops: int
    workflow_events: int
    governance_checks: int
    registry_anchorings: int
    period: str = "monthly"


class CalculateSovereignLicenseRequest(BaseModel):
    nation_name: str
    population_tier: str
    ministry_count: int = 5
    workflow_scale: float = 1.0


# Pricing Tiers endpoints
@router.get("/economy/pricing/tiers")
async def list_pricing_tiers(request: Request):
    """List pricing tier definitions"""
    return {"status": "ok", "tiers": [t.to_dict() for t in PRICING_TIERS.values()]}


@router.get("/economy/pricing/tiers/{tier}")
async def get_pricing_tier(tier: str, request: Request):
    """Get pricing tier details"""
    try:
        tier_enum = PricingTier(tier)
        tier_def = PRICING_TIERS.get(tier_enum)
        if not tier_def:
            raise HTTPException(status_code=404, detail="Tier not found")
        return {"status": "ok", "tier": tier_def.to_dict()}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tier")


# Dynamic Pricing endpoints
@router.post("/economy/pricing/calculate")
async def calculate_dynamic_price(payload: CalculatePriceRequest, request: Request):
    """Calculate dynamic agent price"""
    from .agent_economy import PricingFactors
    factors = PricingFactors(
        quality_score=payload.quality_score,
        trust_score=payload.trust_score,
        semantic_risk_class=payload.semantic_risk_class,
        demand_factor=payload.demand_factor,
        complexity_multiplier=payload.complexity_multiplier,
    )
    result = dynamic_pricing_engine.calculate_price(payload.base_price, factors)
    return {"status": "ok", "pricing": result}


# Revenue Streams endpoints
@router.get("/economy/revenue-streams")
async def list_revenue_streams(request: Request):
    """List creator revenue streams"""
    return {"status": "ok", "streams": [s.to_dict() for s in REVENUE_STREAMS]}


# Task Revenue endpoints
@router.post("/economy/revenue/task")
async def calculate_task_revenue(payload: CalculateTaskRevenueRequest, request: Request):
    """Calculate task-based revenue"""
    revenue = task_revenue_calculator.calculate_task_revenue(
        agent_id=payload.agent_id,
        task_complexity=payload.task_complexity,
        trust_tier=payload.trust_tier,
    )
    return {"status": "ok", "revenue": revenue.to_dict()}


@router.post("/economy/revenue/workflow")
async def calculate_workflow_revenue(payload: CalculateWorkflowRevenueRequest, request: Request):
    """Calculate workflow revenue"""
    result = task_revenue_calculator.calculate_workflow_revenue(
        agent_ids=payload.agent_ids,
        task_complexities=payload.task_complexities,
        trust_tiers=payload.trust_tiers,
    )
    return {"status": "ok", "revenue": result}


# Enterprise Billing endpoints
@router.post("/economy/billing/seat")
async def calculate_seat_billing(payload: CalculateSeatBillingRequest, request: Request):
    """Calculate agent seat-based billing"""
    bill = enterprise_billing_engine.calculate_seat_billing(
        enterprise_id=payload.enterprise_id,
        agent_count=payload.agent_count,
        seat_price=payload.seat_price,
        period=payload.period,
    )
    return {"status": "ok", "bill": bill.to_dict()}


@router.post("/economy/billing/usage")
async def calculate_usage_billing(payload: CalculateUsageBillingRequest, request: Request):
    """Calculate usage-based billing"""
    from .agent_economy import EnterpriseBillingConfig
    config = EnterpriseBillingConfig(billing_mode=EnterpriseBillingMode.USAGE_BASED)
    bill = enterprise_billing_engine.calculate_usage_billing(
        enterprise_id=payload.enterprise_id,
        agent_count=payload.agent_count,
        dag_writes=payload.dag_writes,
        semantic_ops=payload.semantic_ops,
        workflow_events=payload.workflow_events,
        governance_checks=payload.governance_checks,
        registry_anchorings=payload.registry_anchorings,
        config=config,
        period=payload.period,
    )
    return {"status": "ok", "bill": bill.to_dict()}


@router.get("/economy/billing/estimate/{agent_count}/{workflows_per_day}")
async def estimate_enterprise_cost(agent_count: int, workflows_per_day: int, request: Request):
    """Estimate monthly enterprise cost"""
    estimate = enterprise_billing_engine.estimate_enterprise_cost(agent_count, workflows_per_day)
    return {"status": "ok", "estimate": estimate}


@router.get("/economy/billing/modes")
async def get_billing_modes(request: Request):
    """Get enterprise billing mode definitions"""
    return {
        "status": "ok",
        "modes": [m.value for m in EnterpriseBillingMode],
        "descriptions": {
            "agent_seat": "Price per deployed agent per month",
            "usage_based": "Based on DAG writes, semantic processing, workflow events, etc.",
            "workflow_tier": "Enterprise pays per automation type",
            "marketplace_license": "Bulk purchase of high-trust agents",
        },
    }


# Sovereign Licensing endpoints
@router.post("/economy/sovereign/license")
async def calculate_sovereign_license(payload: CalculateSovereignLicenseRequest, request: Request):
    """Calculate sovereign license pricing"""
    license = sovereign_licensing_engine.calculate_license(
        nation_name=payload.nation_name,
        population_tier=payload.population_tier,
        ministry_count=payload.ministry_count,
        workflow_scale=payload.workflow_scale,
    )
    return {"status": "ok", "license": license.to_dict()}


@router.get("/economy/sovereign/scenarios")
async def get_sovereign_pricing_scenarios(request: Request):
    """Get sovereign pricing scenarios"""
    scenarios = sovereign_licensing_engine.get_pricing_scenarios()
    return {"status": "ok", "scenarios": scenarios}


# Incentive Loops endpoints
@router.get("/economy/incentive-loops")
async def list_incentive_loops(request: Request):
    """List incentive loops"""
    return {"status": "ok", "loops": [l.to_dict() for l in INCENTIVE_LOOPS]}


@router.get("/economy/trust-multipliers")
async def get_trust_multipliers(request: Request):
    """Get trust-weighted revenue multipliers"""
    return {
        "status": "ok",
        "multipliers": {
            "T5": {"multiplier": 1.8, "description": "Platinum - Maximum earnings"},
            "T4": {"multiplier": 1.5, "description": "Gold - High earnings"},
            "T3": {"multiplier": 1.2, "description": "Silver - Standard earnings"},
            "T2": {"multiplier": 0.9, "description": "Bronze - Reduced earnings"},
            "T1": {"multiplier": 0.5, "description": "Restricted - Minimum earnings"},
        },
    }


# ============== SECTION 38: TECHNICAL SPECIFICATION ==============

from .technical_specification import (
    specification_catalog,
    CONFORMANCE_REQUIREMENTS, SYMBOL_GLOSSARY,
    PROTOCOL_VERSION, PROTOCOL_STATUS,
)


# Protocol Overview endpoints
@router.get("/specification/overview")
async def get_protocol_overview(request: Request):
    """Get DSID-P protocol overview"""
    return {"status": "ok", "overview": specification_catalog.get_protocol_overview()}


@router.get("/specification/full")
async def get_full_specification(request: Request):
    """Get full DSID-P specification document"""
    return {"status": "ok", "specification": specification_catalog.get_full_specification()}


# Layer Specification endpoints
@router.get("/specification/layers")
async def list_protocol_layers(request: Request):
    """List protocol layer specifications"""
    layers = specification_catalog.list_layers()
    return {"status": "ok", "layers": [l.to_dict() for l in layers]}


@router.get("/specification/layers/{layer}")
async def get_protocol_layer(layer: str, request: Request):
    """Get protocol layer specification"""
    l = specification_catalog.get_layer(layer)
    if not l:
        raise HTTPException(status_code=404, detail="Layer not found")
    return {"status": "ok", "layer": l.to_dict()}


# Subsystem Specification endpoints
@router.get("/specification/subsystems")
async def list_subsystems(request: Request):
    """List auxiliary subsystem specifications"""
    subsystems = specification_catalog.list_subsystems()
    return {"status": "ok", "subsystems": [s.to_dict() for s in subsystems]}


@router.get("/specification/subsystems/{subsystem}")
async def get_subsystem(subsystem: str, request: Request):
    """Get subsystem specification"""
    s = specification_catalog.get_subsystem(subsystem)
    if not s:
        raise HTTPException(status_code=404, detail="Subsystem not found")
    return {"status": "ok", "subsystem": s.to_dict()}


# Conformance & Glossary endpoints
@router.get("/specification/conformance")
async def get_conformance_requirements(request: Request):
    """Get conformance requirements"""
    return {"status": "ok", "requirements": CONFORMANCE_REQUIREMENTS}


@router.get("/specification/glossary")
async def get_symbol_glossary(request: Request):
    """Get symbol glossary"""
    return {"status": "ok", "glossary": SYMBOL_GLOSSARY}


@router.get("/specification/version")
async def get_protocol_version(request: Request):
    """Get protocol version information"""
    return {
        "status": "ok",
        "version": PROTOCOL_VERSION,
        "status_label": PROTOCOL_STATUS,
    }


# ============== SECTION 39: LEGAL & REGULATORY ALIGNMENT ==============

from .legal_regulatory import (
    compliance_catalog,
    COMPLIANCE_PRINCIPLES, EMBEDDED_RISK_CONTROLS,
)


# Framework Alignment endpoints
@router.get("/compliance/frameworks")
async def list_regulatory_frameworks(request: Request):
    """List regulatory framework alignments"""
    frameworks = compliance_catalog.list_frameworks()
    return {"status": "ok", "frameworks": [f.to_dict() for f in frameworks]}


@router.get("/compliance/frameworks/{framework}")
async def get_regulatory_framework(framework: str, request: Request):
    """Get regulatory framework alignment details"""
    f = compliance_catalog.get_framework(framework)
    if not f:
        raise HTTPException(status_code=404, detail="Framework not found")
    return {"status": "ok", "framework": f.to_dict()}


# Sector Compliance endpoints
@router.get("/compliance/sectors")
async def list_sector_compliance(request: Request):
    """List sector-specific compliance requirements"""
    sectors = compliance_catalog.list_sectors()
    return {"status": "ok", "sectors": [s.to_dict() for s in sectors]}


@router.get("/compliance/sectors/{sector}")
async def get_sector_compliance(sector: str, request: Request):
    """Get sector compliance details"""
    s = compliance_catalog.get_sector(sector)
    if not s:
        raise HTTPException(status_code=404, detail="Sector not found")
    return {"status": "ok", "sector": s.to_dict()}


# Legal Structures endpoints
@router.get("/compliance/legal-structures")
async def list_legal_structures(request: Request):
    """List legal structures enabled by DSID-P"""
    structures = compliance_catalog.list_legal_structures()
    return {"status": "ok", "structures": [s.to_dict() for s in structures]}


@router.get("/compliance/legal-structures/{structure_id}")
async def get_legal_structure(structure_id: str, request: Request):
    """Get legal structure details"""
    s = compliance_catalog.get_legal_structure(structure_id)
    if not s:
        raise HTTPException(status_code=404, detail="Legal structure not found")
    return {"status": "ok", "structure": s.to_dict()}


# Compliance Principles endpoints
@router.get("/compliance/principles")
async def get_compliance_principles(request: Request):
    """Get compliance-by-design principles"""
    return {"status": "ok", "principles": COMPLIANCE_PRINCIPLES}


@router.get("/compliance/risk-controls")
async def get_embedded_risk_controls(request: Request):
    """Get embedded risk controls"""
    return {"status": "ok", "controls": EMBEDDED_RISK_CONTROLS}


# ============== SECTION 40: SECURITY ARCHITECTURE ==============

from .security_architecture import (
    security_catalog,
    INCIDENT_RESPONSE_PROCEDURE, HARDENING_DEFAULTS,
    SUPERVISOR_AGENT_CAPABILITIES,
)


# Security Layer endpoints
@router.get("/security/layers")
async def list_security_layers(request: Request):
    """List security layer definitions"""
    layers = security_catalog.list_layers()
    return {"status": "ok", "layers": [l.to_dict() for l in layers]}


@router.get("/security/layers/{layer}")
async def get_security_layer(layer: str, request: Request):
    """Get security layer details"""
    l = security_catalog.get_layer(layer)
    if not l:
        raise HTTPException(status_code=404, detail="Security layer not found")
    return {"status": "ok", "layer": l.to_dict()}


# Threat endpoints
@router.get("/security/threats")
async def list_security_threats(category: Optional[str] = None, request: Request = None):
    """List security threats"""
    threats = security_catalog.list_threats(category)
    return {"status": "ok", "threats": [t.to_dict() for t in threats]}


@router.get("/security/threats/{threat_id}")
async def get_security_threat(threat_id: str, request: Request):
    """Get security threat details"""
    t = security_catalog.get_threat(threat_id)
    if not t:
        raise HTTPException(status_code=404, detail="Threat not found")
    return {"status": "ok", "threat": t.to_dict()}


# Security Control endpoints
@router.get("/security/controls")
async def list_security_controls(control_type: Optional[str] = None, request: Request = None):
    """List security controls"""
    controls = security_catalog.list_controls(control_type)
    return {"status": "ok", "controls": [c.to_dict() for c in controls]}


@router.get("/security/controls/{control_id}")
async def get_security_control(control_id: str, request: Request):
    """Get security control details"""
    c = security_catalog.get_control(control_id)
    if not c:
        raise HTTPException(status_code=404, detail="Control not found")
    return {"status": "ok", "control": c.to_dict()}


# Incident Response endpoints
@router.get("/security/incident-response")
async def get_incident_response_procedure(request: Request):
    """Get incident response procedure"""
    return {"status": "ok", "procedure": [p.to_dict() for p in INCIDENT_RESPONSE_PROCEDURE]}


# Hardening endpoints
@router.get("/security/hardening")
async def get_hardening_defaults(request: Request):
    """Get security hardening defaults"""
    return {"status": "ok", "defaults": HARDENING_DEFAULTS}


# Supervisor Agent endpoints
@router.get("/security/supervisor-capabilities")
async def get_supervisor_capabilities(request: Request):
    """Get supervisor agent security capabilities"""
    return {"status": "ok", "capabilities": SUPERVISOR_AGENT_CAPABILITIES}


# ============== SECTION 41: IMPLEMENTATION GUIDE ==============

from .implementation_guide import (
    implementation_catalog,
    ENGINEERING_BEST_PRACTICES, MONITORING_METRICS,
    IMPLEMENTATION_RISKS, DEVELOPMENT_TIMELINE,
)


# Implementation Step endpoints
@router.get("/implementation/steps")
async def list_implementation_steps(request: Request):
    """List implementation steps"""
    steps = implementation_catalog.list_steps()
    return {"status": "ok", "steps": [s.to_dict() for s in steps]}


@router.get("/implementation/steps/{step}")
async def get_implementation_step(step: str, request: Request):
    """Get implementation step details"""
    s = implementation_catalog.get_step(step)
    if not s:
        raise HTTPException(status_code=404, detail="Step not found")
    return {"status": "ok", "step": s.to_dict()}


# Deployment Model endpoints
@router.get("/implementation/deployment-models")
async def list_deployment_models(request: Request):
    """List deployment model definitions"""
    models = implementation_catalog.list_deployment_models()
    return {"status": "ok", "models": [m.to_dict() for m in models]}


@router.get("/implementation/deployment-models/{model}")
async def get_deployment_model(model: str, request: Request):
    """Get deployment model details"""
    m = implementation_catalog.get_deployment_model(model)
    if not m:
        raise HTTPException(status_code=404, detail="Deployment model not found")
    return {"status": "ok", "model": m.to_dict()}


# Technology Stack endpoints
@router.get("/implementation/tech-stack")
async def list_tech_stack(request: Request):
    """List technology stack recommendations"""
    tech = implementation_catalog.list_tech_stack()
    return {"status": "ok", "tech_stack": [t.to_dict() for t in tech]}


@router.get("/implementation/tech-stack/{category}")
async def get_tech_recommendation(category: str, request: Request):
    """Get technology recommendation for category"""
    t = implementation_catalog.get_tech_recommendation(category)
    if not t:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"status": "ok", "recommendation": t.to_dict()}


# Best Practices endpoints
@router.get("/implementation/best-practices")
async def get_best_practices(request: Request):
    """Get engineering best practices"""
    return {"status": "ok", "best_practices": ENGINEERING_BEST_PRACTICES}


# Monitoring endpoints
@router.get("/implementation/monitoring-metrics")
async def get_monitoring_metrics(request: Request):
    """Get monitoring metrics to track"""
    return {"status": "ok", "metrics": MONITORING_METRICS}


# Risks endpoints
@router.get("/implementation/risks")
async def get_implementation_risks(request: Request):
    """Get implementation risks and mitigations"""
    return {"status": "ok", "risks": IMPLEMENTATION_RISKS}


# Timeline endpoints
@router.get("/implementation/timeline")
async def get_development_timeline(request: Request):
    """Get development timeline"""
    return {"status": "ok", "timeline": DEVELOPMENT_TIMELINE}


# ============== SECTION 42: STRATEGIC PARTNERSHIPS ==============

from .strategic_partnerships import (
    ecosystem_catalog,
    ENTERPRISE_FLYWHEEL, DEVELOPER_ECOSYSTEM_REQUIREMENTS,
    COMMUNITY_GROWTH_INITIATIVES, INTERNATIONAL_ALLIANCE_TARGETS,
    PARTNER_QUALIFICATION_CRITERIA, ECOSYSTEM_RISKS, EXPANSION_TIMELINE,
)


# Partner Categories endpoints
@router.get("/partnerships/categories")
async def list_partner_categories(request: Request):
    """List partner categories"""
    categories = ecosystem_catalog.list_partner_categories()
    return {"status": "ok", "categories": [c.to_dict() for c in categories]}


# Partnership Models endpoints
@router.get("/partnerships/models")
async def list_partnership_models(request: Request):
    """List partnership models"""
    models = ecosystem_catalog.list_partnership_models()
    return {"status": "ok", "models": [m.to_dict() for m in models]}


# Government Models endpoints
@router.get("/partnerships/government-models")
async def list_government_models(request: Request):
    """List government partnership models"""
    models = ecosystem_catalog.list_government_models()
    return {"status": "ok", "models": [m.to_dict() for m in models]}


# Target Industries endpoints
@router.get("/partnerships/target-industries")
async def list_target_industries(request: Request):
    """List target industries for early adoption"""
    industries = ecosystem_catalog.list_target_industries()
    return {"status": "ok", "industries": [i.to_dict() for i in industries]}


# Ecosystem Flywheel endpoints
@router.get("/partnerships/flywheel")
async def get_enterprise_flywheel(request: Request):
    """Get enterprise ecosystem flywheel"""
    return {"status": "ok", "flywheel": ENTERPRISE_FLYWHEEL}


# Developer Ecosystem endpoints
@router.get("/partnerships/developer-ecosystem")
async def get_developer_ecosystem(request: Request):
    """Get developer ecosystem requirements"""
    return {
        "status": "ok",
        "requirements": DEVELOPER_ECOSYSTEM_REQUIREMENTS,
        "community_initiatives": COMMUNITY_GROWTH_INITIATIVES,
    }


# International Alliances endpoints
@router.get("/partnerships/international-alliances")
async def get_international_alliances(request: Request):
    """Get international alliance targets"""
    return {"status": "ok", "alliances": INTERNATIONAL_ALLIANCE_TARGETS}


# Partner Qualification endpoints
@router.get("/partnerships/qualification-criteria")
async def get_qualification_criteria(request: Request):
    """Get partner qualification criteria"""
    return {"status": "ok", "criteria": PARTNER_QUALIFICATION_CRITERIA}


# Ecosystem Risks endpoints
@router.get("/partnerships/risks")
async def get_ecosystem_risks(request: Request):
    """Get ecosystem risks and mitigations"""
    return {"status": "ok", "risks": ECOSYSTEM_RISKS}


# Expansion Timeline endpoints
@router.get("/partnerships/expansion-timeline")
async def get_expansion_timeline(request: Request):
    """Get ecosystem expansion timeline"""
    return {"status": "ok", "timeline": EXPANSION_TIMELINE}


# ============== SECTION 43: COMMERCIALIZATION ==============

from .commercialization import (
    commercialization_catalog,
    ECONOMIC_FLYWHEEL, FLYWHEEL_COMPARISONS,
    MARKET_POSITIONING, PRICING_STRATEGY,
    CUSTOMER_ACQUISITION, REVENUE_PROJECTIONS,
    COMMERCIALIZATION_RISKS,
)


# Revenue Streams endpoints
@router.get("/commercialization/revenue-streams")
async def list_revenue_streams(request: Request):
    """List revenue streams"""
    streams = commercialization_catalog.list_revenue_streams()
    return {"status": "ok", "streams": [s.to_dict() for s in streams]}


# Licensing Tiers endpoints
@router.get("/commercialization/licensing-tiers")
async def list_licensing_tiers(request: Request):
    """List enterprise licensing tiers"""
    tiers = commercialization_catalog.list_licensing_tiers()
    return {"status": "ok", "tiers": [t.to_dict() for t in tiers]}


# Usage Pricing endpoints
@router.get("/commercialization/usage-pricing")
async def list_usage_pricing(request: Request):
    """List usage-based pricing"""
    prices = commercialization_catalog.list_usage_prices()
    return {"status": "ok", "prices": [p.to_dict() for p in prices]}


# Marketplace Rates endpoints
@router.get("/commercialization/marketplace-rates")
async def list_marketplace_rates(request: Request):
    """List marketplace take rates"""
    rates = commercialization_catalog.list_marketplace_rates()
    return {"status": "ok", "rates": [r.to_dict() for r in rates]}


# Enterprise Solutions endpoints
@router.get("/commercialization/enterprise-solutions")
async def list_enterprise_solutions(request: Request):
    """List enterprise add-on solutions"""
    solutions = commercialization_catalog.list_enterprise_solutions()
    return {"status": "ok", "solutions": [s.to_dict() for s in solutions]}


# Government Pricing endpoints
@router.get("/commercialization/government-pricing")
async def list_government_pricing(request: Request):
    """List government contract pricing"""
    pricing = commercialization_catalog.list_government_pricing()
    return {"status": "ok", "pricing": [p.to_dict() for p in pricing]}


# Economic Flywheel endpoints
@router.get("/commercialization/flywheel")
async def get_economic_flywheel(request: Request):
    """Get economic flywheel model"""
    return {
        "status": "ok",
        "flywheel": ECONOMIC_FLYWHEEL,
        "comparisons": FLYWHEEL_COMPARISONS,
    }


# Market Positioning endpoints
@router.get("/commercialization/positioning")
async def get_market_positioning(request: Request):
    """Get market positioning"""
    return {"status": "ok", "positioning": MARKET_POSITIONING}


# Pricing Strategy endpoints
@router.get("/commercialization/pricing-strategy")
async def get_pricing_strategy(request: Request):
    """Get pricing strategy"""
    return {"status": "ok", "strategy": PRICING_STRATEGY}


# Customer Acquisition endpoints
@router.get("/commercialization/customer-acquisition")
async def get_customer_acquisition(request: Request):
    """Get customer acquisition strategy"""
    return {"status": "ok", "acquisition": CUSTOMER_ACQUISITION}


# Revenue Projections endpoints
@router.get("/commercialization/revenue-projections")
async def get_revenue_projections(request: Request):
    """Get revenue projections"""
    return {"status": "ok", "projections": REVENUE_PROJECTIONS}


# Commercialization Risks endpoints
@router.get("/commercialization/risks")
async def get_commercialization_risks(request: Request):
    """Get commercialization risks and mitigations"""
    return {"status": "ok", "risks": COMMERCIALIZATION_RISKS}


# ============== SECTION 44: STANDARDS POSITIONING ==============

from .standards_positioning import (
    standards_catalog,
    DSIDP_PROTOCOL_CLASS, GLOBAL_ADOPTION_MAP,
    STANDARDIZATION_MESSAGES,
)


# Standards Body Alignments endpoints
@router.get("/standards/body-alignments")
async def list_standards_body_alignments(request: Request):
    """List standards body alignments"""
    alignments = standards_catalog.list_body_alignments()
    return {"status": "ok", "alignments": [a.to_dict() for a in alignments]}


# Standards Gaps endpoints
@router.get("/standards/gaps")
async def list_standards_gaps(request: Request):
    """List standards gaps DSID-P fills"""
    gaps = standards_catalog.list_gaps()
    return {"status": "ok", "gaps": [g.to_dict() for g in gaps]}


# Standards Domains endpoints
@router.get("/standards/domains")
async def list_standards_domains(request: Request):
    """List standards domains"""
    domains = standards_catalog.list_domains()
    return {"status": "ok", "domains": [d.to_dict() for d in domains]}


# Standardization Phases endpoints
@router.get("/standards/phases")
async def list_standardization_phases(request: Request):
    """List standardization pathway phases"""
    phases = standards_catalog.list_phases()
    return {"status": "ok", "phases": [p.to_dict() for p in phases]}


# Protocol Class endpoints
@router.get("/standards/protocol-class")
async def get_protocol_class(request: Request):
    """Get DSID-P protocol class definition"""
    return {"status": "ok", "protocol_class": DSIDP_PROTOCOL_CLASS}


# Global Adoption Map endpoints
@router.get("/standards/adoption-map")
async def get_global_adoption_map(request: Request):
    """Get global adoption map"""
    return {"status": "ok", "adoption_map": GLOBAL_ADOPTION_MAP}


# Standardization Messages endpoints
@router.get("/standards/key-messages")
async def get_standardization_messages(request: Request):
    """Get key standardization messages"""
    return {"status": "ok", "messages": STANDARDIZATION_MESSAGES}


# ============== SECTION 46: SCALING & PERFORMANCE ==============

from .scaling_performance import (
    scaling_catalog,
    HA_DR_ARCHITECTURE, NATIONAL_SCALE_BLUEPRINT,
    PERFORMANCE_BENCHMARKS, CAPACITY_PLANNING_METRICS,
    CAPACITY_FORECASTS,
)


# Scaling Surfaces endpoints
@router.get("/scaling/surfaces")
async def list_scaling_surfaces(request: Request):
    """List scaling surfaces"""
    surfaces = scaling_catalog.list_surfaces()
    return {"status": "ok", "surfaces": [s.to_dict() for s in surfaces]}


@router.get("/scaling/surfaces/{surface}")
async def get_scaling_surface(surface: str, request: Request):
    """Get scaling surface details"""
    s = scaling_catalog.get_surface(surface)
    if not s:
        raise HTTPException(status_code=404, detail="Scaling surface not found")
    return {"status": "ok", "surface": s.to_dict()}


# Throughput Targets endpoints
@router.get("/scaling/throughput-targets")
async def list_throughput_targets(request: Request):
    """List throughput targets by deployment scale"""
    targets = scaling_catalog.list_throughput_targets()
    return {"status": "ok", "targets": [t.to_dict() for t in targets]}


# Latency Targets endpoints
@router.get("/scaling/latency-targets")
async def list_latency_targets(request: Request):
    """List latency targets for operations"""
    targets = scaling_catalog.list_latency_targets()
    return {"status": "ok", "targets": [t.to_dict() for t in targets]}


# Optimization Strategies endpoints
@router.get("/scaling/optimization-strategies")
async def list_optimization_strategies(request: Request):
    """List system-wide optimization strategies"""
    strategies = scaling_catalog.list_optimization_strategies()
    return {"status": "ok", "strategies": [s.to_dict() for s in strategies]}


# HA/DR Architecture endpoints
@router.get("/scaling/ha-dr")
async def get_ha_dr_architecture(request: Request):
    """Get HA/DR architecture"""
    return {"status": "ok", "architecture": HA_DR_ARCHITECTURE}


# National Scale Blueprint endpoints
@router.get("/scaling/national-blueprint")
async def get_national_scale_blueprint(request: Request):
    """Get national-scale deployment blueprint"""
    return {"status": "ok", "blueprint": NATIONAL_SCALE_BLUEPRINT}


# Performance Benchmarks endpoints
@router.get("/scaling/benchmarks")
async def get_performance_benchmarks(request: Request):
    """Get performance benchmarks"""
    return {"status": "ok", "benchmarks": PERFORMANCE_BENCHMARKS}


# Capacity Planning endpoints
@router.get("/scaling/capacity-planning")
async def get_capacity_planning(request: Request):
    """Get capacity planning metrics and forecasts"""
    return {
        "status": "ok",
        "metrics": CAPACITY_PLANNING_METRICS,
        "forecasts": CAPACITY_FORECASTS,
    }



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
