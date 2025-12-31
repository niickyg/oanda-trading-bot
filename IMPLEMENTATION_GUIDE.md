# Implementation Guide: Trading Edge Strategies

## Overview

This guide provides step-by-step instructions for deploying the 5 new technical indicator-based edge strategies into the oanda_bot production environment.

---

## Pre-Deployment Checklist

### 1. Environment Setup

Ensure these environment variables are configured:

```bash
export OANDA_TOKEN="your_production_token"
export OANDA_ACCOUNT_ID="your_account_id"
export OANDA_ENV="practice"  # Start with practice, then "live"
```

### 2. Verify Installation

```bash
cd /home/user0/oandabot16/oanda_bot
python -c "from oanda_bot.strategy.rsi_divergence import StrategyRSIDivergence; print('OK')"
python -c "from oanda_bot.strategy.macd_histogram import StrategyMACDHistogram; print('OK')"
python -c "from oanda_bot.strategy.bb_atr_breakout import StrategyBBATRBreakout; print('OK')"
python -c "from oanda_bot.strategy.ma_confluence import StrategyMAConfluence; print('OK')"
python -c "from oanda_bot.strategy.atr_channel import StrategyATRChannel; print('OK')"
```

All should print "OK".

### 3. Update Strategy Registry

Edit `/home/user0/oandabot16/oanda_bot/oanda_bot/strategy/__init__.py`:

```python
from .rsi_divergence import StrategyRSIDivergence
from .macd_histogram import StrategyMACDHistogram
from .bb_atr_breakout import StrategyBBATRBreakout
from .ma_confluence import StrategyMAConfluence
from .atr_channel import StrategyATRChannel

__all__ = [
    # ... existing strategies ...
    "StrategyRSIDivergence",
    "StrategyMACDHistogram",
    "StrategyBBATRBreakout",
    "StrategyMAConfluence",
    "StrategyATRChannel",
]
```

---

## Phase 1: Backtesting (Week 1)

### Step 1: Run Comprehensive Backtest

```bash
cd /home/user0/oandabot16/oanda_bot
python -m oanda_bot.backtest_edges
```

This will:
- Test all 5 strategies
- On 6 currency pairs (EUR_USD, GBP_USD, USD_JPY, AUD_USD, USD_CAD, EUR_GBP)
- On 3 timeframes (M5, M15, H1)
- Generate `edge_backtest_results.json`

**Expected Runtime:** 2-5 minutes

### Step 2: Analyze Results

```bash
python << 'EOF'
import json

with open('edge_backtest_results.json', 'r') as f:
    results = json.load(f)

print("=" * 80)
print("TOP PERFORMING STRATEGIES")
print("=" * 80)

for item in results['comparison'][:10]:
    print(f"{item['strategy']:20s} {item['pair']:10s} {item['timeframe']:5s} | "
          f"WR: {item['win_rate']:.1%} | PF: {item['profit_factor']:.2f} | "
          f"Exp: {item['expectancy']:.5f}")
EOF
```

### Step 3: Identify Top 3 Strategies

Based on results, select top 3 by:
1. **Highest Expectancy** (primary metric)
2. **Win Rate > 55%** (secondary filter)
3. **Profit Factor > 1.8** (tertiary filter)

Example expected output:
```
1. MACDHistogram    EUR_USD    M15   | WR: 63.5% | PF: 2.45 | Exp: 0.00234
2. ATRChannel       EUR_USD    H1    | WR: 59.2% | PF: 2.78 | Exp: 0.00198
3. MAConfluence     GBP_USD    H1    | WR: 64.1% | PF: 2.12 | Exp: 0.00176
```

### Step 4: Parameter Optimization

For each top strategy, run optimization:

```bash
# Example: Optimize MACD Histogram on EUR_USD M15
python -m oanda_bot.optimize \
  --strategy MACDHistogram \
  --instruments EUR_USD \
  --granularity M15 \
  --count 4000 \
  --min_trades 20 \
  --target_win_rate 0.55
```

This will generate `best_params_EUR_USD.json` with optimized parameters.

Repeat for other top strategies.

---

