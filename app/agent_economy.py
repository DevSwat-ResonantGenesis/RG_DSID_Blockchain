"""
HSU-Spec Section 37: Agent Economy Incentive & Pricing System
=============================================================

Economic structures that power the DSID-P agent marketplace, workforce,
and enterprise/government deployments.

Five Economic Layers:
1. Creation Incentives
2. Marketplace Pricing
3. Agent Workforce Revenue Models
4. Enterprise Billing System
5. Sovereign Licensing & National Pricing

Key Features:
- Non-tokenized, compliant economic engine
- Dynamic pricing based on trust, quality, and demand
- Predictable enterprise contracts
- Sovereign licensing at national scale
- Strong incentives for safe, ethical, stable agent behavior
"""

import math
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ============== PRICING TIERS ==============

class PricingTier(Enum):
    """Agent pricing tiers"""
    TIER_1_BASIC = "tier_1"           # $1-$9
    TIER_2_ADVANCED = "tier_2"        # $10-$49
    TIER_3_PROFESSIONAL = "tier_3"    # $50-$199
    TIER_4_ENTERPRISE = "tier_4"      # $200-$999
    TIER_5_CRITICAL = "tier_5"        # Custom pricing


@dataclass
class PricingTierDefinition:
    """Definition of a pricing tier"""
    tier: PricingTier
    name: str
    price_range: str
    description: str
    typical_use_cases: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier.value,
            "name": self.name,
            "price_range": self.price_range,
            "description": self.description,
            "typical_use_cases": self.typical_use_cases,
        }


PRICING_TIERS = {
    PricingTier.TIER_1_BASIC: PricingTierDefinition(
        tier=PricingTier.TIER_1_BASIC,
        name="Basic Agents",
        price_range="$1-$9",
        description="Lightweight functions, high volume sales",
        typical_use_cases=["Simple automation", "Basic queries", "Notifications"],
    ),
    PricingTier.TIER_2_ADVANCED: PricingTierDefinition(
        tier=PricingTier.TIER_2_ADVANCED,
        name="Advanced Agents",
        price_range="$10-$49",
        description="Multi-step workflows",
        typical_use_cases=["Data processing", "Report generation", "Integration tasks"],
    ),
    PricingTier.TIER_3_PROFESSIONAL: PricingTierDefinition(
        tier=PricingTier.TIER_3_PROFESSIONAL,
        name="Professional Agents",
        price_range="$50-$199",
        description="Specialized domains, high reliability required",
        typical_use_cases=["Analytics", "Complex workflows", "Domain expertise"],
    ),
    PricingTier.TIER_4_ENTERPRISE: PricingTierDefinition(
        tier=PricingTier.TIER_4_ENTERPRISE,
        name="Enterprise Agents",
        price_range="$200-$999",
        description="Compliance-heavy domains",
        typical_use_cases=["Financial processing", "Legal analysis", "Healthcare admin"],
    ),
    PricingTier.TIER_5_CRITICAL: PricingTierDefinition(
        tier=PricingTier.TIER_5_CRITICAL,
        name="Critical Agents",
        price_range="Custom",
        description="Governments, banks, regulated sectors",
        typical_use_cases=["National infrastructure", "Critical systems", "Sovereign deployments"],
    ),
}


# ============== CREATOR REVENUE STREAMS ==============

class RevenueStream(Enum):
    """Creator revenue streams"""
    AGENT_SALES = "agent_sales"
    AGENT_RENTALS = "agent_rentals"
    SKILL_SALES = "skill_sales"
    USAGE_ROYALTIES = "usage_royalties"
    ENTERPRISE_LICENSING = "enterprise_licensing"
    MARKETPLACE_REWARDS = "marketplace_rewards"


@dataclass
class RevenueStreamDefinition:
    """Definition of a revenue stream"""
    stream: RevenueStream
    name: str
    description: str
    typical_rate: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "stream": self.stream.value,
            "name": self.name,
            "description": self.description,
            "typical_rate": self.typical_rate,
        }


