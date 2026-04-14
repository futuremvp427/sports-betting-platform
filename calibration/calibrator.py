"""
Probability calibration module.
Ensures predicted probabilities are well-calibrated before betting decisions.
Supports isotonic regression and Platt scaling.
"""
import os
import json
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.isotonic import IsotonicRegression

from config import settings
from config.logging_config import get_logger

logger = get_logger("calibration")


class ProbabilityCalibrator:
    """
    Calibrates predicted probabilities to improve reliability.
    Tracks calibration performance over time.
    """

    def __init__(self, method: str = None):
        self.method = method or settings.model.calibration_method
        self.calibrator = None
        self.calibration_history = []
        self._save_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "models", "saved", "calibrators"
        )

    def fit(self, predicted_probs: np.ndarray, actual_outcomes: np.ndarray) -> Dict[str, Any]:
        """
        Fit the calibrator on historical predictions and outcomes.
        predicted_probs: array of predicted probabilities (0-1)
        actual_outcomes: array of binary outcomes (0 or 1)
        """
        if len(predicted_probs) < 10:
            logger.warning("Not enough data for calibration fitting")
            return {"error": "Insufficient data"}

        predicted_probs = np.clip(predicted_probs, 0.01, 0.99)

        if self.method == "isotonic":
            self.calibrator = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds="clip")
            self.calibrator.fit(predicted_probs, actual_outcomes)
        elif self.method == "platt":
            # Platt scaling using logistic regression
            from sklearn.linear_model import LogisticRegression
            self.calibrator = LogisticRegression()
            self.calibrator.fit(predicted_probs.reshape(-1, 1), actual_outcomes)
        else:
            logger.error(f"Unknown calibration method: {self.method}")
            return {"error": f"Unknown method: {self.method}"}

        # Evaluate calibration
        metrics = self.evaluate(predicted_probs, actual_outcomes)
        logger.info(f"Calibrator fitted using {self.method}. ECE: {metrics.get('ece', 'N/A')}")
        return metrics

    def calibrate(self, probabilities: np.ndarray) -> np.ndarray:
        """
        Apply calibration to predicted probabilities.
        If no calibrator is fitted, returns original probabilities.
        """
        if self.calibrator is None:
            logger.warning("No calibrator fitted. Returning original probabilities.")
            return probabilities

        probs = np.clip(probabilities, 0.01, 0.99)

        if self.method == "isotonic":
            calibrated = self.calibrator.predict(probs)
        elif self.method == "platt":
            calibrated = self.calibrator.predict_proba(probs.reshape(-1, 1))[:, 1]
        else:
            calibrated = probs

        return np.clip(calibrated, 0.01, 0.99)

    def calibrate_prediction(self, prediction: Dict[str, Any]) -> Dict[str, Any]:
        """Calibrate a single prediction dict."""
        home_prob = prediction.get("home_win_prob", 0.5)
        away_prob = prediction.get("away_win_prob", 0.5)

        if self.calibrator is not None:
            cal_home = float(self.calibrate(np.array([home_prob]))[0])
            cal_away = 1.0 - cal_home
        else:
            cal_home = home_prob
            cal_away = away_prob

        return {
            **prediction,
            "original_home_prob": home_prob,
            "original_away_prob": away_prob,
            "calibrated_home_prob": round(cal_home, 4),
            "calibrated_away_prob": round(cal_away, 4),
            "calibration_method": self.method,
            "calibration_adjustment": round(abs(cal_home - home_prob), 4),
        }

    def evaluate(self, predicted_probs: np.ndarray, actual_outcomes: np.ndarray,
                 n_bins: int = 10) -> Dict[str, Any]:
        """
        Evaluate calibration quality.
        Returns ECE (Expected Calibration Error) and reliability metrics.
        """
        fraction_of_positives, mean_predicted_value = calibration_curve(
            actual_outcomes, predicted_probs, n_bins=n_bins, strategy="uniform"
        )

        # Expected Calibration Error
        bin_counts = np.histogram(predicted_probs, bins=n_bins, range=(0, 1))[0]
        total = len(predicted_probs)
        ece = 0.0
        for i in range(len(fraction_of_positives)):
            if i < len(bin_counts) and bin_counts[i] > 0:
                ece += (bin_counts[i] / total) * abs(fraction_of_positives[i] - mean_predicted_value[i])

        # Maximum Calibration Error
        mce = max(abs(fraction_of_positives - mean_predicted_value)) if len(fraction_of_positives) > 0 else 0

        # Brier score
        brier = float(np.mean((predicted_probs - actual_outcomes) ** 2))

        metrics = {
            "ece": round(float(ece), 4),
            "mce": round(float(mce), 4),
            "brier_score": round(brier, 4),
            "n_bins": n_bins,
            "sample_size": len(predicted_probs),
            "reliability_curve": {
                "fraction_of_positives": fraction_of_positives.tolist(),
                "mean_predicted_value": mean_predicted_value.tolist(),
            },
            "evaluated_at": datetime.now().isoformat(),
        }

        self.calibration_history.append(metrics)
        return metrics

    def save(self, path: str = None) -> str:
        """Save the calibrator to disk."""
        save_dir = path or self._save_dir
        os.makedirs(save_dir, exist_ok=True)

        cal_path = os.path.join(save_dir, f"calibrator_{self.method}.joblib")
        history_path = os.path.join(save_dir, f"calibrator_{self.method}_history.json")

        if self.calibrator:
            joblib.dump(self.calibrator, cal_path)

        with open(history_path, "w") as f:
            json.dump(self.calibration_history, f, indent=2)

        logger.info(f"Calibrator saved to {save_dir}")
        return cal_path

    def load(self, path: str = None) -> bool:
        """Load a calibrator from disk."""
        save_dir = path or self._save_dir
        cal_path = os.path.join(save_dir, f"calibrator_{self.method}.joblib")

        if os.path.exists(cal_path):
            self.calibrator = joblib.load(cal_path)
            logger.info(f"Calibrator loaded from {cal_path}")
            return True

        logger.warning(f"No calibrator found at {cal_path}")
        return False

    def get_reliability_score(self) -> float:
        """
        Get an overall reliability score (0-1) based on calibration history.
        Higher is better.
        """
        if not self.calibration_history:
            return 0.0

        latest = self.calibration_history[-1]
        ece = latest.get("ece", 1.0)
        return round(max(0, 1.0 - ece * 5), 4)  # Scale ECE to 0-1
