"""
HSU-Spec Section 34: Global Agent Workforce Simulation Model
============================================================

A predictive simulation framework for scaling DSID-P agent economies
across enterprises, nations, and global federations.

Subsystems:
1. Population Model (agents, users, orgs)
2. Demand Model (tasks, workflows, industries)
3. Supply Model (agents, cluster distribution, trust levels)
4. Performance & Load Model (compute, semantics, DAG ops)
5. Governance & Risk Model (compliance, drift, trust decay)

Key Equations:
- Population: A(t+1) = A(t) + CreationRate × U(t) + AutoGenerationRate × O(t)
- Demand: D(t) = α·U(t) + β·O(t) + γ·I(t) + δ·G(t)
- Supply: S(t) = Σ (Agents_in_cluster × Efficiency × ATS_multiplier)
- Growth: A(t) = MaxAgents / (1 + e^-k(t - midpoint))
"""

import math
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ============== POPULATION MODEL ==============

@dataclass
class PopulationState:
    """State of the agent population at time t"""
    timestamp: int
    total_agents: int
    total_users: int
    total_organizations: int
    cluster_distribution: Dict[str, int]
    creation_rate: float
    auto_generation_rate: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_agents": self.total_agents,
            "total_users": self.total_users,
            "total_organizations": self.total_organizations,
            "cluster_distribution": self.cluster_distribution,
            "creation_rate": round(self.creation_rate, 4),
            "auto_generation_rate": round(self.auto_generation_rate, 4),
        }


class PopulationModel:
    """Model agent population dynamics"""
    
    def __init__(
        self,
        initial_agents: int = 1000,
        initial_users: int = 500,
        initial_orgs: int = 10,
        creation_rate: float = 0.5,
        auto_generation_rate: float = 0.1,
    ):
        self.initial_agents = initial_agents
        self.initial_users = initial_users
        self.initial_orgs = initial_orgs
        self.creation_rate = creation_rate
        self.auto_generation_rate = auto_generation_rate
        self._history: List[PopulationState] = []
    
    def simulate(self, periods: int = 10) -> List[PopulationState]:
        """Simulate population over time periods"""
        
        agents = self.initial_agents
        users = self.initial_users
        orgs = self.initial_orgs
        
        # Default cluster distribution
        cluster_ratios = {
            "A": 0.15, "K": 0.10, "L": 0.12, "C": 0.08,
            "W": 0.20, "S": 0.15, "B": 0.10, "H": 0.03,
            "P": 0.03, "G": 0.02, "M": 0.02,
        }
        
        self._history = []
        
        for t in range(periods):
            # A(t+1) = A(t) + CreationRate × U(t) + AutoGenerationRate × O(t)
            new_agents = int(
                self.creation_rate * users +
                self.auto_generation_rate * orgs * 10
            )
            agents += new_agents
            
            # Users and orgs grow
            users = int(users * 1.3)
            orgs = int(orgs * 1.15)
            
            # Calculate cluster distribution
            cluster_dist = {
                cluster: int(agents * ratio)
                for cluster, ratio in cluster_ratios.items()
            }
            
            state = PopulationState(
                timestamp=int(time.time() * 1000) + t * 86400000,
                total_agents=agents,
                total_users=users,
                total_organizations=orgs,
                cluster_distribution=cluster_dist,
                creation_rate=self.creation_rate,
                auto_generation_rate=self.auto_generation_rate,
            )
            
            self._history.append(state)
        
        return self._history
    
    def get_history(self) -> List[PopulationState]:
        return self._history
    
    def project_growth(
        self,
        max_agents: int,
        k: float = 0.5,
        midpoint: int = 5,
        years: int = 10,
    ) -> List[Dict[str, Any]]:
        """Project growth using logistic curve"""
        projections = []
        for year in range(1, years + 1):
            # A(t) = MaxAgents / (1 + e^-k(t - midpoint))
            agents = int(max_agents / (1 + math.exp(-k * (year - midpoint))))
            projections.append({
                "year": year,
                "projected_agents": agents,
                "growth_rate": round(
                    (agents - projections[-1]["projected_agents"]) / projections[-1]["projected_agents"] * 100, 2
                ) if projections else 0,
            })
        return projections


# ============== DEMAND MODEL ==============