REVENUE_STREAMS = [
    RevenueStreamDefinition(
        stream=RevenueStream.AGENT_SALES,
        name="Agent Sales",
        description="Users buy the agent once",
        typical_rate="Full price",
    ),
    RevenueStreamDefinition(
        stream=RevenueStream.AGENT_RENTALS,
        name="Agent Rentals",
        description="Subscription-style access",
        typical_rate="Monthly fee",
    ),
    RevenueStreamDefinition(
        stream=RevenueStream.SKILL_SALES,
        name="Skill/Module Sales",
        description="Add-ons that extend agents",
        typical_rate="$5-$50 per skill",
    ),
    RevenueStreamDefinition(
        stream=RevenueStream.USAGE_ROYALTIES,
        name="Usage Royalties",
        description="When agent performs tasks for enterprises",
        typical_rate="20-40% of task fee",
    ),
    RevenueStreamDefinition(
        stream=RevenueStream.ENTERPRISE_LICENSING,
        name="Enterprise Licensing",
        description="Enterprise deploys agent fleets at scale",
        typical_rate="Volume discounts",
    ),
    RevenueStreamDefinition(
        stream=RevenueStream.MARKETPLACE_REWARDS,
        name="Marketplace Rewards",
        description="Top trusted agents get exposure bonuses",
        typical_rate="Performance-based",
    ),
]


# ============== DYNAMIC PRICING MODEL ==============

@dataclass
class PricingFactors:
    """Factors that affect agent pricing"""
    quality_score: float      # QS: 0-100
    trust_score: float        # ATS: 0-100
    semantic_risk_class: int  # SRC: 1-5
    demand_factor: float      # DE: 0.5-2.0
    complexity_multiplier: float  # CC: 1.0-3.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "quality_score": round(self.quality_score, 2),
            "trust_score": round(self.trust_score, 2),
            "semantic_risk_class": self.semantic_risk_class,
            "demand_factor": round(self.demand_factor, 2),
            "complexity_multiplier": round(self.complexity_multiplier, 2),
        }


class DynamicPricingEngine:
    """Calculate dynamic agent prices"""
    
    # ATS multipliers by tier
    ATS_MULTIPLIERS = {
        "T5": 1.8, "T4": 1.5, "T3": 1.2, "T2": 0.9, "T1": 0.5,
    }
    
    # Risk class multipliers
    RISK_MULTIPLIERS = {
        1: 1.0, 2: 1.2, 3: 1.5, 4: 2.0, 5: 3.0,
    }
    
    def calculate_price(
        self,
        base_price: float,
        factors: PricingFactors,
    ) -> Dict[str, Any]:
        """Calculate dynamic price: BasePrice × QS × ATS_multiplier × DemandFactor × ComplexityMultiplier"""
        
        # Quality score factor (0.5 - 1.5)
        qs_factor = 0.5 + (factors.quality_score / 100)
        
        # ATS multiplier
        ats_tier = self._get_trust_tier(factors.trust_score)
        ats_multiplier = self.ATS_MULTIPLIERS.get(ats_tier, 1.0)
        
        # Risk multiplier
        risk_multiplier = self.RISK_MULTIPLIERS.get(factors.semantic_risk_class, 1.0)
        
        # Calculate final price
        final_price = (
            base_price *
            qs_factor *
            ats_multiplier *
            factors.demand_factor *
            factors.complexity_multiplier *
            risk_multiplier
        )
        
        return {
            "base_price": base_price,
            "final_price": round(final_price, 2),
            "factors": factors.to_dict(),
            "multipliers_applied": {
                "quality_factor": round(qs_factor, 2),
                "ats_multiplier": ats_multiplier,
                "ats_tier": ats_tier,
                "risk_multiplier": risk_multiplier,
                "demand_factor": factors.demand_factor,
                "complexity_multiplier": factors.complexity_multiplier,
            },
        }
    
    def _get_trust_tier(self, ats: float) -> str:
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
    
    def get_tier_for_price(self, price: float) -> PricingTier:
        """Determine pricing tier based on price"""
        if price < 10:
            return PricingTier.TIER_1_BASIC
        elif price < 50:
            return PricingTier.TIER_2_ADVANCED
        elif price < 200:
            return PricingTier.TIER_3_PROFESSIONAL
        elif price < 1000:
            return PricingTier.TIER_4_ENTERPRISE
        else:
            return PricingTier.TIER_5_CRITICAL


# ============== TASK-BASED REVENUE ==============

@dataclass
class TaskRevenue:
    """Revenue from a task execution"""
    task_id: str
    agent_id: str
    task_fee: float
    platform_fee: float
    creator_royalty: float
    creator_royalty_rate: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "task_fee": round(self.task_fee, 4),
            "platform_fee": round(self.platform_fee, 4),
            "creator_royalty": round(self.creator_royalty, 4),
            "creator_royalty_rate": round(self.creator_royalty_rate, 2),
        }


