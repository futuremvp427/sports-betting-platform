#!/usr/bin/env python3
"""Test that all platform modules import correctly."""
import sys
sys.path.insert(0, ".")

modules = [
    ("config", "settings"),
    ("config.logging_config", "setup_logging"),
    ("storage.database", "get_db"),
    ("data.providers.odds_api", "OddsAPIProvider"),
    ("data.providers.espn", "ESPNProvider"),
    ("data.normalization.normalizer", "DataNormalizer"),
    ("data.historical.loader", "HistoricalDataLoader"),
    ("models.features", "FeatureEngineer"),
    ("models.training.trainer", "ModelTrainer"),
    ("models.inference.predictor", "Predictor"),
    ("calibration.calibrator", "ProbabilityCalibrator"),
    ("decision.engine", "DecisionEngine"),
    ("arbitrage.scanner", "ArbitrageScanner"),
    ("backtesting.engine", "BacktestEngine"),
    ("learning.tracker", "LearningTracker"),
]

passed = 0
failed = 0
for mod, cls in modules:
    try:
        __import__(mod, fromlist=[cls])
        print(f"  OK  {mod}")
        passed += 1
    except Exception as e:
        print(f"  FAIL  {mod}: {e}")
        failed += 1

print(f"\n{passed}/{passed + failed} modules imported successfully")
if failed:
    sys.exit(1)
else:
    print("All imports passed!")
