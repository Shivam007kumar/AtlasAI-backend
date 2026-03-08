import asyncio
import json
import time
import requests
import os
import datetime
from app.database.sqlite_live import get_live_state, update_shipment_carrier, update_shipment_eta
from app.database.duckdb_olap import get_top_carriers, log_action, get_all_carriers
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
LLM_MODEL = "openrouter/free" 

from app.simulation.throughput_simulator import simulate_realistic_throughput
from app.simulation.shipment_lifecycle import update_shipment_status
from app.database.sqlite_live import update_hub_throughput, update_shipment_lifecycle
from app.ml.eta_predictor import eta_predictor_model
from app.ml.anomaly_detector import anomaly_detector_model
from app.ml.risk_classifier import risk_classifier_model

# Global metrics tracker
metrics = {
    "state_syncs": 0,
    "ml_inferences": 0,
    "llm_calls": 0,
    "chaos_events": 0
}

# Global config state
config_state = {
    "llm_enabled": True
}

async def start_engine(sio):
    print("Initializing Core Engine ML Models...")
    try:
        eta_predictor_model.load()
        anomaly_detector_model.load()
        risk_classifier_model.load()
        print("ML Models loaded successfully.")
    except Exception as e:
        print(f"Machine Learning load skipped / failed: {e}")
        
    print("Engine Loop Started...")
    while True:
        try:
            await engine_tick(sio)
        except Exception as e:
            print(f"Error in engine loop: {e}")
        await sio.emit('agent_status', {"status": "Idle. Monitoring Data Stream..."})
        await asyncio.sleep(15)

