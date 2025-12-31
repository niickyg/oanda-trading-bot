# OANDA Bot Architecture Documentation

## Project Overview

The OANDA Bot is a sophisticated automated forex trading system designed for algorithmic trading on the OANDA platform. It features modular strategy plugins, advanced risk management, automated optimization, and real-time monitoring capabilities. The system supports both backtesting and live trading modes with Docker-based deployment.

### Purpose

- Execute automated forex trading strategies on OANDA's API
- Backtest and optimize trading strategies using historical data
- Manage risk through position sizing, stop-loss, and take-profit orders
- Monitor performance and adapt strategies based on market conditions
- Support multiple currency pairs and trading strategies simultaneously

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      OANDA Bot System                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Entry      │    │   Strategy   │    │     Data     │      │
│  │   Points     │───▶│   Engine     │───▶│    Layer     │      │
│  │              │    │              │    │              │      │
│  │ main.py      │    │ Strategies:  │    │ OANDA API    │      │
│  │ app.py       │    │ - MACD       │    │ Candles      │      │
│  │ backtest.py  │    │ - RSI        │    │ Streaming    │      │
│  │ optimize.py  │    │ - Bollinger  │    │ Volume       │      │
│  └──────────────┘    │ - Breakout   │    └──────────────┘      │
│                      │ - TrendMA    │                           │
│                      │ - TriArb     │                           │
│  ┌──────────────┐    │ - VolGrid    │    ┌──────────────┐      │
│  │   Risk Mgmt  │    └──────────────┘    │   Broker     │      │
│  │              │                         │   Interface  │      │
│  │ risk.py      │◀────────────────────────│              │      │
│  │ Position     │                         │ broker.py    │      │
│  │ Sizing       │                         │ Order Exec   │      │
│  │ Drawdown     │                         │ Position Mgmt│      │
│  └──────────────┘                         └──────────────┘      │
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Advanced    │    │ Monitoring & │    │  Research    │      │
│  │  Features    │    │  Analysis    │    │  Tools       │      │
│  │              │    │              │    │              │      │
│  │ regime.py    │    │ correlation  │    │ auto_strat_  │      │
│  │ meta_optimize│    │ Health Check │    │ generator.py │      │
│  │ Trailing SL  │    │ CSV Logging  │    │ run_research │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

                            ▼  ▼  ▼
                    ┌──────────────────┐
                    │  Configuration   │
                    │  Files           │
                    │                  │
                    │ .env             │
                    │ live_config.json │
                    │ best_params.json │
                    └──────────────────┘
