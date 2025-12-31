# OANDA Trading Bot

An automated forex trading system with advanced strategy plugins, backtesting, optimization, and real-time monitoring.

## What Does This Bot Do?

The OANDA Bot is a sophisticated algorithmic trading system that:

- **Trades Automatically**: Executes forex trades 24/7 on OANDA's platform using multiple strategies
- **Adapts to Markets**: Detects market regimes (trending, ranging, volatile) and selects optimal strategies
- **Manages Risk**: Automatically sizes positions, sets stop-losses, and manages drawdowns
- **Optimizes Itself**: Continuously backtests and optimizes strategy parameters for best performance
- **Monitors Performance**: Tracks trades, equity, and strategy effectiveness in real-time

Think of it as a tireless trader that follows proven strategies, never gets emotional, and constantly improves based on data.

---

## Quick Start

### Prerequisites

- Python 3.9+
- Docker and Docker Compose (optional, recommended)
- OANDA account (practice or live)
- OANDA API token

### Installation

#### Option 1: Local Installation

```bash
# Clone the repository
cd /home/user0/oandabot16/oanda_bot

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Copy environment template
cp .env.example .env

# Edit .env with your OANDA credentials
vim .env
```

#### Option 2: Docker Installation (Recommended)

```bash
cd /home/user0/oandabot16/oanda_bot

# Copy environment template
cp .env.example .env

# Edit .env with your OANDA credentials
vim .env

# Build Docker image
docker build -t localhost/oanda-bot:latest .

# Start services
docker-compose up -d
```

---

## Configuration

### 1. Get OANDA Credentials