class TaskRevenueCalculator:
    """Calculate task-based revenue"""
    
    # Trust-weighted royalty multipliers
    TRUST_ROYALTY_MULTIPLIERS = {
        "T5": 1.8, "T4": 1.5, "T3": 1.2, "T2": 0.9, "T1": 0.5,
    }
    
    def __init__(
        self,
        base_task_fee: float = 0.005,
        platform_fee_rate: float = 0.30,
        base_royalty_rate: float = 0.30,
    ):
        self.base_task_fee = base_task_fee
        self.platform_fee_rate = platform_fee_rate
        self.base_royalty_rate = base_royalty_rate
    
    def calculate_task_revenue(
        self,
        agent_id: str,
        task_complexity: float = 1.0,
        trust_tier: str = "T3",
    ) -> TaskRevenue:
        """Calculate revenue for a single task"""
        
        # Task fee based on complexity
        task_fee = self.base_task_fee * task_complexity
        
        # Platform fee
        platform_fee = task_fee * self.platform_fee_rate
        
        # Creator royalty with trust multiplier
        trust_multiplier = self.TRUST_ROYALTY_MULTIPLIERS.get(trust_tier, 1.0)
        royalty_rate = self.base_royalty_rate * trust_multiplier
        creator_royalty = task_fee * royalty_rate
        
        return TaskRevenue(
            task_id=str(uuid.uuid4()),
            agent_id=agent_id,
            task_fee=task_fee,
            platform_fee=platform_fee,
            creator_royalty=creator_royalty,
            creator_royalty_rate=royalty_rate,
        )
    
    def calculate_workflow_revenue(
        self,
        agent_ids: List[str],
        task_complexities: List[float],
        trust_tiers: List[str],
    ) -> Dict[str, Any]:
        """Calculate revenue for a multi-agent workflow"""
        
        revenues = []
        total_task_fees = 0
        total_platform_fees = 0
        total_royalties = 0
        
        for agent_id, complexity, tier in zip(agent_ids, task_complexities, trust_tiers):
            rev = self.calculate_task_revenue(agent_id, complexity, tier)
            revenues.append(rev.to_dict())
            total_task_fees += rev.task_fee
            total_platform_fees += rev.platform_fee
            total_royalties += rev.creator_royalty
        
        return {
            "workflow_id": str(uuid.uuid4()),
            "agent_count": len(agent_ids),
            "task_revenues": revenues,
            "totals": {
                "total_task_fees": round(total_task_fees, 4),
                "total_platform_fees": round(total_platform_fees, 4),
                "total_royalties": round(total_royalties, 4),
            },
        }


# ============== ENTERPRISE BILLING ==============

class EnterpriseBillingMode(Enum):
    """Enterprise billing modes"""
    AGENT_SEAT = "agent_seat"
    USAGE_BASED = "usage_based"
    WORKFLOW_TIER = "workflow_tier"
    MARKETPLACE_LICENSE = "marketplace_license"


@dataclass
class EnterpriseBillingConfig:
    """Enterprise billing configuration"""
    billing_mode: EnterpriseBillingMode
    agent_seat_price: float = 1.0  # per agent per month
    dag_write_price: float = 0.0001
    semantic_processing_price: float = 0.0005
    workflow_event_price: float = 0.0002
    governance_check_price: float = 0.0001
    registry_anchoring_price: float = 0.001
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "billing_mode": self.billing_mode.value,
            "agent_seat_price": self.agent_seat_price,
            "dag_write_price": self.dag_write_price,
            "semantic_processing_price": self.semantic_processing_price,
            "workflow_event_price": self.workflow_event_price,
            "governance_check_price": self.governance_check_price,
            "registry_anchoring_price": self.registry_anchoring_price,
        }


@dataclass
class EnterpriseBill:
    """An enterprise bill"""
    bill_id: str
    enterprise_id: str
    period: str
    billing_mode: EnterpriseBillingMode
    agent_count: int
    usage_breakdown: Dict[str, Any]
    subtotal: float
    platform_fee: float
    creator_royalties: float
    total: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "bill_id": self.bill_id,
            "enterprise_id": self.enterprise_id,
            "period": self.period,
            "billing_mode": self.billing_mode.value,
            "agent_count": self.agent_count,
            "usage_breakdown": self.usage_breakdown,
            "subtotal": round(self.subtotal, 2),
            "platform_fee": round(self.platform_fee, 2),
            "creator_royalties": round(self.creator_royalties, 2),
            "total": round(self.total, 2),
        }


