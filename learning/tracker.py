"""
Learning system - tracks predictions vs outcomes, measures performance,
and supports controlled adaptive improvements.
No silent corruption of baseline models. All updates are reversible and observable.
"""
import json
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime

from storage.database import get_db
from config.logging_config import get_logger

logger = get_logger("learning")


class LearningTracker:
    """
    Tracks predictions, outcomes, and model performance over time.
    Supports controlled learning with observable, reversible updates.
    """

    def __init__(self):
        self.db = get_db()

    def record_prediction(self, game_id: int, prediction: Dict[str, Any]) -> int:
        """Record a prediction for future comparison with outcome."""
        pred_id = self.db.insert_prediction(
            game_id=game_id,
            model_name=prediction.get("model_name", "unknown"),
            model_version=prediction.get("model_version", "1.0"),
            sport=prediction.get("sport", "unknown"),
            home_team=prediction.get("home_team", "Unknown"),
            away_team=prediction.get("away_team", "Unknown"),
            predicted_winner=prediction.get("predicted_winner"),
            home_win_prob=prediction.get("home_win_prob"),
            away_win_prob=prediction.get("away_win_prob"),
            confidence=prediction.get("confidence"),
            features_used=prediction.get("features_used", {}),
        )
        logger.info(f"Recorded prediction {pred_id} for game {game_id}")
        return pred_id

    def record_outcome(self, game_id: int, actual_winner: str,
                       home_score: int, away_score: int) -> List[int]:
        """
        Record the actual outcome and compare with predictions.
        Returns list of outcome IDs created.
        """
        predictions = self.db.get_predictions(game_id=game_id)
        outcome_ids = []

        for pred in predictions:
            prediction_correct = 1 if pred["predicted_winner"] == actual_winner else 0

            # Calculate probability error
            if actual_winner == pred["home_team"]:
                actual_prob = 1.0
                predicted_prob = pred.get("home_win_prob", 0.5)
            else:
                actual_prob = 0.0
                predicted_prob = pred.get("home_win_prob", 0.5)

            prob_error = abs(predicted_prob - actual_prob)

            outcome_id = self.db.insert_outcome(
                game_id=game_id,
                prediction_id=pred["id"],
                actual_winner=actual_winner,
                home_score=home_score,
                away_score=away_score,
                prediction_correct=prediction_correct,
                probability_error=round(prob_error, 4),
            )
            outcome_ids.append(outcome_id)

        logger.info(f"Recorded {len(outcome_ids)} outcomes for game {game_id}")
        return outcome_ids

    def get_model_performance(self, model_name: str = None,
                               sport: str = None,
                               last_n: int = 100) -> Dict[str, Any]:
        """
        Calculate performance metrics for a model.
        Returns accuracy, calibration, ROI, and trend data.
        """
        query = """
            SELECT p.model_name, p.model_version, p.sport,
                   p.home_win_prob, p.away_win_prob, p.confidence,
                   o.prediction_correct, o.probability_error, o.actual_winner,
                   o.home_score, o.away_score
            FROM predictions p
            JOIN outcomes o ON p.id = o.prediction_id
            WHERE 1=1
        """
        params = []
        if model_name:
            query += " AND p.model_name = ?"
            params.append(model_name)
        if sport:
            query += " AND p.sport = ?"
            params.append(sport)
        query += f" ORDER BY o.recorded_at DESC LIMIT {last_n}"

        results = self.db.execute_query(query, tuple(params))

        if not results:
            return {"error": "No outcomes found", "sample_size": 0}

        df = pd.DataFrame(results)

        accuracy = df["prediction_correct"].mean()
        avg_prob_error = df["probability_error"].mean()
        avg_confidence = df["confidence"].mean() if "confidence" in df.columns else 0

        # Calibration check: bin predictions and compare
        calibration_data = self._calculate_calibration(df)

        # Performance trend (rolling accuracy)
        if len(df) >= 10:
            rolling_acc = df["prediction_correct"].rolling(10).mean().dropna().tolist()
        else:
            rolling_acc = [accuracy]

        return {
            "model_name": model_name or "all",
            "sport": sport or "all",
            "sample_size": len(df),
            "accuracy": round(float(accuracy), 4),
            "avg_probability_error": round(float(avg_prob_error), 4),
            "avg_confidence": round(float(avg_confidence), 4),
            "calibration": calibration_data,
            "rolling_accuracy": rolling_acc,
            "last_10_accuracy": round(float(df.head(10)["prediction_correct"].mean()), 4),
        }

    def _calculate_calibration(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate calibration metrics from prediction/outcome data."""
        bins = [0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        df_cal = df.copy()
        df_cal["prob_bin"] = pd.cut(df_cal["home_win_prob"], bins=bins)

        cal_data = []
        for bin_range, group in df_cal.groupby("prob_bin", observed=True):
            if len(group) > 0:
                predicted_avg = group["home_win_prob"].mean()
                actual_rate = group["prediction_correct"].mean()
                cal_data.append({
                    "bin": str(bin_range),
                    "predicted_avg": round(float(predicted_avg), 4),
                    "actual_rate": round(float(actual_rate), 4),
                    "count": len(group),
                    "gap": round(abs(float(predicted_avg) - float(actual_rate)), 4),
                })

        return cal_data

    def should_retrain(self, model_name: str, threshold: float = 0.05) -> Dict[str, Any]:
        """
        Determine if a model should be retrained based on performance degradation.
        Compares recent performance to historical performance.
        Returns recommendation with justification.
        """
        recent = self.get_model_performance(model_name, last_n=20)
        historical = self.get_model_performance(model_name, last_n=100)

        if recent.get("sample_size", 0) < 10:
            return {
                "should_retrain": False,
                "reason": "Insufficient recent data for evaluation",
                "recent_accuracy": recent.get("accuracy", 0),
                "historical_accuracy": historical.get("accuracy", 0),
            }

        accuracy_drop = historical.get("accuracy", 0) - recent.get("accuracy", 0)
        prob_error_increase = recent.get("avg_probability_error", 0) - historical.get("avg_probability_error", 0)

        should_retrain = accuracy_drop > threshold or prob_error_increase > threshold

        return {
            "should_retrain": should_retrain,
            "reason": (
                f"Accuracy dropped by {accuracy_drop:.2%}" if accuracy_drop > threshold
                else f"Probability error increased by {prob_error_increase:.2%}" if prob_error_increase > threshold
                else "Performance within acceptable range"
            ),
            "recent_accuracy": recent.get("accuracy", 0),
            "historical_accuracy": historical.get("accuracy", 0),
            "accuracy_change": round(-accuracy_drop, 4),
            "prob_error_change": round(prob_error_increase, 4),
        }

    def get_prediction_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent predictions with their outcomes."""
        query = """
            SELECT p.*, o.actual_winner, o.home_score, o.away_score,
                   o.prediction_correct, o.probability_error
            FROM predictions p
            LEFT JOIN outcomes o ON p.id = o.prediction_id
            ORDER BY p.prediction_time DESC
            LIMIT ?
        """
        return self.db.execute_query(query, (limit,))

    def get_bankroll_summary(self) -> Dict[str, Any]:
        """Get bankroll performance summary."""
        history = self.db.get_bankroll_history(limit=1000)
        if not history:
            return {
                "current_balance": 0,
                "total_deposits": 0,
                "total_profit_loss": 0,
                "peak_balance": 0,
                "trough_balance": 0,
            }

        balances = [h["balance"] for h in history]
        return {
            "current_balance": balances[0] if balances else 0,
            "total_entries": len(history),
            "peak_balance": max(balances),
            "trough_balance": min(balances),
            "max_drawdown_pct": round(
                (max(balances) - min(balances)) / max(balances) * 100 if max(balances) > 0 else 0, 2
            ),
        }