```

---

## Directory Structure

```
/home/user0/oandabot16/oanda_bot/
│
├── oanda_bot/                      # Main package directory
│   ├── __init__.py
│   ├── main.py                     # Live trading entry point
│   ├── app.py                      # Streamlit dashboard
│   ├── broker.py                   # OANDA broker interface
│   ├── backtest.py                 # Backtesting engine
│   ├── optimize.py                 # Parameter optimization
│   ├── meta_optimize.py            # Multi-armed bandit optimizer
│   ├── manager.py                  # Strategy hot-reload manager
│   ├── risk.py                     # Risk management utilities
│   ├── config_manager.py           # Configuration handling
│   │
│   ├── data/                       # Data layer
│   │   ├── __init__.py
│   │   ├── core.py                 # OANDA API client & candles
│   │   └── news.py                 # News/event data (optional)
│   │
│   ├── strategy/                   # Strategy plugins
│   │   ├── __init__.py
│   │   ├── base.py                 # BaseStrategy abstract class
│   │   ├── utils.py                # Strategy utilities (SL/TP)
│   │   ├── macd_trends.py          # MACD trend following
│   │   ├── rsi_reversion.py        # RSI mean reversion
│   │   ├── bollinger_squeeze.py    # Bollinger bands squeeze
│   │   ├── breakout.py             # Breakout strategy
│   │   ├── trend_ma.py             # Moving average trend
│   │   ├── tri_arb.py              # Triangular arbitrage
│   │   └── volatility_grid.py      # Volatility-based grid
│   │
│   ├── research/                   # Strategy research tools
│   │   ├── __init__.py
│   │   ├── run_research.py         # Research runner
│   │   ├── auto_strategy_generator.py  # Auto-generate strategies
│   │   ├── contexts/               # Research context data
│   │   └── template/               # Strategy templates
│   │       └── strategy_template.j2.py
│   │
│   ├── common/                     # Shared utilities
│   │   ├── __init__.py
│   │   └── indicators.py           # Technical indicators
│   │
│   ├── utils/                      # General utilities
│   │   ├── __init__.py
│   │   └── retry.py                # API retry decorator
│   │
│   ├── tests/                      # Test suite
│   │   ├── __init__.py
│   │   ├── test_main_drawdown.py
│   │   ├── test_meta_optimize.py
│   │   ├── test_risk.py
│   │   ├── test_all_strategies.py
│   │   ├── test_macd_trends.py
│   │   ├── test_rsi_reversion.py
│   │   ├── test_config_manager.py
│   │   └── test_run_research.py
│   │
│   ├── regime.py                   # NEW: Market regime detection
│   ├── correlation.py              # NEW: Strategy correlation analysis
│   └── probe_accounts.py           # Account diagnostics
│
├── .env                            # Environment variables (secrets)
├── .env.example                    # Environment template
├── live_config.json                # Live strategy parameters
├── best_params.json                # Optimized parameters per pair
├── docker-compose.yml              # Docker orchestration
├── Dockerfile                      # Container definition
├── setup.py                        # Package installation
├── requirements.txt                # Python dependencies
├── dev_requirements.txt            # Dev dependencies
├── .flake8                         # Linting configuration
├── .gitignore                      # Git ignore rules
│
├── live_trading.log                # Live trading logs (rotating)
├── backtest.log                    # Backtest logs (rotating)
├── trades_log.csv                  # Trade history CSV
├── shared/                         # Hot-swap parameter directory
└── README.md                       # Quick-start guide
```

---

## Core Components

### 1. Main Entry Point (`main.py`)

**Purpose**: Live trading engine that streams market data and executes trades

**Key Features**:
- Streams 2-second price bars from OANDA
- Evaluates all enabled strategies on each bar
- Manages position sizing based on account equity and risk
- Implements cooldown periods to prevent over-trading
- Monitors drawdown and triggers re-optimization
- Provides HTTP health check endpoint on port 8000
- Logs all trades to CSV and rotating JSON logs

**Flow**:
1. Bootstrap historical prices for all pairs
2. Load and initialize all strategy plugins
3. Run validation backtest on recent data
4. Enter main loop: stream bars, evaluate strategies, place orders
5. Monitor equity and adapt risk based on drawdown

**Key Functions**:
- `handle_signal()`: Process trading signals with risk management
- `handle_bar()`: Process each price bar through all strategies
- `bootstrap_history()`: Pre-fill price history
- `trail_to_breakeven()`: Trailing stop-loss (stub for future enhancement)

---

### 2. Broker Interface (`broker.py`)

**Purpose**: Abstraction layer for OANDA API order execution

**Key Features**:
- Place market orders with SL/TP
- Risk-managed order placement (position sizing)
- Close positions (all or profitable only)
- Test mode simulation for CI/testing
- Automatic precision handling (JPY vs non-JPY pairs)

**Key Functions**:
- `place_order()`: Basic order placement
- `place_risk_managed_order()`: Calculate position size based on risk
- `close_all_positions()`: Close all open positions
- `close_profitable_positions()`: Close only winning positions

**Risk Management Integration**:
- Calculates units based on: equity × risk% ÷ (entry - stop)
- Caps maximum position size at 1000 units
- Rounds prices to correct decimal precision per instrument

---

### 3. Backtest Engine (`backtest.py`)

**Purpose**: Simulate strategy performance on historical data

**Key Features**:
- Generic backtesting for any strategy plugin
- Supports stop-loss, take-profit, and max duration exits
- Tracks wins, losses, expectancy, and total P&L
- JSON structured logging for analysis
- Warmup period to initialize indicators

**Metrics Calculated**:
- Total trades
- Win rate
- Average win/loss
- Expectancy (expected value per trade)
- Total P&L (in pips and currency)

**Usage**:
```bash
python -m oanda_bot.backtest \
  --strategy MACDTrend \
  --config live_config.json \
  --instrument EUR_USD \
  --granularity H1 \
  --count 2000 \
  --warmup 200