class EnterpriseBillingEngine:
    """Calculate enterprise billing"""
    
    def calculate_seat_billing(
        self,
        enterprise_id: str,
        agent_count: int,
        seat_price: float = 1.0,
        period: str = "monthly",
    ) -> EnterpriseBill:
        """Calculate agent seat-based billing"""
        
        subtotal = agent_count * seat_price
        platform_fee = subtotal * 0.1
        creator_royalties = subtotal * 0.2
        total = subtotal + platform_fee
        
        return EnterpriseBill(
            bill_id=str(uuid.uuid4()),
            enterprise_id=enterprise_id,
            period=period,
            billing_mode=EnterpriseBillingMode.AGENT_SEAT,
            agent_count=agent_count,
            usage_breakdown={
                "agent_seats": agent_count,
                "price_per_seat": seat_price,
            },
            subtotal=subtotal,
            platform_fee=platform_fee,
            creator_royalties=creator_royalties,
            total=total,
        )
    
    def calculate_usage_billing(
        self,
        enterprise_id: str,
        agent_count: int,
        dag_writes: int,
        semantic_ops: int,
        workflow_events: int,
        governance_checks: int,
        registry_anchorings: int,
        config: EnterpriseBillingConfig,
        period: str = "monthly",
    ) -> EnterpriseBill:
        """Calculate usage-based billing"""
        
        dag_cost = dag_writes * config.dag_write_price
        semantic_cost = semantic_ops * config.semantic_processing_price
        workflow_cost = workflow_events * config.workflow_event_price
        governance_cost = governance_checks * config.governance_check_price
        registry_cost = registry_anchorings * config.registry_anchoring_price
        
        subtotal = dag_cost + semantic_cost + workflow_cost + governance_cost + registry_cost
        platform_fee = subtotal * 0.1
        creator_royalties = subtotal * 0.15
        total = subtotal + platform_fee
        
        return EnterpriseBill(
            bill_id=str(uuid.uuid4()),
            enterprise_id=enterprise_id,
            period=period,
            billing_mode=EnterpriseBillingMode.USAGE_BASED,
            agent_count=agent_count,
            usage_breakdown={
                "dag_writes": {"count": dag_writes, "cost": round(dag_cost, 2)},
                "semantic_ops": {"count": semantic_ops, "cost": round(semantic_cost, 2)},
                "workflow_events": {"count": workflow_events, "cost": round(workflow_cost, 2)},
                "governance_checks": {"count": governance_checks, "cost": round(governance_cost, 2)},
                "registry_anchorings": {"count": registry_anchorings, "cost": round(registry_cost, 2)},
            },
            subtotal=subtotal,
            platform_fee=platform_fee,
            creator_royalties=creator_royalties,
            total=total,
        )
    
    def estimate_enterprise_cost(
        self,
        agent_count: int,
        workflows_per_day: int,
    ) -> Dict[str, Any]:
        """Estimate monthly enterprise cost"""
        
        # Estimate based on typical usage patterns
        monthly_workflows = workflows_per_day * 30
        dag_writes = agent_count * 1000  # 1000 writes per agent per month
        semantic_ops = agent_count * 500
        workflow_events = monthly_workflows * 5  # 5 events per workflow
        governance_checks = agent_count * 100
        registry_anchorings = agent_count * 10
        
        config = EnterpriseBillingConfig(billing_mode=EnterpriseBillingMode.USAGE_BASED)
        
        usage_cost = (
            dag_writes * config.dag_write_price +
            semantic_ops * config.semantic_processing_price +
            workflow_events * config.workflow_event_price +
            governance_checks * config.governance_check_price +
            registry_anchorings * config.registry_anchoring_price
        )
        
        seat_cost = agent_count * 1.0  # $1 per agent
        
        return {
            "agent_count": agent_count,
            "workflows_per_day": workflows_per_day,
            "estimated_monthly_cost": {
                "seat_based": round(seat_cost, 2),
                "usage_based": round(usage_cost, 2),
                "recommended": round(min(seat_cost, usage_cost), 2),
            },
            "cost_range": f"${int(min(seat_cost, usage_cost) * 0.8):,} - ${int(max(seat_cost, usage_cost) * 1.2):,}",
        }


# ============== SOVEREIGN LICENSING ==============

@dataclass
class SovereignLicense:
    """A sovereign/national license"""
    license_id: str
    nation_name: str
    population_tier: str  # "small", "medium", "large"
    base_license_fee: float
    ministry_fees: float
    workflow_fees: float
    semantic_fees: float
    oversight_fees: float
    total_annual: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "license_id": self.license_id,
            "nation_name": self.nation_name,
            "population_tier": self.population_tier,
            "base_license_fee": round(self.base_license_fee, 2),
            "ministry_fees": round(self.ministry_fees, 2),
            "workflow_fees": round(self.workflow_fees, 2),
            "semantic_fees": round(self.semantic_fees, 2),
            "oversight_fees": round(self.oversight_fees, 2),
            "total_annual": round(self.total_annual, 2),
        }


