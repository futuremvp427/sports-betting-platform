"""
Database manager for the Sports Betting Intelligence Platform.
Uses SQLite for simplicity and portability. All entities are stored
in a single database with proper schema and indexing.
"""
import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from config.logging_config import get_logger

logger = get_logger("storage")

SCHEMA_SQL = """
-- Teams table
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    abbreviation TEXT,
    sport TEXT NOT NULL,
    league TEXT NOT NULL,
    external_id TEXT,
    metadata TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, sport, league)
);

-- Games table
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT UNIQUE,
    sport TEXT NOT NULL,
    league TEXT NOT NULL,
    home_team_id INTEGER REFERENCES teams(id),
    away_team_id INTEGER REFERENCES teams(id),
    home_team_name TEXT NOT NULL,
    away_team_name TEXT NOT NULL,
    scheduled_time TIMESTAMP,
    status TEXT DEFAULT 'scheduled',
    home_score INTEGER,
    away_score INTEGER,
    winner TEXT,
    season TEXT,
    week TEXT,
    venue TEXT,
    metadata TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Odds snapshots table
CREATE TABLE IF NOT EXISTS odds_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER REFERENCES games(id),
    external_game_id TEXT,
    sport TEXT NOT NULL,
    sportsbook TEXT NOT NULL,
    market_type TEXT NOT NULL DEFAULT 'h2h',
    home_odds REAL,
    away_odds REAL,
    draw_odds REAL,
    spread_home REAL,
    spread_away REAL,
    spread_home_odds REAL,
    spread_away_odds REAL,
    total_over REAL,
    total_under REAL,
    total_over_odds REAL,
    total_under_odds REAL,
    snapshot_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source TEXT DEFAULT 'odds_api',
    raw_data TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Predictions table
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER REFERENCES games(id),
    model_name TEXT NOT NULL,
    model_version TEXT DEFAULT '1.0',
    sport TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    predicted_winner TEXT,
    home_win_prob REAL,
    away_win_prob REAL,
    draw_prob REAL,
    confidence REAL,
    features_used TEXT DEFAULT '{}',
    prediction_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Calibrated predictions table
CREATE TABLE IF NOT EXISTS calibrated_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id INTEGER REFERENCES predictions(id),
    game_id INTEGER REFERENCES games(id),
    calibration_method TEXT NOT NULL,
    original_home_prob REAL,
    original_away_prob REAL,
    calibrated_home_prob REAL,
    calibrated_away_prob REAL,
    calibration_adjustment REAL,
    reliability_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bet decisions table
CREATE TABLE IF NOT EXISTS bet_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER REFERENCES games(id),
    prediction_id INTEGER REFERENCES predictions(id),
    calibrated_prediction_id INTEGER REFERENCES calibrated_predictions(id),
    decision_type TEXT NOT NULL DEFAULT 'value_bet',
    side TEXT NOT NULL,
    sportsbook TEXT,
    odds REAL NOT NULL,
    implied_prob REAL,
    predicted_prob REAL,
    edge REAL,
    expected_value REAL,
    recommended_stake REAL,
    kelly_fraction REAL,
    confidence REAL,
    justification TEXT,
    status TEXT DEFAULT 'recommended',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Placed bets table
CREATE TABLE IF NOT EXISTS placed_bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id INTEGER REFERENCES bet_decisions(id),
    game_id INTEGER REFERENCES games(id),
    stake REAL NOT NULL,
    odds REAL NOT NULL,
    side TEXT NOT NULL,
    sportsbook TEXT,
    placed_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    settled_time TIMESTAMP,
    outcome TEXT,
    payout REAL,
    profit_loss REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bankroll logs table
CREATE TABLE IF NOT EXISTS bankroll_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    balance REAL NOT NULL,
    change_amount REAL DEFAULT 0,
    change_reason TEXT,
    bet_id INTEGER REFERENCES placed_bets(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model metrics table
CREATE TABLE IF NOT EXISTS model_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    model_version TEXT DEFAULT '1.0',
    sport TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    sample_size INTEGER,
    evaluation_period TEXT,
    metadata TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Backtest runs table
CREATE TABLE IF NOT EXISTS backtest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    strategy TEXT NOT NULL,
    model_name TEXT,
    sport TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    initial_bankroll REAL NOT NULL,
    final_bankroll REAL,
    total_bets INTEGER DEFAULT 0,
    winning_bets INTEGER DEFAULT 0,
    losing_bets INTEGER DEFAULT 0,
    roi REAL,
    max_drawdown REAL,
    sharpe_ratio REAL,
    hit_rate REAL,
    avg_edge REAL,
    parameters TEXT DEFAULT '{}',
    results_summary TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Arbitrage opportunities table
CREATE TABLE IF NOT EXISTS arbitrage_opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER REFERENCES games(id),
    sport TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    book_a TEXT NOT NULL,
    book_b TEXT NOT NULL,
    side_a TEXT NOT NULL,
    side_b TEXT NOT NULL,
    odds_a REAL NOT NULL,
    odds_b REAL NOT NULL,
    profit_pct REAL NOT NULL,
    stake_a REAL,
    stake_b REAL,
    total_stake REAL,
    guaranteed_profit REAL,
    detected_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expiry_time TIMESTAMP,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Outcomes table (for learning)
CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER REFERENCES games(id),
    prediction_id INTEGER REFERENCES predictions(id),
    actual_winner TEXT,
    home_score INTEGER,
    away_score INTEGER,
    prediction_correct INTEGER,
    probability_error REAL,
    edge_realized REAL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_games_sport ON games(sport);
CREATE INDEX IF NOT EXISTS idx_games_status ON games(status);
CREATE INDEX IF NOT EXISTS idx_games_scheduled ON games(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_odds_game ON odds_snapshots(game_id);
CREATE INDEX IF NOT EXISTS idx_odds_sport ON odds_snapshots(sport);
CREATE INDEX IF NOT EXISTS idx_odds_time ON odds_snapshots(snapshot_time);
CREATE INDEX IF NOT EXISTS idx_predictions_game ON predictions(game_id);
CREATE INDEX IF NOT EXISTS idx_predictions_model ON predictions(model_name);
CREATE INDEX IF NOT EXISTS idx_decisions_game ON bet_decisions(game_id);
CREATE INDEX IF NOT EXISTS idx_bets_game ON placed_bets(game_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_game ON outcomes(game_id);
CREATE INDEX IF NOT EXISTS idx_arb_sport ON arbitrage_opportunities(sport);
"""