```

---

### 4. Data Layer (`data/core.py`)

**Purpose**: Interface to OANDA API for market data

**Key Features**:
- Historical candle retrieval (multiple granularities)
- Real-time price streaming via WebSocket
- Volume-based pair filtering (active market detection)
- 1-minute OHLC aggregation from tick stream
- Automatic retry with exponential backoff

**Key Functions**:
- `get_candles()`: Fetch historical OHLC data
- `stream_bars()`: Stream real-time price bars
- `get_last_volume()`: Get recent volume for a pair
- `build_active_list()`: Select most active pairs by volume

**Supported Granularities**:
- Seconds: S5, S10, S15, S30
- Minutes: M1, M2, M5, M15, M30
- Hours: H1, H2, H4, H6, H8, H12
- Daily/Weekly/Monthly: D, W, M

---

### 5. Strategy System

#### Base Strategy (`strategy/base.py`)

Abstract base class that all strategies must implement:

```python
class BaseStrategy(ABC):
    @abstractmethod
    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        """Return 'BUY', 'SELL', or None"""
        pass

    def update_trade_result(self, win: bool, pnl: float) -> None:
        """Callback for adaptive strategies"""
        pass
```

#### Available Strategies

| Strategy | Type | Best Market Condition | Key Parameters |
|----------|------|----------------------|----------------|
| **MACDTrend** | Trend Following | Trending markets | `ema_trend`, `macd_fast`, `macd_slow`, `macd_signal` |
| **RSIReversion** | Mean Reversion | Ranging markets | `rsi_len`, `rsi_oversold`, `rsi_overbought` |
| **BollingerSqueeze** | Volatility Breakout | Ranging → trending | `bb_period`, `bb_std`, `squeeze_threshold` |
| **Breakout** | Momentum | Volatile markets | `lookback_period`, `breakout_multiplier` |
| **TrendMA** | Trend Following | Trending markets | `fast_period`, `slow_period`, `atr_period` |
| **TriArb** | Arbitrage | Any | `min_profit_bps` |
| **VolatilityGrid** | Grid Trading | Volatile sideways | `grid_spacing`, `grid_levels` |

#### Strategy Utilities (`strategy/utils.py`)

- `sl_tp_levels()`: Calculate stop-loss and take-profit from ATR
- ATR-based position sizing
- Trend slope validation

---

### 6. Optimization System (`optimize.py`)

**Purpose**: Grid search optimization for strategy parameters

**Key Features**:
- Parallel processing with ProcessPoolExecutor
- Multi-instrument optimization
- Grid search over SL/TP multipliers, max duration, trailing ATR
- Filters by minimum trades and target win rate
- Writes optimized parameters to `best_params.json`

**Parameter Grid**:
- SL multipliers: 0.5 to 3.0 (0.25 steps)
- TP multipliers: 0.5 to 3.0 (0.25 steps)
- Max duration: [10, 20, 50, 100] bars
- Trailing ATR: [0.5, 1.0, 1.5]

**Usage**:
```bash
python -m oanda_bot.optimize \
  --strategy MACDTrend \
  --instruments EUR_USD USD_JPY \
  --granularity H1 \
  --count 4999 \
  --min_trades 30 \
  --target_win_rate 0.55
```

---

### 7. Meta-Optimizer (`meta_optimize.py`)

**Purpose**: Multi-armed bandit (UCB1) for strategy selection

**Key Features**:
- Treats each strategy as an "arm" in a bandit problem
- Uses UCB1 algorithm to balance exploration vs exploitation
- Calibration phase: test each strategy once
- Optimization rounds: select best strategy based on UCB score
- Writes winning strategy configuration

**Algorithm (UCB1)**:
```
score = average_pnl + sqrt(2 * ln(total_pulls) / strategy_pulls)
```

---

## Configuration Files

### 1. Environment Variables (`.env`)

```bash
# OANDA API Configuration
OANDA_TOKEN=your_api_token_here
OANDA_ACCOUNT_ID=your_account_id_here
OANDA_ENV=practice  # or 'live'

