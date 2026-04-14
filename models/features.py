"""
Feature engineering module.
Transforms raw game data into features for machine learning models.
Adapted from ml-for-sports-betting and NBA-Machine-Learning-Sports-Betting patterns.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional

from config.logging_config import get_logger

logger = get_logger("models.features")


class FeatureEngineer:
    """
    Transforms raw sports data into ML-ready features.
    Supports rolling statistics, head-to-head features, and contextual factors.
    """

    def __init__(self, window_sizes: List[int] = None):
        self.window_sizes = window_sizes or [3, 5, 10]

    def create_features(self, games_df: pd.DataFrame) -> pd.DataFrame:
        """
        Create a full feature set from historical game data.
        Expects columns: home_team_name, away_team_name, home_score, away_score,
                         scheduled_time, winner
        """
        if games_df.empty:
            logger.warning("Empty DataFrame provided for feature engineering")
            return games_df

        df = games_df.copy()
        df = self._ensure_columns(df)
        df = df.sort_values("scheduled_time").reset_index(drop=True)

        # Basic features
        df["score_diff"] = df["home_score"] - df["away_score"]
        df["total_score"] = df["home_score"] + df["away_score"]
        df["home_win"] = (df["home_score"] > df["away_score"]).astype(int)

        # Rolling features per team
        df = self._add_rolling_features(df)

        # Head-to-head features
        df = self._add_h2h_features(df)

        # Rest days feature
        df = self._add_rest_days(df)

        # Strength of schedule proxy
        df = self._add_sos_proxy(df)

        logger.info(f"Created {len(df.columns)} features for {len(df)} games")
        return df

    def _ensure_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure required columns exist."""
        required = ["home_team_name", "away_team_name", "home_score", "away_score", "scheduled_time"]
        for col in required:
            if col not in df.columns:
                logger.warning(f"Missing column: {col}")
                if col in ("home_score", "away_score"):
                    df[col] = 0
                elif col == "scheduled_time":
                    df[col] = pd.Timestamp.now()
                else:
                    df[col] = "Unknown"

        df["home_score"] = pd.to_numeric(df["home_score"], errors="coerce").fillna(0)
        df["away_score"] = pd.to_numeric(df["away_score"], errors="coerce").fillna(0)
        df["scheduled_time"] = pd.to_datetime(df["scheduled_time"], errors="coerce")
        return df

    def _add_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add rolling average features for each team."""
        all_teams = set(df["home_team_name"].unique()) | set(df["away_team_name"].unique())

        for window in self.window_sizes:
            home_roll_col = f"home_avg_score_{window}"
            away_roll_col = f"away_avg_score_{window}"
            home_win_rate_col = f"home_win_rate_{window}"
            away_win_rate_col = f"away_win_rate_{window}"

            df[home_roll_col] = np.nan
            df[away_roll_col] = np.nan
            df[home_win_rate_col] = np.nan
            df[away_win_rate_col] = np.nan

            # Build team game history
            team_scores = {team: [] for team in all_teams}
            team_wins = {team: [] for team in all_teams}

            for idx, row in df.iterrows():
                home = row["home_team_name"]
                away = row["away_team_name"]

                # Set features from history
                if len(team_scores[home]) >= window:
                    df.at[idx, home_roll_col] = np.mean(team_scores[home][-window:])
                    df.at[idx, home_win_rate_col] = np.mean(team_wins[home][-window:])
                if len(team_scores[away]) >= window:
                    df.at[idx, away_roll_col] = np.mean(team_scores[away][-window:])
                    df.at[idx, away_win_rate_col] = np.mean(team_wins[away][-window:])

                # Update history
                team_scores[home].append(row["home_score"])
                team_scores[away].append(row["away_score"])
                home_won = 1 if row["home_score"] > row["away_score"] else 0
                team_wins[home].append(home_won)
                team_wins[away].append(1 - home_won)

        return df

    def _add_h2h_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add head-to-head features between matchup teams."""
        df["h2h_home_wins"] = 0
        df["h2h_total_games"] = 0
        df["h2h_avg_score_diff"] = 0.0

        h2h_history = {}

        for idx, row in df.iterrows():
            matchup_key = tuple(sorted([row["home_team_name"], row["away_team_name"]]))

            if matchup_key in h2h_history:
                history = h2h_history[matchup_key]
                home_wins = sum(
                    1 for g in history
                    if g["winner"] == row["home_team_name"]
                )
                total = len(history)
                avg_diff = np.mean([
                    g["home_score"] - g["away_score"]
                    if g["home_team"] == row["home_team_name"]
                    else g["away_score"] - g["home_score"]
                    for g in history
                ])

                df.at[idx, "h2h_home_wins"] = home_wins
                df.at[idx, "h2h_total_games"] = total
                df.at[idx, "h2h_avg_score_diff"] = avg_diff

            # Update history
            if matchup_key not in h2h_history:
                h2h_history[matchup_key] = []
            h2h_history[matchup_key].append({
                "home_team": row["home_team_name"],
                "away_team": row["away_team_name"],
                "home_score": row["home_score"],
                "away_score": row["away_score"],
                "winner": row["home_team_name"] if row["home_score"] > row["away_score"] else row["away_team_name"],
            })

        return df

    def _add_rest_days(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add rest days feature for each team."""
        df["home_rest_days"] = np.nan
        df["away_rest_days"] = np.nan

        last_game = {}

        for idx, row in df.iterrows():
            home = row["home_team_name"]
            away = row["away_team_name"]
            game_time = row["scheduled_time"]

            if pd.notna(game_time):
                if home in last_game:
                    delta = (game_time - last_game[home]).days
                    df.at[idx, "home_rest_days"] = max(0, delta)
                if away in last_game:
                    delta = (game_time - last_game[away]).days
                    df.at[idx, "away_rest_days"] = max(0, delta)

                last_game[home] = game_time
                last_game[away] = game_time

        return df

    def _add_sos_proxy(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add a simple strength-of-schedule proxy based on opponent win rates."""
        # Calculate overall win rates
        team_records = {}
        for _, row in df.iterrows():
            home = row["home_team_name"]
            away = row["away_team_name"]
            home_won = row["home_score"] > row["away_score"]

            for team in (home, away):
                if team not in team_records:
                    team_records[team] = {"wins": 0, "games": 0}

            team_records[home]["games"] += 1
            team_records[away]["games"] += 1
            if home_won:
                team_records[home]["wins"] += 1
            else:
                team_records[away]["wins"] += 1

        # Map opponent win rates
        def get_win_rate(team):
            if team in team_records and team_records[team]["games"] > 0:
                return team_records[team]["wins"] / team_records[team]["games"]
            return 0.5

        df["home_opp_win_rate"] = df["away_team_name"].apply(get_win_rate)
        df["away_opp_win_rate"] = df["home_team_name"].apply(get_win_rate)

        return df

    def get_feature_columns(self) -> List[str]:
        """Return the list of feature columns used for modeling."""
        base_features = [
            "score_diff", "total_score",
            "h2h_home_wins", "h2h_total_games", "h2h_avg_score_diff",
            "home_rest_days", "away_rest_days",
            "home_opp_win_rate", "away_opp_win_rate",
        ]
        for w in self.window_sizes:
            base_features.extend([
                f"home_avg_score_{w}", f"away_avg_score_{w}",
                f"home_win_rate_{w}", f"away_win_rate_{w}",
            ])
        return base_features

    def get_prediction_features(self) -> List[str]:
        """Return features used at prediction time (excludes target-leaking features)."""
        features = []
        for w in self.window_sizes:
            features.extend([
                f"home_avg_score_{w}", f"away_avg_score_{w}",
                f"home_win_rate_{w}", f"away_win_rate_{w}",
            ])
        features.extend([
            "h2h_home_wins", "h2h_total_games", "h2h_avg_score_diff",
            "home_rest_days", "away_rest_days",
            "home_opp_win_rate", "away_opp_win_rate",
        ])
        return features
