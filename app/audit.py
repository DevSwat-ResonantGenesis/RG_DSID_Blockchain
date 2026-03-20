"""Audit chain for compliance and tracking."""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AuditEntry, Block
from .config import settings

logger = logging.getLogger(__name__)


class AuditChainManager:
    """Manages the audit chain for compliance tracking."""

    async def get_latest_entry(
        self,
        db_session: AsyncSession,
    ) -> Optional[AuditEntry]:
        """Get the latest audit entry."""
        result = await db_session.execute(
            select(AuditEntry).order_by(AuditEntry.sequence_number.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    def compute_entry_hash(
        self,
        sequence_number: int,
        previous_hash: str,
        event_type: str,
        event_data: Dict[str, Any],
        timestamp: datetime,
    ) -> str:
        """Compute hash for an audit entry."""
        content = {
            "sequence": sequence_number,
            "previous": previous_hash,
            "event_type": event_type,
            "data": event_data,
            "timestamp": timestamp.isoformat(),
        }
        return hashlib.sha256(
            json.dumps(content, sort_keys=True).encode()
        ).hexdigest()

    async def create_entry(
        self,
        event_type: str,
        event_category: str,
        action: str,
        actor_dsid: Optional[str] = None,
        actor_ip: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        target_dsid: Optional[str] = None,
        description: Optional[str] = None,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        changes: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        compliance_tags: Optional[List[str]] = None,
        db_session: AsyncSession = None,
    ) -> AuditEntry:
        """Create a new audit entry."""
        # Get previous entry
        latest = await self.get_latest_entry(db_session)
        
        sequence_number = (latest.sequence_number + 1) if latest else 0
        previous_hash = latest.entry_hash if latest else "0" * 64
        
        # Compute state hashes
        before_state_hash = None
        after_state_hash = None
        if before_state:
            before_state_hash = hashlib.sha256(
                json.dumps(before_state, sort_keys=True).encode()
            ).hexdigest()
        if after_state:
            after_state_hash = hashlib.sha256(
                json.dumps(after_state, sort_keys=True).encode()
            ).hexdigest()
        
        timestamp = datetime.utcnow()
        
        # Compute entry hash
        event_data = {
            "category": event_category,
            "action": action,
            "actor": actor_dsid,
            "target_type": target_type,
            "target_id": str(target_id) if target_id else None,
            "success": success,
        }
        entry_hash = self.compute_entry_hash(
            sequence_number, previous_hash, event_type, event_data, timestamp
        )
        
        entry = AuditEntry(
            entry_hash=entry_hash,
            sequence_number=sequence_number,
            previous_entry_hash=previous_hash,
            event_type=event_type,
            event_category=event_category,
            actor_dsid=actor_dsid,
            actor_ip=actor_ip,
            target_type=target_type,
            target_id=target_id,
            target_dsid=target_dsid,
            action=action,
            description=description,
            before_state_hash=before_state_hash,
            after_state_hash=after_state_hash,
            changes=changes,
            success=success,
            error_message=error_message,
            compliance_tags=compliance_tags,
            timestamp=timestamp,
        )
        db_session.add(entry)
        await db_session.commit()
        await db_session.refresh(entry)

        # Record audit entry as a blockchain transaction
        try:
            from .chain import transaction_manager
            await transaction_manager.create_transaction(
                tx_type="audit_entry",
                payload={
                    "entry_hash": entry.entry_hash,
                    "sequence_number": entry.sequence_number,
                    "event_type": event_type,
                    "event_category": event_category,
                    "action": action,
                    "actor_dsid": actor_dsid,
                    "target_type": target_type,
                    "target_id": str(target_id) if target_id else None,
                    "success": success,
                    "compliance_tags": compliance_tags or [],
                },
                from_dsid=actor_dsid,
                to_dsid=target_dsid,
                db_session=db_session,
            )
            logger.info("Blockchain TX created for audit entry #%d", entry.sequence_number)
        except Exception as e:
            logger.warning("Failed to create blockchain TX for audit #%d: %s", entry.sequence_number, e)

        return entry

    async def get_entry(
        self,
        entry_hash: str,
        db_session: AsyncSession,
    ) -> Optional[AuditEntry]:
        """Get an audit entry by hash."""
        result = await db_session.execute(
            select(AuditEntry).where(AuditEntry.entry_hash == entry_hash)
        )
        return result.scalar_one_or_none()

    async def get_entries_by_actor(
        self,
        actor_dsid: str,
        limit: int = 100,
        offset: int = 0,
        db_session: AsyncSession = None,
    ) -> List[AuditEntry]:
        """Get audit entries for an actor."""
        result = await db_session.execute(
            select(AuditEntry)
            .where(AuditEntry.actor_dsid == actor_dsid)
            .order_by(AuditEntry.sequence_number.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_entries_by_target(
        self,
        target_type: str,
        target_id: str,
        limit: int = 100,
        db_session: AsyncSession = None,
    ) -> List[AuditEntry]:
        """Get audit entries for a target."""
        result = await db_session.execute(
            select(AuditEntry)
            .where(AuditEntry.target_type == target_type)
            .where(AuditEntry.target_id == target_id)
            .order_by(AuditEntry.sequence_number.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_entries_by_category(
        self,
        category: str,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        limit: int = 100,
        db_session: AsyncSession = None,
    ) -> List[AuditEntry]:
        """Get audit entries by category."""
        stmt = select(AuditEntry).where(AuditEntry.event_category == category)
        
        if from_time:
            stmt = stmt.where(AuditEntry.timestamp >= from_time)
        if to_time:
            stmt = stmt.where(AuditEntry.timestamp <= to_time)
        
        stmt = stmt.order_by(AuditEntry.sequence_number.desc()).limit(limit)
        
        result = await db_session.execute(stmt)
        return list(result.scalars().all())

    async def get_entries_by_compliance_tag(
        self,
        tag: str,
        limit: int = 100,
        db_session: AsyncSession = None,
    ) -> List[AuditEntry]:
        """Get audit entries with a compliance tag."""
        result = await db_session.execute(
            select(AuditEntry)
            .where(AuditEntry.compliance_tags.contains([tag]))
            .order_by(AuditEntry.sequence_number.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def verify_chain(
        self,
        from_sequence: int = 0,
        to_sequence: Optional[int] = None,
        db_session: AsyncSession = None,
    ) -> Dict[str, Any]:
        """Verify audit chain integrity."""
        latest = await self.get_latest_entry(db_session)
        if not latest:
            return {"valid": True, "entries_checked": 0}
        
        to_sequence = to_sequence or latest.sequence_number
        
        errors = []
        entries_checked = 0
        
        previous_hash = None
        for seq in range(from_sequence, to_sequence + 1):
            result = await db_session.execute(
                select(AuditEntry).where(AuditEntry.sequence_number == seq)
            )
            entry = result.scalar_one_or_none()
            
            if not entry:
                errors.append(f"Missing entry at sequence {seq}")
                continue
            
            entries_checked += 1
            
            # Verify chain linkage
            if previous_hash and entry.previous_entry_hash != previous_hash:
                errors.append(f"Sequence {seq}: Invalid previous hash")
            
            previous_hash = entry.entry_hash
        
        return {
            "valid": len(errors) == 0,
            "entries_checked": entries_checked,
            "errors": errors,
        }

    async def get_audit_stats(
        self,
        db_session: AsyncSession,
    ) -> Dict[str, Any]:
        """Get audit chain statistics."""
        latest = await self.get_latest_entry(db_session)
        
        # Count by category
        category_counts = await db_session.execute(
            select(AuditEntry.event_category, func.count(AuditEntry.id))
            .group_by(AuditEntry.event_category)
        )
        
        # Count by event type
        type_counts = await db_session.execute(
            select(AuditEntry.event_type, func.count(AuditEntry.id))
            .group_by(AuditEntry.event_type)
        )
        
        # Success rate
        total_count = await db_session.execute(
            select(func.count(AuditEntry.id))
        )
        success_count = await db_session.execute(
            select(func.count(AuditEntry.id)).where(AuditEntry.success == True)
        )
        
        total = total_count.scalar() or 0
        successes = success_count.scalar() or 0
        
        return {
            "total_entries": total,
            "latest_sequence": latest.sequence_number if latest else -1,
            "success_rate": (successes / total * 100) if total > 0 else 100,
            "by_category": dict(category_counts.all()),
            "by_event_type": dict(type_counts.all()),
        }

    async def export_audit_log(
        self,
        from_sequence: int,
        to_sequence: int,
        db_session: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Export audit entries for compliance reporting."""
        result = await db_session.execute(
            select(AuditEntry)
            .where(AuditEntry.sequence_number >= from_sequence)
            .where(AuditEntry.sequence_number <= to_sequence)
            .order_by(AuditEntry.sequence_number)
        )
        entries = result.scalars().all()
        
        return [
            {
                "sequence": e.sequence_number,
                "hash": e.entry_hash,
                "previous_hash": e.previous_entry_hash,
                "event_type": e.event_type,
                "category": e.event_category,
                "action": e.action,
                "actor": e.actor_dsid,
                "target_type": e.target_type,
                "target_id": str(e.target_id) if e.target_id else None,
                "success": e.success,
                "timestamp": e.timestamp.isoformat(),
                "compliance_tags": e.compliance_tags,
            }
            for e in entries
        ]


class ComplianceReporter:
    """Generates compliance reports from audit data."""

    async def generate_gdpr_report(
        self,
        user_dsid: str,
        db_session: AsyncSession,
    ) -> Dict[str, Any]:
        """Generate GDPR compliance report for a user."""
        # Get all entries related to user
        entries = await audit_manager.get_entries_by_actor(
            user_dsid, limit=1000, db_session=db_session
        )
        
        # Also get entries where user is target
        target_entries = await db_session.execute(
            select(AuditEntry)
            .where(AuditEntry.target_dsid == user_dsid)
            .order_by(AuditEntry.sequence_number.desc())
            .limit(1000)
        )
        
        all_entries = entries + list(target_entries.scalars().all())
        
        # Categorize
        data_access = [e for e in all_entries if e.event_type == "access"]
        data_modifications = [e for e in all_entries if e.event_type in ("create", "update", "delete")]
        data_exports = [e for e in all_entries if e.event_type == "export"]
        
        return {
            "user_dsid": user_dsid,
            "report_generated": datetime.utcnow().isoformat(),
            "total_events": len(all_entries),
            "data_access_count": len(data_access),
            "data_modification_count": len(data_modifications),
            "data_export_count": len(data_exports),
            "first_activity": min(e.timestamp for e in all_entries).isoformat() if all_entries else None,
            "last_activity": max(e.timestamp for e in all_entries).isoformat() if all_entries else None,
        }

    async def generate_soc2_report(
        self,
        from_date: datetime,
        to_date: datetime,
        db_session: AsyncSession,
    ) -> Dict[str, Any]:
        """Generate SOC2 compliance report."""
        # Security events
        security_entries = await audit_manager.get_entries_by_category(
            "security", from_time=from_date, to_time=to_date, limit=10000, db_session=db_session
        )
        
        # Failed operations
        failed_result = await db_session.execute(
            select(AuditEntry)
            .where(AuditEntry.success == False)
            .where(AuditEntry.timestamp >= from_date)
            .where(AuditEntry.timestamp <= to_date)
        )
        failed_entries = failed_result.scalars().all()
        
        # Access control events
        access_entries = await db_session.execute(
            select(AuditEntry)
            .where(AuditEntry.event_type.in_(["login", "logout", "access_denied"]))
            .where(AuditEntry.timestamp >= from_date)
            .where(AuditEntry.timestamp <= to_date)
        )
        
        return {
            "report_period": {
                "from": from_date.isoformat(),
                "to": to_date.isoformat(),
            },
            "security_events": len(security_entries),
            "failed_operations": len(list(failed_entries)),
            "access_control_events": len(list(access_entries.scalars().all())),
            "chain_integrity": await audit_manager.verify_chain(db_session=db_session),
        }


class ExternalAnchorManager:
    """
    Manages anchoring of internal audit chain to external blockchain.
    
    This provides cryptographic proof that the internal audit chain
    existed at a specific point in time on a public blockchain.
    """
    
    def __init__(self):
        self.anchor_interval = 100  # Anchor every N entries
        self._chain_client = None
    
    async def _get_chain_client(self):
        """Get or create chain client."""
        if self._chain_client is None:
            import os
            from node.src.resonant_node.chain.client import ChainClient
            
            self._chain_client = ChainClient(
                rpc_url=os.getenv("BASE_RPC_URL", "https://mainnet.base.org"),
                memory_contract=os.getenv("MEMORY_ANCHORS_CONTRACT", ""),
            )
            await self._chain_client.connect()
        return self._chain_client
    
    async def should_anchor(self, sequence_number: int) -> bool:
        """Check if we should anchor at this sequence number."""
        return sequence_number > 0 and sequence_number % self.anchor_interval == 0
    
    async def create_anchor_hash(
        self,
        from_sequence: int,
        to_sequence: int,
        db_session: AsyncSession,
    ) -> str:
        """Create a Merkle root hash for a range of audit entries."""
        result = await db_session.execute(
            select(AuditEntry)
            .where(AuditEntry.sequence_number >= from_sequence)
            .where(AuditEntry.sequence_number <= to_sequence)
            .order_by(AuditEntry.sequence_number)
        )
        entries = result.scalars().all()
        
        if not entries:
            return "0" * 64
        
        # Create Merkle root from entry hashes
        hashes = [e.entry_hash for e in entries]
        
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])
            
            new_hashes = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                new_hash = hashlib.sha256(combined.encode()).hexdigest()
                new_hashes.append(new_hash)
            hashes = new_hashes
        
        return hashes[0]
    
    async def anchor_to_external_chain(
        self,
        from_sequence: int,
        to_sequence: int,
        private_key: str,
        db_session: AsyncSession,
    ) -> Optional[Dict[str, Any]]:
        """
        Anchor a range of audit entries to external blockchain.
        
        This creates a cryptographic proof that the internal audit chain
        existed at a specific point in time.
        """
        # Create Merkle root
        merkle_root = await self.create_anchor_hash(from_sequence, to_sequence, db_session)
        
        # Get chain client
        try:
            client = await self._get_chain_client()
            
            if not client.connected:
                return {"error": "Chain not connected", "merkle_root": merkle_root}
            
            # Anchor to external chain
            tx_hash = await client.anchor_memory(merkle_root, private_key)
            
            if tx_hash:
                # Record the anchor in audit chain
                await audit_manager.create_entry(
                    event_type="external_anchor",
                    event_category="blockchain",
                    action="anchor_to_base",
                    description=f"Anchored sequences {from_sequence}-{to_sequence} to Base",
                    changes={
                        "from_sequence": from_sequence,
                        "to_sequence": to_sequence,
                        "merkle_root": merkle_root,
                        "tx_hash": tx_hash,
                    },
                    compliance_tags=["immutability", "audit_trail"],
                    db_session=db_session,
                )
                
                return {
                    "success": True,
                    "merkle_root": merkle_root,
                    "tx_hash": tx_hash,
                    "from_sequence": from_sequence,
                    "to_sequence": to_sequence,
                }
            
            return {"error": "Transaction failed", "merkle_root": merkle_root}
            
        except Exception as e:
            return {"error": str(e), "merkle_root": merkle_root}
    
    async def verify_external_anchor(
        self,
        merkle_root: str,
    ) -> Optional[Dict[str, Any]]:
        """Verify an anchor exists on external chain."""
        try:
            client = await self._get_chain_client()
            
            if not client.connected:
                return {"verified": False, "error": "Chain not connected"}
            
            anchor = await client.get_memory_anchor(merkle_root)
            
            if anchor:
                return {
                    "verified": True,
                    "anchor": anchor,
                }
            
            return {"verified": False, "error": "Anchor not found"}
            
        except Exception as e:
            return {"verified": False, "error": str(e)}


audit_manager = AuditChainManager()
compliance_reporter = ComplianceReporter()
external_anchor_manager = ExternalAnchorManager()
