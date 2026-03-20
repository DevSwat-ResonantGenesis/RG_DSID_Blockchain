"""
HSU-Spec Section 22: Performance Benchmarking Framework
========================================================

Evaluation methodology for DSID-P across all layers (L1-L5).

Benchmarking Domains:
1. Identity Performance (L1)
2. User Sphere DAG Performance (L2)
3. Agent Sphere DAG Performance (L3)
4. Coordination Layer Performance (L4)
5. Registry Blockchain Performance (L5)
6. Semantic Subsystem Performance
7. Node Network & Transport Performance
8. End-to-End Agent Performance

This framework is built specifically for multi-layer DAG protocols and agent ecosystems.
"""

import time
import statistics
import asyncio
import logging
from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
import random

logger = logging.getLogger(__name__)


# ============== BENCHMARK DOMAINS ==============

class BenchmarkDomain(Enum):
    """Benchmarking domains corresponding to DSID-P subsystems"""
    L1_IDENTITY = "identity"
    L2_USER_DAG = "user_dag"
    L3_AGENT_DAG = "agent_dag"
    L4_COORDINATION = "coordination"
    L5_REGISTRY = "registry"
    SEMANTIC = "semantic"
    NETWORK = "network"
    END_TO_END = "end_to_end"


class BenchmarkType(Enum):
    """Type of benchmark"""
    CORE = "core"       # Standard metrics
    STRESS = "stress"   # High-load tests
    SOVEREIGN = "sovereign"  # Government-grade tests


# ============== BENCHMARK RESULTS ==============

@dataclass
class BenchmarkResult:
    """Result of a single benchmark run"""
    benchmark_id: str
    domain: str
    metric_name: str
    benchmark_type: str
    samples: List[float]
    min_ms: float
    max_ms: float
    mean_ms: float
    median_ms: float
    std_dev_ms: float
    p95_ms: float
    p99_ms: float
    throughput: Optional[float]  # ops/sec
    success_rate: float
    timestamp: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "domain": self.domain,
            "metric_name": self.metric_name,
            "benchmark_type": self.benchmark_type,
            "sample_count": len(self.samples),
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "mean_ms": round(self.mean_ms, 3),
            "median_ms": round(self.median_ms, 3),
            "std_dev_ms": round(self.std_dev_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "p99_ms": round(self.p99_ms, 3),
            "throughput_ops_sec": round(self.throughput, 2) if self.throughput else None,
            "success_rate": round(self.success_rate, 4),
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class BenchmarkSuite:
    """Collection of benchmark results"""
    suite_id: str
    name: str
    domain: str
    results: List[BenchmarkResult] = field(default_factory=list)
    started_at: int = 0
    completed_at: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "name": self.name,
            "domain": self.domain,
            "results": [r.to_dict() for r in self.results],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.completed_at - self.started_at if self.completed_at else 0,
        }


# ============== BENCHMARK ENGINE ==============