@dataclass
class DemandState:
    """Demand state at time t"""
    timestamp: int
    total_demand: float
    user_demand: float
    enterprise_demand: float
    industry_demand: float
    government_demand: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_demand": round(self.total_demand, 2),
            "user_demand": round(self.user_demand, 2),
            "enterprise_demand": round(self.enterprise_demand, 2),
            "industry_demand": round(self.industry_demand, 2),
            "government_demand": round(self.government_demand, 2),
        }


class DemandModel:
    """Model task and workflow demand"""
    
    def __init__(
        self,
        alpha: float = 10.0,   # user task demand elasticity
        beta: float = 100.0,   # enterprise workload scaling
        gamma: float = 50.0,   # industry complexity coefficient
        delta: float = 500.0,  # national infrastructure demand
    ):
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.delta = delta
    
    def calculate_demand(
        self,
        users: int,
        organizations: int,
        industry_multiplier: float = 1.0,
        government_scale: float = 0.0,
    ) -> DemandState:
        """Calculate demand: D(t) = α·U(t) + β·O(t) + γ·I(t) + δ·G(t)"""
        
        user_demand = self.alpha * users
        enterprise_demand = self.beta * organizations
        industry_demand = self.gamma * industry_multiplier * organizations
        government_demand = self.delta * government_scale
        
        total_demand = user_demand + enterprise_demand + industry_demand + government_demand
        
        return DemandState(
            timestamp=int(time.time() * 1000),
            total_demand=total_demand,
            user_demand=user_demand,
            enterprise_demand=enterprise_demand,
            industry_demand=industry_demand,
            government_demand=government_demand,
        )


# ============== SUPPLY MODEL ==============

@dataclass
class SupplyState:
    """Supply state at time t"""
    timestamp: int
    total_supply: float
    cluster_supply: Dict[str, float]
    trust_adjusted_capacity: float
    governance_compliant_capacity: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_supply": round(self.total_supply, 2),
            "cluster_supply": {k: round(v, 2) for k, v in self.cluster_supply.items()},
            "trust_adjusted_capacity": round(self.trust_adjusted_capacity, 2),
            "governance_compliant_capacity": round(self.governance_compliant_capacity, 2),
        }


class SupplyModel:
    """Model agent supply capacity"""
    
    # Efficiency by cluster
    CLUSTER_EFFICIENCY = {
        "A": 0.85, "K": 0.80, "L": 0.90, "C": 0.75,
        "W": 0.95, "S": 0.88, "B": 0.82, "H": 0.70,
        "P": 0.72, "G": 0.95, "M": 0.90,
    }
    
    # ATS multipliers by tier
    ATS_MULTIPLIERS = {
        "T5": 1.8, "T4": 1.5, "T3": 1.2, "T2": 0.9, "T1": 0.5,
    }
    
    def calculate_supply(
        self,
        cluster_distribution: Dict[str, int],
        trust_distribution: Dict[str, float] = None,
    ) -> SupplyState:
        """Calculate supply: S(t) = Σ (Agents × Efficiency × ATS_multiplier)"""
        
        if trust_distribution is None:
            trust_distribution = {"T5": 0.05, "T4": 0.20, "T3": 0.40, "T2": 0.25, "T1": 0.10}
        
        # Calculate weighted ATS multiplier
        avg_ats_multiplier = sum(
            self.ATS_MULTIPLIERS[tier] * ratio
            for tier, ratio in trust_distribution.items()
        )
        
        cluster_supply = {}
        total_supply = 0
        
        for cluster, count in cluster_distribution.items():
            efficiency = self.CLUSTER_EFFICIENCY.get(cluster, 0.8)
            supply = count * efficiency * avg_ats_multiplier
            cluster_supply[cluster] = supply
            total_supply += supply
        
        # Governance-compliant capacity (90% of total)
        governance_compliant = total_supply * 0.9
        
        return SupplyState(
            timestamp=int(time.time() * 1000),
            total_supply=total_supply,
            cluster_supply=cluster_supply,
            trust_adjusted_capacity=total_supply,
            governance_compliant_capacity=governance_compliant,
        )


# ============== PERFORMANCE & LOAD MODEL ==============

@dataclass
class ClusterLoadProfile:
    """Load profile for a semantic cluster"""
    cluster: str
    avg_load: str  # "low", "medium", "high", "very_high", "extremely_high"
    volatility: str  # "low", "moderate", "high", "very_high"
    scaling_need: str  # "low", "medium", "high", "very_high"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster": self.cluster,
            "avg_load": self.avg_load,
            "volatility": self.volatility,
            "scaling_need": self.scaling_need,
        }