# Risk Management
RISK_FRAC=0.02  # Risk 2% per trade

# Optional
ERROR_WEBHOOK_URL=https://your-webhook-url
ENABLE_HEALTH=1
```

### 2. Live Configuration (`live_config.json`)

Strategy-specific parameters loaded at runtime:

```json
{
  "MACDTrend": {
    "EUR_USD": {
      "sl_mult": 3.0,
      "tp_mult": 3.0,
      "max_duration": 100,
      "trail_atr": 0.5,
      "ema_trend": 200,
      "macd_fast": 12,
      "macd_slow": 26,
      "macd_signal": 9
    }
  }
}
```

### 3. Optimized Parameters (`best_params.json`)

Instrument-specific optimized parameters:

```json
{
  "MACDTrend": {
    "EUR_USD": {
      "sl_mult": 3.0,
      "tp_mult": 3.0,
      "max_duration": 100,
      "trail_atr": 0.5
    }
  }
}
```

---

## Docker Deployment

### Docker Compose Services

#### 1. Bot Service
- **Image**: `localhost/oanda-bot:latest`
- **Command**: `python -m oanda_bot.main`
- **Ports**: 8000 (health check)
- **Volumes**:
  - `./shared:/shared:Z` - Hot-swap parameters
  - `./live_trading.log` - Persistent logs
  - `./trades_log.csv` - Trade history
- **Healthcheck**: HTTP GET /health every 30s
- **Restart**: Unless stopped

#### 2. Researcher Service
- **Purpose**: Continuous optimization in background
- **Command**: Optimize every 30 minutes and update shared params
- **Volumes**: `./shared:/shared` for parameter hot-swap

### Building the Image

```bash
# Build production image
docker build -t localhost/oanda-bot:latest .

# Build dev image (with test dependencies)
docker build --target dev -t localhost/oanda-bot:dev .
```

### Running with Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f bot

# Stop services
docker-compose down
```

---

## Entry Points and CLI Usage

### 1. Live Trading

```bash
# Direct Python
python -m oanda_bot.main

# Docker
docker-compose up bot
```

### 2. Streamlit Dashboard

```bash
streamlit run oanda_bot/app.py
```

### 3. Backtesting

```bash
python -m oanda_bot.backtest \
  --strategy MACDTrend \
  --instrument EUR_USD \
  --granularity H1 \
  --count 2000
```

### 4. Optimization

```bash
python -m oanda_bot.optimize \
  --strategy MACDTrend \
  --instruments EUR_USD GBP_USD \
  --granularity M5 \
  --count 1500
```

### 5. Research Runner

```bash
python -m oanda_bot.research.run_research
```

---

## Key Features

### Risk Management

1. **Position Sizing**
   - Risk percentage of equity (default 2%)
   - Reduces to 0.6% if drawdown > 5%
   - Reduces to 0.18% if drawdown > 10%
   - Max position: 1000 units

2. **Stop-Loss & Take-Profit**
   - ATR-based levels (default: SL=3.5×ATR, TP=5.0×ATR)
   - Instrument-specific precision rounding
   - Validation to prevent SL=entry errors

3. **Drawdown Monitoring**
   - Tracks peak equity
   - Calculates drawdown percentage
   - Triggers re-optimization at 5% drawdown
   - Sends alerts via webhook

### Monitoring & Observability

1. **Structured Logging**
   - JSON logs with pythonjsonlogger
   - Rotating file handler (10MB max, 5 backups)
   - Logs to console and file simultaneously

2. **Trade History**
   - CSV export: `trades_log.csv`
   - Columns: timestamp, pair, side, units, order_id, strategy, entry, SL, TP, ATR, session_hour

3. **Health Check**
   - HTTP endpoint: `http://localhost:8000/health`
   - Docker healthcheck integration
   - 30-second interval checks

4. **Metrics Tracking**
   - Internal counter dict (`_metrics`)
   - Tracks: signals received, rate-limited, orders placed, etc.

---

## NEW FEATURES (In Development)

### 1. Market Regime Detection (`regime.py`)

**Purpose**: Classify market conditions to enable regime-aware strategy selection

