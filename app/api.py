from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any

from app.models import ChaosInjectPayload, ActionApprovePayload
from app.database.sqlite_live import get_live_state, inject_chaos, update_shipment_carrier
from app.database.duckdb_olap import get_all_carriers

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "healthy"}


@router.get("/api/state")
async def api_state():
    state = get_live_state()
    carriers = get_all_carriers()
    state["carriers"] = carriers
    return state

@router.post("/api/chaos/inject")
async def api_chaos_inject(payload: ChaosInjectPayload):
    # Action: Updates SQLite Warehouse table to set throughput_pct and is_congested
    inject_chaos(payload.target_id, payload.severity_pct)
    from app.engine import metrics
    metrics["chaos_events"] += 1
    return {"status": "success", "message": f"Chaos injected at {payload.target_id}"}


# Shared memory store for pending actions
pending_actions: Dict[str, Any] = {}

@router.post("/api/action/approve")
async def api_action_approve(payload: ActionApprovePayload):
    if payload.audit_id in pending_actions and payload.approved:
        action = pending_actions.pop(payload.audit_id)
        # Assuming action is AgentDecision dict
        
        # Execute the database swap
        update_shipment_carrier(action['target_shipment_id'], action['new_carrier_id'])
        
        # In a full app, we would emit action_executed here via socket.io, 
        # but the engine will pick up state changes. Or we emit directly.
        from app.main import sio
        await sio.emit('agent_status', {"status": "Human Approval Received. Action Executed."})
        await sio.emit('action_executed', {"message": f"Swapped to {action['new_carrier_id']}. Cost ${action['estimated_cost']}"})
        
        return {"status": "success", "message": "Action approved and executed"}
    
    return {"status": "failed", "message": "Approval failed or not found"}
