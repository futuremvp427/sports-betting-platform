# Sports Betting Intelligence Platform

A unified, production-minded sports betting intelligence system that consolidates data ingestion, ML predictions, probability calibration, expected value analysis, arbitrage detection, backtesting, and continuous learning into one clean platform.

## Architecture Overview

```
sports-betting-platform/
├── config/              # Configuration & logging
│   ├── settings.py      # All settings (env-aware)
│   └── logging_config.py
├── data/                # Data ingestion layer
│   ├── providers/       # API providers (The Odds API, ESPN)
│   ├── normalization/   # Data normalization
│   ├── historical/      # Historical data loading & synthetic generation
│   └── scrapers/        # Fallback scraping
├── models/              # ML models
│   ├── features.py      # Feature engineering
│   ├── training/        # Model training (LR, RF, GB, XGB)
│   ├── inference/       # Prediction engine
│   └── comparison/      # Model comparison
├── calibration/         # Probability calibration (isotonic, Platt)
├── decision/            # Decision engine (EV, edge, Kelly sizing)
├── arbitrage/           # Cross-book arbitrage scanner
├── backtesting/         # Strategy backtesting engine
├── learning/            # Performance tracking & adaptive learning
├── storage/             # SQLite database layer
├── api/                 # FastAPI REST endpoints
├── main.py              # Entry point
└── requirements.txt     # Python dependencies
```

## Key Components

### Data Ingestion
- **The Odds API**: Live odds from 15+ sportsbooks
- **ESPN API**: Game schedules, scores, team stats
- **Data Normalizer**: Unified format across all sources
- **Historical Loader**: Load real or generate synthetic data for backtesting

### ML Models
- **Feature Engineering**: 20+ features including Elo ratings, win streaks, rest days, head-to-head records
- **Model Types**: Logistic Regression, Random Forest, Gradient Boosting, XGBoost
- **Model Comparison**: Side-by-side evaluation on the same dataset

### Calibration
- **Isotonic Regression**: Non-parametric calibration
- **Platt Scaling**: Logistic regression-based calibration
- **ECE Tracking**: Expected Calibration Error monitoring

### Decision Engine
- **Expected Value (EV)**: Calculates EV for every bet opportunity
- **Edge Detection**: Identifies where predicted probability exceeds implied probability
- **Kelly Criterion**: Fractional Kelly sizing with configurable fraction and max bet caps
- **Justification**: Human-readable reasoning for every decision

### Arbitrage Scanner
- **Cross-Book Detection**: Scans all book combinations for arbitrage
- **Profit Calculation**: Exact stakes and guaranteed profit for each opportunity
- **Real-Time**: Designed for live odds scanning

### Backtesting
- **Chronological Split**: Proper train/test split to prevent look-ahead bias
- **Strategy Comparison**: Compare multiple models and parameter sets
- **Full Metrics**: ROI, hit rate, max drawdown, Sharpe ratio, average edge

### Learning System
- **Prediction Tracking**: Records every prediction for future comparison
- **Outcome Matching**: Compares predictions to actual results
- **Performance Monitoring**: Rolling accuracy, calibration drift detection
- **Retrain Recommendations**: Alerts when model performance degrades

## Quick Start

### 1. Install Dependencies

```bash
cd sports-betting-platform
pip install -r requirements.txt
```

### 2. Configure API Keys

Create a `.env` file:

```env
ODDS_API_KEY=your_key_here
```

Get a free API key at [the-odds-api.com](https://the-odds-api.com/).

### 3. Start the Server

```bash
python main.py
```

The API will be available at `http://localhost:8000` with interactive docs at `/docs`.

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/dashboard/summary` | GET | Dashboard summary stats |
| `/api/games` | GET | Get games from database |
| `/api/games/live` | GET | Live games from ESPN |
| `/api/games/sync` | POST | Sync games to database |
| `/api/odds` | GET | Get stored odds |
| `/api/odds/live` | GET | Fetch live odds |
| `/api/odds/sync` | POST | Sync odds to database |
| `/api/predictions` | GET | Get stored predictions |
| `/api/predictions/generate` | POST | Generate ML predictions |
| `/api/edges` | GET | Get value bet opportunities |
| `/api/arbitrage` | GET | Get arbitrage opportunities |
| `/api/arbitrage/scan` | POST | Scan for arbitrage |
| `/api/backtests` | GET | Get backtest results |
| `/api/backtests/run` | POST | Run a backtest |
| `/api/models/metrics` | GET | Model performance metrics |
| `/api/models/train` | POST | Train a new model |
| `/api/models/compare` | POST | Compare model types |
| `/api/bankroll` | GET | Bankroll history |
| `/api/data/generate-synthetic` | POST | Generate test data |

## Dashboard

The platform includes a React dashboard built with:
- **React 19** + **TypeScript**
- **Tailwind CSS 4** with custom "Midnight Command" dark theme
- **Recharts** for data visualization
- **Framer Motion** for animations
- **shadcn/ui** components

Dashboard pages:
1. **Dashboard**: Overview with KPIs, bankroll chart, top edges, recent predictions
2. **Predictions**: Full prediction table with sport/outcome filters
3. **Value Bets**: Edge opportunities with EV, Kelly sizing, and confidence
4. **Arbitrage**: Cross-book arbitrage scanner with profit calculations
5. **Backtesting**: Strategy comparison with bankroll progression charts
6. **Models**: ML model performance radar chart and detailed metrics
7. **Bankroll**: P&L tracking, win/loss distribution, transaction log

## Configuration

All settings are in `config/settings.py` and can be overridden via environment variables:

| Setting | Default | Description |
|---|---|---|
| `ODDS_API_KEY` | (required) | The Odds API key |
| `API_HOST` | `0.0.0.0` | API server host |
| `API_PORT` | `8000` | API server port |
| `INITIAL_BANKROLL` | `10000` | Starting bankroll |
| `MIN_EDGE` | `0.03` | Minimum edge to bet (3%) |
| `KELLY_FRACTION` | `0.25` | Kelly criterion fraction |
| `MAX_BET_FRACTION` | `0.05` | Max bet as % of bankroll |
| `CALIBRATION_METHOD` | `isotonic` | Calibration method |
| `MIN_CONFIDENCE` | `0.55` | Minimum prediction confidence |

## Design Principles

1. **Separation of concerns**: Predictive betting and arbitrage are completely separate systems
2. **No silent corruption**: All model updates are observable and reversible
3. **Calibration-first**: Raw probabilities are always calibrated before decisions
4. **Kelly sizing**: Never risk more than the math recommends
5. **Backtest everything**: No strategy goes live without historical validation
6. **Learn continuously**: Track every prediction and outcome for improvement

## Supported Sports

- NBA (Basketball)
- NFL (Football)
- MLB (Baseball)
- NHL (Hockey)

## License

MIT
