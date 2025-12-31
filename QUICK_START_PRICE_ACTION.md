# Quick Start Guide: Price Action Trading

## How to Run Backtests

### Quick Test (Recommended First)
```bash
cd /home/user0/oandabot16/oanda_bot
python quick_price_action_test.py
```

This runs a fast test on 2 pairs and 2 timeframes with 3 strategy configurations.
**Runtime:** 2-5 minutes
**Output:** Console summary with best setups

### Comprehensive Test
```bash
python backtest_price_action.py
```

This runs extensive tests on 4 pairs, 5 timeframes, and 8 configurations.
**Runtime:** 15-30 minutes
**Output:**
- Console detailed results
- JSON file: `price_action_backtest_results.json`

### Test Existing Strategies
```bash
python test_strategies.py
```

Tests all existing strategies including price action on recent M1 data.
**Runtime:** 3-8 minutes

---

## Interpreting Results

### Key Metrics to Watch

**Trades:** Minimum 5 for statistical significance, prefer 10+

**Win Rate:**
- < 45%: Poor edge, avoid
- 45-50%: Acceptable with good R:R
- 50-55%: Good edge
- 55-60%: Excellent edge
- > 60%: Verify not curve-fitted

**Total PnL:**
- Positive = profitable configuration
- Negative = losing configuration
- Focus on consistency across pairs

**Expectancy:**
- Negative: Skip this setup
- 0.0001-0.0003: Marginal edge (scalping)
- 0.0003-0.0006: Good edge
- > 0.0006: Excellent edge

**Risk:Reward:**
- Minimum: 1:1.5
- Target: 1:2-1:3
- Excellent: 1:4+

---

## Adding to Live Config

### Step 1: Identify Best Configuration

From backtest results, find setup with:
- Total PnL > 0.001
- Win rate > 50%
- Trades > 10
- Expectancy > 0.0003

### Step 2: Edit live_config.json

```bash
cd /home/user0/oandabot16/oanda_bot
nano live_config.json
```

### Step 3: Add Configuration

```json
{
  "enabled": ["PriceAction"],
  "PriceAction": {
    "EUR_USD": {
      "pin_wick_ratio": 2.5,
      "lookback_sr": 20,
      "sl_mult": 1.2,
      "tp_mult": 2.8,
      "pin_weight": 1.5,
      "engulf_weight": 1.0,
      "breakout_weight": 0.8,
      "min_signal_strength": 1.5,
      "atr_period": 14
    }
  }
}
```

### Step 4: Test in Paper Mode

```bash
# Set paper trading mode in main.py or config
python -m oanda_bot.main --paper-trade
```

### Step 5: Go Live (After Paper Success)

```bash
python -m oanda_bot.main
```

---

## File Structure

### Strategy Files
```
/home/user0/oandabot16/oanda_bot/oanda_bot/strategy/
├── price_action.py       # Main price action strategy
├── supply_demand.py      # Supply/demand zones
├── micro_reversion.py    # Ultra-short timeframe reversion
├── momentum_scalp.py     # Momentum-based scalping
└── base.py              # Base strategy class
```

### Backtest Files
```
/home/user0/oandabot16/oanda_bot/
├── backtest_price_action.py      # Comprehensive backtester
├── quick_price_action_test.py    # Quick test script
└── test_strategies.py            # All strategies tester
```

### Documentation
```
/home/user0/oandabot16/oanda_bot/
├── PRICE_ACTION_RESEARCH.md      # In-depth research
├── EDGE_ANALYSIS_SUMMARY.md      # Complete edge analysis
└── QUICK_START_PRICE_ACTION.md   # This file
```

---

## Common Commands

### Fetch Historical Data
```python
from oanda_bot.data.core import get_candles

# Get 500 H1 candles for EUR/USD
candles = get_candles("EUR_USD", "H1", 500)

# Available granularities:
# S5, S10, S15, S30 (seconds)
# M1, M2, M5, M15, M30 (minutes)
# H1, H2, H4, H8, H12 (hours)
# D, W, M (daily, weekly, monthly)
```

### Run Single Backtest
```python
from oanda_bot.data.core import get_candles
from oanda_bot.backtest import run_backtest
from oanda_bot.strategy.price_action import StrategyPriceAction

# Fetch data
candles = get_candles("EUR_USD", "H1", 500)

# Create strategy
params = {
    "pin_wick_ratio": 2.5,
    "lookback_sr": 20,
    "sl_mult": 1.2,
    "tp_mult": 2.8,
    "min_signal_strength": 1.5
}
strategy = StrategyPriceAction(params)

# Run backtest
stats = run_backtest(strategy, candles, warmup=30)

# Print results
print(f"Trades: {stats['trades']}")
print(f"Win Rate: {stats['win_rate']:.2%}")
print(f"Total PnL: {stats['total_pnl']:.5f}")
print(f"Expectancy: {stats['expectancy']:.6f}")
```

---

## Parameter Tuning Guide

### Pin Bar Detection
**pin_wick_ratio:** How much larger wick must be vs body
- 1.5: Many signals, lower quality
- 2.0-2.5: Balanced (recommended)
- 3.0+: Rare but strong signals

**min_body_ratio:** Maximum body size relative to range
- 0.25: Very strict pin bars only
- 0.30-0.35: Balanced (recommended)
- 0.40+: Includes larger body pins

### Pattern Weights
Adjust relative importance of each pattern:

**pin_weight:** 0.5-2.0
- Higher = prioritize pin bars
- Lower = de-emphasize pins