class DatabaseManager:
    """Manages all database operations for the platform."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from config import settings
            db_path = settings.database.db_path
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            logger.info(f"Database initialized at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    # ---- Team operations ----
    def upsert_team(self, name: str, sport: str, league: str,
                    abbreviation: str = None, external_id: str = None) -> int:
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO teams (name, sport, league, abbreviation, external_id)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(name, sport, league) DO UPDATE SET
                   abbreviation=COALESCE(excluded.abbreviation, teams.abbreviation),
                   external_id=COALESCE(excluded.external_id, teams.external_id)""",
                (name, sport, league, abbreviation, external_id)
            )
            cursor = conn.execute(
                "SELECT id FROM teams WHERE name=? AND sport=? AND league=?",
                (name, sport, league)
            )
            return cursor.fetchone()["id"]

    # ---- Game operations ----
    def upsert_game(self, **kwargs) -> int:
        with self._get_connection() as conn:
            ext_id = kwargs.get("external_id")
            if ext_id:
                existing = conn.execute(
                    "SELECT id FROM games WHERE external_id=?", (ext_id,)
                ).fetchone()
                if existing:
                    sets = ", ".join(f"{k}=?" for k in kwargs if k != "external_id")
                    vals = [v for k, v in kwargs.items() if k != "external_id"]
                    vals.append(ext_id)
                    conn.execute(f"UPDATE games SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE external_id=?", vals)
                    return existing["id"]
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" * len(kwargs))
            conn.execute(f"INSERT INTO games ({cols}) VALUES ({placeholders})", list(kwargs.values()))
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_games(self, sport: str = None, status: str = None,
                  limit: int = 100) -> List[Dict]:
        with self._get_connection() as conn:
            query = "SELECT * FROM games WHERE 1=1"
            params = []
            if sport:
                query += " AND sport=?"
                params.append(sport)
            if status:
                query += " AND status=?"
                params.append(status)
            query += " ORDER BY scheduled_time DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    # ---- Odds operations ----
    def insert_odds_snapshot(self, **kwargs) -> int:
        with self._get_connection() as conn:
            if "raw_data" in kwargs and isinstance(kwargs["raw_data"], dict):
                kwargs["raw_data"] = json.dumps(kwargs["raw_data"])
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" * len(kwargs))
            conn.execute(f"INSERT INTO odds_snapshots ({cols}) VALUES ({placeholders})", list(kwargs.values()))
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_latest_odds(self, game_id: int = None, sport: str = None) -> List[Dict]:
        with self._get_connection() as conn:
            query = """SELECT * FROM odds_snapshots WHERE 1=1"""
            params = []
            if game_id:
                query += " AND game_id=?"
                params.append(game_id)
            if sport:
                query += " AND sport=?"
                params.append(sport)
            query += " ORDER BY snapshot_time DESC LIMIT 100"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    # ---- Prediction operations ----
    def insert_prediction(self, **kwargs) -> int:
        with self._get_connection() as conn:
            if "features_used" in kwargs and isinstance(kwargs["features_used"], dict):
                kwargs["features_used"] = json.dumps(kwargs["features_used"])
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" * len(kwargs))
            conn.execute(f"INSERT INTO predictions ({cols}) VALUES ({placeholders})", list(kwargs.values()))
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_predictions(self, game_id: int = None, model_name: str = None,
                        limit: int = 100) -> List[Dict]:
        with self._get_connection() as conn:
            query = "SELECT * FROM predictions WHERE 1=1"
            params = []
            if game_id:
                query += " AND game_id=?"
                params.append(game_id)
            if model_name:
                query += " AND model_name=?"
                params.append(model_name)
            query += " ORDER BY prediction_time DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    # ---- Calibrated prediction operations ----
    def insert_calibrated_prediction(self, **kwargs) -> int:
        with self._get_connection() as conn:
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" * len(kwargs))
            conn.execute(f"INSERT INTO calibrated_predictions ({cols}) VALUES ({placeholders})", list(kwargs.values()))
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # ---- Bet decision operations ----
    def insert_bet_decision(self, **kwargs) -> int:
        with self._get_connection() as conn:
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" * len(kwargs))
            conn.execute(f"INSERT INTO bet_decisions ({cols}) VALUES ({placeholders})", list(kwargs.values()))
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_bet_decisions(self, status: str = None, limit: int = 100) -> List[Dict]:
        with self._get_connection() as conn:
            query = "SELECT * FROM bet_decisions WHERE 1=1"
            params = []
            if status:
                query += " AND status=?"
                params.append(status)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    # ---- Placed bet operations ----
    def insert_placed_bet(self, **kwargs) -> int:
        with self._get_connection() as conn:
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" * len(kwargs))
            conn.execute(f"INSERT INTO placed_bets ({cols}) VALUES ({placeholders})", list(kwargs.values()))
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # ---- Bankroll operations ----
    def log_bankroll(self, balance: float, change_amount: float = 0,
                     change_reason: str = None, bet_id: int = None) -> int:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO bankroll_logs (balance, change_amount, change_reason, bet_id) VALUES (?,?,?,?)",
                (balance, change_amount, change_reason, bet_id)
            )
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_bankroll_history(self, limit: int = 100) -> List[Dict]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM bankroll_logs ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ---- Model metrics operations ----
    def insert_model_metric(self, **kwargs) -> int:
        with self._get_connection() as conn:
            if "metadata" in kwargs and isinstance(kwargs["metadata"], dict):
                kwargs["metadata"] = json.dumps(kwargs["metadata"])
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" * len(kwargs))
            conn.execute(f"INSERT INTO model_metrics ({cols}) VALUES ({placeholders})", list(kwargs.values()))
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_model_metrics(self, model_name: str = None, limit: int = 50) -> List[Dict]:
        with self._get_connection() as conn:
            query = "SELECT * FROM model_metrics WHERE 1=1"
            params = []
            if model_name:
                query += " AND model_name=?"
                params.append(model_name)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    # ---- Backtest operations ----
    def insert_backtest_run(self, **kwargs) -> int:
        with self._get_connection() as conn:
            for key in ("parameters", "results_summary"):
                if key in kwargs and isinstance(kwargs[key], dict):
                    kwargs[key] = json.dumps(kwargs[key])
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" * len(kwargs))
            conn.execute(f"INSERT INTO backtest_runs ({cols}) VALUES ({placeholders})", list(kwargs.values()))
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_backtest_runs(self, sport: str = None, limit: int = 50) -> List[Dict]:
        with self._get_connection() as conn:
            query = "SELECT * FROM backtest_runs WHERE 1=1"
            params = []
            if sport:
                query += " AND sport=?"
                params.append(sport)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    # ---- Arbitrage operations ----
    def insert_arbitrage_opportunity(self, **kwargs) -> int:
        with self._get_connection() as conn:
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" * len(kwargs))
            conn.execute(f"INSERT INTO arbitrage_opportunities ({cols}) VALUES ({placeholders})", list(kwargs.values()))
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_arbitrage_opportunities(self, sport: str = None, status: str = "active",
                                    limit: int = 50) -> List[Dict]:
        with self._get_connection() as conn:
            query = "SELECT * FROM arbitrage_opportunities WHERE 1=1"
            params = []
            if sport:
                query += " AND sport=?"
                params.append(sport)
            if status:
                query += " AND status=?"
                params.append(status)
            query += " ORDER BY profit_pct DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    # ---- Outcome operations ----
    def insert_outcome(self, **kwargs) -> int:
        with self._get_connection() as conn:
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" * len(kwargs))
            conn.execute(f"INSERT INTO outcomes ({cols}) VALUES ({placeholders})", list(kwargs.values()))
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_outcomes(self, limit: int = 100) -> List[Dict]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM outcomes ORDER BY recorded_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ---- Generic query ----
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get summary statistics for the dashboard."""
        with self._get_connection() as conn:
            summary = {}
            summary["total_games"] = conn.execute("SELECT COUNT(*) as c FROM games").fetchone()["c"]
            summary["total_predictions"] = conn.execute("SELECT COUNT(*) as c FROM predictions").fetchone()["c"]
            summary["total_bets"] = conn.execute("SELECT COUNT(*) as c FROM placed_bets").fetchone()["c"]
            summary["total_arb_opps"] = conn.execute("SELECT COUNT(*) as c FROM arbitrage_opportunities").fetchone()["c"]

            bankroll = conn.execute("SELECT balance FROM bankroll_logs ORDER BY timestamp DESC LIMIT 1").fetchone()
            summary["current_bankroll"] = bankroll["balance"] if bankroll else 0

            outcomes = conn.execute(
                "SELECT COUNT(*) as total, SUM(prediction_correct) as correct FROM outcomes WHERE prediction_correct IS NOT NULL"
            ).fetchone()
            summary["accuracy"] = (outcomes["correct"] / outcomes["total"] * 100) if outcomes["total"] and outcomes["correct"] else 0
            summary["total_outcomes"] = outcomes["total"] or 0

            return summary


# Module-level singleton
_db_instance: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """Get or create the singleton database manager."""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance
