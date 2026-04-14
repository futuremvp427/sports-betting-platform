"""
Backtesting engine - simulates betting strategies on historical data.
Tracks bankroll progression, ROI, drawdown, hit rate, and more.
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime

from models.features import FeatureEngineer
from models.training.trainer import ModelTrainer
from decision.engine import DecisionEngine
from calibration.calibrator import ProbabilityCalibrator
from config import settings
from config.logging_config import get_logger

logger = get_logger("backtesting")


class BacktestEngine:
    """
    Simulates betting strategies on historical data.
    Supports multiple strategies and model comparison.
    """

    def __init__(self, initial_bankroll: float = None):
        self.initial_bankroll = initial_bankroll or settings.backtest.initial_bankroll
        self.results = []

    def run_backtest(self, historical_df: pd.DataFrame,
                     model_type: str = "gradient_boosting",
                     strategy: str = "value_betting",
                     train_pct: float = 0.6,
                     min_edge: float = None,
                     kelly_fraction: float = None) -> Dict[str, Any]:
        """
        Run a full backtest on historical data.

        1. Split data into train/test chronologically
        2. Train model on training set
        3. Generate predictions on test set
        4. Apply calibration
        5. Make betting decisions
        6. Simulate bankroll progression
        """
        if historical_df.empty or len(historical_df) < 50:
            return {"error": "Insufficient data for backtesting"}

        logger.info(f"Running backtest: {strategy} with {model_type} on {len(historical_df)} games")

        # Chronological split
        split_idx = int(len(historical_df) * train_pct)
        train_df = historical_df.iloc[:split_idx].copy()
        test_df = historical_df.iloc[split_idx:].copy()

        # Train model
        trainer = ModelTrainer(model_type=model_type)
        train_metrics = trainer.train(train_df)
        if "error" in train_metrics:
            return train_metrics

        # Feature engineer test data with full history
        fe = FeatureEngineer()
        full_featured = fe.create_features(historical_df.copy())
        test_featured = full_featured.iloc[split_idx:].copy()

        # Get predictions
        feature_cols = fe.get_prediction_features()
        valid_cols = [c for c in feature_cols if c in test_featured.columns]

        # Simulate
        bankroll = self.initial_bankroll
        bankroll_history = [bankroll]
        bets = []
        peak_bankroll = bankroll

        for idx, row in test_featured.iterrows():
            # Skip if missing features
            features = []
            valid = True
            for col in valid_cols:
                val = row.get(col)
                if pd.isna(val):
                    valid = False
                    break
                features.append(val)

            if not valid or not features:
                bankroll_history.append(bankroll)
                continue

            # Predict
            X = np.array([features])
            try:
                proba = trainer.model.predict_proba(X)[0]
                home_prob = float(proba[1]) if len(proba) > 1 else float(proba[0])
            except Exception:
                bankroll_history.append(bankroll)
                continue

            away_prob = 1.0 - home_prob

            # Get odds (from stored odds or synthetic)
            home_odds = row.get("home_odds")
            away_odds = row.get("away_odds")

            if home_odds is None or away_odds is None:
                bankroll_history.append(bankroll)
                continue

            # Decision engine
            engine = DecisionEngine(bankroll=bankroll)
            if min_edge is not None:
                engine.min_edge = min_edge
            if kelly_fraction is not None:
                engine.kelly_fraction = kelly_fraction

            prediction = {
                "home_team": row.get("home_team_name", "Home"),
                "away_team": row.get("away_team_name", "Away"),
                "home_win_prob": home_prob,
                "away_win_prob": away_prob,
                "calibrated_home_prob": home_prob,
                "calibrated_away_prob": away_prob,
                "confidence": abs(home_prob - 0.5) * 2,
            }

            odds_data = {
                "home_odds": float(home_odds),
                "away_odds": float(away_odds),
                "sportsbook": "backtest",
            }

            decisions = engine.evaluate_bet(prediction, odds_data)

            # Execute best decision
            if decisions:
                best = max(decisions, key=lambda d: d["edge"])
                stake = min(best["recommended_stake"], bankroll * 0.1)  # Cap at 10%

                if stake > 0 and bankroll >= stake:
                    # Determine outcome
                    actual_home_win = row.get("home_score", 0) > row.get("away_score", 0)
                    bet_won = (
                        (best["side"] == "home" and actual_home_win) or
                        (best["side"] == "away" and not actual_home_win)
                    )

                    if bet_won:
                        payout = stake * (best["decimal_odds"] - 1)
                        bankroll += payout
                    else:
                        bankroll -= stake

                    bets.append({
                        "game_idx": idx,
                        "side": best["side"],
                        "team": best["team"],
                        "odds": best["odds"],
                        "edge": best["edge"],
                        "ev": best["expected_value"],
                        "stake": round(stake, 2),
                        "won": bet_won,
                        "payout": round(payout if bet_won else -stake, 2),
                        "bankroll_after": round(bankroll, 2),
                    })

            bankroll_history.append(bankroll)
            peak_bankroll = max(peak_bankroll, bankroll)

        # Calculate metrics
        total_bets = len(bets)
        winning_bets = sum(1 for b in bets if b["won"])
        losing_bets = total_bets - winning_bets

        roi = ((bankroll - self.initial_bankroll) / self.initial_bankroll * 100) if self.initial_bankroll > 0 else 0
        hit_rate = (winning_bets / total_bets * 100) if total_bets > 0 else 0

        # Max drawdown
        max_drawdown = 0
        peak = self.initial_bankroll
        for b in bankroll_history:
            peak = max(peak, b)
            drawdown = (peak - b) / peak * 100 if peak > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)

        # Sharpe ratio approximation
        if bets:
            returns = [b["payout"] / b["stake"] if b["stake"] > 0 else 0 for b in bets]
            sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(len(returns))) if np.std(returns) > 0 else 0
        else:
            sharpe = 0

        avg_edge = np.mean([b["edge"] for b in bets]) if bets else 0

        result = {
            "name": f"backtest_{model_type}_{strategy}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "strategy": strategy,
            "model_name": model_type,
            "sport": historical_df.get("sport", pd.Series(["unknown"])).iloc[0] if "sport" in historical_df.columns else "unknown",
            "start_date": str(historical_df["scheduled_time"].min()) if "scheduled_time" in historical_df.columns else "unknown",
            "end_date": str(historical_df["scheduled_time"].max()) if "scheduled_time" in historical_df.columns else "unknown",
            "initial_bankroll": self.initial_bankroll,
            "final_bankroll": round(bankroll, 2),
            "total_bets": total_bets,
            "winning_bets": winning_bets,
            "losing_bets": losing_bets,
            "roi": round(roi, 2),
            "hit_rate": round(hit_rate, 2),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe, 4),
            "avg_edge": round(avg_edge, 4),
            "bankroll_history": bankroll_history,
            "bets": bets,
            "train_metrics": train_metrics,
        }

        self.results.append(result)
        logger.info(
            f"Backtest complete: {total_bets} bets, "
            f"ROI: {roi:.2f}%, Hit rate: {hit_rate:.1f}%, "
            f"Final bankroll: ${bankroll:.2f}"
        )
        return result

    def compare_strategies(self, historical_df: pd.DataFrame,
                           strategies: List[Dict] = None) -> pd.DataFrame:
        """
        Compare multiple strategies/models on the same data.
        Returns a comparison DataFrame.
        """
        if strategies is None:
            strategies = [
                {"model_type": "logistic_regression", "strategy": "value_betting"},
                {"model_type": "random_forest", "strategy": "value_betting"},
                {"model_type": "gradient_boosting", "strategy": "value_betting"},
                {"model_type": "gradient_boosting", "strategy": "value_betting", "min_edge": 0.05},
                {"model_type": "gradient_boosting", "strategy": "value_betting", "kelly_fraction": 0.1},
            ]

        results = []
        for strat in strategies:
            result = self.run_backtest(historical_df, **strat)
            if "error" not in result:
                results.append({
                    "model": strat.get("model_type"),
                    "strategy": strat.get("strategy"),
                    "min_edge": strat.get("min_edge", settings.betting.min_edge),
                    "kelly_fraction": strat.get("kelly_fraction", settings.betting.kelly_fraction),
                    "total_bets": result["total_bets"],
                    "roi": result["roi"],
                    "hit_rate": result["hit_rate"],
                    "max_drawdown": result["max_drawdown"],
                    "sharpe": result["sharpe_ratio"],
                    "final_bankroll": result["final_bankroll"],
                })

        return pd.DataFrame(results).sort_values("roi", ascending=False) if results else pd.DataFrame()