1. Sign up at [OANDA](https://www.oanda.com/)
2. Go to **Manage API Access**
3. Generate an **API Token**
4. Note your **Account ID**

### 2. Configure Environment Variables

Edit `.env`:

```bash
# Required: OANDA API credentials
OANDA_TOKEN=your_api_token_here
OANDA_ACCOUNT_ID=your_account_id_here
OANDA_ENV=practice  # Use 'practice' for testing, 'live' for real trading

# Optional: Risk management
RISK_FRAC=0.02  # Risk 2% of equity per trade (default)

# Optional: Webhook for error alerts (Slack, Discord, etc.)
ERROR_WEBHOOK_URL=https://your-webhook-url

# Optional: Enable/disable health check server
ENABLE_HEALTH=1
```

### 3. Configure Strategies

Edit `live_config.json` to enable strategies and set parameters:

```json
{
  "MACDTrend": {
    "EUR_USD": {
      "sl_mult": 3.0,
      "tp_mult": 3.0,
      "max_duration": 100,
      "trail_atr": 0.5
    }
  },
  "RSIReversion": {
    "EUR_USD": {
      "rsi_len": 14,
      "rsi_oversold": 30,
      "rsi_overbought": 70
    }
  }
}
```

---

## Running the Bot

### Live Trading

#### Using Docker (Recommended)

```bash
# Start the bot
docker-compose up -d

# View logs
docker-compose logs -f bot

# Stop the bot
docker-compose down
```

#### Using Python Directly

```bash
# Activate virtual environment
source .venv/bin/activate

# Run the bot
python -m oanda_bot.main
```

The bot will:
1. Load strategies from `live_config.json`
2. Bootstrap historical data for all pairs
3. Stream live prices and evaluate strategies
4. Place trades automatically based on signals
5. Log all activity to `live_trading.log` and `trades_log.csv`

### Streamlit Dashboard

Monitor the bot in real-time with the Streamlit dashboard:

```bash
# Run dashboard
streamlit run oanda_bot/app.py
```

Open your browser to `http://localhost:8501` to see:
- Live price charts
- Active signals
- Trade history
- Strategy performance

---

## Common Commands

### Backtesting

Test a strategy on historical data before going live:

```bash
python -m oanda_bot.backtest \
  --strategy MACDTrend \
  --instrument EUR_USD \
  --granularity H1 \
  --count 2000 \
  --warmup 200
```

**Output:**
```json
{
  "trades": 45,
  "wins": 28,
  "losses": 17,
  "win_rate": 0.62,
  "avg_win": 0.0012,
  "avg_loss": 0.0008,
  "expectancy": 0.0004,
  "total_pnl": 0.018
}
```

### Optimization

Find the best parameters for a strategy:

```bash
python -m oanda_bot.optimize \
  --strategy MACDTrend \
  --instruments EUR_USD GBP_USD \
  --granularity M5 \
  --count 1500 \
  --min_trades 30 \
  --target_win_rate 0.55
```

This will:
- Test thousands of parameter combinations
- Filter by minimum trades and win rate
- Save the best parameters to `best_params_EUR_USD.json`
- Update `live_config.json` for live trading

### View Logs

```bash
# Live trading log (JSON format)
tail -f live_trading.log

# Backtest log
tail -f backtest.log

# Trade history (CSV format)
cat trades_log.csv
```

### Check Bot Health

```bash
# Health check endpoint
curl http://localhost:8000/health
```

Returns `OK` if the bot is running properly.

---

## Available Strategies

| Strategy | Type | Best For | Win Rate Target |
|----------|------|----------|-----------------|
| **MACDTrend** | Trend Following | Trending markets | 50-60% |
| **RSIReversion** | Mean Reversion | Ranging markets | 55-65% |
| **BollingerSqueeze** | Volatility Breakout | Low → high volatility | 45-55% |
| **Breakout** | Momentum | High volatility | 40-50% |
| **TrendMA** | Trend Following | Strong trends | 50-60% |
| **VolatilityGrid** | Grid Trading | Sideways markets | 60-70% |
| **TriArb** | Arbitrage | Any (low frequency) | 80-90% |

The bot automatically selects strategies based on current market conditions (regime detection).

---

## Monitoring & Analysis

### Trade Logs

All trades are logged to `trades_log.csv`:

```csv
timestamp,pair,side,units,order_id,strategy,entry,stop_loss,take_profit,ATR,session_hour
2025-12-25T10:30:15,EUR_USD,BUY,500,12345,MACDTrend,1.08123,1.07800,1.08800,0.00150,10
```

### Log Files

- **live_trading.log**: JSON-formatted logs (rotates at 10MB)
- **backtest.log**: Backtest results
- **optimize.log**: Optimization progress

### Health Monitoring

The bot exposes a health check endpoint at `http://localhost:8000/health` for Docker/Kubernetes monitoring.

---

## Safety Features

### Risk Management

1. **Position Sizing**: Automatically calculates units based on risk percentage and stop-loss distance
2. **Maximum Position**: Caps at 1000 units to prevent excessive exposure
3. **Drawdown Protection**: Reduces risk when drawdown exceeds 5% or 10%
4. **Stop-Loss**: Every trade has a stop-loss (typically 3-3.5× ATR)
5. **Take-Profit**: Every trade has a take-profit target (typically 5× ATR)

### Safeguards

- **Test Mode**: Set `CI=true` in `.env` to simulate trades without real execution
- **Practice Account**: Use `OANDA_ENV=practice` for safe testing
- **Cooldown Periods**: Prevents over-trading (20-second cooldown per pair-strategy)
- **Rate Limiting**: Respects OANDA's 60 requests/minute limit
- **Error Alerts**: Sends webhook notifications on errors

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    OANDA Bot                             │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  main.py ──▶ Strategy Engine ──▶ Data Layer (OANDA API) │
│      │              │                                     │
│      │              ▼                                     │
│      │       Risk Management                             │
│      │              │                                     │
│      └──────────────▼                                     │
│              Broker Interface                            │
│                     │                                     │
│                     ▼                                     │
│              Order Execution                             │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

For detailed architecture documentation, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Deployment

### Production Checklist

Before deploying to production:

1. [ ] Test thoroughly on practice account
2. [ ] Review and optimize strategy parameters
3. [ ] Set appropriate risk limits (`RISK_FRAC`)
4. [ ] Configure error webhook for alerts
5. [ ] Enable health checks
6. [ ] Set up log monitoring
7. [ ] Switch to `OANDA_ENV=live`
8. [ ] Start with small capital
9. [ ] Monitor closely for first 24 hours

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed production deployment guide.

---

## Troubleshooting

### Bot won't start

**Check**:
1. Is `.env` configured correctly?
2. Are OANDA credentials valid?
3. Is port 8000 available?
4. Run `python -m oanda_bot.main` directly to see error messages

### No trades executing

**Check**:
1. Are strategies enabled in `live_config.json`?
2. Is ATR too low? (Bot skips trades when ATR < 0.0008)
3. Check cooldown periods (20s per pair-strategy)
4. Review logs for "SKIP" messages

### Drawdown too high

**Actions**:
1. Reduce `RISK_FRAC` in `.env`
2. Review strategy parameters
3. Run optimization with `--target_win_rate 0.60`
4. Disable underperforming strategies

### Orders rejected by OANDA

**Check**:
1. Account has sufficient funds
2. Position size doesn't exceed limits
3. Stop-loss and take-profit prices are valid
4. Not trading during market close

---

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -r dev_requirements.txt

# Run all tests
pytest

# Run specific test
pytest oanda_bot/tests/test_main_drawdown.py

# Run with coverage
pytest --cov=oanda_bot
```

### Adding a New Strategy

1. Create `oanda_bot/strategy/my_strategy.py`:

```python
from oanda_bot.strategy.base import BaseStrategy

class StrategyMyStrategy(BaseStrategy):
    name = "MyStrategy"

    def next_signal(self, bars):
        if len(bars) < 20:
            return None

        # Your logic here
        if some_condition:
            return "BUY"
        elif other_condition:
            return "SELL"

        return None
```

2. Add tests in `oanda_bot/tests/test_my_strategy.py`
3. Add parameters to `live_config.json`
4. Run optimization to find best parameters
5. Test on practice account before going live

### Code Style

```bash
# Run linter
flake8 oanda_bot/

# Configuration in .flake8
```

---

## Resources

- **OANDA API Documentation**: https://developer.oanda.com/rest-live-v20/introduction/
- **Architecture Documentation**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Deployment Guide**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **Strategy Development**: See `oanda_bot/strategy/base.py` for interface

---

## Support

For issues, questions, or contributions:

1. Check existing issues on GitHub
2. Review [ARCHITECTURE.md](ARCHITECTURE.md) for technical details
3. Review logs in `live_trading.log` and `backtest.log`
4. Contact: nickguerriero@example.com

---

## Disclaimer

**IMPORTANT**: Trading forex and CFDs involves significant risk of loss. This software is provided for educational purposes only. Past performance does not guarantee future results. Always:

- Start with a practice account
- Only risk capital you can afford to lose
- Understand the strategies before deploying
- Monitor the bot regularly
- Have a risk management plan

The authors are not responsible for any financial losses incurred using this software.

---

## License

Proprietary - All rights reserved.

Author: Nick Guerriero

---

**Version**: 0.1.0
**Last Updated**: 2025-12-25

Happy Trading! 📈
