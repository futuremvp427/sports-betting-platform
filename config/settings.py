"""
Unified configuration for the Sports Betting Intelligence Platform.
All secrets are loaded from environment variables.
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OddsAPIConfig:
    api_key: str = field(default_factory=lambda: os.getenv("ODDS_API_KEY", ""))
    base_url: str = "https://api.the-odds-api.com/v4"
    default_regions: str = "us"
    default_markets: str = "h2h,spreads,totals"
    default_odds_format: str = "american"


@dataclass
class ESPNConfig:
    base_url: str = "https://site.api.espn.com/apis/site/v2/sports"
    supported_sports: list = field(default_factory=lambda: [
        "basketball/nba",
        "football/nfl",
        "baseball/mlb",
        "hockey/nhl",
    ])


@dataclass
class DatabaseConfig:
    db_path: str = field(default_factory=lambda: os.getenv(
        "DB_PATH",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "betting.db")
    ))


@dataclass
class ModelConfig:
    models_dir: str = field(default_factory=lambda: os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "models", "saved"
    ))
    default_model: str = "xgboost"
    calibration_method: str = "isotonic"
    min_confidence: float = 0.55
    retrain_interval_hours: int = 24


@dataclass
class BettingConfig:
    min_edge: float = 0.03
    max_bet_fraction: float = 0.05  # Kelly fraction cap
    min_odds: float = -500
    max_odds: float = 500
    initial_bankroll: float = 10000.0
    kelly_fraction: float = 0.25  # Quarter Kelly


@dataclass
class ArbitrageConfig:
    min_profit_pct: float = 0.5
    max_books: int = 10
    refresh_interval_seconds: int = 60


@dataclass
class BacktestConfig:
    default_start_date: str = "2024-01-01"
    default_end_date: str = "2025-12-31"
    initial_bankroll: float = 10000.0
    commission_rate: float = 0.0


@dataclass
class APIConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    cors_origins: list = field(default_factory=lambda: ["*"])


@dataclass
class Settings:
    odds_api: OddsAPIConfig = field(default_factory=OddsAPIConfig)
    espn: ESPNConfig = field(default_factory=ESPNConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    betting: BettingConfig = field(default_factory=BettingConfig)
    arbitrage: ArbitrageConfig = field(default_factory=ArbitrageConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    api: APIConfig = field(default_factory=APIConfig)


# Singleton settings instance
settings = Settings()