class BenchmarkEngine:
    """
    Performance Benchmarking Engine for DSID-P
    
    Measures:
    - Speed, capacity, scalability
    - Reliability, fault-tolerance
    - Semantic consistency
    - Governance performance
    - Reconstruction time
    - Block anchoring latency
    - Storage replication efficiency
    """
    
    def __init__(self):
        self._results: Dict[str, BenchmarkResult] = {}
        self._suites: Dict[str, BenchmarkSuite] = {}
        self._running_benchmarks: Dict[str, bool] = {}
    
    def _calculate_percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile from sorted data"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def _create_result(
        self,
        domain: str,
        metric_name: str,
        benchmark_type: str,
        samples: List[float],
        success_count: int,
        total_count: int,
        metadata: Dict[str, Any] = None,
    ) -> BenchmarkResult:
        """Create a benchmark result from samples"""
        if not samples:
            samples = [0.0]
        
        mean = statistics.mean(samples)
        throughput = 1000 / mean if mean > 0 else 0  # ops/sec
        
        return BenchmarkResult(
            benchmark_id=str(uuid.uuid4()),
            domain=domain,
            metric_name=metric_name,
            benchmark_type=benchmark_type,
            samples=samples,
            min_ms=min(samples),
            max_ms=max(samples),
            mean_ms=mean,
            median_ms=statistics.median(samples),
            std_dev_ms=statistics.stdev(samples) if len(samples) > 1 else 0,
            p95_ms=self._calculate_percentile(samples, 95),
            p99_ms=self._calculate_percentile(samples, 99),
            throughput=throughput,
            success_rate=success_count / total_count if total_count > 0 else 0,
            timestamp=int(time.time() * 1000),
            metadata=metadata or {},
        )
    
    async def _run_benchmark(
        self,
        operation: Callable,
        iterations: int,
        warmup: int = 10,
    ) -> Tuple[List[float], int, int]:
        """Run a benchmark operation multiple times"""
        # Warmup
        for _ in range(warmup):
            try:
                await operation() if asyncio.iscoroutinefunction(operation) else operation()
            except:
                pass
        
        samples = []
        success_count = 0
        
        for _ in range(iterations):
            start = time.perf_counter()
            try:
                await operation() if asyncio.iscoroutinefunction(operation) else operation()
                success_count += 1
            except Exception as e:
                logger.warning(f"Benchmark iteration failed: {e}")
            end = time.perf_counter()
            samples.append((end - start) * 1000)  # Convert to ms
        
        return samples, success_count, iterations
    
    # ============== 22.2 IDENTITY LAYER (L1) ==============
    
    async def benchmark_identity_creation(self, iterations: int = 1000) -> BenchmarkResult:
        """
        Identity Creation Latency
        Time to generate identity metadata & hash.
        """
        import hashlib
        
        def create_identity():
            # Simulate identity creation
            data = str(uuid.uuid4()).encode()
            return hashlib.sha256(data).hexdigest()
        
        samples, success, total = await self._run_benchmark(create_identity, iterations)
        
        result = self._create_result(
            domain=BenchmarkDomain.L1_IDENTITY.value,
            metric_name="identity_creation_latency",
            benchmark_type=BenchmarkType.CORE.value,
            samples=samples,
            success_count=success,
            total_count=total,
            metadata={"iterations": iterations},
        )
        
        self._results[result.benchmark_id] = result
        return result
    
    async def benchmark_signature_verification(self, iterations: int = 1000) -> BenchmarkResult:
        """
        Signature Verification Latency
        Time to validate identity-bound signatures.
        """
        import hashlib
        
        def verify_signature():
            # Simulate signature verification
            message = b"test_message"
            signature = hashlib.sha256(message).digest()
            return len(signature) == 32
        
        samples, success, total = await self._run_benchmark(verify_signature, iterations)
        
        result = self._create_result(
            domain=BenchmarkDomain.L1_IDENTITY.value,
            metric_name="signature_verification_latency",
            benchmark_type=BenchmarkType.CORE.value,
            samples=samples,
            success_count=success,
            total_count=total,
        )
        
        self._results[result.benchmark_id] = result
        return result
    
    async def benchmark_mass_identity_issuance(self, count: int = 10000) -> BenchmarkResult:
        """
        Mass Identity Issuance Throughput
        Simulate 10k-10M identities.
        """
        import hashlib
        
        start = time.perf_counter()
        success_count = 0
        
        for i in range(count):
            try:
                data = f"identity_{i}_{uuid.uuid4()}".encode()
                hashlib.sha256(data).hexdigest()
                success_count += 1
            except:
                pass
        
        end = time.perf_counter()
        total_ms = (end - start) * 1000
        
        result = self._create_result(
            domain=BenchmarkDomain.L1_IDENTITY.value,
            metric_name="mass_identity_issuance",
            benchmark_type=BenchmarkType.STRESS.value,
            samples=[total_ms / count] * min(count, 100),  # Average per identity
            success_count=success_count,
            total_count=count,
            metadata={
                "total_identities": count,
                "total_time_ms": total_ms,
                "identities_per_second": count / (total_ms / 1000),
            },
        )
        
        self._results[result.benchmark_id] = result
        return result
    
    # ============== 22.3 USER SPHERE DAG (L2) ==============
    
    async def benchmark_dag_node_creation(self, iterations: int = 1000) -> BenchmarkResult:
        """
        Node Creation Latency
        Time to create & encode a single DAG node.
        """
        import json
        import hashlib
        
        def create_node():
            node = {
                "id": str(uuid.uuid4()),
                "payload": {"data": "test_payload"},
                "links": [],
                "timestamp": int(time.time()),
            }
            encoded = json.dumps(node, sort_keys=True).encode()
            node_id = hashlib.sha256(encoded).hexdigest()
            return node_id
        
        samples, success, total = await self._run_benchmark(create_node, iterations)
        
        result = self._create_result(
            domain=BenchmarkDomain.L2_USER_DAG.value,
            metric_name="dag_node_creation_latency",
            benchmark_type=BenchmarkType.CORE.value,
            samples=samples,
            success_count=success,
            total_count=total,
        )
        
        self._results[result.benchmark_id] = result
        return result
    
    async def benchmark_dag_rehydration(self, node_count: int = 1000) -> BenchmarkResult:
        """
        Cold Rehydration Time
        First-time DAG reconstruction from storage.
        """
        import json
        import hashlib
        
        # Create test DAG
        nodes = {}
        for i in range(node_count):
            node = {
                "id": f"node_{i}",
                "payload": {"index": i, "data": "x" * 100},
                "links": [f"node_{i-1}"] if i > 0 else [],
            }
            encoded = json.dumps(node, sort_keys=True).encode()
            node_id = hashlib.sha256(encoded).hexdigest()
            nodes[node_id] = node
        
        def rehydrate():
            # Simulate rehydration
            reconstructed = {}
            for node_id, node in nodes.items():
                reconstructed[node_id] = {
                    **node,
                    "verified": True,
                }
            return len(reconstructed)
        
        samples, success, total = await self._run_benchmark(rehydrate, 100)
        
        result = self._create_result(
            domain=BenchmarkDomain.L2_USER_DAG.value,
            metric_name="dag_rehydration_latency",
            benchmark_type=BenchmarkType.CORE.value,
            samples=samples,
            success_count=success,
            total_count=total,
            metadata={"node_count": node_count},
        )
        
        self._results[result.benchmark_id] = result
        return result
    
    # ============== 22.4 AGENT SPHERE DAG (L3) ==============
    
    async def benchmark_memory_append(self, iterations: int = 1000) -> BenchmarkResult:
        """
        Memory Append Latency
        Time to add a new memory node.
        """
        import json
        import hashlib
        
        memory_store = []
        
        def append_memory():
            memory_node = {
                "type": "episodic",
                "content": f"memory_{len(memory_store)}",
                "timestamp": int(time.time() * 1000),
                "embedding": [random.random() for _ in range(128)],
            }
            encoded = json.dumps(memory_node, sort_keys=True).encode()
            node_id = hashlib.sha256(encoded).hexdigest()
            memory_store.append((node_id, memory_node))
            return node_id
        
        samples, success, total = await self._run_benchmark(append_memory, iterations)
        
        result = self._create_result(
            domain=BenchmarkDomain.L3_AGENT_DAG.value,
            metric_name="memory_append_latency",
            benchmark_type=BenchmarkType.CORE.value,
            samples=samples,
            success_count=success,
            total_count=total,
        )
        
        self._results[result.benchmark_id] = result
        return result
    
    async def benchmark_embedding_update(self, iterations: int = 1000) -> BenchmarkResult:
        """
        Embedding Update Latency
        Time to store & update semantic vectors.
        """
        def update_embedding():
            # Simulate embedding update
            vector = [random.random() for _ in range(768)]  # Typical embedding size
            normalized = [v / sum(vector) for v in vector]
            return normalized
        
        samples, success, total = await self._run_benchmark(update_embedding, iterations)
        
        result = self._create_result(
            domain=BenchmarkDomain.L3_AGENT_DAG.value,
            metric_name="embedding_update_latency",
            benchmark_type=BenchmarkType.CORE.value,
            samples=samples,
            success_count=success,
            total_count=total,
        )
        
        self._results[result.benchmark_id] = result
        return result
    
    # ============== 22.5 COORDINATION LAYER (L4) ==============
    
    async def benchmark_event_append(self, iterations: int = 1000) -> BenchmarkResult:
        """
        Event Append Latency
        Time to write a single coordination event.
        """
        import json
        import hashlib
        
        events = []
        
        def append_event():
            event = {
                "type": "interaction",
                "sender": f"agent_{random.randint(1, 100)}",
                "receiver": f"agent_{random.randint(1, 100)}",
                "action": "message",
                "timestamp": int(time.time() * 1000),
            }
            encoded = json.dumps(event, sort_keys=True).encode()
            event_id = hashlib.sha256(encoded).hexdigest()
            events.append((event_id, event))
            return event_id
        
        samples, success, total = await self._run_benchmark(append_event, iterations)
        
        result = self._create_result(
            domain=BenchmarkDomain.L4_COORDINATION.value,
            metric_name="event_append_latency",
            benchmark_type=BenchmarkType.CORE.value,
            samples=samples,
            success_count=success,
            total_count=total,
        )
        
        self._results[result.benchmark_id] = result
        return result
    
    # ============== 22.6 REGISTRY BLOCKCHAIN (L5) ==============
    
    async def benchmark_block_anchoring(self, iterations: int = 100) -> BenchmarkResult:
        """
        Block Anchoring Latency
        Time to write a UserBlock or AgentBlock.
        """
        import json
        import hashlib
        
        chain = []
        
        def anchor_block():
            prev_hash = chain[-1]["id"] if chain else None
            block = {
                "version": 1,
                "prevHash": prev_hash,
                "userID": f"user_{random.randint(1, 1000)}",
                "sphereRoot": hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest(),
                "timestamp": int(time.time()),
            }
            encoded = json.dumps(block, sort_keys=True).encode()
            block["id"] = hashlib.sha256(encoded).hexdigest()
            chain.append(block)
            return block["id"]
        
        samples, success, total = await self._run_benchmark(anchor_block, iterations)
        
        result = self._create_result(
            domain=BenchmarkDomain.L5_REGISTRY.value,
            metric_name="block_anchoring_latency",
            benchmark_type=BenchmarkType.CORE.value,
            samples=samples,
            success_count=success,
            total_count=total,
            metadata={"chain_length": len(chain)},
        )
        
        self._results[result.benchmark_id] = result
        return result
    
    # ============== 22.7 SEMANTIC SUBSYSTEM ==============
    
    async def benchmark_vector_ingestion(self, count: int = 10000) -> BenchmarkResult:
        """
        Vector Ingestion Rate
        How many semantic vectors can be processed/sec.
        """
        vectors = []
        
        start = time.perf_counter()
        
        for i in range(count):
            vector = [random.random() for _ in range(384)]
            vectors.append({
                "agent_id": f"agent_{i}",
                "vector": vector,
            })
        
        end = time.perf_counter()
        total_ms = (end - start) * 1000
        
        result = self._create_result(
            domain=BenchmarkDomain.SEMANTIC.value,
            metric_name="vector_ingestion_rate",
            benchmark_type=BenchmarkType.CORE.value,
            samples=[total_ms / count] * min(count, 100),
            success_count=count,
            total_count=count,
            metadata={
                "total_vectors": count,
                "total_time_ms": total_ms,
                "vectors_per_second": count / (total_ms / 1000),
            },
        )
        
        self._results[result.benchmark_id] = result
        return result
    
    async def benchmark_cluster_recalculation(self, agent_count: int = 1000, cluster_count: int = 10) -> BenchmarkResult:
        """
        Cluster Recalculation Latency
        Time to recompute centroids.
        """
        # Generate test vectors
        vectors = [[random.random() for _ in range(128)] for _ in range(agent_count)]
        
        def recalculate_clusters():
            # Simple k-means iteration
            centroids = vectors[:cluster_count]
            
            # Assign to clusters
            assignments = []
            for v in vectors:
                min_dist = float('inf')
                min_idx = 0
                for i, c in enumerate(centroids):
                    dist = sum((a - b) ** 2 for a, b in zip(v, c)) ** 0.5
                    if dist < min_dist:
                        min_dist = dist
                        min_idx = i
                assignments.append(min_idx)
            
            return assignments
        
        samples, success, total = await self._run_benchmark(recalculate_clusters, 100)
        
        result = self._create_result(
            domain=BenchmarkDomain.SEMANTIC.value,
            metric_name="cluster_recalculation_latency",
            benchmark_type=BenchmarkType.CORE.value,
            samples=samples,
            success_count=success,
            total_count=total,
            metadata={
                "agent_count": agent_count,
                "cluster_count": cluster_count,
            },
        )
        
        self._results[result.benchmark_id] = result
        return result
    
    # ============== 22.8 NETWORK & TRANSPORT ==============
    
    async def benchmark_cbor_encoding(self, iterations: int = 1000) -> BenchmarkResult:
        """
        CBOR Message Latency
        Time for message encode + decode cycles.
        """
        import json
        
        test_data = {
            "type": "message",
            "payload": {"data": "x" * 1000},
            "timestamp": int(time.time()),
            "links": [f"link_{i}" for i in range(10)],
        }
        
        def encode_decode():
            # Simulate CBOR encode/decode with JSON
            encoded = json.dumps(test_data, sort_keys=True).encode()
            decoded = json.loads(encoded.decode())
            return decoded
        
        samples, success, total = await self._run_benchmark(encode_decode, iterations)
        
        result = self._create_result(
            domain=BenchmarkDomain.NETWORK.value,
            metric_name="cbor_encoding_latency",
            benchmark_type=BenchmarkType.CORE.value,
            samples=samples,
            success_count=success,
            total_count=total,
        )
        
        self._results[result.benchmark_id] = result
        return result
    
    # ============== 22.9 END-TO-END ==============
    
    async def benchmark_full_agent_workflow(self, iterations: int = 100) -> BenchmarkResult:
        """
        Task Execution Latency
        Total time for complete agent workflow:
        1. Fetch identity
        2. Load memory DAG
        3. Execute reasoning
        4. Update memory
        5. Append coordination event
        6. Push semantic vectors
        7. Anchor updated state
        """
        import json
        import hashlib
        
        def full_workflow():
            # 1. Fetch identity
            identity = hashlib.sha256(b"agent_identity").hexdigest()
            
            # 2. Load memory DAG
            memory = [{"type": "episodic", "content": f"mem_{i}"} for i in range(10)]
            
            # 3. Execute reasoning (simulated)
            result = {"decision": "action_a", "confidence": 0.95}
            
            # 4. Update memory
            new_memory = {"type": "episodic", "content": "new_memory", "result": result}
            memory.append(new_memory)
            
            # 5. Append coordination event
            event = {
                "type": "action",
                "agent": identity,
                "action": result["decision"],
                "timestamp": int(time.time() * 1000),
            }
            
            # 6. Push semantic vectors
            vector = [random.random() for _ in range(128)]
            
            # 7. Anchor state
            state = {
                "identity": identity,
                "memory_root": hashlib.sha256(json.dumps(memory).encode()).hexdigest(),
                "vector": vector[:10],
            }
            block = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
            
            return block
        
        samples, success, total = await self._run_benchmark(full_workflow, iterations)
        
        result = self._create_result(
            domain=BenchmarkDomain.END_TO_END.value,
            metric_name="full_agent_workflow_latency",
            benchmark_type=BenchmarkType.CORE.value,
            samples=samples,
            success_count=success,
            total_count=total,
        )
        
        self._results[result.benchmark_id] = result
        return result
    
    # ============== 22.10 SOVEREIGN BENCHMARKS ==============
    
    async def benchmark_compliance_audit(self, agent_count: int = 100) -> BenchmarkResult:
        """
        Compliance Audit Latency
        Full-agent reconstruction within X seconds.
        """
        import json
        import hashlib
        
        # Create test agent histories
        agents = {}
        for i in range(agent_count):
            agents[f"agent_{i}"] = {
                "identity": hashlib.sha256(f"agent_{i}".encode()).hexdigest(),
                "memory": [{"event": j} for j in range(100)],
                "coordination": [{"action": j} for j in range(50)],
            }
        
        def audit_all_agents():
            audit_results = []
            for agent_id, agent_data in agents.items():
                # Reconstruct and verify
                audit = {
                    "agent_id": agent_id,
                    "memory_count": len(agent_data["memory"]),
                    "coordination_count": len(agent_data["coordination"]),
                    "verified": True,
                }
                audit_results.append(audit)
            return audit_results
        
        samples, success, total = await self._run_benchmark(audit_all_agents, 10)
        
        result = self._create_result(
            domain=BenchmarkDomain.END_TO_END.value,
            metric_name="compliance_audit_latency",
            benchmark_type=BenchmarkType.SOVEREIGN.value,
            samples=samples,
            success_count=success,
            total_count=total,
            metadata={"agent_count": agent_count},
        )
        
        self._results[result.benchmark_id] = result
        return result
    
    # ============== SUITE MANAGEMENT ==============
    
    async def run_full_benchmark_suite(self) -> BenchmarkSuite:
        """Run all benchmarks and return a complete suite"""
        suite = BenchmarkSuite(
            suite_id=str(uuid.uuid4()),
            name="DSID-P Full Benchmark Suite",
            domain="all",
            started_at=int(time.time() * 1000),
        )
        
        # L1 Identity
        suite.results.append(await self.benchmark_identity_creation())
        suite.results.append(await self.benchmark_signature_verification())
        
        # L2 User DAG
        suite.results.append(await self.benchmark_dag_node_creation())
        suite.results.append(await self.benchmark_dag_rehydration(500))
        
        # L3 Agent DAG
        suite.results.append(await self.benchmark_memory_append())
        suite.results.append(await self.benchmark_embedding_update())
        
        # L4 Coordination
        suite.results.append(await self.benchmark_event_append())
        
        # L5 Registry
        suite.results.append(await self.benchmark_block_anchoring())
        
        # Semantic
        suite.results.append(await self.benchmark_vector_ingestion(5000))
        suite.results.append(await self.benchmark_cluster_recalculation(500, 5))
        
        # Network
        suite.results.append(await self.benchmark_cbor_encoding())
        
        # End-to-End
        suite.results.append(await self.benchmark_full_agent_workflow(50))
        
        suite.completed_at = int(time.time() * 1000)
        self._suites[suite.suite_id] = suite
        
        return suite
    
    def get_results(self) -> List[Dict[str, Any]]:
        """Get all benchmark results"""
        return [r.to_dict() for r in self._results.values()]
    
    def get_suites(self) -> List[Dict[str, Any]]:
        """Get all benchmark suites"""
        return [s.to_dict() for s in self._suites.values()]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get benchmark summary"""
        results_by_domain = {}
        for result in self._results.values():
            if result.domain not in results_by_domain:
                results_by_domain[result.domain] = []
            results_by_domain[result.domain].append(result.to_dict())
        
        return {
            "total_benchmarks": len(self._results),
            "total_suites": len(self._suites),
            "domains": list(results_by_domain.keys()),
            "results_by_domain": {
                domain: len(results) for domain, results in results_by_domain.items()
            },
        }


# ============== GLOBAL INSTANCE ==============

benchmark_engine = BenchmarkEngine()
