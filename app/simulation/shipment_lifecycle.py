import datetime

def has_reached_destination(shipment: dict, current_time: datetime.datetime) -> bool:
    """
    Simulate arrival if current time is past promised ETA or arbitrary duration.
    """
    try:
        promised = datetime.datetime.fromisoformat(shipment['promised_eta'].replace('Z', '+00:00'))
        # Using a slightly earlier threshold so some shipments naturally 'arrive'
        expected_arrival = promised - datetime.timedelta(hours=1) 
        
        return current_time > expected_arrival
    except Exception:
        return False

def is_past_eta(current_eta_str: str, current_time: datetime.datetime) -> bool:
    """
    Check if the shipment is currently delayed past its ETA definition
    """
    try:
        eta = datetime.datetime.fromisoformat(current_eta_str.replace('Z', '+00:00'))
        return current_time > eta
    except Exception:
        return False
        
def update_shipment_status(shipment: dict, current_time: datetime.datetime) -> str:
    """
    Transitions:
    - in_transit -> delayed (if current_eta > promised_eta timeline)
    - in_transit/delayed -> delivered (if elapsed_time meets conditions)
    """
    current_status = shipment['status']
    
    if current_status == 'delivered':
        return current_status
        
    if has_reached_destination(shipment, current_time):
        return 'delivered'
        
    if current_status == 'in_transit' and is_past_eta(shipment['current_eta'], current_time):
        return 'delayed'
        
    return current_status
