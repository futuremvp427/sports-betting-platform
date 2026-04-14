"""
Model training pipeline.
Supports multiple model types: XGBoost, Random Forest, Logistic Regression.
Adapted from NBA-Machine-Learning-Sports-Betting and ml-for-sports-betting patterns.
"""
import os
import json
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    brier_score_loss, log_loss, roc_auc_score
)

from models.features import FeatureEngineer
from config import settings
from config.logging_config import get_logger

logger = get_logger("models.trainer")


class ModelTrainer:
    """
    Trains and evaluates prediction models.
    Supports multiple algorithms with consistent interface.
    """

    SUPPORTED_MODELS = {
        "logistic_regression": LogisticRegression,
        "random_forest": RandomForestClassifier,
        "gradient_boosting": GradientBoostingClassifier,
    }

    DEFAULT_PARAMS = {
        "logistic_regression": {"max_iter": 1000, "C": 1.0, "random_state": 42},
        "random_forest": {"n_estimators": 200, "max_depth": 10, "random_state": 42, "n_jobs": -1},
        "gradient_boosting": {"n_estimators": 200, "max_depth": 5, "learning_rate": 0.1, "random_state": 42},
    }

    def __init__(self, model_type: str = None):
        self.model_type = model_type or settings.model.default_model
        if self.model_type == "xgboost":
            self.model_type = "gradient_boosting"  # Use sklearn GB as default
        self.feature_engineer = FeatureEngineer()
        self.model = None
        self.feature_columns = []
        self.metrics = {}
        self.model_version = datetime.now().strftime("%Y%m%d_%H%M%S")

    def train(self, df: pd.DataFrame, target_col: str = "home_win",
              test_size: float = 0.2, params: Dict = None) -> Dict[str, Any]:
        """
        Train a model on the provided DataFrame.
        Returns training metrics.
        """
        logger.info(f"Training {self.model_type} model on {len(df)} samples")

        # Engineer features
        featured_df = self.feature_engineer.create_features(df)

        # Get feature columns
        self.feature_columns = self.feature_engineer.get_prediction_features()

        # Ensure target exists
        if target_col not in featured_df.columns:
            featured_df[target_col] = (featured_df["home_score"] > featured_df["away_score"]).astype(int)

        # Drop rows with NaN in features
        valid_cols = [c for c in self.feature_columns if c in featured_df.columns]
        self.feature_columns = valid_cols
        clean_df = featured_df.dropna(subset=valid_cols + [target_col])

        if len(clean_df) < 20:
            logger.error(f"Not enough clean samples: {len(clean_df)}")
            return {"error": "Insufficient data after cleaning"}

        X = clean_df[valid_cols].values
        y = clean_df[target_col].values

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )

        # Initialize model
        model_class = self.SUPPORTED_MODELS.get(self.model_type)
        if model_class is None:
            logger.error(f"Unsupported model type: {self.model_type}")
            return {"error": f"Unsupported model: {self.model_type}"}

        model_params = params or self.DEFAULT_PARAMS.get(self.model_type, {})
        self.model = model_class(**model_params)

        # Train
        self.model.fit(X_train, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test)
        y_proba = self.model.predict_proba(X_test)[:, 1]

        self.metrics = {
            "model_type": self.model_type,
            "model_version": self.model_version,
            "train_size": len(X_train),
            "test_size": len(X_test),
            "accuracy": round(accuracy_score(y_test, y_pred), 4),
            "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
            "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
            "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
            "brier_score": round(brier_score_loss(y_test, y_proba), 4),
            "log_loss": round(log_loss(y_test, y_proba), 4),
            "roc_auc": round(roc_auc_score(y_test, y_proba), 4),
            "feature_count": len(valid_cols),
            "features": valid_cols,
        }

        # Cross-validation
        cv_scores = cross_val_score(self.model, X, y, cv=5, scoring="accuracy")
        self.metrics["cv_accuracy_mean"] = round(cv_scores.mean(), 4)
        self.metrics["cv_accuracy_std"] = round(cv_scores.std(), 4)

        # Feature importance
        if hasattr(self.model, "feature_importances_"):
            importance = dict(zip(valid_cols, self.model.feature_importances_.tolist()))
            self.metrics["feature_importance"] = {
                k: round(v, 4) for k, v in
                sorted(importance.items(), key=lambda x: x[1], reverse=True)
            }

        logger.info(f"Model trained - Accuracy: {self.metrics['accuracy']}, AUC: {self.metrics['roc_auc']}")
        return self.metrics

    def save_model(self, path: str = None) -> str:
        """Save the trained model to disk."""
        if self.model is None:
            raise ValueError("No model to save. Train a model first.")

        save_dir = path or settings.model.models_dir
        os.makedirs(save_dir, exist_ok=True)

        model_path = os.path.join(save_dir, f"{self.model_type}_{self.model_version}.joblib")
        meta_path = os.path.join(save_dir, f"{self.model_type}_{self.model_version}_meta.json")

        joblib.dump(self.model, model_path)

        meta = {
            "model_type": self.model_type,
            "model_version": self.model_version,
            "feature_columns": self.feature_columns,
            "metrics": self.metrics,
            "saved_at": datetime.now().isoformat(),
        }
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        logger.info(f"Model saved to {model_path}")
        return model_path

    def load_model(self, model_path: str) -> None:
        """Load a trained model from disk."""
        self.model = joblib.load(model_path)

        meta_path = model_path.replace(".joblib", "_meta.json")
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            self.feature_columns = meta.get("feature_columns", [])
            self.model_type = meta.get("model_type", "unknown")
            self.model_version = meta.get("model_version", "unknown")
            self.metrics = meta.get("metrics", {})

        logger.info(f"Model loaded from {model_path}")

    def compare_models(self, df: pd.DataFrame, models: List[str] = None) -> pd.DataFrame:
        """
        Train and compare multiple model types.
        Returns a DataFrame of metrics for each model.
        """
        models = models or list(self.SUPPORTED_MODELS.keys())
        results = []

        for model_type in models:
            logger.info(f"Training {model_type} for comparison...")
            trainer = ModelTrainer(model_type=model_type)
            metrics = trainer.train(df)
            if "error" not in metrics:
                results.append(metrics)

        if results:
            comparison_df = pd.DataFrame(results)
            comparison_df = comparison_df.sort_values("roc_auc", ascending=False)
            logger.info(f"Model comparison complete. Best: {comparison_df.iloc[0]['model_type']}")
            return comparison_df

        return pd.DataFrame()
