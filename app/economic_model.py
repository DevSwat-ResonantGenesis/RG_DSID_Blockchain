"""
HSU-Spec Section 29: DSID-P Economic Forecasting Model
======================================================

A full simulation model for revenue, growth, adoption, and agent-economy expansion.

Revenue Engines:
1. Agent Marketplace Revenue
2. Enterprise Deployment Revenue
3. Government Sovereign Infrastructure Revenue
4. Platform Usage/API Revenue

Economic Variables:
- U = # of Users
- A = # of Active Agents
- E = # of Enterprise Deployments
- G = # of Government Deployments
- R = Average Revenue per Agent (ARAA)
- S = Marketplace Sales per User
- C = Agent Creation Rate
- L = Lifetime Value per Enterprise Deployment
- P = Platform Usage Revenue

Network Effect Loops:
1. Creator Loop
2. Agent Loop
3. Enterprise Loop
4. Government Loop
"""

import math
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# ============== ECONOMIC VARIABLES ==============

@dataclass
class EconomicVariables:
    """Core economic variables for forecasting"""
    users: int = 0                      # U - number of users
    active_agents: int = 0              # A - active agents
    enterprise_deployments: int = 0     # E - enterprise deployments
    government_deployments: int = 0     # G - government deployments
    avg_revenue_per_agent: float = 0.0  # R - ARAA
    marketplace_sales_per_user: float = 0.0  # S
    agent_creation_rate: float = 0.0    # C - agents per user per period
    enterprise_ltv: float = 0.0         # L - lifetime value
    platform_usage_revenue: float = 0.0 # P
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "users": self.users,
            "active_agents": self.active_agents,
            "enterprise_deployments": self.enterprise_deployments,
            "government_deployments": self.government_deployments,
            "avg_revenue_per_agent": round(self.avg_revenue_per_agent, 2),
            "marketplace_sales_per_user": round(self.marketplace_sales_per_user, 2),
            "agent_creation_rate": round(self.agent_creation_rate, 4),
            "enterprise_ltv": round(self.enterprise_ltv, 2),
            "platform_usage_revenue": round(self.platform_usage_revenue, 2),
        }


# ============== MARKETPLACE REVENUE MODEL ==============

@dataclass
class MarketplaceRevenueConfig:
    """Configuration for marketplace revenue calculation"""
    mint_price: float = 50.0           # Average mint price
    mint_fee_rate: float = 0.05        # Platform fee on minting (5%)
    sale_price: float = 100.0          # Average sale price
    marketplace_fee_rate: float = 0.10 # Platform fee on sales (10%)
    rental_price: float = 25.0         # Average rental price per period
    rental_fee_rate: float = 0.15      # Platform fee on rentals (15%)
    skill_price: float = 20.0          # Average skill/upgrade price
    skill_fee_rate: float = 0.10       # Platform fee on skills (10%)
    a2a_micro_fee: float = 0.001       # Agent-to-agent micro fee
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mint_price": self.mint_price,
            "mint_fee_rate": self.mint_fee_rate,
            "sale_price": self.sale_price,
            "marketplace_fee_rate": self.marketplace_fee_rate,
            "rental_price": self.rental_price,
            "rental_fee_rate": self.rental_fee_rate,
            "skill_price": self.skill_price,
            "skill_fee_rate": self.skill_fee_rate,
            "a2a_micro_fee": self.a2a_micro_fee,
        }


@dataclass
class MarketplaceRevenue:
    """Marketplace revenue breakdown"""
    period: int
    mint_revenue: float
    sales_revenue: float
    rental_revenue: float
    skill_revenue: float
    a2a_revenue: float
    total: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "mint_revenue": round(self.mint_revenue, 2),
            "sales_revenue": round(self.sales_revenue, 2),
            "rental_revenue": round(self.rental_revenue, 2),
            "skill_revenue": round(self.skill_revenue, 2),
            "a2a_revenue": round(self.a2a_revenue, 2),
            "total": round(self.total, 2),
        }


