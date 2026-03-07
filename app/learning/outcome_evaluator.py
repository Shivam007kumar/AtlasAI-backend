import asyncio
import datetime
import duckdb
from app.database.sqlite_live import get_live_state
from app.database.duckdb_olap import OLAP_DB_PATH

async def evaluate_action_outcome(audit_id: str, target_shipment_id: str):
    """
    Evaluates an action 30 simulated seconds later (representing 30 minutes in reality)
    to see if the shipment status improved or ETA was met.
    """
    # Wait for the situation to resolve (shortened for hackathon demo purposes)
    await asyncio.sleep(30)
    
    # Check live state
    state = get_live_state()
    shipment_now = next((s for s in state['shipments'] if s['id'] == target_shipment_id), None)
    
    outcome_success = False
    
    if shipment_now:
        # Success criteria: It either delivered, or is simply not delayed past its current_eta timeframe anymore
        if shipment_now['status'] == 'delivered':
            outcome_success = True
        elif shipment_now['status'] == 'in_transit': # It recovered from delayed or stayed in transit
            outcome_success = True
            
    # Update Action_Logs_Mart in DuckDB
    try:
        conn = duckdb.connect(OLAP_DB_PATH)
        conn.execute('''
            UPDATE Action_Logs_Mart 
            SET outcome_success = ?
            WHERE log_id = ?
        ''', (outcome_success, audit_id))
        
        # Trigger the feedback loop dynamically
        await update_carrier_scores(conn)
        
        conn.close()
        print(f"Outcome evaluated for {audit_id}: Success={outcome_success}")
    except Exception as e:
        print(f"Error evaluating outcome: {e}")

async def update_carrier_scores(conn):
    """
    Adjusts the success_rate_pct of carriers based on recent Action Logs
    """
    try:
        # Get all carriers
        carriers = conn.execute('SELECT id, success_rate_pct FROM Carrier_Performance_Mart').fetchall()
        
        for carrier_id, current_score in carriers:
            # Check their recent logged actions
            recent_logs = conn.execute('''
                SELECT outcome_success 
                FROM Action_Logs_Mart 
                WHERE selected_vendor = ? 
                ORDER BY timestamp DESC LIMIT 5
            ''', (carrier_id,)).fetchall()
            
            if not recent_logs:
                continue
                
            successes = sum(1 for log in recent_logs if log[0])
            total = len(recent_logs)
            recent_success_rate = (successes / total) * 100
            
            # Blend the scores (70% historical weight, 30% recent performance loop weight)
            new_score = (current_score * 0.7) + (recent_success_rate * 0.3)
            
            # Cap at 99.9%
            new_score = min(99.9, max(1.0, new_score))
            
            conn.execute('''
                UPDATE Carrier_Performance_Mart 
                SET success_rate_pct = ?
                WHERE id = ?
            ''', (new_score, carrier_id))
            
    except Exception as e:
        print(f"Error updating carrier scores: {e}")
