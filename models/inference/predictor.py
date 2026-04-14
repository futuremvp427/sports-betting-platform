"""
Inference engine - generates predictions for upcoming games.
Loads trained models and produces probability outputs.
"""
import os
import json
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List
from glob import glob

from models.features import FeatureEngineer
from config import settings
from config.logging_config import get_logger

logger = get_logger("models.predictor")


class Predictor:
    """
    Generates predictions for upcoming games using trained models.
    Supports loading the best available model and producing probability outputs.
    """

    def __init__(self, model_path: str = None):
        self.model = None
        self.feature_columns = []
        self.model_type = "unknown"
        self.model_version = "unknown"
        self.feature_engineer = FeatureEngineer()

        if model_path:
            self.load_model(model_path)
        else:
            self._load_best_model()

    def _load_best_model(self):
        """Load the most recently saved model."""
        models_dir = settings.model.models_dir
        if not os.path.exists(models_dir):
            logger.warning("No models directory found. Predictor will use baseline.")
            return

        model_files = sorted(glob(os.path.join(models_dir, "*.joblib")), reverse=True)
        if model_files:
            self.load_model(model_files[0])
        else:
            logger.warning("No saved models found. Predictor will use baseline.")

    def load_model(self, model_path: str):
        """Load a specific model."""
        try:
            self.model = joblib.load(model_path)
            meta_path = model_path.replace(".joblib", "_meta.json")
            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    meta = json.load(f)
                self.feature_columns = meta.get("feature_columns", [])
                self.model_type = meta.get("model_type", "unknown")
                self.model_version = meta.get("model_version", "unknown")
            logger.info(f"Loaded model: {self.model_type} v{self.model_version}")
        except Exception as e:
            logger.error(f"Failed to load model from {model_path}: {e}")

    def predict(self, games_df: pd.DataFrame, historical_df: pd.DataFrame = None) -> List[Dict[str, Any]]:
        """
        Generate predictions for a set of games.
        If no trained model is available, uses a baseline predictor.
        """
        if games_df.empty:
            return []

        predictions = []

        if self.model is not None and self.feature_columns:
            predictions = self._model_predict(games_df, historical_df)
        else:
            predictions = self._baseline_predict(games_df)

        return predictions

    def _model_predict(self, games_df: pd.DataFrame, historical_df: pd.DataFrame = None) -> List[Dict[str, Any]]:
        """Use trained model for predictions."""
        # Combine with historical data for feature engineering
        if historical_df is not None and not historical_df.empty:
            combined = pd.concat([historical_df, games_df], ignore_index=True)
        else:
            combined = games_df.copy()

        featured = self.feature_engineer.create_features(combined)

        # Get only the rows for games we want to predict
        predict_indices = featured.tail(len(games_df)).index
        predictions = []

        for idx in predict_indices:
            row = featured.loc[idx]
            feature_values = []
            valid = True

            for col in self.feature_columns:
                val = row.get(col)
                if pd.isna(val):
                    valid = False
                    break
                feature_values.append(val)

            if valid and feature_values:
                X = np.array([feature_values])
                proba = self.model.predict_proba(X)[0]
                home_prob = float(proba[1]) if len(proba) > 1 else float(proba[0])
                away_prob = 1.0 - home_prob
            else:
                # Fallback to baseline
                home_prob = 0.55  # Home advantage baseline
                away_prob = 0.45

            confidence = abs(home_prob - 0.5) * 2  # 0 to 1 scale

            predictions.append({
                "home_team": row.get("home_team_name", "Unknown"),
                "away_team": row.get("away_team_name", "Unknown"),
                "home_win_prob": round(home_prob, 4),
                "away_win_prob": round(away_prob, 4),
                "predicted_winner": (
                    row.get("home_team_name") if home_prob > 0.5
                    else row.get("away_team_name")
                ),
                "confidence": round(confidence, 4),
                "model_name": self.model_type,
                "model_version": self.model_version,
            })

        logger.info(f"Generated {len(predictions)} predictions using {self.model_type}")
        return predictions

    def _baseline_predict(self, games_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Baseline predictor when no trained model is available.
        Uses home advantage and simple heuristics.
        """
        predictions = []

        for _, row in games_df.iterrows():
            # Simple home advantage baseline
            home_prob = 0.55
            away_prob = 0.45
            confidence = 0.1  # Low confidence for baseline

            predictions.append({
                "home_team": row.get("home_team_name", "Unknown"),
                "away_team": row.get("away_team_name", "Unknown"),
                "home_win_prob": home_prob,
                "away_win_prob": away_prob,
                "predicted_winner": row.get("home_team_name", "Unknown"),
                "confidence": confidence,
                "model_name": "baseline",
                "model_version": "1.0",
            })

        logger.info(f"Generated {len(predictions)} baseline predictions")
        return predictions