class MarketplaceRevenueCalculator:
    """Calculate marketplace revenue"""
    
    def __init__(self, config: MarketplaceRevenueConfig = None):
        self.config = config or MarketplaceRevenueConfig()
    
    def calculate(
        self,
        period: int,
        agents_minted: int,
        agents_sold: int,
        rental_transactions: int,
        skills_sold: int,
        a2a_interactions: int,
    ) -> MarketplaceRevenue:
        """Calculate marketplace revenue for a period"""
        
        mint_revenue = agents_minted * self.config.mint_price * self.config.mint_fee_rate
        sales_revenue = agents_sold * self.config.sale_price * self.config.marketplace_fee_rate
        rental_revenue = rental_transactions * self.config.rental_price * self.config.rental_fee_rate
        skill_revenue = skills_sold * self.config.skill_price * self.config.skill_fee_rate
        a2a_revenue = a2a_interactions * self.config.a2a_micro_fee
        
        total = mint_revenue + sales_revenue + rental_revenue + skill_revenue + a2a_revenue
        
        return MarketplaceRevenue(
            period=period,
            mint_revenue=mint_revenue,
            sales_revenue=sales_revenue,
            rental_revenue=rental_revenue,
            skill_revenue=skill_revenue,
            a2a_revenue=a2a_revenue,
            total=total,
        )


# ============== ENTERPRISE REVENUE MODEL ==============

@dataclass
class EnterpriseRevenueConfig:
    """Configuration for enterprise revenue calculation"""
    license_fee: float = 50000.0       # Annual SaaS license
    agent_seat_price: float = 100.0    # Price per agent seat per month
    usage_fee_per_op: float = 0.001    # Per-operation usage fee
    avg_agents_per_enterprise: int = 50
    avg_ops_per_agent_month: int = 10000
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "license_fee": self.license_fee,
            "agent_seat_price": self.agent_seat_price,
            "usage_fee_per_op": self.usage_fee_per_op,
            "avg_agents_per_enterprise": self.avg_agents_per_enterprise,
            "avg_ops_per_agent_month": self.avg_ops_per_agent_month,
        }


@dataclass
class EnterpriseRevenue:
    """Enterprise revenue breakdown"""
    period: int
    num_enterprises: int
    license_revenue: float
    agent_fleet_revenue: float
    usage_revenue: float
    total: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "num_enterprises": self.num_enterprises,
            "license_revenue": round(self.license_revenue, 2),
            "agent_fleet_revenue": round(self.agent_fleet_revenue, 2),
            "usage_revenue": round(self.usage_revenue, 2),
            "total": round(self.total, 2),
        }


class EnterpriseRevenueCalculator:
    """Calculate enterprise deployment revenue"""
    
    def __init__(self, config: EnterpriseRevenueConfig = None):
        self.config = config or EnterpriseRevenueConfig()
    
    def calculate(self, period: int, num_enterprises: int) -> EnterpriseRevenue:
        """Calculate enterprise revenue for a period"""
        
        license_revenue = num_enterprises * self.config.license_fee
        
        total_agents = num_enterprises * self.config.avg_agents_per_enterprise
        agent_fleet_revenue = total_agents * self.config.agent_seat_price * 12  # Annual
        
        total_ops = total_agents * self.config.avg_ops_per_agent_month * 12
        usage_revenue = total_ops * self.config.usage_fee_per_op
        
        total = license_revenue + agent_fleet_revenue + usage_revenue
        
        return EnterpriseRevenue(
            period=period,
            num_enterprises=num_enterprises,
            license_revenue=license_revenue,
            agent_fleet_revenue=agent_fleet_revenue,
            usage_revenue=usage_revenue,
            total=total,
        )
    
    def forecast_adoption(
        self,
        max_enterprises: int,
        k: float = 0.5,
        midpoint: int = 5,
        periods: int = 10,
    ) -> List[int]:
        """Forecast enterprise adoption using S-curve model"""
        adoptions = []
        for t in range(1, periods + 1):
            # S-curve: E(t) = MaxEnterprise × (1 / (1 + e^-k(t - midpoint)))
            adoption = int(max_enterprises * (1 / (1 + math.exp(-k * (t - midpoint)))))
            adoptions.append(adoption)
        return adoptions


# ============== GOVERNMENT REVENUE MODEL ==============

@dataclass
class GovernmentRevenueConfig:
    """Configuration for government revenue calculation"""
    sovereign_license_fee: float = 500000.0    # Annual sovereign license
    ministry_deployment_fee: float = 100000.0  # Per ministry/department
    agent_workforce_fee: float = 200.0         # Per agent per month
    infrastructure_usage_fee: float = 50000.0  # Monthly infrastructure
    avg_ministries_per_deployment: int = 5
    avg_agents_per_ministry: int = 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sovereign_license_fee": self.sovereign_license_fee,
            "ministry_deployment_fee": self.ministry_deployment_fee,
            "agent_workforce_fee": self.agent_workforce_fee,
            "infrastructure_usage_fee": self.infrastructure_usage_fee,
            "avg_ministries_per_deployment": self.avg_ministries_per_deployment,
            "avg_agents_per_ministry": self.avg_agents_per_ministry,
        }


