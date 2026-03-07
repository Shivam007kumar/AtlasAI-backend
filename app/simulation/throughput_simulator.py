import datetime
import random

def simulate_realistic_throughput(current_throughput: int, current_time: datetime.datetime) -> int:
    """
    Simulate realistic patterns for a single warehouse based on time of day.
    - Morning rush (6-10): 60-80% throughput
    - Peak/Normal (10-16): 90-100% throughput
    - Evening (16-20): 70-90% throughput
    - Night (20-6): 85-100% throughput
    - Random chaos event: 5% chance of dropping to 20-40%
    """
    # Start with a base realistic range
    base = current_throughput
    hour = current_time.hour
    
    # Natural Time-of-day fluctuation
    if 6 <= hour < 10:  
        base = random.randint(60, 80)
    elif 10 <= hour < 16:  
        base = random.randint(90, 100)
    elif 16 <= hour < 20:  
        base = random.randint(70, 90)
    else:
        base = random.randint(85, 100)
        
    # Micro-fluctuations so numbers jitter realistically even within ranges
    base += random.randint(-5, 5)
    
    # 2% Chaos probability per tick per hub
    if random.random() < 0.02:
        base = random.randint(20, 45) # Triggers the < 50% Watchtower rule
        
    # Cap thresholds
    return max(0, min(100, base))
