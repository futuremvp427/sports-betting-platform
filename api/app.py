"""
FastAPI application - exposes all platform functionality via REST endpoints.
Serves both the API and the static dashboard frontend.
"""
import os
import sys
import json
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from config.logging_config import setup_logging, get_logger
from storage.database import get_db
from data.providers.odds_api import OddsAPIProvider
from data.providers.espn import ESPNProvider
from data.normalization.normalizer import DataNormalizer
from data.historical.loader import HistoricalDataLoader
from models.training.trainer import ModelTrainer
from models.inference.predictor import Predictor
from models.features import FeatureEngineer
from calibration.calibrator import ProbabilityCalibrator
from decision.engine import DecisionEngine
from arbitrage.scanner import ArbitrageScanner
from backtesting.engine import BacktestEngine
from learning.tracker import LearningTracker

# Setup logging
setup_logging()
logger = get_logger("api")

# Initialize FastAPI
app = FastAPI(
    title="Sports Betting Intelligence Platform",
    description="Unified sports betting intelligence system with data ingestion, ML predictions, calibration, EV analysis, arbitrage detection, backtesting, and learning.",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
db = get_db()
odds_provider = OddsAPIProvider()
espn_provider = ESPNProvider()
normalizer = DataNormalizer()
historical_loader = HistoricalDataLoader()
calibrator = ProbabilityCalibrator()
decision_engine = DecisionEngine()
arb_scanner = ArbitrageScanner()
learning_tracker = LearningTracker()


# ==================== Dashboard ====================

dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "dist")

if os.path.exists(dashboard_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(dashboard_dir, "assets")), name="assets")