**engulf_weight:** 0.5-2.0
- Higher = prioritize engulfing
- Lower = de-emphasize engulfing

**breakout_weight:** 0.5-2.0
- Higher = prioritize breakouts
- Lower = de-emphasize breakouts

### Signal Filtering
**min_signal_strength:** Minimum combined signal to trade
- 0.8: More trades, lower quality
- 1.0-1.3: Balanced
- 1.5+: Fewer trades, higher quality (recommended)

### Risk Management
**sl_mult:** Stop loss ATR multiplier
- 0.8-1.0: Tight stops, more losses
- 1.2-1.5: Balanced (recommended)
- 2.0+: Wide stops, fewer but larger losses

**tp_mult:** Take profit ATR multiplier
- 2.0: Conservative, higher win rate
- 2.5-3.0: Balanced (recommended)
- 4.0+: Aggressive, lower win rate but larger wins

---

## Troubleshooting

### No Trades Generated
**Possible causes:**
1. Signal strength threshold too high
   - Solution: Lower `min_signal_strength` to 1.0

2. Not enough data for warmup
   - Solution: Fetch more candles (increase count)

3. Pattern parameters too strict
   - Solution: Relax `pin_wick_ratio` to 2.0

### Too Many Trades (Low Quality)
**Possible causes:**
1. Signal threshold too low
   - Solution: Increase `min_signal_strength` to 1.5+

2. Pattern weights not calibrated
   - Solution: Reduce weights or focus on one pattern

### Low Win Rate
**Possible causes:**
1. Stops too tight
   - Solution: Increase `sl_mult` to 1.5

2. Not respecting S/R levels
   - Solution: Ensure patterns trade near levels

3. Wrong timeframe
   - Solution: Test on H1 instead of M1

### Backtest Crashes
**Possible causes:**
1. API rate limit
   - Solution: Add delay between candle fetches

2. Invalid data format
   - Solution: Check OANDA API response

3. Missing dependencies
   - Solution: `pip install -r requirements.txt`

---

## Best Practices

### Before Going Live

1. **Backtest thoroughly**
   - Test on at least 500 bars
   - Verify across multiple pairs
   - Check different timeframes

2. **Paper trade first**
   - Run for minimum 1 week
   - Verify signals match backtest
   - Check execution quality

3. **Start small**
   - Begin with 0.25-0.5% risk
   - Trade 1-2 pairs initially
   - Scale gradually

### During Live Trading

1. **Monitor daily**
   - Check trade quality
   - Verify stops/targets hit correctly
   - Track slippage

2. **Keep records**
   - Log every trade
   - Note market conditions
   - Track emotions/decisions

3. **Review weekly**
   - Analyze P&L by edge type
   - Compare to backtest expectations
   - Adjust if needed

### Risk Management Rules

1. **Never** exceed 2% risk per trade
2. **Always** set stop before entry
3. **Limit** daily loss to 5% of account
4. **Stop** after 3 consecutive losses
5. **Review** after any 10% drawdown

---

## Performance Expectations

### Realistic Monthly Returns
- **Conservative (0.5% risk):** 3-6%
- **Moderate (1% risk):** 5-10%
- **Aggressive (2% risk):** 8-15%

### Expected Drawdowns
- **Conservative:** 10-15%
- **Moderate:** 15-25%
- **Aggressive:** 20-35%

### Trade Frequency
- **Scalping (M1-M5):** 10-30 trades/day
- **Day Trading (M15-H1):** 2-8 trades/day
- **Swing (H1-H4):** 3-10 trades/week

---

## Support and Resources

### Code Files
- **Strategy:** `/oanda_bot/strategy/price_action.py`
- **Backtest:** `/oanda_bot/backtest.py`
- **Data:** `/oanda_bot/data/core.py`

### Documentation
- **Research:** `PRICE_ACTION_RESEARCH.md`
- **Analysis:** `EDGE_ANALYSIS_SUMMARY.md`
- **Architecture:** `ARCHITECTURE.md`

### Logs
- **Backtest:** `backtest.log`
- **Live Trading:** `live_trading.log`
- **Trades:** `trades_log.csv`

---

## Quick Reference: Strategy Selection

### Choose Pin Bar If:
- Trading major S/R levels
- H1+ timeframe
- Want high R:R setups
- Can wait for quality

### Choose Engulfing If:
- Want faster signals
- Trading all timeframes
- Like momentum setups
- Prefer confirmation

### Choose Breakout If:
- Trading trending markets
- Patient for confirmation
- Want highest win rate
- Can wait for retests

### Choose Supply/Demand If:
- Trading H1+ only
- Want institutional levels
- Prefer swing trading
- Like zone-based trading

### Choose Combined If:
- Want balanced approach
- Multiple timeframes
- Diversify edge types
- Maximize opportunities

---

## Next Steps

1. **Run quick test:**
   ```bash
   python quick_price_action_test.py
   ```

2. **Review results:**
   - Identify profitable setups
   - Note best pairs/timeframes
   - Check win rates

3. **Run comprehensive test:**
   ```bash
   python backtest_price_action.py
   ```

4. **Analyze output:**
   - Open `price_action_backtest_results.json`
   - Find highest PnL configurations
   - Verify across multiple pairs

5. **Configure live system:**
   - Edit `live_config.json`
   - Add best configuration
   - Set risk parameters

6. **Start trading:**
   - Paper trade 1 week
   - Micro positions 2 weeks
   - Scale to full size

**Good luck and trade with discipline!**