@dataclass
class GovernmentRevenue:
    """Government revenue breakdown"""
    period: int
    num_deployments: int
    sovereign_license_revenue: float
    ministry_revenue: float
    agent_workforce_revenue: float
    infrastructure_revenue: float
    total: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "num_deployments": self.num_deployments,
            "sovereign_license_revenue": round(self.sovereign_license_revenue, 2),
            "ministry_revenue": round(self.ministry_revenue, 2),
            "agent_workforce_revenue": round(self.agent_workforce_revenue, 2),
            "infrastructure_revenue": round(self.infrastructure_revenue, 2),
            "total": round(self.total, 2),
        }


class GovernmentRevenueCalculator:
    """Calculate government deployment revenue"""
    
    def __init__(self, config: GovernmentRevenueConfig = None):
        self.config = config or GovernmentRevenueConfig()
    
    def calculate(self, period: int, num_deployments: int) -> GovernmentRevenue:
        """Calculate government revenue for a period"""
        
        sovereign_license_revenue = num_deployments * self.config.sovereign_license_fee
        
        total_ministries = num_deployments * self.config.avg_ministries_per_deployment
        ministry_revenue = total_ministries * self.config.ministry_deployment_fee
        
        total_agents = total_ministries * self.config.avg_agents_per_ministry
        agent_workforce_revenue = total_agents * self.config.agent_workforce_fee * 12  # Annual
        
        infrastructure_revenue = num_deployments * self.config.infrastructure_usage_fee * 12
        
        total = sovereign_license_revenue + ministry_revenue + agent_workforce_revenue + infrastructure_revenue
        
        return GovernmentRevenue(
            period=period,
            num_deployments=num_deployments,
            sovereign_license_revenue=sovereign_license_revenue,
            ministry_revenue=ministry_revenue,
            agent_workforce_revenue=agent_workforce_revenue,
            infrastructure_revenue=infrastructure_revenue,
            total=total,
        )


# ============== PLATFORM USAGE REVENUE ==============

@dataclass
class PlatformUsageRevenue:
    """Platform usage revenue breakdown"""
    period: int
    dag_operations: int
    anchoring_operations: int
    coordination_events: int
    semantic_operations: int
    agent_interactions: int
    total_revenue: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "dag_operations": self.dag_operations,
            "anchoring_operations": self.anchoring_operations,
            "coordination_events": self.coordination_events,
            "semantic_operations": self.semantic_operations,
            "agent_interactions": self.agent_interactions,
            "total_revenue": round(self.total_revenue, 2),
        }


class PlatformUsageCalculator:
    """Calculate platform usage revenue"""
    
    def __init__(
        self,
        dag_op_price: float = 0.0001,
        anchoring_price: float = 0.001,
        coordination_price: float = 0.0005,
        semantic_price: float = 0.0002,
        interaction_price: float = 0.0001,
    ):
        self.dag_op_price = dag_op_price
        self.anchoring_price = anchoring_price
        self.coordination_price = coordination_price
        self.semantic_price = semantic_price
        self.interaction_price = interaction_price
    
    def calculate(
        self,
        period: int,
        active_agents: int,
        ops_per_agent: int = 1000,
    ) -> PlatformUsageRevenue:
        """Calculate platform usage revenue"""
        
        # Estimate operations based on active agents
        dag_operations = active_agents * ops_per_agent
        anchoring_operations = active_agents * int(ops_per_agent * 0.1)
        coordination_events = active_agents * int(ops_per_agent * 0.2)
        semantic_operations = active_agents * int(ops_per_agent * 0.3)
        agent_interactions = active_agents * active_agents * 10  # Quadratic growth
        
        total_revenue = (
            dag_operations * self.dag_op_price +
            anchoring_operations * self.anchoring_price +
            coordination_events * self.coordination_price +
            semantic_operations * self.semantic_price +
            agent_interactions * self.interaction_price
        )
        
        return PlatformUsageRevenue(
            period=period,
            dag_operations=dag_operations,
            anchoring_operations=anchoring_operations,
            coordination_events=coordination_events,
            semantic_operations=semantic_operations,
            agent_interactions=agent_interactions,
            total_revenue=total_revenue,
        )


# ============== COMBINED FORECAST MODEL ==============

