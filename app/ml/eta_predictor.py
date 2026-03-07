import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
import datetime
import pickle
import os

MODEL_PATH = "app/ml/eta_model.pkl"
ENCODER_PATH = "app/ml/eta_encoder.pkl"

class ETAPredictor:
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=50, random_state=42)
        self.encoders = {}
        
    def _create_dummy_data(self):
        """Creates dummy training data representing historical shipments for the hackathon"""
        np.random.seed(42)
        n_samples = 1000
        
        # Features
        priorities = np.random.choice(['Low', 'Medium', 'High'], n_samples)
        throughput = np.random.randint(20, 100, n_samples)
        carrier_success = np.random.uniform(85, 99, n_samples)
        distance_proxy = np.random.randint(100, 2000, n_samples) # rough km
        
        # Target: delay in minutes. Highly correlated with throughput drops
        base_delays = np.where(throughput < 50, np.random.randint(120, 1440, n_samples), np.random.randint(0, 60, n_samples))
        # Add priority factor (High priority gets less delay)
        priority_factor = np.where(priorities == 'High', 0.5, np.where(priorities == 'Medium', 1.0, 1.5))
        # Add carrier factor
        carrier_factor = (100 - carrier_success) / 10
        
        target_delays = (base_delays * priority_factor * carrier_factor) + (distance_proxy / 100)
        
        df = pd.DataFrame({
            'priority': priorities,
            'origin_throughput': throughput,
            'carrier_success': carrier_success,
            'distance': distance_proxy,
            'delay_minutes': target_delays
        })
        
        return df
        
    def train(self):
        print("Training ETA Prediction Model on historical data...")
        df = self._create_dummy_data()
        
        # Encode categorical
        le = LabelEncoder()
        df['priority_encoded'] = le.fit_transform(df['priority'])
        self.encoders['priority'] = le
        
        X = df[['priority_encoded', 'origin_throughput', 'carrier_success', 'distance']]
        y = df['delay_minutes']
        
        self.model.fit(X, y)
        
        # Save model
        with open(MODEL_PATH, 'wb') as f:
            pickle.dump(self.model, f)
        with open(ENCODER_PATH, 'wb') as f:
            pickle.dump(self.encoders, f)
            
        print("ETA Model trained and saved.")
        
    def load(self):
        if not os.path.exists(MODEL_PATH):
            self.train()
        else:
            with open(MODEL_PATH, 'rb') as f:
                self.model = pickle.load(f)
            with open(ENCODER_PATH, 'rb') as f:
                self.encoders = pickle.load(f)
                
    def predict_delay_minutes(self, priority: str, origin_throughput: int, carrier_success: float, distance_proxy: int = 500) -> float:
        """Returns the dynamically predicted delay in minutes based on real-time factors"""
        try:
            p_enc = self.encoders['priority'].transform([priority])[0]
        except KeyError:
            p_enc = 1 # default to medium
            
        X_pred = pd.DataFrame({
            'priority_encoded': [p_enc],
            'origin_throughput': [origin_throughput],
            'carrier_success': [carrier_success],
            'distance': [distance_proxy]
        })
        
        delay = self.model.predict(X_pred)[0]
        return max(0, float(delay))

# Singleton instance for the app to use
eta_predictor_model = ETAPredictor()
