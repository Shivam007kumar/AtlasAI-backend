from pydantic import BaseModel
from typing import Optional

class Warehouse(BaseModel):
    id: str
    name: str
    throughput_pct: int
    is_congested: bool
    inventory_level_pct: int = 80

class Carrier(BaseModel):
    id: str
    name: str
    success_rate_pct: float
    avg_delay_mins: int
    cost_multiplier: float
    tier: str
    reliability_score: float = 0.0
    vehicle_capacity_pct: int = 80

class Shipment(BaseModel):
    id: str
    origin_id: str
    destination_id: str
    carrier_id: str
    priority: str
    status: str
    promised_eta: str
    current_eta: str
    risk_score: float = 0.0
    predicted_delay: int = 0
    weather_signal: str = "Clear"
    traffic_delay_mins: int = 0
    pickup_delay_mins: int = 0

class CostBreakdown(BaseModel):
    reroute_cost: float
    delay_penalty: float
    sla_risk: float
    total: float

class AgentDecision(BaseModel):
    reasoning: list[str]
    action_type: str
    target_shipment_id: str
    new_carrier_id: str
    cost_breakdown: CostBreakdown
    confidence: float
    requires_approval: bool = False

class ChaosInjectPayload(BaseModel):
    target_id: str
    event: str
    severity_pct: int

class ActionApprovePayload(BaseModel):
    audit_id: str
    approved: bool

class LlmTogglePayload(BaseModel):
    enabled: bool
