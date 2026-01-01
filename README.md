# OANDA Trading Bot

Forex trading bot for OANDA with multiple strategy engines, backtesting, optimization, and risk management.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Configure `.env`:
```bash
OANDA_TOKEN=your_token
OANDA_ACCOUNT_ID=your_account_id
OANDA_ENV=practice  # or 'live'
RISK_FRAC=0.02
```

Configure strategies in `live_config.json`:
```json
{
  "MACDTrend": {
    "EUR_USD": {
      "sl_mult": 3.0,
      "tp_mult": 3.0
    }
  }
}
```

## Usage

**Live trading:**
```bash
python -m oanda_bot.main
```

**Docker:**
```bash
docker-compose up -d
docker-compose logs -f bot
```

**Dashboard:**
```bash
streamlit run oanda_bot/app.py
```

**Backtest:**
```bash
python -m oanda_bot.backtest --strategy MACDTrend --instrument EUR_USD --granularity H1 --count 2000
```

**Optimize:**
```bash
python -m oanda_bot.optimize --strategy MACDTrend --instruments EUR_USD GBP_USD --min_trades 30
```

## Strategies

- **MACDTrend** - Trend following
- **RSIReversion** - Mean reversion
- **BollingerSqueeze** - Volatility breakout
- **Breakout** - Momentum
- **TrendMA** - Moving average trends
- **VolatilityGrid** - Grid trading
- **TriArb** - Triangular arbitrage

Bot selects strategies based on detected market regime.

## Risk Management

- Position sizing based on ATR and risk percentage
- Stop-loss on every trade (3-3.5× ATR)
- Take-profit targets (5× ATR)
- Drawdown protection at 5% and 10%
- Max position size: 1000 units
- 20-second cooldown per pair-strategy

## Logs

- `live_trading.log` - JSON trading logs
- `trades_log.csv` - Trade history
- `backtest.log` - Backtest results

Health check: `curl http://localhost:8000/health`

## Adding Strategies

Create `oanda_bot/strategy/my_strategy.py`:

```python
from oanda_bot.strategy.base import BaseStrategy

class StrategyMyStrategy(BaseStrategy):
    name = "MyStrategy"

    def next_signal(self, bars):
        # Your logic
        if condition:
            return "BUY"
        return None
```

Add parameters to `live_config.json`, optimize, and test on practice account.

## Deployment

1. Test on practice account
2. Optimize parameters
3. Set risk limits
4. Configure alerts
5. Enable health checks
6. Start with small capital

See [DEPLOYMENT.md](DEPLOYMENT.md) for details.

**Disclaimer:** Trading involves significant risk. Educational purposes only. Test thoroughly before live trading.
