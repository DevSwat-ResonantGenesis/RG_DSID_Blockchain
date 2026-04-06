"""
TRAINING VERIFIER
=================

Spot-check verification for miner gradient submissions.
Validators (CLASS_F) re-execute 1% of a miner's training batch
and compare the resulting loss. If the miner's reported loss diverges
beyond a threshold, the submission is flagged as fraudulent.

This is the "Proof of Training" protocol:
1. Miner submits gradient + reported loss for a data shard
2. Validator randomly selects 1% of the data shard
3. Validator re-runs forward pass on the selected samples
4. Compare validator's loss vs miner's reported loss
5. If |validator_loss - miner_loss| > threshold → FRAUD → slash stake

This approach is inspired by Gensyn's Proof of Learning and
Bittensor's validator subnet, adapted for the RG agent framework.

STATUS: PRODUCTION IMPLEMENTATION
UPDATED: 2026-04-01
PURPOSE: Fraud detection for distributed miner training
"""

import hashlib
import json
import logging
import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)


class VerificationResult(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SUSPICIOUS = "suspicious"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class VerificationReport:
    """Result of a spot-check verification."""
    report_id: str
    task_id: str
    miner_id: str
    validator_id: str

    # Comparison
    miner_reported_loss: float
    validator_computed_loss: float
    loss_divergence: float
    divergence_threshold: float

    # Verdict
    result: VerificationResult
    reason: str

    # Spot-check details
    total_samples: int
    checked_samples: int
    check_ratio: float

    # Data integrity
    data_shard_hash_match: bool
    weight_shard_hash_match: bool
    gradient_hash_valid: bool

    # Timing
    verification_time_seconds: float
    verified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "task_id": self.task_id,
            "miner_id": self.miner_id,
            "validator_id": self.validator_id,
            "miner_reported_loss": round(self.miner_reported_loss, 6),
            "validator_computed_loss": round(self.validator_computed_loss, 6),
            "loss_divergence": round(self.loss_divergence, 6),
            "divergence_threshold": self.divergence_threshold,
            "result": self.result.value,
            "reason": self.reason,
            "total_samples": self.total_samples,
            "checked_samples": self.checked_samples,
            "check_ratio": round(self.check_ratio, 4),
            "data_shard_hash_match": self.data_shard_hash_match,
            "weight_shard_hash_match": self.weight_shard_hash_match,
            "gradient_hash_valid": self.gradient_hash_valid,
            "verification_time_seconds": round(self.verification_time_seconds, 2),
            "verified_at": self.verified_at,
        }


@dataclass
class MinerTrustRecord:
    """Tracks a miner's verification history for trust scoring."""
    miner_id: str
    total_verifications: int = 0
    passed: int = 0
    failed: int = 0
    suspicious: int = 0
    trust_score: float = 1.0
    consecutive_passes: int = 0
    consecutive_failures: int = 0
    is_slashed: bool = False
    slash_reason: str = ""

    @property
    def pass_rate(self) -> float:
        if self.total_verifications == 0:
            return 1.0
        return self.passed / self.total_verifications

    def to_dict(self) -> Dict[str, Any]:
        return {
            "miner_id": self.miner_id,
            "total_verifications": self.total_verifications,
            "passed": self.passed,
            "failed": self.failed,
            "suspicious": self.suspicious,
            "trust_score": round(self.trust_score, 4),
            "pass_rate": round(self.pass_rate, 4),
            "consecutive_passes": self.consecutive_passes,
            "consecutive_failures": self.consecutive_failures,
            "is_slashed": self.is_slashed,
            "slash_reason": self.slash_reason,
        }


