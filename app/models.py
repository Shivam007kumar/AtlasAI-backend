from pydantic import BaseModel
from typing import Optional

class Warehouse(BaseModel):
    id: str
    name: str
    throughput_pct: int
    is_congested: bool

class Carrier(BaseModel):
    id: str
    name: str
    success_rate_pct: float
    avg_delay_mins: int
    cost_multiplier: float
    tier: str

class Shipment(BaseModel):
    id: str
    origin_id: str
    destination_id: str
    carrier_id: str
    priority: str
    status: str
    promised_eta: str
    current_eta: str

class AgentDecision(BaseModel):
    thought_process: str
    action_type: str
    target_shipment_id: str
    new_carrier_id: str
    estimated_cost: float
    requires_approval: bool

class ChaosInjectPayload(BaseModel):
    target_id: str
    event: str
    severity_pct: int

class ActionApprovePayload(BaseModel):
    audit_id: str
    approved: bool

class LlmTogglePayload(BaseModel):
    enabled: bool