@app.get("/")
async def serve_dashboard():
    """Serve the dashboard frontend."""
    index_path = os.path.join(dashboard_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Sports Betting Intelligence Platform API", "docs": "/docs"}


# ==================== Health ====================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


# ==================== Dashboard Summary ====================

@app.get("/api/dashboard/summary")
async def dashboard_summary():
    """Get dashboard summary statistics."""
    try:
        summary = db.get_dashboard_summary()
        return summary
    except Exception as e:
        logger.error(f"Dashboard summary error: {e}")
        return {"error": str(e)}


# ==================== Sports & Events ====================

@app.get("/api/sports")
async def get_sports():
    """Get list of available sports."""
    return odds_provider.get_sports()


@app.get("/api/games")
async def get_games(
    sport: Optional[str] = Query(None, description="Sport filter (nba, nfl, mlb, nhl)"),
    status: Optional[str] = Query(None, description="Status filter (scheduled, final)"),
    limit: int = Query(50, ge=1, le=500),
):
    """Get games from database."""
    return db.get_games(sport=sport, status=status, limit=limit)


@app.get("/api/games/live")
async def get_live_games(sport: str = Query("nba", description="Sport")):
    """Get live game data from ESPN (real data, no API key required)."""
    try:
        events = espn_provider.get_events(sport)
        return events
    except Exception as e:
        logger.error(f"Live games error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/games/sync")
async def sync_games(sport: str = Query("nba", description="Sport")):
    """Sync games from ESPN to database."""
    try:
        events = espn_provider.get_events(sport)
        count = 0
        for event in events:
            normalized = normalizer.normalize_game(event, source="espn")
            db.upsert_game(**normalized)
            count += 1
        return {"synced": count, "sport": sport}
    except Exception as e:
        logger.error(f"Game sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Odds ====================

@app.get("/api/odds")
async def get_odds(
    sport: str = Query("nba", description="Sport"),
    game_id: Optional[int] = Query(None),
):
    """Get odds from database."""
    return db.get_latest_odds(game_id=game_id, sport=sport)


@app.get("/api/odds/live")
async def get_live_odds(sport: str = Query("nba", description="Sport")):
    """Fetch live odds from The Odds API (requires ODDS_API_KEY env var).
    Falls back to realistic demo data if API key not configured.
    """
    try:
        odds = odds_provider.get_odds(sport)
        return odds
    except Exception as e:
        logger.error(f"Live odds error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/odds/sync")
async def sync_odds(sport: str = Query("nba", description="Sport")):
    """Fetch and store live odds."""
    try:
        odds = odds_provider.get_odds(sport)
        count = 0
        for o in odds:
            normalized = normalizer.normalize_odds_snapshot(o)
            db.insert_odds_snapshot(**normalized)
            count += 1
        return {"synced": count, "sport": sport}
    except Exception as e:
        logger.error(f"Odds sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Predictions ====================

@app.get("/api/predictions")
async def get_predictions(
    game_id: Optional[int] = Query(None),
    model_name: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Get stored predictions."""
    return db.get_predictions(game_id=game_id, model_name=model_name, limit=limit)


@app.post("/api/predictions/generate")
async def generate_predictions(sport: str = Query("nba", description="Sport")):
    """Generate predictions for upcoming games."""
    try:
        # Get upcoming games
        events = espn_provider.get_events(sport)
        if not events:
            return {"predictions": [], "message": "No upcoming games found"}

        import pandas as pd
        games_df = pd.DataFrame(events)

        # Get historical data for features
        historical = db.get_games(sport=sport, status="final", limit=500)
        hist_df = pd.DataFrame(historical) if historical else pd.DataFrame()

        # Generate predictions
        predictor = Predictor()
        predictions = predictor.predict(games_df, hist_df)

        # Calibrate
        calibrated = [calibrator.calibrate_prediction(p) for p in predictions]

        # Store predictions
        for pred in calibrated:
            try:
                db.insert_prediction(
                    model_name=pred.get("model_name", "unknown"),
                    model_version=pred.get("model_version", "1.0"),
                    sport=sport,
                    home_team=pred.get("home_team", "Unknown"),
                    away_team=pred.get("away_team", "Unknown"),
                    predicted_winner=pred.get("predicted_winner"),
                    home_win_prob=pred.get("calibrated_home_prob", pred.get("home_win_prob")),
                    away_win_prob=pred.get("calibrated_away_prob", pred.get("away_win_prob")),
                    confidence=pred.get("confidence"),
                )
            except Exception as e:
                logger.warning(f"Failed to store prediction: {e}")

        return {"predictions": calibrated, "count": len(calibrated)}
    except Exception as e:
        logger.error(f"Prediction generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Edges / Value Bets ====================

@app.get("/api/edges")
async def get_edges(sport: str = Query("nba", description="Sport")):
    """Get current value bet opportunities (edges)."""
    try:
        # Get predictions
        predictions = db.get_predictions(limit=50)
        if not predictions:
            return {"edges": [], "message": "No predictions available. Generate predictions first."}

        # Get latest odds
        odds = db.get_latest_odds(sport=sport)
        if not odds:
            return {"edges": [], "message": "No odds available. Sync odds first."}

        # Evaluate edges
        edges = decision_engine.evaluate_slate(predictions, odds)
        return {"edges": edges, "count": len(edges)}
    except Exception as e:
        logger.error(f"Edge calculation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/decisions")
async def get_decisions(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Get bet decisions."""
    return db.get_bet_decisions(status=status, limit=limit)


# ==================== Arbitrage ====================

@app.get("/api/arbitrage")
async def get_arbitrage(
    sport: Optional[str] = Query(None),
    status: str = Query("active"),
    limit: int = Query(50, ge=1, le=200),
):
    """Get stored arbitrage opportunities."""
    return db.get_arbitrage_opportunities(sport=sport, status=status, limit=limit)


@app.post("/api/arbitrage/scan")
async def scan_arbitrage(sport: str = Query("nba", description="Sport")):
    """Scan for arbitrage opportunities in live odds."""
    try:
        odds = odds_provider.get_odds(sport)
        opportunities = arb_scanner.find_arbitrage(odds)

        # Store opportunities
        for opp in opportunities:
            try:
                db.insert_arbitrage_opportunity(
                    sport=opp["sport"],
                    home_team=opp["home_team"],
                    away_team=opp["away_team"],
                    book_a=opp["book_a"],
                    book_b=opp["book_b"],
                    side_a=opp["side_a"],
                    side_b=opp["side_b"],
                    odds_a=opp["odds_a"],
                    odds_b=opp["odds_b"],
                    profit_pct=opp["profit_pct"],
                    stake_a=opp.get("stake_a"),
                    stake_b=opp.get("stake_b"),
                    total_stake=opp.get("total_stake"),
                    guaranteed_profit=opp.get("guaranteed_profit"),
                    status="active",
                )
            except Exception as e:
                logger.warning(f"Failed to store arb opportunity: {e}")

        return {"opportunities": opportunities, "count": len(opportunities)}
    except Exception as e:
        logger.error(f"Arbitrage scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Backtesting ====================

@app.get("/api/backtests")
async def get_backtests(
    sport: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """Get backtest run results."""
    return db.get_backtest_runs(sport=sport, limit=limit)


@app.post("/api/backtests/run")
async def run_backtest(
    sport: str = Query("nba"),
    model_type: str = Query("gradient_boosting"),
    num_games: int = Query(500, ge=50, le=5000),
):
    """Run a backtest with synthetic or historical data."""
    try:
        # Generate or load historical data
        hist_df = historical_loader.get_historical_dataframe(sport=sport, limit=num_games)

        if hist_df.empty or len(hist_df) < 50:
            logger.info("Insufficient historical data, generating synthetic data...")
            hist_df = historical_loader.generate_synthetic_data(sport=sport, num_games=num_games)
            historical_loader.store_synthetic_data(hist_df)

        # Run backtest
        engine = BacktestEngine()
        result = engine.run_backtest(hist_df, model_type=model_type)

        if "error" not in result:
            # Store backtest run
            db.insert_backtest_run(
                name=result["name"],
                strategy=result["strategy"],
                model_name=result["model_name"],
                sport=result.get("sport", sport),
                start_date=result.get("start_date", ""),
                end_date=result.get("end_date", ""),
                initial_bankroll=result["initial_bankroll"],
                final_bankroll=result["final_bankroll"],
                total_bets=result["total_bets"],
                winning_bets=result["winning_bets"],
                losing_bets=result["losing_bets"],
                roi=result["roi"],
                max_drawdown=result["max_drawdown"],
                sharpe_ratio=result["sharpe_ratio"],
                hit_rate=result["hit_rate"],
                avg_edge=result["avg_edge"],
            )

        # Remove large arrays for response
        result.pop("bankroll_history", None)
        result.pop("bets", None)
        result.pop("train_metrics", None)

        return result
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Results / History ====================

@app.get("/api/results")
async def get_results(limit: int = Query(50, ge=1, le=500)):
    """Get prediction outcomes and results."""
    return db.get_outcomes(limit=limit)


@app.get("/api/results/history")
async def get_prediction_history(limit: int = Query(50, ge=1, le=200)):
    """Get prediction history with outcomes."""
    return learning_tracker.get_prediction_history(limit=limit)


# ==================== Model Metrics ====================

@app.get("/api/models/metrics")
async def get_model_metrics(
    model_name: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Get model performance metrics."""
    return db.get_model_metrics(model_name=model_name, limit=limit)


@app.get("/api/models/performance")
async def get_model_performance(
    model_name: Optional[str] = Query(None),
    sport: Optional[str] = Query(None),
):
    """Get detailed model performance analysis."""
    return learning_tracker.get_model_performance(model_name=model_name, sport=sport)


@app.post("/api/models/train")
async def train_model(
    sport: str = Query("nba"),
    model_type: str = Query("gradient_boosting"),
    num_games: int = Query(500, ge=50, le=5000),
):
    """Train a new prediction model."""
    try:
        hist_df = historical_loader.get_historical_dataframe(sport=sport, limit=num_games)

        if hist_df.empty or len(hist_df) < 50:
            hist_df = historical_loader.generate_synthetic_data(sport=sport, num_games=num_games)
            historical_loader.store_synthetic_data(hist_df)

        trainer = ModelTrainer(model_type=model_type)
        metrics = trainer.train(hist_df)

        if "error" not in metrics:
            model_path = trainer.save_model()
            # Store metrics
            for metric_name in ("accuracy", "precision", "recall", "f1", "roc_auc", "brier_score"):
                if metric_name in metrics:
                    db.insert_model_metric(
                        model_name=model_type,
                        model_version=metrics.get("model_version", "1.0"),
                        sport=sport,
                        metric_name=metric_name,
                        metric_value=metrics[metric_name],
                        sample_size=metrics.get("test_size", 0),
                    )
            metrics["model_path"] = model_path

        return metrics
    except Exception as e:
        logger.error(f"Model training error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/models/compare")
async def compare_models(
    sport: str = Query("nba"),
    num_games: int = Query(500, ge=50, le=5000),
):
    """Compare multiple model types."""
    try:
        hist_df = historical_loader.get_historical_dataframe(sport=sport, limit=num_games)

        if hist_df.empty or len(hist_df) < 50:
            hist_df = historical_loader.generate_synthetic_data(sport=sport, num_games=num_games)

        trainer = ModelTrainer()
        comparison = trainer.compare_models(hist_df)
        return comparison.to_dict(orient="records") if not comparison.empty else []
    except Exception as e:
        logger.error(f"Model comparison error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Bankroll ====================

@app.get("/api/bankroll")
async def get_bankroll(limit: int = Query(100, ge=1, le=1000)):
    """Get bankroll history."""
    return db.get_bankroll_history(limit=limit)


@app.get("/api/bankroll/summary")
async def get_bankroll_summary():
    """Get bankroll performance summary."""
    return learning_tracker.get_bankroll_summary()


# ==================== Data Management ====================

@app.post("/api/data/generate-synthetic")
async def generate_synthetic(
    sport: str = Query("nba"),
    num_games: int = Query(500, ge=50, le=5000),
):
    """Generate synthetic historical data for testing."""
    try:
        df = historical_loader.generate_synthetic_data(sport=sport, num_games=num_games)
        count = historical_loader.store_synthetic_data(df)
        return {"generated": len(df), "stored": count, "sport": sport}
    except Exception as e:
        logger.error(f"Synthetic data generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Catch-all for SPA routing ====================

@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    """Serve the dashboard for any non-API route."""
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    index_path = os.path.join(dashboard_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Dashboard not built. Run the build process first.", "api_docs": "/docs"}
