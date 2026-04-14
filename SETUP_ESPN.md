# Setup Guide: Running with Real ESPN Data

## Overview

The Sports Betting Intelligence Platform is now configured to use **ESPN as the default data source** for real game schedules, scores, and team information. This requires **no API key** and provides real data immediately.

## Quick Start

### 1. Install Dependencies

```bash
cd /home/ubuntu/sports-betting-platform
pip3 install -r requirements.txt
```

### 2. Run the Backend Server

```bash
python3 main.py
```

The server will start on `http://localhost:8000` with:
- **Real game data** from ESPN (no API key required)
- **Demo odds data** from Caesars, PrizePicks, and other books (realistic but simulated)
- Full ML predictions, backtesting, and arbitrage scanning

### 3. Connect the Dashboard

The dashboard at `https://sportsdash-jq6jzvoy.manus.space` will automatically:
1. Detect the backend running on port 8000
2. Switch from "Demo Mode" to "Live" mode
3. Display real game data with realistic predictions

## Data Sources

| Component | Source | Status | Notes |
|-----------|--------|--------|-------|
| **Game Schedules** | ESPN API | ✅ Real | No API key required |
| **Scores & Results** | ESPN API | ✅ Real | Live updates from ESPN |
| **Team Information** | ESPN API | ✅ Real | Team names, abbreviations, venues |
| **Betting Odds** | Demo Data | 📊 Simulated | Realistic but generated locally |
| **Predictions** | ML Models | 🤖 Real | Trained on historical data |
| **Arbitrage** | Scanner | 🔍 Real | Finds opportunities in demo odds |

## Upgrading to Live Sportsbook Odds

When you receive your **Odds API key** from [theoddsapi.com](https://theoddsapi.com):

```bash
export ODDS_API_KEY="your-key-here"
python3 main.py
```

This will replace demo odds with **real live odds** from Caesars, DraftKings, FanDuel, BetMGM, and other books.

## API Endpoints

All endpoints are available at `http://localhost:8000`:

- `GET /api/health` — Health check
- `GET /api/games/live?sport=nba` — Real games from ESPN
- `GET /api/odds/live?sport=nba` — Demo odds (or real if ODDS_API_KEY set)
- `GET /api/predictions` — ML predictions
- `GET /api/arbitrage` — Arbitrage opportunities
- `GET /api/backtesting/results` — Backtest results
- `POST /api/games/sync` — Sync ESPN games to database
- `POST /api/odds/sync` — Sync odds to database

Full API docs: `http://localhost:8000/docs`

## Troubleshooting

### Backend not connecting?
- Ensure port 8000 is not in use: `lsof -i :8000`
- Check logs: `python3 main.py` (verbose output)
- Verify ESPN API is accessible: `curl https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard`

### Still seeing "Demo Mode" banner?
- Refresh the dashboard page (Ctrl+R or Cmd+R)
- Check browser console for errors (F12)
- Verify backend is running: `curl http://localhost:8000/api/health`

### Want to test with specific dates?
Use the sync endpoints to pull historical data:
```bash
curl -X POST "http://localhost:8000/api/games/sync?sport=nba"
```

## Architecture

```
Dashboard (React)
    ↓
    ↓ (tries port 8000)
    ↓
Backend API (FastAPI)
    ├── ESPN Provider (real game data)
    ├── Odds API Provider (demo or real odds)
    ├── ML Models (predictions)
    ├── Arbitrage Scanner
    └── Backtesting Engine
```

## Next Steps

1. ✅ Run backend with ESPN data (you are here)
2. 📧 Wait for Odds API key, then add `ODDS_API_KEY` for live sportsbook odds
3. 🔔 Set up notifications for high-edge value bets
4. 📊 Configure bankroll and Kelly sizing in settings
5. 🎯 Start tracking real bets and learning from results

---

**Questions?** Check the main README.md or review the API docs at `http://localhost:8000/docs`
