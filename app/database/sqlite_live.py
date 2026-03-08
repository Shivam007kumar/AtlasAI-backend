import sqlite3

LIVE_DB_PATH = "live_state.db"

def init_live_db():
    conn = sqlite3.connect(LIVE_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Hub_Live (
            id TEXT PRIMARY KEY,
            name TEXT,
            throughput_pct INTEGER,
            is_congested BOOLEAN
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Carrier_Live (
            id TEXT PRIMARY KEY,
            current_active_shipments INTEGER,
            live_gps_ping_status BOOLEAN
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Shipment_Live (
            id TEXT PRIMARY KEY,
            origin_id TEXT,
            destination_id TEXT,
            carrier_id TEXT,
            priority TEXT,
            status TEXT,
            promised_eta TEXT,
            current_eta TEXT,
            risk_score REAL DEFAULT 0.0,
            predicted_delay INTEGER DEFAULT 0
        )
    ''')
    
    import random
    import datetime
    
    # 50 Hubs
    hubs = [
        ('WH_MUM_1', 'Mumbai Port South', 100, 0), ('WH_MUM_2', 'Mumbai Airport', 100, 0),
        ('WH_DEL_1', 'Delhi Main', 100, 0), ('WH_DEL_2', 'Delhi East', 100, 0),
        ('WH_BLR_1', 'Bangalore Central', 100, 0), ('WH_BLR_2', 'Bangalore North', 100, 0),
        ('WH_CHE_1', 'Chennai Port', 100, 0), ('WH_HYD_1', 'Hyderabad Gateway', 100, 0),
        ('WH_PUN_1', 'Pune Fulfillment', 100, 0), ('WH_KOL_1', 'Kolkata Depot', 100, 0)
    ]
    # Add generic hubs to reach 50
    for i in range(11, 51):
        hubs.append((f'WH_IN_{i}', f'India Reg Node {i}', 100, 0))
    
    cursor.executemany('''
        INSERT OR IGNORE INTO Hub_Live (id, name, throughput_pct, is_congested)
        VALUES (?, ?, ?, ?)
    ''', hubs)
    
    # 100 Shipments
    carriers = ['C_BLUEDART', 'C_FEDEX', 'C_DHL', 'C_LOCAL_XP', 'C_SAFE_EXPRESS', 'C_GATI', 'C_DTDC']
    shipments = []
    
    now = datetime.datetime.now(datetime.timezone.utc)
    for i in range(100):
        origin = random.choice(hubs)[0]
        dest = random.choice(hubs)[0]
        while dest == origin:
            dest = random.choice(hubs)[0]
            
        carrier = random.choice(carriers)
        priority = random.choice(['High', 'Medium', 'Low'])
        
        # Promised ETA between 2 to 72 hours from now
        promised = now + datetime.timedelta(hours=random.randint(2, 72))
        
        shipments.append((
            f'SHP_1{i:03d}', origin, dest, carrier, priority, 'in_transit', 
            promised.isoformat().replace('+00:00', 'Z'),
            promised.isoformat().replace('+00:00', 'Z'),
            0.0, 0
        ))
        
    cursor.executemany('''
        INSERT OR IGNORE INTO Shipment_Live (id, origin_id, destination_id, carrier_id, priority, status, promised_eta, current_eta, risk_score, predicted_delay)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', shipments)
    
    conn.commit()
    conn.close()

def get_live_state():
    conn = sqlite3.connect(LIVE_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    warehouses = [dict(row) for row in cursor.execute('SELECT * FROM Hub_Live').fetchall()]
    # SQLite returns 1/0 for boolean, convert for schema compliance
    for w in warehouses:
        w['is_congested'] = bool(w['is_congested'])
        
    shipments = [dict(row) for row in cursor.execute('SELECT * FROM Shipment_Live').fetchall()]
    
    conn.close()
    return {"warehouses": warehouses, "shipments": shipments}

def inject_chaos(target_id: str, severity_pct: int):
    conn = sqlite3.connect(LIVE_DB_PATH)
    cursor = conn.cursor()
    
    is_congested = severity_pct < 50
    cursor.execute('''
        UPDATE Hub_Live 
        SET throughput_pct = ?, is_congested = ?
        WHERE id = ?
    ''', (severity_pct, is_congested, target_id))
    
    conn.commit()
    conn.close()

def update_shipment_carrier(shipment_id: str, new_carrier_id: str):
    conn = sqlite3.connect(LIVE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE Shipment_Live 
        SET carrier_id = ?
        WHERE id = ?
    ''', (new_carrier_id, shipment_id))
    conn.commit()
    conn.close()

def update_hub_throughput(target_id: str, new_pct: int):
    conn = sqlite3.connect(LIVE_DB_PATH)
    cursor = conn.cursor()
    is_congested = new_pct < 50
    cursor.execute('''
        UPDATE Hub_Live 
        SET throughput_pct = ?, is_congested = ?
        WHERE id = ?
    ''', (new_pct, is_congested, target_id))
    conn.commit()
    conn.close()
    
def update_shipment_lifecycle(target_id: str, new_status: str):
    conn = sqlite3.connect(LIVE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE Shipment_Live 
        SET status = ?
        WHERE id = ?
    ''', (new_status, target_id))
    conn.commit()
    conn.close()

def update_shipment_eta(shipment_id: str, new_eta: str):
    conn = sqlite3.connect(LIVE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE Shipment_Live 
        SET current_eta = ?
        WHERE id = ?
    ''', (new_eta, shipment_id))
    conn.commit()
    conn.close()

def update_shipment_risk(shipment_id: str, risk_score: float, predicted_delay: int):
    conn = sqlite3.connect(LIVE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE Shipment_Live 
        SET risk_score = ?, predicted_delay = ?
        WHERE id = ?
    ''', (risk_score, predicted_delay, shipment_id))
    conn.commit()
    conn.close()