@dataclass
class PeriodForecast:
    """Complete forecast for a single period"""
    period: int
    year: int
    marketplace_revenue: float
    enterprise_revenue: float
    government_revenue: float
    platform_revenue: float
    total_revenue: float
    growth_rate: float
    users: int
    active_agents: int
    enterprises: int
    governments: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "year": self.year,
            "marketplace_revenue": round(self.marketplace_revenue, 2),
            "enterprise_revenue": round(self.enterprise_revenue, 2),
            "government_revenue": round(self.government_revenue, 2),
            "platform_revenue": round(self.platform_revenue, 2),
            "total_revenue": round(self.total_revenue, 2),
            "growth_rate": round(self.growth_rate * 100, 2),
            "users": self.users,
            "active_agents": self.active_agents,
            "enterprises": self.enterprises,
            "governments": self.governments,
        }


class EconomicForecastEngine:
    """Complete economic forecasting engine"""
    
    def __init__(self):
        self.marketplace_calc = MarketplaceRevenueCalculator()
        self.enterprise_calc = EnterpriseRevenueCalculator()
        self.government_calc = GovernmentRevenueCalculator()
        self.platform_calc = PlatformUsageCalculator()
        self._forecasts: List[PeriodForecast] = []
    
    def generate_forecast(
        self,
        periods: int = 10,
        initial_users: int = 1000,
        user_growth_rate: float = 1.5,
        agent_creation_rate: float = 0.5,
        max_enterprises: int = 500,
        enterprise_k: float = 0.6,
        enterprise_midpoint: int = 4,
        max_governments: int = 50,
        government_k: float = 0.4,
        government_midpoint: int = 6,
    ) -> List[PeriodForecast]:
        """Generate multi-period economic forecast"""
        
        self._forecasts = []
        prev_revenue = 0
        
        # Pre-calculate adoption curves
        enterprise_adoptions = self.enterprise_calc.forecast_adoption(
            max_enterprises, enterprise_k, enterprise_midpoint, periods
        )
        
        government_adoptions = []
        for t in range(1, periods + 1):
            adoption = int(max_governments * (1 / (1 + math.exp(-government_k * (t - government_midpoint)))))
            government_adoptions.append(adoption)
        
        for period in range(1, periods + 1):
            # Calculate users and agents
            users = int(initial_users * (user_growth_rate ** (period - 1)))
            agents_created = int(users * agent_creation_rate)
            active_agents = sum(
                int(initial_users * (user_growth_rate ** (p - 1)) * agent_creation_rate)
                for p in range(1, period + 1)
            )
            
            # Marketplace revenue
            marketplace = self.marketplace_calc.calculate(
                period=period,
                agents_minted=agents_created,
                agents_sold=int(agents_created * 0.3),
                rental_transactions=int(active_agents * 0.1),
                skills_sold=int(agents_created * 0.5),
                a2a_interactions=active_agents * active_agents,
            )
            
            # Enterprise revenue
            enterprises = enterprise_adoptions[period - 1]
            enterprise = self.enterprise_calc.calculate(period, enterprises)
            
            # Government revenue
            governments = government_adoptions[period - 1]
            government = self.government_calc.calculate(period, governments)
            
            # Platform usage revenue
            platform = self.platform_calc.calculate(period, active_agents)
            
            # Total
            total_revenue = (
                marketplace.total +
                enterprise.total +
                government.total +
                platform.total_revenue
            )
            
            # Growth rate
            growth_rate = (total_revenue - prev_revenue) / prev_revenue if prev_revenue > 0 else 0
            
            forecast = PeriodForecast(
                period=period,
                year=period,
                marketplace_revenue=marketplace.total,
                enterprise_revenue=enterprise.total,
                government_revenue=government.total,
                platform_revenue=platform.total_revenue,
                total_revenue=total_revenue,
                growth_rate=growth_rate,
                users=users,
                active_agents=active_agents,
                enterprises=enterprises,
                governments=governments,
            )
            
            self._forecasts.append(forecast)
            prev_revenue = total_revenue
        
        return self._forecasts
    
    def get_forecast(self, period: int) -> Optional[PeriodForecast]:
        """Get forecast for a specific period"""
        for f in self._forecasts:
            if f.period == period:
                return f
        return None
    
    def get_summary(self) -> Dict[str, Any]:
        """Get forecast summary"""
        if not self._forecasts:
            return {"error": "No forecast generated"}
        
        return {
            "periods": len(self._forecasts),
            "year_1_revenue": round(self._forecasts[0].total_revenue, 2),
            "year_5_revenue": round(self._forecasts[4].total_revenue, 2) if len(self._forecasts) >= 5 else None,
            "year_10_revenue": round(self._forecasts[9].total_revenue, 2) if len(self._forecasts) >= 10 else None,
            "total_10_year_revenue": round(sum(f.total_revenue for f in self._forecasts), 2),
            "avg_growth_rate": round(
                sum(f.growth_rate for f in self._forecasts[1:]) / (len(self._forecasts) - 1) * 100, 2
            ) if len(self._forecasts) > 1 else 0,
            "final_users": self._forecasts[-1].users,
            "final_agents": self._forecasts[-1].active_agents,
            "final_enterprises": self._forecasts[-1].enterprises,
            "final_governments": self._forecasts[-1].governments,
        }


