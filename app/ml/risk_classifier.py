import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
import pickle
import os

MODEL_PATH = "app/ml/risk_model.pkl"

class RiskClassifier:
    def __init__(self):
        self.model = LogisticRegression(random_state=42)
        self.enc_priority = LabelEncoder()
        
    def _create_dummy_data(self):
        """ Historical data for shipments and if they ended up delayed """
        np.random.seed(42)
        n = 1000
        
        throughput = np.random.randint(20, 100, n)
        carrier_success = np.random.uniform(85, 99, n)
        priorities = np.random.choice(['Low', 'Medium', 'High'], n)
        
        # The equation for probability of failure/delay
        # Low throughput = high risk. High carrier success = low risk. High priority = med risk (tighter deadlines)
        raw_risk = ((100 - throughput) * 0.4) + ((100 - carrier_success) * 0.5)
        raw_risk += np.where(priorities == 'High', 10, np.where(priorities == 'Medium', 5, 0))
        
        # Convert to 0/1 (0 = safe, 1 = delayed)
        # If risk score is > 30, it delayed
        delayed = (raw_risk > 30).astype(int)
        
        df = pd.DataFrame({
            'throughput': throughput,
            'carrier_success': carrier_success,
            'priority': priorities,
            'is_delayed': delayed
        })
        return df
        
    def train(self):
        print("Training Risk Classification Model...")
        df = self._create_dummy_data()
        
        df['priority_enc'] = self.enc_priority.fit_transform(df['priority'])
        
        X = df[['throughput', 'carrier_success', 'priority_enc']]
        y = df['is_delayed']
        
        self.model.fit(X, y)
        
        with open(MODEL_PATH, 'wb') as f:
            pickle.dump({'model': self.model, 'encoder': self.enc_priority}, f)
            
        print("Risk Model trained and saved.")
        
    def load(self):
        if not os.path.exists(MODEL_PATH):
            self.train()
        else:
            with open(MODEL_PATH, 'rb') as f:
                data = pickle.load(f)
                self.model = data['model']
                self.enc_priority = data['encoder']
                
    def predict_risk_probability(self, throughput: int, carrier_success: float, priority: str) -> float:
        """ Returns float 0.0 to 1.0 representing probability of delay """
        try:
            p_enc = self.enc_priority.transform([priority])[0]
        except KeyError:
            p_enc = 1
            
        X_pred = pd.DataFrame({
            'throughput': [throughput],
            'carrier_success': [carrier_success],
            'priority_enc': [p_enc]
        })
        
        # predict_proba returns [[prob_0, prob_1]]
        prob_delay = self.model.predict_proba(X_pred)[0][1]
        return round(float(prob_delay), 2)

risk_classifier_model = RiskClassifier()