async def engine_tick(sio):
    await sio.emit('agent_status', {"status": "Simulating Logistics Flow..."})
    state = get_live_state()
    current_time = datetime.datetime.now(datetime.timezone.utc)
    
    # Run Background Simulations
    for wh in state['warehouses']:
        new_pct = simulate_realistic_throughput(wh['throughput_pct'], current_time)
        if new_pct != wh['throughput_pct']:
            update_hub_throughput(wh['id'], new_pct)
            
    for s in state['shipments']:
        new_status = update_shipment_status(s, current_time)
        if new_status != s['status']:
            update_shipment_lifecycle(s['id'], new_status)
    
    # Reload fresh state
    state = get_live_state()
    from app.api import api_state
    full_state = await api_state()
    
    # Pre-fetch carriers for lookups
    all_carriers = get_all_carriers()
    carrier_lookup = {c['id']: c for c in all_carriers}
    top_carriers = all_carriers[:3]
    
    metrics["state_syncs"] += 1
    await sio.emit('metrics_update', metrics)
    await sio.emit('sync_state', full_state)
    
    # 1. Dynamic ETA Updates (Spec requirement)
    for s in state['shipments']:
        if s['status'] == 'in_transit':
            origin_wh = next((w for w in state['warehouses'] if w['id'] == s['origin_id']), None)
            assigned_c = carrier_lookup.get(s['carrier_id'])
            
            if origin_wh and assigned_c:
                delay_mins = eta_predictor_model.predict_delay_minutes(
                    s['priority'],
                    origin_wh['throughput_pct'],
                    assigned_c['success_rate_pct']
                )
                
                # Add environmental signals
                delay_mins += s.get('traffic_delay_mins', 0)
                delay_mins += s.get('pickup_delay_mins', 0)
                if s.get('weather_signal') == 'Monsoon':
                    delay_mins += 45
                
                # Based on delay_mins, update current_eta
                # Parse promised_eta and add delay
                try:
                    promised_dt = datetime.datetime.fromisoformat(s['promised_eta'].replace('Z', '+00:00'))
                    new_eta_dt = promised_dt + datetime.timedelta(minutes=delay_mins)
                    new_eta_str = new_eta_dt.isoformat().replace('+00:00', 'Z')
                    
                    if new_eta_str != s['current_eta']:
                        update_shipment_eta(s['id'], new_eta_str)
                except Exception as e:
                    print(f"Error updating ETA for {s['id']}: {e}")

    anomalies = []
    high_risk_shipments = []
    
    await sio.emit('agent_status', {"status": "Scanning for Anomalies (ML Watchtower)..."})
    
    # 2. Watchtower + ML Anomaly Detection Loop
    for wh in state['warehouses']:
        # Replace hardcoded threshold with isolation forest classifier
        ml_eval = anomaly_detector_model.detect(wh['throughput_pct'])
        metrics["ml_inferences"] += 1
        
        if ml_eval['is_anomaly']:
            anomalies.append(wh)
            await sio.emit('watchtower_alert', {
                "message": f"ML Anomaly (Conf: {ml_eval['confidence']}): Hub {wh['id']}",
                "node_id": wh['id']
            })
            
    # Cascading Failure Emergency Override
    if len(anomalies) >= 2:
        await sio.emit('watchtower_alert', {
            "message": f"CASCADING FAILURE DETECTED: {len(anomalies)} warehouses congested simultaneously.",
            "node_id": "SYSTEM_WIDE"
        })
            
    await sio.emit('agent_status', {"status": "Evaluating Shipment Risk Models..."})
            
    # 3. Shipment Risk Classification Loop
    # (top_carriers and carrier_lookup moved to top of function)
            
    for s in state['shipments']:
        if s['status'] == 'in_transit':
            # Identify underlying dynamic variables
            origin_wh = next((w for w in state['warehouses'] if w['id'] == s['origin_id']), None)
            assigned_c = carrier_lookup.get(s['carrier_id'])
            
            if origin_wh and assigned_c:
                risk_prob = risk_classifier_model.predict_risk_probability(
                    origin_wh['throughput_pct'], 
                    assigned_c['success_rate_pct'], 
                    s['priority']
                )
                metrics["ml_inferences"] += 1
                
                # Dynamic ETA Modeling
                predicted_delay_mins = eta_predictor_model.predict_delay_minutes(
                    s['priority'], 
                    origin_wh['throughput_pct'], 
                    assigned_c['success_rate_pct']
                )
                predicted_delay_mins += s.get('traffic_delay_mins', 0)
                predicted_delay_mins += s.get('pickup_delay_mins', 0)
                if s.get('weather_signal') == 'Monsoon':
                    predicted_delay_mins += 45
                metrics["ml_inferences"] += 1
                
                if risk_prob > 0.8:  # 80%+ chance of failure even if hub isn't strictly an 'anomaly'
                    high_risk_shipments.append({"shipment": s, "risk": risk_prob, "delay": predicted_delay_mins})
                    
                # Save computed metrics to live DB for frontend consumption
                from app.database.sqlite_live import update_shipment_risk
                if risk_prob != s.get('risk_score', 0.0) or predicted_delay_mins != s.get('predicted_delay', 0):
                    update_shipment_risk(s['id'], risk_prob, int(predicted_delay_mins))

    # Graph-Aware Cascading Failure Detection
    warehouse_risk_counts = {}
    for element in high_risk_shipments:
        w_id = element['shipment']['origin_id']
        warehouse_risk_counts[w_id] = warehouse_risk_counts.get(w_id, 0) + 1
        
    for w_id, count in warehouse_risk_counts.items():
        if count >= 3:
            await sio.emit('watchtower_alert', {
                "message": f"GRAPH BOTTLENECK: Hub {w_id} has {count} cascading high-risk shipments.",
                "node_id": w_id
            })
            if not any(a['id'] == w_id for a in anomalies):
                wh = next((w for w in state['warehouses'] if w['id'] == w_id), None)
                if wh: anomalies.append(wh)

    # Combine strict anomalies with high risk ML shipments
    for anomaly in anomalies:
        wh_id = anomaly['id']
        impacted_shipments = [s for s in state['shipments'] if s['origin_id'] == wh_id and s['status'] == 'in_transit']
        
        if not impacted_shipments:
            continue
            
        target_shipment = impacted_shipments[0]
        
        await sio.emit('agent_status', {"status": "Anomaly Detected! Querying OLAP Carrier Database..."})
        await sio.emit('agent_stream', {"chunk": f"ML Sequence Anomaly detected at {wh_id}. Assessing carrier success rates... "})
        await asyncio.sleep(1) 
        
        prompt = f"""
ANOMALY CONTEXT:
- Warehouse: {wh_id} is operating at ({anomaly['throughput_pct']}%) throughput.
- Warehouse Inventory Level: {anomaly.get('inventory_level_pct', 80)}%
- Target Shipment ID: {target_shipment['id']}
- Priority: {target_shipment['priority']}
- Weather Signal: {target_shipment.get('weather_signal', 'Clear')}
- Traffic Delay: {target_shipment.get('traffic_delay_mins', 0)} mins
- Pickup Delay: {target_shipment.get('pickup_delay_mins', 0)} mins
- Identified high-risk shipments system-wide: {len(high_risk_shipments)}

CARRIER OPTIONS:
{json.dumps(top_carriers, indent=2)}

CONSTRAINTS:
- Use your multi-factor reasoning to decide if we should reroute the carrier.
- Try to balance maintaining SLA for High priority shipments with cost for Medium/Low.
- Decide an action type: "reroute_carrier" or "priority_boost".
- Calculate an economic optimization cost via a cost_breakdown dictionary.
- Supply a confidence score (0.0 to 1.0).

You must output ONLY valid JSON matching this schema exactly:
{{
  "reasoning": [
    "Insight 1 explaining the risk",
    "Insight 2 explaining why this carrier was chosen"
  ],
  "action_type": "reroute_carrier", 
  "target_shipment_id": "{target_shipment['id']}",
  "new_carrier_id": "ID_HERE", // MUST BE THE EXACT String ID like 'C_BLUEDART'
  "cost_breakdown": {{
    "reroute_cost": 50.0,
    "delay_penalty": 25.0,
    "sla_risk": 15.0,
    "total": 90.0
  }},
  "confidence": 0.95,
  "requires_approval": true
}}
        """

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Atlas Agent Control Tower",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": "You output only RAW JSON."},
                {"role": "user", "content": prompt}
            ],
            "stream": True 
        }
        
        await sio.emit('agent_status', {"status": "Consulting Cognitive Agent for Rerouting Strategy..."})
        
        decision = None
        
        if not OPENROUTER_API_KEY or not config_state["llm_enabled"]:
            mock_text = f'Anomalies detected. I propose rerouting shipment {target_shipment["id"]} to {top_carriers[0]["name"]}.'
            for word in mock_text.split():
                await sio.emit('agent_stream', {"chunk": word + " "})
                await asyncio.sleep(0.1)
                
            decision = {
                "reasoning": [mock_text, "Selected highest reliability carrier."],
                "action_type": "reroute_carrier",
                "target_shipment_id": target_shipment['id'],
                "new_carrier_id": top_carriers[0]['id'],
                "cost_breakdown": {
                    "reroute_cost": 60.0,
                    "delay_penalty": 20.0,
                    "sla_risk": 10.0,
                    "total": 90.0
                },
                "confidence": 0.85,
                "requires_approval": True
            }
            metrics["llm_calls"] += 1 # Tracking mock calls too for visibility
            await sio.emit('agent_stream', {"chunk": "\n\n"})
        else:
            try:
                metrics["llm_calls"] += 1
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    stream=True,
                    timeout=15
                )

                if response.status_code != 200:
                    error_data = response.text
                    await sio.emit('agent_stream', {"chunk": f"\n\n[ERROR] OpenRouter API Error ({response.status_code}): {error_data[:100]}...\n"})
                    continue
                
                full_reply = ""
                for line in response.iter_lines():
                    if line:
                        decoded = line.decode('utf-8')
                        if decoded.startswith("data: ") and decoded != "data: [DONE]":
                            try:
                                chunk_data = json.loads(decoded[6:])
                                content_chunk = chunk_data['choices'][0]['delta'].get('content', '')
                                if content_chunk:
                                    full_reply += content_chunk
                                    await sio.emit('agent_stream', {"chunk": content_chunk})
                            except Exception:
                                pass
                
                await sio.emit('agent_stream', {"chunk": "\n\n"})
                
                full_reply = full_reply.strip()
                if not full_reply:
                    await sio.emit('agent_stream', {"chunk": "\n\n[ERROR] LLM returned an empty response.\n"})
                    continue

                if full_reply.startswith("```json"):
                    full_reply = full_reply[7:-3].strip()
                elif full_reply.startswith("```"):
                    full_reply = full_reply[3:-3].strip()
                    
                decision = json.loads(full_reply)
            except Exception as e:
                await sio.emit('agent_stream', {"chunk": f"\n\nError during LLM processing: {str(e)}\n"})
                print(f"LLM Error: {str(e)}")
                continue
                
        if decision:
            try:
                cb = decision.get('cost_breakdown', {})
                estimated_cost = float(cb.get('total', 0) if isinstance(cb, dict) else decision.get('estimated_cost', 0))
                confidence = float(decision.get('confidence', 0.8))
                
                # Base rule: > $50 needs approval
                is_expensive = estimated_cost > 50
                
                # Confidence overriding
                if confidence < 0.8:
                    is_expensive = True # Always require approval if agent is unsure
                elif confidence >= 0.95 and estimated_cost < 50:
                    is_expensive = False # Auto-execute only if absolutely certain AND cheap
                    
                decision['requires_approval'] = is_expensive 
                decision['estimated_cost'] = estimated_cost # Inject for Frontend UI
                
                # Ensure carrier ID isn't hallucinated as a name
                if decision.get('new_carrier_id') not in carrier_lookup.keys():
                    # fallback to top carrier if hallucinated
                    decision['new_carrier_id'] = top_carriers[0]['id']
                
                audit_id = f"LOG_{int(time.time())}"
                
                log_action(
                    log_id=audit_id,
                    trigger_event=f"Anomaly at {wh_id}",
                    llm_reasoning=json.dumps(decision.get('reasoning', [])),
                    selected_vendor=decision.get('new_carrier_id', ''),
                    outcome_success=True, 
                    action_type=decision.get('action_type', ''),
                    target_shipment_id=decision.get('target_shipment_id', ''),
                    estimated_cost=estimated_cost,
                    requires_approval=is_expensive
                )
                
                if is_expensive:
                    from app.api import pending_actions
                    pending_actions[audit_id] = decision
                    await sio.emit('agent_status', {"status": "Awaiting Human Approval for High-Cost Action"})
                    await sio.emit('approval_required', {
                        "audit_id": audit_id,
                        "decision": decision
                    })
                else:
                    update_shipment_carrier(decision.get('target_shipment_id'), decision.get('new_carrier_id'))
                    await sio.emit('agent_status', {"status": "Action Executed Successfully"})
                    await sio.emit('action_executed', {
                        "message": f"Swapped to {decision.get('new_carrier_id')}. Cost ${estimated_cost}."
                    })
                    
                    # Spawn Outcome Evaluator Task
                    from app.learning.outcome_evaluator import evaluate_action_outcome
                    asyncio.create_task(evaluate_action_outcome(audit_id, decision.get('target_shipment_id')))
                    
            except Exception as e:
                print(f"Error in PoLP guardrail execution: {e}")
                
        from app.database.sqlite_live import inject_chaos
        inject_chaos(wh_id, 100) 
