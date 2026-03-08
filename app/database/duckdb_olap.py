import duckdb

OLAP_DB_PATH = "olap_warehouse.duckdb"

def init_olap_db():
    conn = duckdb.connect(OLAP_DB_PATH)
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS Carrier_Performance_Mart (
            id VARCHAR PRIMARY KEY,
            name VARCHAR,
            success_rate_pct DOUBLE,
            avg_delay_mins INTEGER,
            cost_multiplier DOUBLE,
            tier VARCHAR,
            failure_rate_pct DOUBLE,
            reliability_score DOUBLE
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS Hub_History_Mart (
            id VARCHAR PRIMARY KEY,
            historical_bottleneck_frequency DOUBLE,
            avg_clearance_time_hrs DOUBLE
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS Action_Logs_Mart (
            log_id VARCHAR PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            trigger_event VARCHAR,
            llm_reasoning TEXT,
            selected_vendor VARCHAR,
            outcome_success BOOLEAN,
            action_type VARCHAR,
            target_shipment_id VARCHAR,
            estimated_cost DOUBLE,
            requires_approval BOOLEAN
        )
    ''')
    
    # Seed Carriers
    conn.execute('''
        INSERT OR REPLACE INTO Carrier_Performance_Mart 
        (id, name, success_rate_pct, avg_delay_mins, cost_multiplier, tier, failure_rate_pct, reliability_score)
        VALUES 
            ('C_BLUEDART', 'BlueDart Premium', 98.5, 15, 1.5, 'A', 1.5, 97.0),
            ('C_FEDEX', 'FedEx Select', 99.0, 10, 2.0, 'A', 1.0, 98.0),
            ('C_DHL', 'DHL Standard', 95.0, 45, 1.0, 'B', 5.0, 90.5),
            ('C_LOCAL_XP', 'Local Express', 88.0, 120, 0.8, 'C', 12.0, 76.0),
            ('C_SAFE_EXPRESS', 'Safe Express', 92.0, 30, 0.9, 'B', 8.0, 89.0),
            ('C_GATI', 'Gati Ground', 85.0, 180, 0.5, 'C', 15.0, 67.0),
            ('C_DTDC', 'DTDC Saver', 89.0, 90, 0.7, 'C', 11.0, 80.0)
    ''')
    
    conn.close()

def get_top_carriers(limit: int = 3):
    conn = duckdb.connect(OLAP_DB_PATH)
    result = conn.execute(f'''
        SELECT id, name, success_rate_pct, avg_delay_mins, cost_multiplier, tier, reliability_score 
        FROM Carrier_Performance_Mart 
        ORDER BY success_rate_pct DESC 
        LIMIT {limit}
    ''').fetchall()
    
    conn.close()
    
    keys = ['id', 'name', 'success_rate_pct', 'avg_delay_mins', 'cost_multiplier', 'tier', 'reliability_score']
    return [dict(zip(keys, row)) for row in result]

def log_action(log_id: str, trigger_event: str, llm_reasoning: str, selected_vendor: str, 
               outcome_success: bool, action_type: str, target_shipment_id: str, 
               estimated_cost: float, requires_approval: bool):
    conn = duckdb.connect(OLAP_DB_PATH)
    
    conn.execute('''
        INSERT INTO Action_Logs_Mart 
        (log_id, trigger_event, llm_reasoning, selected_vendor, outcome_success, 
         action_type, target_shipment_id, estimated_cost, requires_approval)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (log_id, trigger_event, llm_reasoning, selected_vendor, outcome_success, 
          action_type, target_shipment_id, estimated_cost, requires_approval))
    
    conn.close()
    
def get_all_carriers():
    return get_top_carriers(limit=100)
