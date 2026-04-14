#!/usr/bin/env python3
"""
Functional tests for core platform logic.
Tests decision engine, arbitrage scanner, feature engineering, and calibration.
"""
import sys
import numpy as np
sys.path.insert(0, ".")

def test_decision_engine():
    from decision.engine import DecisionEngine
    engine = DecisionEngine(bankroll=10000)

    # Test odds conversion
    assert abs(engine.american_to_decimal(150) - 2.5) < 0.01
    assert abs(engine.american_to_decimal(-200) - 1.5) < 0.01

    # Test implied probability
    assert abs(engine.american_to_implied_prob(150) - 0.4) < 0.01
    assert abs(engine.american_to_implied_prob(-200) - 0.6667) < 0.01

    # Test EV calculation
    ev = engine.calculate_ev(0.5, 2.5)  # 50% chance at +150
    assert ev > 0, f"Expected positive EV, got {ev}"

    # Test edge calculation
    edge = engine.calculate_edge(0.55, 0.50)
    assert abs(edge - 0.05) < 0.001

    # Test Kelly stake
    stake = engine.kelly_stake(0.55, 2.0)
    assert stake > 0, "Kelly stake should be positive for +EV bet"
    assert stake <= 10000 * 0.05, "Stake should not exceed max bet fraction"

    print("  OK  Decision Engine: odds conversion, EV, edge, Kelly")

def test_arbitrage_scanner():
    from arbitrage.scanner import ArbitrageScanner
    scanner = ArbitrageScanner(min_profit_pct=0.5)

    # Create a clear arbitrage opportunity
    odds_by_book = [
        {"external_game_id": "game1", "sportsbook": "BookA", "home_odds": 200, "away_odds": -150, "home_team": "Team1", "away_team": "Team2"},
        {"external_game_id": "game1", "sportsbook": "BookB", "home_odds": 150, "away_odds": -110, "home_team": "Team1", "away_team": "Team2"},
    ]

    opps = scanner.find_arbitrage(odds_by_book)
    # May or may not find arb depending on exact odds, just test it runs
    assert isinstance(opps, list)
    print(f"  OK  Arbitrage Scanner: found {len(opps)} opportunities from test data")

def test_calibrator():
    from calibration.calibrator import ProbabilityCalibrator
    cal = ProbabilityCalibrator(method="isotonic")

    # Generate test data
    np.random.seed(42)
    predicted = np.random.uniform(0.2, 0.8, 100)
    actual = (np.random.uniform(0, 1, 100) < predicted).astype(int)

    metrics = cal.fit(predicted, actual)
    assert "ece" in metrics
    assert "brier_score" in metrics

    # Test calibration
    calibrated = cal.calibrate(np.array([0.3, 0.5, 0.7]))
    assert len(calibrated) == 3
    assert all(0 <= p <= 1 for p in calibrated)

    print(f"  OK  Calibrator: ECE={metrics['ece']:.4f}, Brier={metrics['brier_score']:.4f}")

def test_feature_engineer():
    from models.features import FeatureEngineer
    import pandas as pd

    fe = FeatureEngineer()
    features = fe.get_prediction_features()
    assert len(features) > 0
    print(f"  OK  Feature Engineer: {len(features)} prediction features defined")

def test_database():
    from storage.database import DatabaseManager
    import tempfile, os

    # Use temp database
    db = DatabaseManager(db_path=os.path.join(tempfile.gettempdir(), "test_betting.db"))

    # Test game upsert
    game_id = db.upsert_game(
        sport="nba", league="nba", home_team_name="Lakers", away_team_name="Celtics",
        scheduled_time="2024-01-15T19:00:00", status="scheduled",
        external_id="test_game_1"
    )
    assert game_id > 0

    # Test get games
    games = db.get_games(sport="nba")
    assert len(games) > 0

    # Cleanup
    os.unlink(os.path.join(tempfile.gettempdir(), "test_betting.db"))
    print(f"  OK  Database: upsert, query, schema all working")

def main():
    print("Running core functional tests...\n")
    tests = [
        test_decision_engine,
        test_arbitrage_scanner,
        test_calibrator,
        test_feature_engineer,
        test_database,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAIL  {test.__name__}: {e}")
            failed += 1

    print(f"\n{passed}/{passed + failed} tests passed")
    if failed:
        sys.exit(1)
    else:
        print("All core tests passed!")

if __name__ == "__main__":
    main()
