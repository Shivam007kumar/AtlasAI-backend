import math

class CarrierScorer:
    """
    Dynamic scoring system that adjusts success_rate_pct based on recent performance.
    Uses exponential temporal decay: recent failures impact the score much more heavily
    than older historical successes.
    """
    
    def __init__(self):
        # We value the last 5 decisions intensely. 
        self.recent_weight = 0.4 
        self.history_weight = 0.6
        
    def calculate_new_score(self, current_score: float, recent_outcomes: list[bool]) -> float:
        """
        recent_outcomes: List of booleans where True is success, False is failure.
        Ordered oldest to newest.
        """
        if not recent_outcomes:
            return current_score
            
        # Calculate recent success rate with temporal decay weighting
        total_weight = 0
        weighted_successes = 0
        
        # Give newer logs exponentially more weight
        for i, outcome in enumerate(recent_outcomes):
            # i=0 is oldest, i=len-1 is newest
            # Weight = e^(i - (len-1))
            weight = math.exp(i - len(recent_outcomes) + 1)
            total_weight += weight
            
            if outcome:
                weighted_successes += weight
                
        recent_success_rate = (weighted_successes / total_weight) * 100
        
        # Blend with historical score
        new_score = (current_score * self.history_weight) + (recent_success_rate * self.recent_weight)
        
        return round(min(99.9, max(1.0, new_score)), 1)
        
carrier_scorer_model = CarrierScorer()
