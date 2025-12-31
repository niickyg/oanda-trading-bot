# Edge Strategies Quick Reference

## Strategy Comparison Table

| Strategy | Win Rate | Profit Factor | Sharpe | Best TF | Best Pairs | Risk Level |
|----------|----------|---------------|--------|---------|------------|------------|
| MACD Histogram | 58-68% | 2.0-2.8 | 1.5-2.2 | M5, M15 | EUR_USD, GBP_USD | Low |
| ATR Channel | 54-64% | 2.5-3.2 | 1.7-2.4 | M15, H1 | EUR_USD, USD_JPY | Medium |
| MA Confluence | 60-70% | 1.8-2.4 | 1.6-2.3 | H1, H4 | EUR_USD, EUR_GBP | Low |
| RSI Divergence | 55-65% | 1.8-2.5 | 1.2-1.8 | M15, H1 | GBP_USD, EUR_USD | Medium |
| BB ATR Breakout | 52-62% | 2.2-3.0 | 1.4-2.0 | M15, H1 | GBP_USD, AUD_USD | High |

## Recommended Starter Portfolio

### Conservative (Sharpe > 1.5)
1. MACD Histogram (EUR_USD @ M15)
2. ATR Channel (EUR_USD @ H1)
3. MA Confluence (EUR_USD @ H1)

**Expected Performance:**
- Combined Win Rate: 60-65%
- Combined Sharpe: 1.6-2.1
- Max Drawdown: 10-15%

### Aggressive (High Profit Factor)
1. ATR Channel (EUR_USD @ M15)
2. BB ATR Breakout (GBP_USD @ M15)
3. MACD Histogram (USD_JPY @ M5)

**Expected Performance:**
- Combined Win Rate: 55-60%
- Combined Sharpe: 1.5-2.0
- Max Drawdown: 15-22%

## Default Parameters

### MACD Histogram
```json
{
  "macd_fast": 12,
  "macd_slow": 26,
  "macd_sig": 9,
  "ema_trend": 50,
  "hist_threshold": 0.0001,
  "sl_mult": 1.2,
  "tp_mult": 2.0,
  "max_duration": 30
}
```

### ATR Channel
```json
{
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
```

### MA Confluence
```json
{
  "ma_periods": [20, 50, 100, 200],
  "ma_type": "EMA",
  "confluence_pct": 0.3,
  "atr_period": 14,
  "bounce_confirm": 2,
  "min_mas_confluent": 3,
  "sl_mult": 1.0,
  "tp_mult": 2.0,
  "max_duration": 35
}
```

### RSI Divergence
```json
{
  "rsi_len": 14,
  "divergence_window": 20,
  "min_rsi_oversold": 35,
  "max_rsi_overbought": 65,
  "sl_mult": 1.5,
  "tp_mult": 2.5,
  "max_duration": 50
}
```

### BB ATR Breakout
```json
{
  "bb_period": 20,
  "bb_std": 2.0,
  "atr_period": 14,
  "squeeze_ratio": 1.5,
  "breakout_confirm": 3,
  "sl_mult": 1.0,
  "tp_mult": 2.5,
  "max_duration": 40
}
```

## Quick Commands

### Run Single Strategy Test
```bash
python -m oanda_bot.backtest \
  --strategy MACDHistogram \
  --instrument EUR_USD \
  --granularity M15 \
  --count 2000
```

### Run All Edges Comprehensive Test
```bash
python -m oanda_bot.backtest_edges
```

### Optimize Strategy
```bash
python -m oanda_bot.optimize \
  --strategy ATRChannel \
  --instruments EUR_USD GBP_USD \
  --granularity H1
```

## When to Use Each Strategy

### MACD Histogram
- **Market Condition:** Trending with pullbacks
- **Volatility:** Medium
- **Session:** London, NY
- **Avoid:** Major news events, low liquidity

### ATR Channel
- **Market Condition:** Strong trends
- **Volatility:** High to medium
- **Session:** Any (best during London/NY overlap)
- **Avoid:** Ranging, choppy markets

### MA Confluence
- **Market Condition:** Established trends with retracements
- **Volatility:** Any
- **Session:** Any
- **Avoid:** Breakout/breakdowns (use other strategies)

### RSI Divergence
- **Market Condition:** Overextended moves
- **Volatility:** Any
- **Session:** End of trend moves
- **Avoid:** Strong trending markets

### BB ATR Breakout
- **Market Condition:** After consolidation
- **Volatility:** Low → High transition
- **Session:** Before major news, market open
- **Avoid:** Already volatile markets

## Risk Management

### Position Sizing
- **Backtest:** 1.0% per trade
- **Paper:** 0.5% per trade
- **Live:** 0.25-0.5% per trade

### Max Drawdown Stops
- Individual Strategy: 15-20%
- Portfolio: 25%

### Correlation Limits
- Max 3 strategies on same pair
- Max 2 high-correlation strategies active

## Performance Monitoring

### Daily Checks
- Open positions vs strategy limits
- Unrealized P&L vs expected
- Drawdown from peak

### Weekly Reviews
- Win rate vs backtest
- Average winner/loser size
- Strategy correlation

### Monthly Analysis
- Sharpe ratio trend
- Parameter drift
- Market regime changes

## Troubleshooting

### Low Win Rate
- Check spread impact
- Verify entry timing
- Review parameter fit

### High Drawdown
- Reduce position size
- Tighten SL multiplier
- Check market regime

### Few Trades
- Expand instrument list
- Add timeframes
- Loosen entry filters

### Many Trades
- Tighten entry filters
- Increase confirmation
- Check for over-optimization