@dataclass
class PerformanceMetrics:
    """Performance metrics for the workforce"""
    timestamp: int
    total_productivity: float
    avg_throughput: float
    avg_success_rate: float
    avg_compliance_factor: float
    top_performers_share: float  # % of work done by top 20%
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_productivity": round(self.total_productivity, 2),
            "avg_throughput": round(self.avg_throughput, 4),
            "avg_success_rate": round(self.avg_success_rate, 4),
            "avg_compliance_factor": round(self.avg_compliance_factor, 4),
            "top_performers_share": round(self.top_performers_share, 2),
        }


class PerformanceModel:
    """Model workforce performance and load"""
    
    CLUSTER_LOAD_PROFILES = {
        "A": ClusterLoadProfile("A", "very_high", "moderate", "high"),
        "K": ClusterLoadProfile("K", "medium", "low", "medium"),
        "L": ClusterLoadProfile("L", "high", "moderate", "medium"),
        "C": ClusterLoadProfile("C", "medium", "high", "low"),
        "W": ClusterLoadProfile("W", "extremely_high", "high", "very_high"),
        "S": ClusterLoadProfile("S", "high", "low", "medium"),
        "B": ClusterLoadProfile("B", "high", "moderate", "medium"),
        "H": ClusterLoadProfile("H", "extremely_low", "extremely_sensitive", "supervised"),
        "P": ClusterLoadProfile("P", "low", "low", "low"),
        "G": ClusterLoadProfile("G", "low", "very_low", "low"),
        "M": ClusterLoadProfile("M", "medium", "moderate", "medium"),
    }
    
    def calculate_productivity(
        self,
        agents: int,
        avg_throughput: float = 100.0,
        avg_success_rate: float = 0.92,
        avg_compliance_factor: float = 0.95,
    ) -> PerformanceMetrics:
        """Calculate workforce productivity"""
        
        # P_agent = Throughput × SuccessRate × ComplianceFactor
        agent_productivity = avg_throughput * avg_success_rate * avg_compliance_factor
        
        # P_total = Σ P_agent
        total_productivity = agents * agent_productivity
        
        # Power-law: 20% of agents perform 80% of work
        top_performers_share = 80.0
        
        return PerformanceMetrics(
            timestamp=int(time.time() * 1000),
            total_productivity=total_productivity,
            avg_throughput=avg_throughput,
            avg_success_rate=avg_success_rate,
            avg_compliance_factor=avg_compliance_factor,
            top_performers_share=top_performers_share,
        )
    
    def get_cluster_load_profile(self, cluster: str) -> Optional[ClusterLoadProfile]:
        return self.CLUSTER_LOAD_PROFILES.get(cluster)
    
    def list_cluster_load_profiles(self) -> List[ClusterLoadProfile]:
        return list(self.CLUSTER_LOAD_PROFILES.values())


# ============== GOVERNANCE & RISK MODEL ==============

@dataclass
class DriftSimulation:
    """Drift simulation result"""
    agent_id: str
    initial_drift: float
    drift_velocity: float
    threshold: float
    periods_to_threshold: int
    action_triggered: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "initial_drift": round(self.initial_drift, 4),
            "drift_velocity": round(self.drift_velocity, 6),
            "threshold": self.threshold,
            "periods_to_threshold": self.periods_to_threshold,
            "action_triggered": self.action_triggered,
        }


@dataclass
class TrustDynamics:
    """Trust dynamics simulation"""
    agent_id: str
    initial_ats: float
    decay_rate: float
    reinforcement: float
    final_ats: float
    tier_change: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "initial_ats": round(self.initial_ats, 2),
            "decay_rate": round(self.decay_rate, 6),
            "reinforcement": round(self.reinforcement, 4),
            "final_ats": round(self.final_ats, 2),
            "tier_change": self.tier_change,
        }