## Phase 2: Paper Trading (Week 2-3)

### Step 1: Configure Paper Trading

Create `paper_config.json`:

```json
{
  "enabled": [
    "MACDHistogram",
    "ATRChannel"
  ],
  "risk_pct": 0.005,
  "meta_bandit": false,
  "active_top_k": 10,
  "pair_whitelist": [
    "EUR_USD",
    "GBP_USD",
    "USD_JPY"
  ],

  "MACDHistogram": {
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_sig": 9,
    "ema_trend": 50,
    "hist_threshold": 0.0001,
    "sl_mult": 1.2,
    "tp_mult": 2.0,
    "max_duration": 30
  },

  "ATRChannel": {
    "ema_period": 20,
    "atr_period": 14,
    "atr_mult": 2.0,
    "trend_ema": 50,
    "breakout_confirm": 2,
    "min_atr": 0.0001,
    "sl_mult": 1.5,
    "tp_mult": 3.0,
    "max_duration": 40
  }
}
```

### Step 2: Start Paper Trading

```bash
# Ensure OANDA_ENV=practice
export OANDA_ENV="practice"

# Run with paper config
python -m oanda_bot.main --config paper_config.json
```

### Step 3: Monitor Performance

Set up daily monitoring script `monitor_paper.py`:

```python
#!/usr/bin/env python3
"""Daily performance monitoring for paper trading."""

import json
import pandas as pd
from datetime import datetime

# Read trades log
df = pd.read_csv('trades_log.csv')

# Filter last 24 hours
df['timestamp'] = pd.to_datetime(df['timestamp'])
last_24h = df[df['timestamp'] > (datetime.now() - pd.Timedelta(days=1))]

# Calculate metrics
total_trades = len(last_24h)
wins = len(last_24h[last_24h['pnl'] > 0])
losses = len(last_24h[last_24h['pnl'] < 0])
win_rate = wins / total_trades if total_trades > 0 else 0
total_pnl = last_24h['pnl'].sum()

print(f"Last 24h Performance:")
print(f"  Trades: {total_trades}")
print(f"  Win Rate: {win_rate:.2%}")
print(f"  Total P&L: {total_pnl:.4f}")

# By strategy
for strategy in last_24h['strategy'].unique():
    strat_df = last_24h[last_24h['strategy'] == strategy]
    strat_pnl = strat_df['pnl'].sum()
    strat_wr = len(strat_df[strat_df['pnl'] > 0]) / len(strat_df)
    print(f"  {strategy}: {len(strat_df)} trades, WR={strat_wr:.2%}, PnL={strat_pnl:.4f}")
```

Run daily:
```bash
python monitor_paper.py
```

### Step 4: Validate Performance

After 2 weeks, compare paper trading to backtest:

| Metric | Backtest | Paper | Diff |
|--------|----------|-------|------|
| Win Rate | 63.5% | ? | ? |
| Profit Factor | 2.45 | ? | ? |
| Avg Winner | 0.0024 | ? | ? |
| Avg Loser | -0.0011 | ? | ? |

**Acceptance Criteria:**
- Win rate within ±5% of backtest
- Profit factor within ±0.3 of backtest
- No catastrophic drawdowns (>25%)

If criteria met, proceed to Phase 3. Otherwise, re-optimize parameters.

---

## Phase 3: Live Deployment (Week 4+)

### Step 1: Conservative Live Config

Create `live_config_conservative.json`:

```json
{
  "enabled": [
    "MACDHistogram"
  ],
  "risk_pct": 0.0025,
  "meta_bandit": false,
  "active_top_k": 5,
  "pair_whitelist": [
    "EUR_USD"
  ],

  "MACDHistogram": {
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_sig": 9,
    "ema_trend": 50,
    "hist_threshold": 0.0001,
    "sl_mult": 1.5,
    "tp_mult": 2.0,
    "max_duration": 30
  }
}
```

**Key Changes:**
- Only 1 strategy
- Only 1 currency pair (EUR_USD)
- Reduced risk: 0.25% per trade (vs 0.5% in paper)
- Wider SL: 1.5x (vs 1.2x in backtest)

### Step 2: Deploy to Live

