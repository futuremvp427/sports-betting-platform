# TOOLS SUMMARY (Manual Bootstrap)

## Current Repo Classification

### USE NOW
- FastAPI backend (`api/app.py`)
- Odds API provider (`data/providers/odds_api.py`)
- ESPN provider (`data/providers/espn.py`)
- Decision engine (`decision/engine.py`)
- Arbitrage scanner (`arbitrage/scanner.py`)
- Backtesting engine (`backtesting/engine.py`)
- Learning tracker (`learning/tracker.py`)

### LATER
- Scraper fallback (`data/scrapers/odds_scraper.py`)
- Synthetic data generator (for scaling/testing only)

### REFERENCE
- README architecture spec
- SETUP_ESPN.md

## Notes
- Demo mode currently triggered when ODDS_API_KEY is missing
- ESPN is primary real data source
- Odds still partially simulated