class GovernanceRiskModel:
    """Model governance and risk dynamics"""
    
    DRIFT_THRESHOLDS = {
        "low_risk": 0.5,
        "medium_risk": 0.3,
        "high_risk": 0.15,
        "critical_risk": 0.1,
    }
    
    def simulate_drift(
        self,
        agent_id: str,
        initial_drift: float = 0.05,
        drift_velocity: float = 0.01,
        risk_level: str = "medium_risk",
        periods: int = 10,
    ) -> DriftSimulation:
        """Simulate semantic drift over time"""
        
        threshold = self.DRIFT_THRESHOLDS.get(risk_level, 0.3)
        
        current_drift = initial_drift
        periods_to_threshold = 0
        
        for p in range(periods):
            current_drift += drift_velocity
            if current_drift >= threshold:
                periods_to_threshold = p + 1
                break
        else:
            periods_to_threshold = -1  # Never reaches threshold
        
        action = "none"
        if periods_to_threshold > 0:
            action = "restricted_mode_triggered"
        
        return DriftSimulation(
            agent_id=agent_id,
            initial_drift=initial_drift,
            drift_velocity=drift_velocity,
            threshold=threshold,
            periods_to_threshold=periods_to_threshold,
            action_triggered=action,
        )
    
    def simulate_trust_dynamics(
        self,
        agent_id: str,
        initial_ats: float = 75.0,
        decay_rate: float = 0.001,
        reinforcement: float = 0.5,
        periods: int = 30,
    ) -> TrustDynamics:
        """Simulate trust dynamics: ATS(t+1) = ATS(t) × (1 - decay_rate) + Reinforcement"""
        
        ats = initial_ats
        
        for _ in range(periods):
            ats = ats * (1 - decay_rate) + reinforcement
        
        # Determine tier change
        initial_tier = self._get_tier(initial_ats)
        final_tier = self._get_tier(ats)
        tier_change = None
        if initial_tier != final_tier:
            tier_change = f"{initial_tier} → {final_tier}"
        
        return TrustDynamics(
            agent_id=agent_id,
            initial_ats=initial_ats,
            decay_rate=decay_rate,
            reinforcement=reinforcement,
            final_ats=ats,
            tier_change=tier_change,
        )
    
    def _get_tier(self, ats: float) -> str:
        if ats >= 90:
            return "T5"
        elif ats >= 75:
            return "T4"
        elif ats >= 60:
            return "T3"
        elif ats >= 40:
            return "T2"
        else:
            return "T1"


# ============== EQUILIBRIUM MODEL ==============

@dataclass
class EquilibriumState:
    """Supply-demand equilibrium state"""
    timestamp: int
    supply: float
    demand: float
    equilibrium: bool
    shortage: float
    surplus: float
    recommended_actions: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "supply": round(self.supply, 2),
            "demand": round(self.demand, 2),
            "equilibrium": self.equilibrium,
            "shortage": round(self.shortage, 2),
            "surplus": round(self.surplus, 2),
            "recommended_actions": self.recommended_actions,
        }


class EquilibriumModel:
    """Model supply-demand equilibrium"""
    
    def calculate_equilibrium(
        self,
        supply: float,
        demand: float,
    ) -> EquilibriumState:
        """Calculate equilibrium state"""
        
        equilibrium = supply >= demand
        shortage = max(0, demand - supply)
        surplus = max(0, supply - demand)
        
        actions = []
        if shortage > 0:
            actions.append("Create new agents")
            actions.append("Expand semantic clusters")
            actions.append("Scale compute resources")
            if shortage > demand * 0.2:
                actions.append("Enable auto-generation")
        elif surplus > supply * 0.3:
            actions.append("Reduce auto-generation rate")
            actions.append("Optimize cluster allocation")
        
        return EquilibriumState(
            timestamp=int(time.time() * 1000),
            supply=supply,
            demand=demand,
            equilibrium=equilibrium,
            shortage=shortage,
            surplus=surplus,
            recommended_actions=actions,
        )


# ============== SCENARIO SIMULATOR ==============

@dataclass
class SimulationScenario:
    """A simulation scenario"""
    scenario_id: str
    name: str
    description: str
    agent_count: int
    user_count: int
    org_count: int
    government_scale: float
    industry_multiplier: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "agent_count": self.agent_count,
            "user_count": self.user_count,
            "org_count": self.org_count,
            "government_scale": self.government_scale,
            "industry_multiplier": self.industry_multiplier,
        }


@dataclass
class SimulationResult:
    """Result of a simulation run"""
    scenario: SimulationScenario
    population: PopulationState
    demand: DemandState
    supply: SupplyState
    performance: PerformanceMetrics
    equilibrium: EquilibriumState
    outcome: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario.to_dict(),
            "population": self.population.to_dict(),
            "demand": self.demand.to_dict(),
            "supply": self.supply.to_dict(),
            "performance": self.performance.to_dict(),
            "equilibrium": self.equilibrium.to_dict(),
            "outcome": self.outcome,
        }