```bash
# Switch to live environment
export OANDA_ENV="live"
export OANDA_TOKEN="your_live_token"
export OANDA_ACCOUNT_ID="your_live_account"

# Start trading (use screen/tmux for persistence)
screen -S oanda_live
python -m oanda_bot.main --config live_config_conservative.json
# Ctrl+A, D to detach
```

### Step 3: Real-Time Monitoring

Set up alert script `alert_drawdown.py`:

```python
#!/usr/bin/env python3
"""Alert on drawdown threshold."""

import pandas as pd
import smtplib
from email.message import EmailMessage

# Read trades
df = pd.read_csv('trades_log.csv')
df['pnl'] = pd.to_numeric(df['pnl'])

# Calculate cumulative P&L
df['cum_pnl'] = df['pnl'].cumsum()

# Calculate drawdown
running_max = df['cum_pnl'].cumsum().expanding().max()
drawdown = (df['cum_pnl'] - running_max) / running_max

# Alert threshold
MAX_DRAWDOWN = 0.15  # 15%

if drawdown.min() < -MAX_DRAWDOWN:
    msg = EmailMessage()
    msg['Subject'] = 'ALERT: Drawdown Threshold Exceeded'
    msg['From'] = 'bot@example.com'
    msg['To'] = 'trader@example.com'
    msg.set_content(f'Current drawdown: {drawdown.min():.2%}')

    # Send email (configure SMTP)
    # with smtplib.SMTP('localhost') as s:
    #     s.send_message(msg)

    print(f"ALERT: Drawdown {drawdown.min():.2%} exceeds {MAX_DRAWDOWN:.2%}")
```

Run via cron every hour:
```bash
0 * * * * /usr/bin/python3 /path/to/alert_drawdown.py
```

### Step 4: Gradual Scaling

**Week 4:** 1 strategy, 1 pair, 0.25% risk
**Week 5:** Same config, increase to 0.35% risk (if performing well)
**Week 6:** Add 2nd strategy (ATRChannel)
**Week 7:** Add 2nd pair (GBP_USD)
**Week 8:** Add 3rd strategy (MAConfluence)
**Week 9+:** Full portfolio (5 strategies, 6 pairs)

---

## Ongoing Maintenance

### Daily Tasks

1. **Check Open Positions**
   ```bash
   python -c "from oanda_bot.broker import get_open_positions; print(get_open_positions())"
   ```

2. **Review Overnight Trades**
   ```bash
   tail -20 trades_log.csv
   ```

3. **Monitor Drawdown**
   ```bash
   python monitor_paper.py
   ```

### Weekly Tasks

1. **Performance Review**
   - Compare to backtest expectations
   - Identify underperforming strategies
   - Check for parameter drift

2. **Parameter Check**
   - Are SL/TP levels still appropriate?
   - Is ATR changing significantly?
   - Should we re-optimize?

3. **Correlation Analysis**
   - Are strategies becoming correlated?
   - Should we disable some temporarily?

### Monthly Tasks

1. **Full Re-Optimization**
   ```bash
   # Re-run optimization on live data
   python -m oanda_bot.optimize \
     --strategy MACDHistogram \
     --instruments EUR_USD \
     --granularity M15 \
     --count 5000
   ```

2. **Walk-Forward Analysis**
   - Test new parameters on out-of-sample data
   - Deploy only if improvement confirmed

3. **Strategy Rotation**
   - Disable strategies with sustained poor performance
   - Enable new strategies or variations

---

## Troubleshooting

### Problem: Low Win Rate

**Symptoms:**
- Win rate 10%+ below backtest
- Frequent small losses

**Solutions:**
1. Check spread impact:
   ```python
   # Add to strategy
   spread = ask - bid
   if spread > 2 * avg_spread:
       return None  # Skip trade
   ```

2. Tighten entry filters:
   - Increase `breakout_confirm` by 1
   - Raise `hist_threshold` by 0.00005

3. Review execution timing:
   - Are we getting filled at expected prices?
   - Is slippage excessive?

### Problem: Excessive Drawdown

**Symptoms:**
- Drawdown >20% from peak
- Multiple consecutive losses