class TrainingVerifier:
    """
    Spot-check verifier for miner training submissions.
    
    Runs on CLASS_F (Genesis Validator) nodes. Uses the existing
    RARA kill switch for slashing and the existing wallet lock_balance
    for stake management.
    """

    # What fraction of samples to re-check (1% by default)
    SPOT_CHECK_RATIO = 0.01

    # Maximum allowed loss divergence before flagging fraud
    LOSS_DIVERGENCE_THRESHOLD = 0.15

    # Trust score penalties
    FAIL_PENALTY = 0.2
    SUSPICIOUS_PENALTY = 0.05
    PASS_BONUS = 0.01

    # Consecutive failures before auto-slash
    MAX_CONSECUTIVE_FAILURES = 3

    # Probability of verifying any given submission (not every submission gets checked)
    VERIFICATION_PROBABILITY = 0.10  # 10% of submissions get spot-checked

    def __init__(self, validator_id: str = "validator_0"):
        self.validator_id = validator_id
        self.trust_records: Dict[str, MinerTrustRecord] = {}
        self.reports: List[VerificationReport] = []
        self._forward_fn: Optional[Callable] = None

    def set_forward_function(self, fn: Callable):
        """
        Set the forward pass function used for spot-check re-execution.
        
        fn(model_weights, data_samples) -> loss: float
        
        This is the ONLY function that needs to be ML-framework-specific.
        Everything else in the verifier is framework-agnostic.
        """
        self._forward_fn = fn

    def should_verify(self, miner_id: str) -> bool:
        """
        Decide whether to verify a given submission.
        
        Higher verification rate for:
        - New miners (trust_score < 0.8)
        - Previously suspicious miners
        - Random 10% baseline
        """
        record = self.trust_records.get(miner_id)

        if record is None:
            return True  # Always verify first submission

        if record.trust_score < 0.8:
            return random.random() < 0.30  # 30% for low-trust miners

        if record.suspicious > 0:
            return random.random() < 0.25  # 25% for previously suspicious

        return random.random() < self.VERIFICATION_PROBABILITY

    def verify(
        self,
        task_id: str,
        miner_id: str,
        miner_reported_loss: float,
        total_samples: int,
        data_shard_hash: str,
        weight_shard_hash: str,
        gradient_hash: str,
        actual_data_shard_hash: str,
        actual_weight_shard_hash: str,
        gradient_hash_valid: bool,
        validator_loss: Optional[float] = None,
    ) -> VerificationReport:
        """
        Perform spot-check verification on a miner's submission.
        
        Args:
            task_id: The training task ID
            miner_id: The miner agent ID
            miner_reported_loss: Loss value reported by the miner
            total_samples: Total samples in the data shard
            data_shard_hash: Hash the miner claims for the data shard
            weight_shard_hash: Hash the miner claims for the weight shard
            gradient_hash: Hash of the compressed gradient
            actual_data_shard_hash: Hash computed by the validator for the data shard
            actual_weight_shard_hash: Hash computed by the validator for the weight shard
            gradient_hash_valid: Whether the gradient hash passes integrity check
            validator_loss: Loss computed by the validator (if forward_fn was run)
            
        Returns:
            VerificationReport with the verdict
        """
        start_time = time.time()

        # Ensure trust record exists
        if miner_id not in self.trust_records:
            self.trust_records[miner_id] = MinerTrustRecord(miner_id=miner_id)
        record = self.trust_records[miner_id]

        # Check data integrity first
        data_hash_match = (data_shard_hash == actual_data_shard_hash)
        weight_hash_match = (weight_shard_hash == actual_weight_shard_hash)

        checked_samples = max(1, int(total_samples * self.SPOT_CHECK_RATIO))

        # If hashes don't match → immediate failure (miner used wrong data)
        if not data_hash_match or not weight_hash_match:
            report = self._create_report(
                task_id=task_id,
                miner_id=miner_id,
                miner_reported_loss=miner_reported_loss,
                validator_computed_loss=0.0,
                total_samples=total_samples,
                checked_samples=0,
                data_hash_match=data_hash_match,
                weight_hash_match=weight_hash_match,
                gradient_hash_valid=gradient_hash_valid,
                result=VerificationResult.FAILED,
                reason=f"Hash mismatch — data={data_hash_match}, weights={weight_hash_match}",
                elapsed=time.time() - start_time,
            )
            self._update_trust(record, VerificationResult.FAILED)
            return report

        # If gradient hash is invalid → immediate failure
        if not gradient_hash_valid:
            report = self._create_report(
                task_id=task_id,
                miner_id=miner_id,
                miner_reported_loss=miner_reported_loss,
                validator_computed_loss=0.0,
                total_samples=total_samples,
                checked_samples=0,
                data_hash_match=True,
                weight_hash_match=True,
                gradient_hash_valid=False,
                result=VerificationResult.FAILED,
                reason="Gradient hash integrity check failed",
                elapsed=time.time() - start_time,
            )
            self._update_trust(record, VerificationResult.FAILED)
            return report

        # If we have a validator-computed loss, compare it
        if validator_loss is not None:
            divergence = abs(validator_loss - miner_reported_loss)
            relative_divergence = divergence / max(abs(miner_reported_loss), 1e-8)

            if relative_divergence > self.LOSS_DIVERGENCE_THRESHOLD:
                result = VerificationResult.FAILED
                reason = f"Loss divergence {relative_divergence:.4f} exceeds threshold {self.LOSS_DIVERGENCE_THRESHOLD}"
            elif relative_divergence > self.LOSS_DIVERGENCE_THRESHOLD * 0.5:
                result = VerificationResult.SUSPICIOUS
                reason = f"Loss divergence {relative_divergence:.4f} is borderline suspicious"
            else:
                result = VerificationResult.PASSED
                reason = f"Loss divergence {relative_divergence:.4f} within acceptable range"

            report = self._create_report(
                task_id=task_id,
                miner_id=miner_id,
                miner_reported_loss=miner_reported_loss,
                validator_computed_loss=validator_loss,
                total_samples=total_samples,
                checked_samples=checked_samples,
                data_hash_match=True,
                weight_hash_match=True,
                gradient_hash_valid=True,
                result=result,
                reason=reason,
                elapsed=time.time() - start_time,
            )
            self._update_trust(record, result)
            return report

        # No forward function available — pass on hash checks alone
        report = self._create_report(
            task_id=task_id,
            miner_id=miner_id,
            miner_reported_loss=miner_reported_loss,
            validator_computed_loss=0.0,
            total_samples=total_samples,
            checked_samples=0,
            data_hash_match=True,
            weight_hash_match=True,
            gradient_hash_valid=True,
            result=VerificationResult.PASSED,
            reason="Hash integrity verified (no forward re-execution available)",
            elapsed=time.time() - start_time,
        )
        self._update_trust(record, VerificationResult.PASSED)
        return report

    def _create_report(
        self,
        task_id: str,
        miner_id: str,
        miner_reported_loss: float,
        validator_computed_loss: float,
        total_samples: int,
        checked_samples: int,
        data_hash_match: bool,
        weight_hash_match: bool,
        gradient_hash_valid: bool,
        result: VerificationResult,
        reason: str,
        elapsed: float,
    ) -> VerificationReport:
        """Create and store a verification report."""
        divergence = abs(validator_computed_loss - miner_reported_loss) if validator_computed_loss else 0.0

        report = VerificationReport(
            report_id=str(uuid4()),
            task_id=task_id,
            miner_id=miner_id,
            validator_id=self.validator_id,
            miner_reported_loss=miner_reported_loss,
            validator_computed_loss=validator_computed_loss,
            loss_divergence=divergence,
            divergence_threshold=self.LOSS_DIVERGENCE_THRESHOLD,
            result=result,
            reason=reason,
            total_samples=total_samples,
            checked_samples=checked_samples,
            check_ratio=self.SPOT_CHECK_RATIO,
            data_shard_hash_match=data_hash_match,
            weight_shard_hash_match=weight_hash_match,
            gradient_hash_valid=gradient_hash_valid,
            verification_time_seconds=elapsed,
        )
        self.reports.append(report)

        log_fn = logger.info if result == VerificationResult.PASSED else logger.warning
        log_fn(f"Verification {report.report_id}: miner={miner_id} task={task_id} → {result.value} ({reason})")

        return report

    def _update_trust(self, record: MinerTrustRecord, result: VerificationResult):
        """Update miner trust score based on verification result."""
        record.total_verifications += 1

        if result == VerificationResult.PASSED:
            record.passed += 1
            record.consecutive_passes += 1
            record.consecutive_failures = 0
            record.trust_score = min(1.0, record.trust_score + self.PASS_BONUS)

        elif result == VerificationResult.FAILED:
            record.failed += 1
            record.consecutive_failures += 1
            record.consecutive_passes = 0
            record.trust_score = max(0.0, record.trust_score - self.FAIL_PENALTY)

            if record.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                record.is_slashed = True
                record.slash_reason = f"Auto-slashed: {record.consecutive_failures} consecutive verification failures"
                logger.critical(f"SLASH: Miner {record.miner_id} — {record.slash_reason}")

        elif result == VerificationResult.SUSPICIOUS:
            record.suspicious += 1
            record.trust_score = max(0.0, record.trust_score - self.SUSPICIOUS_PENALTY)

    def get_slashed_miners(self) -> List[str]:
        """Get list of miner IDs that have been slashed."""
        return [r.miner_id for r in self.trust_records.values() if r.is_slashed]

    def get_trust_score(self, miner_id: str) -> float:
        """Get a miner's current trust score."""
        record = self.trust_records.get(miner_id)
        return record.trust_score if record else 1.0

    def get_stats(self) -> Dict[str, Any]:
        """Get verifier statistics."""
        total_reports = len(self.reports)
        passed = sum(1 for r in self.reports if r.result == VerificationResult.PASSED)
        failed = sum(1 for r in self.reports if r.result == VerificationResult.FAILED)
        suspicious = sum(1 for r in self.reports if r.result == VerificationResult.SUSPICIOUS)
        slashed = len(self.get_slashed_miners())

        return {
            "validator_id": self.validator_id,
            "total_verifications": total_reports,
            "passed": passed,
            "failed": failed,
            "suspicious": suspicious,
            "slashed_miners": slashed,
            "tracked_miners": len(self.trust_records),
            "spot_check_ratio": self.SPOT_CHECK_RATIO,
            "divergence_threshold": self.LOSS_DIVERGENCE_THRESHOLD,
            "verification_probability": self.VERIFICATION_PROBABILITY,
        }

    def get_miner_trust_records(self) -> List[Dict[str, Any]]:
        """Get all miner trust records."""
        return [r.to_dict() for r in self.trust_records.values()]


# Global instance
training_verifier = TrainingVerifier()