class ScenarioSimulator:
    """Run simulation scenarios"""
    
    PREDEFINED_SCENARIOS = {
        "enterprise_50k": SimulationScenario(
            scenario_id="S-001",
            name="Enterprise with 50k Agents",
            description="Mid-size enterprise deployment",
            agent_count=50000,
            user_count=5000,
            org_count=1,
            government_scale=0.0,
            industry_multiplier=1.0,
        ),
        "national_5m": SimulationScenario(
            scenario_id="S-002",
            name="National Workforce with 5M Agents",
            description="National-scale government deployment",
            agent_count=5000000,
            user_count=500000,
            org_count=50,
            government_scale=1.0,
            industry_multiplier=2.0,
        ),
        "global_500m": SimulationScenario(
            scenario_id="S-003",
            name="Global Federation of 500M Agents",
            description="Global federated deployment",
            agent_count=500000000,
            user_count=50000000,
            org_count=5000,
            government_scale=10.0,
            industry_multiplier=5.0,
        ),
    }
    
    def __init__(self):
        self.population_model = PopulationModel()
        self.demand_model = DemandModel()
        self.supply_model = SupplyModel()
        self.performance_model = PerformanceModel()
        self.equilibrium_model = EquilibriumModel()
    
    def run_scenario(self, scenario: SimulationScenario) -> SimulationResult:
        """Run a simulation scenario"""
        
        # Calculate cluster distribution
        cluster_ratios = {
            "A": 0.15, "K": 0.10, "L": 0.12, "C": 0.08,
            "W": 0.20, "S": 0.15, "B": 0.10, "H": 0.03,
            "P": 0.03, "G": 0.02, "M": 0.02,
        }
        cluster_dist = {
            cluster: int(scenario.agent_count * ratio)
            for cluster, ratio in cluster_ratios.items()
        }
        
        # Population state
        population = PopulationState(
            timestamp=int(time.time() * 1000),
            total_agents=scenario.agent_count,
            total_users=scenario.user_count,
            total_organizations=scenario.org_count,
            cluster_distribution=cluster_dist,
            creation_rate=0.5,
            auto_generation_rate=0.1,
        )
        
        # Demand
        demand = self.demand_model.calculate_demand(
            users=scenario.user_count,
            organizations=scenario.org_count,
            industry_multiplier=scenario.industry_multiplier,
            government_scale=scenario.government_scale,
        )
        
        # Supply
        supply = self.supply_model.calculate_supply(cluster_dist)
        
        # Performance
        performance = self.performance_model.calculate_productivity(scenario.agent_count)
        
        # Equilibrium
        equilibrium = self.equilibrium_model.calculate_equilibrium(
            supply.total_supply,
            demand.total_demand,
        )
        
        # Determine outcome
        if equilibrium.equilibrium:
            if equilibrium.surplus > supply.total_supply * 0.2:
                outcome = "stable_with_surplus"
            else:
                outcome = "stable_optimal"
        else:
            if equilibrium.shortage > demand.total_demand * 0.3:
                outcome = "critical_shortage"
            else:
                outcome = "moderate_shortage"
        
        return SimulationResult(
            scenario=scenario,
            population=population,
            demand=demand,
            supply=supply,
            performance=performance,
            equilibrium=equilibrium,
            outcome=outcome,
        )
    
    def get_predefined_scenario(self, name: str) -> Optional[SimulationScenario]:
        return self.PREDEFINED_SCENARIOS.get(name)
    
    def list_predefined_scenarios(self) -> List[SimulationScenario]:
        return list(self.PREDEFINED_SCENARIOS.values())


# ============== GLOBAL GROWTH PROJECTIONS ==============

def get_global_growth_projections() -> List[Dict[str, Any]]:
    """Get projected global agent workforce growth"""
    return [
        {"year": 2025, "agents_low": 50000, "agents_high": 200000},
        {"year": 2027, "agents_low": 5000000, "agents_high": 10000000},
        {"year": 2030, "agents_low": 100000000, "agents_high": 300000000},
        {"year": 2035, "agents_low": 500000000, "agents_high": 3000000000},
    ]


# ============== GLOBAL INSTANCES ==============

population_model = PopulationModel()
demand_model = DemandModel()
supply_model = SupplyModel()
performance_model = PerformanceModel()
governance_risk_model = GovernanceRiskModel()
equilibrium_model = EquilibriumModel()
scenario_simulator = ScenarioSimulator()