**Solutions:**
1. **Immediate:** Reduce position size by 50%
2. **Short-term:** Disable underperforming strategies
3. **Long-term:** Re-optimize parameters or implement regime detection

### Problem: Few Trades

**Symptoms:**
- <5 trades per day expected
- Strategies not triggering

**Solutions:**
1. Check data feed:
   ```bash
   python -c "from oanda_bot.data import get_candles; print(len(get_candles('EUR_USD', 'M15', 100)))"
   ```

2. Lower entry thresholds:
   - Reduce `min_atr`
   - Lower `bounce_confirm`

3. Add more pairs/timeframes

### Problem: Unexpected Behavior

**Symptoms:**
- Strategies behaving differently than backtest
- Unusual entry/exit patterns

**Solutions:**
1. Enable debug logging:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. Validate data:
   ```python
   # Check for NaN or missing data
   import pandas as pd
   df = pd.DataFrame(candles)
   print(df.isnull().sum())
   ```

3. Review recent code changes:
   ```bash
   git diff HEAD~5..HEAD strategy/
   ```

---

## Advanced Features (Optional)

### 1. Multi-Timeframe Confirmation

Combine M15 signals with H1 trend filter:

```python
# In strategy
def next_signal(self, bars):
    # Get M15 signal
    m15_signal = self._generate_signal(bars)

    # Get H1 candles for trend confirmation
    h1_candles = get_candles(self.pair, "H1", 100)
    h1_trend = self._detect_trend(h1_candles)

    # Only trade if M15 signal aligns with H1 trend
    if m15_signal == "BUY" and h1_trend == "UP":
        return "BUY"
    elif m15_signal == "SELL" and h1_trend == "DOWN":
        return "SELL"

    return None
```

### 2. Dynamic Position Sizing

Adjust position size based on recent performance:

```python
def calculate_position_size(self, base_risk_pct):
    # Increase size after wins, decrease after losses
    win_streak = self._count_recent_wins(5)

    if win_streak >= 3:
        return base_risk_pct * 1.2  # 20% increase
    elif win_streak <= -3:
        return base_risk_pct * 0.7  # 30% decrease

    return base_risk_pct
```

### 3. News Event Filter

Avoid trading during high-impact news:

```python
from oanda_bot.data.news import fetch_forex_news_from_twitter

def should_trade(self):
    # Check for upcoming news in next 30 minutes
    news = fetch_forex_news_from_twitter()
    upcoming = [n for n in news if n['time_to_event'] < 1800]  # 30 min

    if upcoming and any(n['impact'] == 'HIGH' for n in upcoming):
        return False

    return True
```

---

## Performance Targets

### Month 1 (Conservative)
- **Target Return:** 5-10%
- **Max Drawdown:** <10%
- **Sharpe Ratio:** >1.0
- **Win Rate:** >55%

### Month 2-3 (Scaling)
- **Target Return:** 10-20% per month
- **Max Drawdown:** <15%
- **Sharpe Ratio:** >1.3
- **Win Rate:** >57%

### Month 4+ (Optimized)
- **Target Return:** 15-30% per month
- **Max Drawdown:** <20%
- **Sharpe Ratio:** >1.5
- **Win Rate:** >60%

---

## Support & Resources

### Documentation
- Main Report: `EDGE_ANALYSIS_REPORT.md`
- Quick Reference: `EDGE_STRATEGIES_QUICKREF.md`
- This Guide: `IMPLEMENTATION_GUIDE.md`

### Code Locations
- Strategies: `/home/user0/oandabot16/oanda_bot/oanda_bot/strategy/`
- Backtest: `/home/user0/oandabot16/oanda_bot/oanda_bot/backtest_edges.py`
- Main Engine: `/home/user0/oandabot16/oanda_bot/oanda_bot/main.py`

### Testing
```bash
# Unit tests
python -m pytest oanda_bot/tests/

# Integration tests
python -m oanda_bot.test_single_edge

# Full backtest
python -m oanda_bot.backtest_edges
```

---

**Good luck with deployment! Remember: Start small, scale gradually, monitor constantly.**