class SovereignLicensingEngine:
    """Calculate sovereign/national licensing"""
    
    # Base fees by population tier
    BASE_FEES = {
        "small": 2000000,    # $2M - 2M population
        "medium": 5000000,   # $5M - 10M population
        "large": 10000000,   # $10M - 30M+ population
    }
    
    # Ministry deployment fees
    MINISTRY_FEE = 500000  # $500K per ministry
    
    def calculate_license(
        self,
        nation_name: str,
        population_tier: str,
        ministry_count: int = 5,
        workflow_scale: float = 1.0,
    ) -> SovereignLicense:
        """Calculate sovereign license pricing"""
        
        base_fee = self.BASE_FEES.get(population_tier, 5000000)
        ministry_fees = ministry_count * self.MINISTRY_FEE
        workflow_fees = base_fee * 0.3 * workflow_scale
        semantic_fees = base_fee * 0.2
        oversight_fees = base_fee * 0.1
        
        total = base_fee + ministry_fees + workflow_fees + semantic_fees + oversight_fees
        
        return SovereignLicense(
            license_id=str(uuid.uuid4()),
            nation_name=nation_name,
            population_tier=population_tier,
            base_license_fee=base_fee,
            ministry_fees=ministry_fees,
            workflow_fees=workflow_fees,
            semantic_fees=semantic_fees,
            oversight_fees=oversight_fees,
            total_annual=total,
        )
    
    def get_pricing_scenarios(self) -> List[Dict[str, Any]]:
        """Get example pricing scenarios"""
        return [
            {
                "scenario": "Small Country (2M population)",
                "total_range": "$3M - $6M/year",
                "components": ["Base license", "3-5 ministries", "Basic workflows"],
            },
            {
                "scenario": "Medium Country (10M population)",
                "total_range": "$8M - $20M/year",
                "components": ["Base license", "8-12 ministries", "Advanced workflows", "Semantic sovereignty"],
            },
            {
                "scenario": "Large Digital Nation (30M+ population)",
                "total_range": "$20M - $50M/year",
                "components": ["Base license", "15+ ministries", "Full automation", "Federation ready"],
            },
        ]


# ============== INCENTIVE LOOPS ==============

@dataclass
class IncentiveLoop:
    """An incentive loop in the economy"""
    loop_id: str
    name: str
    description: str
    stages: List[str]
    outcome: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "name": self.name,
            "description": self.description,
            "stages": self.stages,
            "outcome": self.outcome,
        }


INCENTIVE_LOOPS = [
    IncentiveLoop(
        loop_id="IL-001",
        name="Quality Loop",
        description="High-quality agents earn more, incentivizing better designs",
        stages=[
            "High-quality agents",
            "Higher trust scores",
            "Higher pricing",
            "More buyers",
            "More incentives",
            "Even better agents",
        ],
        outcome="Continuous quality improvement",
    ),
    IncentiveLoop(
        loop_id="IL-002",
        name="Compliance Loop",
        description="Governance-compliant agents gain enterprise trust",
        stages=[
            "Governance-compliant agents",
            "Trusted by enterprises",
            "Enterprise purchases",
            "National adoption",
            "Marketplace growth",
        ],
        outcome="Enterprise ecosystem expansion",
    ),
    IncentiveLoop(
        loop_id="IL-003",
        name="Workforce Loop",
        description="More tasks generate more revenue for creators",
        stages=[
            "More tasks",
            "More fees",
            "More royalties",
            "More creator engagement",
            "More agents",
        ],
        outcome="Growing agent workforce",
    ),
    IncentiveLoop(
        loop_id="IL-004",
        name="Enterprise Loop",
        description="Enterprise adoption drives creator investment",
        stages=[
            "Enterprise adoption",
            "Predictable revenue",
            "Creators build enterprise-grade agents",
            "Enterprise ecosystem grows",
        ],
        outcome="Enterprise-grade ecosystem",
    ),
]


# ============== GLOBAL INSTANCES ==============

dynamic_pricing_engine = DynamicPricingEngine()
task_revenue_calculator = TaskRevenueCalculator()
enterprise_billing_engine = EnterpriseBillingEngine()
sovereign_licensing_engine = SovereignLicensingEngine()