# ============== NETWORK EFFECTS MODEL ==============

@dataclass
class NetworkEffectMetrics:
    """Network effect metrics"""
    creator_loop_strength: float
    agent_loop_strength: float
    enterprise_loop_strength: float
    government_loop_strength: float
    combined_flywheel_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creator_loop_strength": round(self.creator_loop_strength, 4),
            "agent_loop_strength": round(self.agent_loop_strength, 4),
            "enterprise_loop_strength": round(self.enterprise_loop_strength, 4),
            "government_loop_strength": round(self.government_loop_strength, 4),
            "combined_flywheel_score": round(self.combined_flywheel_score, 4),
        }


class NetworkEffectCalculator:
    """Calculate network effect strength"""
    
    def calculate(
        self,
        users: int,
        agents: int,
        enterprises: int,
        governments: int,
        marketplace_revenue: float,
    ) -> NetworkEffectMetrics:
        """Calculate network effect metrics"""
        
        # Creator loop: more creators → more agents → more revenue → more creators
        creator_loop = math.log1p(users) * math.log1p(agents) / 100
        
        # Agent loop: more agents → more interactions → more demand
        agent_loop = (agents * agents) / (1000000 + agents * agents)
        
        # Enterprise loop: more enterprises → more workflow agents → more sales
        enterprise_loop = math.log1p(enterprises) * math.log1p(agents) / 50
        
        # Government loop: more governments → higher trust → more adoption
        government_loop = math.log1p(governments) * math.log1p(enterprises) / 30
        
        # Combined flywheel
        combined = (creator_loop + agent_loop + enterprise_loop + government_loop) / 4
        
        return NetworkEffectMetrics(
            creator_loop_strength=creator_loop,
            agent_loop_strength=agent_loop,
            enterprise_loop_strength=enterprise_loop,
            government_loop_strength=government_loop,
            combined_flywheel_score=combined,
        )


# ============== TAM ANALYSIS ==============

@dataclass
class TAMAnalysis:
    """Total Addressable Market analysis"""
    market_name: str
    tam_value: float  # in billions
    dsidp_relevance: str
    capture_potential: float  # percentage
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "market_name": self.market_name,
            "tam_value_billions": self.tam_value,
            "dsidp_relevance": self.dsidp_relevance,
            "capture_potential_percent": self.capture_potential,
        }


def get_tam_analysis() -> List[TAMAnalysis]:
    """Get TAM analysis for DSID-P markets"""
    return [
        TAMAnalysis(
            market_name="Enterprise AI Agents",
            tam_value=1100.0,
            dsidp_relevance="Core market - agent identity and governance",
            capture_potential=5.0,
        ),
        TAMAnalysis(
            market_name="Government AI Infrastructure",
            tam_value=300.0,
            dsidp_relevance="Sovereign deployment and compliance",
            capture_potential=10.0,
        ),
        TAMAnalysis(
            market_name="Compliance Automation",
            tam_value=150.0,
            dsidp_relevance="Built-in audit and compliance architecture",
            capture_potential=8.0,
        ),
        TAMAnalysis(
            market_name="Workflow Automation",
            tam_value=770.0,
            dsidp_relevance="Agent coordination and workflow DAG",
            capture_potential=3.0,
        ),
        TAMAnalysis(
            market_name="Developer Agent Marketplaces",
            tam_value=200.0,
            dsidp_relevance="Direct marketplace integration",
            capture_potential=15.0,
        ),
    ]


# ============== GLOBAL INSTANCES ==============

forecast_engine = EconomicForecastEngine()
network_effect_calc = NetworkEffectCalculator()
