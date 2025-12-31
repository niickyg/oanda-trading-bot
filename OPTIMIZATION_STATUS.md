# OANDA Bot Optimization Status

**Last Updated**: 2025-12-31 04:25 UTC

## Night Testing Session Complete

### Multi-Strategy Test Results (03:23-04:25 UTC)

| Trade | Pair | Direction | Entry | SL | TP | P/L | Result |
|-------|------|-----------|-------|----|----|-----|--------|
| 1 | GBP_JPY | BUY | 210.634 | 210.60 | 210.69 | +$1.14 | WIN |
| 2 | USD_CHF | BUY | - | - | - | -$1.52 | LOSS |
| 3 | GBP_USD | BUY | 1.34625 | 1.34602 | 1.34661 | -$1.70 | LOSS |
| 4 | USD_JPY | BUY | - | - | - | +$1.14 | WIN |
| 5 | EUR_USD | BUY | - | - | - | -$1.40 | LOSS |

**Summary:**
- Win Rate: **40%** (2/5)
- Average Win: +$1.14
- Average Loss: -$1.54
- Net P/L: -$2.33

### Analysis

1. **Win Rate Improvement**: 40% is better than historical 12%, but still unprofitable
2. **Risk:Reward Issue**: Losses average $1.54 while wins average $1.14
   - Need R:R > 1.5:1 OR win rate > 57% to break even
3. **All Signals Were BUY**: Strategy had bullish bias during test period
4. **Timing**: Asian session (02:30-04:30 UTC) typically has low volatility

### Current Configuration
```json
{
  "enabled_strategies": ["MomentumScalp", "MACDTrend"],
  "MACDTrend": {"macd_fast": 8, "macd_slow": 17, "ema_trend": 100},
  "MomentumScalp": {"momentum_period": 8, "momentum_threshold": 1.5},
  "global": {"sl_mult": 2.0, "tp_mult": 3.0}
}
```

### Recommendations

1. **Increase TP multiplier**: Try tp_mult=4.0 or 5.0 to improve R:R
2. **Wait for London Session**: 08:00 UTC has better trends and volatility
3. **Add directional filter**: If strategy is biased (all BUY), may need trend confirmation
4. **Consider reducing SL**: sl_mult=1.5 gives tighter stops but needs higher win rate

---

## Night Session Summary

| Test | Strategy | Trades | Win Rate | P/L |
|------|----------|--------|----------|-----|
| 1A | MACDTrend (sl=1.5, tp=3.0) | 2 | 0% | -$2.65 |
| 1B | MACDTrend (sl=2.5, tp=4.0) | 2 | 0% | -$3.66 |
| 2 | TrendMA | 0 | - | $0 |
| 3 | MomentumScalp | 0 | - | $0 |
| **4** | **Multi-Strategy** | **5** | **40%** | -$2.33 |

**Total Night Session Loss**: ~$8.64
**Total Account Loss**: $1,512.23 (1.51%)

---

## Account Status
- Starting Balance: $100,000
- Current Balance: $98,487.77
- Available Margin: $98,487.77

---

## Next Steps

1. **London Session Test** (08:00+ UTC)
   - Higher volatility expected
   - Better trending conditions

2. **Parameter Optimization**
   - Test tp_mult=4.0 or 5.0
   - Test tighter sl_mult=1.5 with higher win rate strategy

3. **Alternative Strategies**
   - Try VolatilityRegime for breakouts
   - Try RSIReversion in ranging markets

---
*Night testing session complete: 2025-12-31 04:25 UTC*