**Regimes**:
- **Trending Up**: Strong upward movement (ADX > 25, +DI > -DI)
- **Trending Down**: Strong downward movement (ADX > 25, -DI > +DI)
- **Ranging**: Sideways consolidation (low ADX)
- **Volatile**: High ATR percentile (>75th percentile)
- **Quiet**: Low ATR percentile (<25th percentile)

**Key Methods**:
- `detect_regime()`: Analyze candles and classify current regime
- `calculate_adx()`: Compute Average Directional Index
- `should_enable_strategy()`: Recommend if strategy suits current regime
- `get_regime_statistics()`: Historical regime distribution

**Strategy-Regime Mapping**:
- MACD/TrendMA → Trending markets
- RSI → Ranging/Quiet markets
- Bollinger/Volatility → Volatile markets
- Breakout → Trending/Volatile markets

---

### 2. Strategy Correlation Analysis (`correlation.py`)

**Purpose**: Identify redundant strategies and optimize portfolio diversification

**Key Features**:
- Track signal correlation between strategies
- Calculate correlation matrix across all pairs
- Recommend optimal strategy portfolio (low correlation)
- Export correlation reports to JSON

**Key Methods**:
- `log_signal()`: Track strategy signals over time
- `calculate_correlation_matrix()`: Compute pairwise correlations
- `get_highly_correlated_pairs()`: Find redundant strategies (>70% correlation)
- `recommend_strategy_portfolio()`: Greedy selection for max diversification
- `get_signal_agreement_rate()`: Percentage of time two strategies agree

**Use Case**:
If MACDTrend and TrendMA have 85% correlation, disable one to reduce redundancy and improve diversification.

---

### 3. Enhanced Trailing Stops

**Status**: Stub in `main.py` (line 590)

**Planned Features**:
- Move stop to breakeven after N pips profit
- Trail stop by ATR multiples
- Partial position closing at milestones

---

### 4. Performance Monitoring Dashboard

**Current**: Basic Streamlit UI in `app.py`

**Planned Enhancements**:
- Real-time equity curve visualization
- Strategy performance comparison
- Regime distribution charts
- Correlation heatmap
- Trade analytics (win rate by hour, pair, strategy)

---

### 5. Comprehensive Test Suite

**Current Coverage**:
- `test_main_drawdown.py`: Drawdown detection
- `test_meta_optimize.py`: Bandit optimizer
- `test_risk.py`: Position sizing
- `test_all_strategies.py`: Strategy signal generation
- `test_config_manager.py`: Configuration loading

**Planned Additions**:
- Integration tests for full trading loop
- Regime detection tests
- Correlation analyzer tests
- End-to-end backtesting validation

---

## Trading Pairs and Precision

### Supported Pairs

The bot tracks 20+ forex pairs:
- **USD Majors**: EUR_USD, GBP_USD, AUD_USD, NZD_USD, USD_JPY, USD_CHF, USD_CAD
- **EUR Crosses**: EUR_GBP, EUR_AUD, EUR_CHF, EUR_CAD, EUR_JPY
- **GBP Crosses**: GBP_JPY, GBP_AUD, GBP_CHF, GBP_CAD
- **Other**: AUD_JPY, AUD_NZD, AUD_CAD, NZD_JPY, NZD_CAD

### Active Pair Selection

The bot dynamically selects the top 10 most active pairs every 5 minutes based on recent tick volume.

### Price Precision

| Currency Type | Decimal Places | Example |
|---------------|----------------|---------|
| JPY pairs | 2 | 161.45 |
| All others | 5 | 1.08123 |

Precision is automatically handled by `round_price()` function.

---

## Dependencies

### Runtime Dependencies (`requirements.txt`)

```
oandapyV20          # OANDA API client
jinja2              # Template engine (for research)
schedule            # Task scheduling
python-dotenv       # Environment variable loading
ccxt                # Crypto exchange library (future use)
backtrader          # Alternative backtest framework
streamlit           # Dashboard UI
python-json-logger  # Structured logging
numpy               # Numerical operations
```

### Development Dependencies (`dev_requirements.txt`)

```
pytest>=7.0.0       # Testing framework
pytest-timeout>=2.4.0  # Test timeout handling
flake8              # Code linting
watchdog            # File watching (hot-reload)
```

