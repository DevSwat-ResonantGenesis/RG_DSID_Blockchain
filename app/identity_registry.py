"""
Blockchain Identity Registry - Layer 4

Registers crypto identities on the internal blockchain.
Provides identity verification and lookup.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .db import Base, get_session
from fastapi import Depends

router = APIRouter(prefix="/identity", tags=["identity"])


# ============================================
# DATABASE MODEL
# ============================================

class BlockchainIdentity(Base):
    """Blockchain identity record."""
    __tablename__ = "blockchain_identities"
    
    user_id = Column(PGUUID(as_uuid=True), primary_key=True, index=True)
    crypto_hash = Column(String(64), unique=True, index=True, nullable=False)
    user_hash = Column(String(64), unique=True, index=True, nullable=False)
    universe_id = Column(String(32), index=True, nullable=False)
    email = Column(String(255), nullable=False)
    
    registered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_crypto_hash', 'crypto_hash'),
        Index('idx_user_hash', 'user_hash'),
        Index('idx_universe_id', 'universe_id'),
    )


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class IdentityRegistrationRequest(BaseModel):
    user_id: str
    crypto_hash: str
    user_hash: str
    universe_id: str
    email: str


class IdentityResponse(BaseModel):
    user_id: str
    crypto_hash: str
    user_hash: str
    universe_id: str
    registered_at: str


# ============================================
# ENDPOINTS
# ============================================

@router.post("/register", response_model=IdentityResponse)
async def register_identity(
    request: IdentityRegistrationRequest,
    db: AsyncSession = Depends(get_session),
):
    """
    Register a crypto identity on the blockchain.
    
    This is called during user registration to create a permanent
    record of the user's cryptographic identity.
    """
    try:
        # Check if already registered
        result = await db.execute(
            select(BlockchainIdentity).where(
                BlockchainIdentity.user_id == UUID(request.user_id)
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Already registered, return existing
            return IdentityResponse(
                user_id=str(existing.user_id),
                crypto_hash=existing.crypto_hash,
                user_hash=existing.user_hash,
                universe_id=existing.universe_id,
                registered_at=existing.registered_at.isoformat(),
            )
        
        # Create new identity record
        identity = BlockchainIdentity(
            user_id=UUID(request.user_id),
            crypto_hash=request.crypto_hash,
            user_hash=request.user_hash,
            universe_id=request.universe_id,
            email=request.email,
        )
        
        db.add(identity)
        await db.commit()
        await db.refresh(identity)
        
        return IdentityResponse(
            user_id=str(identity.user_id),
            crypto_hash=identity.crypto_hash,
            user_hash=identity.user_hash,
            universe_id=identity.universe_id,
            registered_at=identity.registered_at.isoformat(),
        )
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Identity registration failed: {str(e)}")


@router.get("/lookup/{user_hash}", response_model=IdentityResponse)
async def lookup_identity(
    user_hash: str,
    db: AsyncSession = Depends(get_session),
):
    """
    Look up an identity by user_hash.
    """
    result = await db.execute(
        select(BlockchainIdentity).where(
            BlockchainIdentity.user_hash == user_hash
        )
    )
    identity = result.scalar_one_or_none()
    
    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")
    
    return IdentityResponse(
        user_id=str(identity.user_id),
        crypto_hash=identity.crypto_hash,
        user_hash=identity.user_hash,
        universe_id=identity.universe_id,
        registered_at=identity.registered_at.isoformat(),
    )


@router.get("/verify/{crypto_hash}")
async def verify_identity(
    crypto_hash: str,
    db: AsyncSession = Depends(get_session),
):
    """
    Verify if a crypto_hash is registered.
    """
    result = await db.execute(
        select(BlockchainIdentity).where(
            BlockchainIdentity.crypto_hash == crypto_hash
        )
    )
    identity = result.scalar_one_or_none()
    
    return {
        "verified": identity is not None,
        "user_hash": identity.user_hash if identity else None,
    }