---

## Common Operations

### Starting the Bot

```bash
# Load environment variables
source .env

# Run locally
python -m oanda_bot.main

# Or with Docker
docker-compose up -d
```

### Optimizing a Strategy

```bash
# Optimize MACDTrend for EUR/USD
python -m oanda_bot.optimize \
  --strategy MACDTrend \
  --instruments EUR_USD \
  --granularity H1 \
  --count 2000 \
  --min_trades 30
```

### Running Backtests

```bash
# Backtest with current config
python -m oanda_bot.backtest \
  --strategy MACDTrend \
  --config live_config.json \
  --instrument EUR_USD \
  --granularity H1 \
  --count 2000 \
  --warmup 200
```

### Viewing Logs

```bash
# Live trading log
tail -f live_trading.log

# Backtest log
tail -f backtest.log

# Trade history
cat trades_log.csv
```

### Hot-Swapping Parameters

```bash
# Update live_config.json
vim live_config.json

# The manager watches for file changes and reloads strategies
# No restart needed!
```

---

## Troubleshooting

### Common Issues

1. **"OANDA_TOKEN is missing"**
   - Check `.env` file exists
   - Ensure token is valid and >30 characters
   - Reload environment: `source .env`

2. **"Insufficient data for correlation analysis"**
   - Bot needs at least 50 signals per strategy
   - Run for longer or reduce `min_samples` parameter

3. **"Health check failed"**
   - Check port 8000 is not in use
   - Verify `ENABLE_HEALTH=1` in `.env`
   - Check firewall settings

4. **Orders rejected by OANDA**
   - Verify account has sufficient funds
   - Check SL/TP precision matches pair requirements
   - Ensure units don't exceed max position size

5. **Drawdown triggers constant re-optimization**
   - Review strategy parameters
   - Reduce risk percentage
   - Increase `BANDIT_DRAWDOWN_THRESHOLD`

---

## Performance Characteristics

### Latency
- **Bar aggregation**: 2-second intervals
- **Signal evaluation**: <10ms per strategy
- **Order execution**: 50-200ms (OANDA API)
- **Health check**: <5ms response time

### Throughput
- **Strategies evaluated**: 7+ strategies per bar
- **Pairs monitored**: 20+ pairs simultaneously
- **API rate limit**: 60 requests/minute (OANDA)
- **Backtest speed**: ~1000 bars/second

### Resource Usage
- **Memory**: ~200MB (with 10 pairs, 7 strategies)
- **CPU**: <5% idle, <50% during optimization
- **Disk**: Logs rotate at 10MB (max 50MB total)

---

## Future Roadmap

1. **Machine Learning Integration**
   - LSTM/Transformer models for price prediction
   - Reinforcement learning for strategy selection
   - Feature engineering from regime/correlation data

2. **Multi-Asset Support**
   - Crypto via CCXT integration
   - Stocks/ETFs via Alpaca API
   - Commodities via OANDA CFDs

3. **Advanced Risk Features**
   - Portfolio-level risk management
   - Correlation-based position limits
   - VaR (Value at Risk) calculations

4. **Enhanced Monitoring**
   - Grafana/Prometheus metrics
   - Real-time alerts (Telegram, SMS)
   - Performance attribution analysis

5. **Cloud Deployment**
   - Kubernetes orchestration
   - AWS/GCP deployment guides
   - Multi-region redundancy

---

## Contributing

To add a new strategy:

1. Create `oanda_bot/strategy/your_strategy.py`
2. Inherit from `BaseStrategy`
3. Implement `next_signal()` method
4. Add tests in `oanda_bot/tests/test_your_strategy.py`
5. Add parameter definitions to `live_config.json`
6. Run optimization to find best parameters

Example:
```python
from oanda_bot.strategy.base import BaseStrategy

class StrategyYourName(BaseStrategy):
    name = "YourName"

    def next_signal(self, bars):
        if len(bars) < 20:
            return None
        # Your logic here
        if condition:
            return "BUY"
        elif other_condition:
            return "SELL"
        return None
```

---

## License

Proprietary - All rights reserved.

Author: Nick Guerriero

---

**Last Updated**: 2025-12-25
**Version**: 0.1.0
