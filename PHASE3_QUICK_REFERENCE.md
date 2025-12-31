# Phase 3 Quick Reference Card

**For detailed information, see:** `PHASE3_IMPLEMENTATION_PLAN.md`

---

## 1. Kelly Criterion Position Sizing (7 hours)

**Formula:** `f* = (p*W - L) / W`

**File:** `/oanda_bot/risk/kelly.py`

**Key Functions:**
```python
kelly.calculate_kelly_fraction(win_rate, avg_win, avg_loss)
kelly.get_position_size(strategy, equity, stop_distance)
kelly.update_strategy_stats(strategy, win, pnl)
```

**Config:**
```bash
USE_KELLY_SIZING=1
FRACTIONAL_KELLY=0.25
MAX_KELLY=0.5
MIN_KELLY_TRADES=30
```

**Test:**
```bash
pytest oanda_bot/tests/test_kelly.py
python -m oanda_bot.backtest --strategy MACDTrend --use-kelly
```

---

## 2. Dynamic Volatility Sizing (13 hours)

**Formula:** `adjusted_size = base_size / volatility_ratio`

**File:** `/oanda_bot/risk/volatility_sizing.py`

**Key Functions:**
```python
vol_sizer.update_atr(instrument, atr)
vol_sizer.get_volatility_ratio(instrument, current_atr)
vol_sizer.adjust_position_size(instrument, base_units, current_atr, price)
```

**Config:**
```bash
USE_VOLATILITY_SIZING=1
VOL_ATR_WINDOW=50
VOL_MIN_MULTIPLIER=0.25
VOL_MAX_MULTIPLIER=2.0
```

**Integration:**
```python
# In broker.place_risk_managed_order()
if vol_sizer and current_atr:
    units = vol_sizer.adjust_position_size(
        instrument, base_units, current_atr, price
    )
```

---

## 3. Multi-Timeframe Analysis (16 hours)

**Concept:** Check H4/D1 trends before taking M5/H1 trades

**File:** `/oanda_bot/analysis/multi_timeframe.py`

**Key Functions:**
```python
mtf.detect_htf_trend(instrument, timeframe)
mtf.should_allow_signal(instrument, signal)
mtf.get_trend_score(instrument)
```

**Config:**
```bash
USE_MTF_FILTER=1
MTF_TIMEFRAMES=H4,D1
MTF_REQUIRE_ALL=0
MTF_CACHE_TTL=900
```

**Integration:**
```python
# In handle_signal()
allowed, reason = mtf_analyzer.should_allow_signal(pair, signal)
if not allowed:
    logger.info(f"MTF rejected {signal} - {reason}")
    return
```

---

## 4. Walk-Forward Optimization (22 hours)

**Concept:** Train → Test → Roll forward (prevent overfitting)

**File:** `/oanda_bot/optimization/walk_forward.py`

**Key Functions:**
```python
wf = WalkForwardOptimizer(strategy_class, instrument, granularity)
results = wf.run_walk_forward()
wf.calculate_efficiency_ratio(results)
```

**CLI:**
```bash
python -m oanda_bot.run_walk_forward \
  --strategy MACDTrend \
  --instrument EUR_USD \
  --train-bars 1000 \
  --test-bars 250 \
  --step-bars 250
```

**Success Metric:** Efficiency ratio (test/train) > 0.5

---

## 5. Trade Attribution Analysis (15 hours)

**Concept:** Break down P&L by strategy/pair/regime/session

**File:** `/oanda_bot/analysis/attribution.py`

**Key Functions:**
```python
attr.log_trade(strategy, pair, side, entry_time, exit_time, pnl, regime)
attr.get_attribution_by_dimension('strategy')
attr.get_cross_attribution('strategy', 'regime')
attr.export_attribution_report('attribution.html')
```

**Config:**
```bash
USE_ATTRIBUTION=1
ATTRIBUTION_FILE=attribution_data.json
```

**Dashboard:**
```python
# In Streamlit app
show_attribution_analysis(attribution_analyzer)
```

---

## 6. LSTM Neural Networks (43 hours, OPTIONAL)

**Concept:** Predict next price direction using deep learning

**Files:**
- `/oanda_bot/ml/lstm_predictor.py`
- `/oanda_bot/ml/feature_engineering.py`
- `/oanda_bot/ml/model_trainer.py`

**Dependencies:**
```bash
pip install tensorflow scikit-learn keras
```

**Training:**
```bash
python -m oanda_bot.ml.model_trainer \
  --instrument EUR_USD \
  --granularity H1 \
  --epochs 50
```

**Usage:**
```python
lstm = LSTMPredictor()
lstm.load_model('models/EUR_USD_H1.h5')
signal = lstm.predict_direction(features)  # "BUY", "SELL", or None
```

**Success:** >60% directional accuracy (out-of-sample)

---

## 7. Reinforcement Learning (51 hours, OPTIONAL)

**Concept:** DQN agent learns optimal strategy selection

**Files:**
- `/oanda_bot/rl/trading_env.py`
- `/oanda_bot/rl/dqn_agent.py`
- `/oanda_bot/rl/train_dqn.py`

**Dependencies:**
```bash
pip install tensorflow gym stable-baselines3
```

**Training:**
```python
from oanda_bot.rl.train_dqn import train_dqn
agent, rewards = train_dqn(strategies, episodes=1000)
```

**Usage:**
```python
rl_selector = RLStrategySelector(all_strategies)
selected = rl_selector.select_strategy(market_state, strategy_performance)
signal = selected.next_signal(bars)
```

**Success:** Sharpe ratio > 2.5

---

## Environment Variables Reference

```bash
# Phase 3A: Foundation
USE_KELLY_SIZING=1
FRACTIONAL_KELLY=0.25
MAX_KELLY=0.5
MIN_KELLY_TRADES=30

USE_VOLATILITY_SIZING=1
VOL_ATR_WINDOW=50
VOL_MIN_MULTIPLIER=0.25
VOL_MAX_MULTIPLIER=2.0

USE_MTF_FILTER=1
MTF_TIMEFRAMES=H4,D1
MTF_REQUIRE_ALL=0
MTF_CACHE_TTL=900

USE_ATTRIBUTION=1
ATTRIBUTION_FILE=attribution_data.json

# Phase 3B: Advanced
# Walk-forward is offline tool (no runtime config)

# Phase 3C: ML (Optional)
USE_LSTM=0
LSTM_CONFIDENCE_THRESHOLD=0.6
LSTM_MODEL_PATH=oanda_bot/ml/models/

USE_RL_SELECTOR=0
RL_MODEL_PATH=oanda_bot/rl/models/dqn_strategy_selector.h5
```

---

## Testing Commands

### Unit Tests
```bash
# Test Kelly
pytest oanda_bot/tests/test_kelly.py -v

# Test Volatility Sizing
pytest oanda_bot/tests/test_volatility_sizing.py -v

# Test Multi-Timeframe
pytest oanda_bot/tests/test_multi_timeframe.py -v

# Test Attribution
pytest oanda_bot/tests/test_attribution.py -v

# Run all Phase 3 tests
pytest oanda_bot/tests/test_phase3*.py -v
```

### Backtest Validation
```bash
# Before Phase 3 (baseline)
python -m oanda_bot.backtest \
  --strategy MACDTrend \
  --instrument EUR_USD \
  --granularity H1 \
  --count 2000 > baseline.json

# After Phase 3 (with features)
python -m oanda_bot.backtest \
  --strategy MACDTrend \
  --instrument EUR_USD \
  --granularity H1 \
  --count 2000 \
  --use-kelly \
  --use-volatility \
  --use-mtf > phase3.json

# Compare
python -m oanda_bot.compare_results baseline.json phase3.json
```

### Live Testing
```bash
# Paper trading (practice account)
OANDA_ENV=practice python -m oanda_bot.main

# Monitor logs
tail -f live_trading.log | grep -E "kelly|volatility|mtf|attribution"

# Check metrics
curl http://localhost:8000/health
curl http://localhost:8000/metrics  # If metrics endpoint added
```

---

## Integration Checklist

### Feature 1: Kelly Criterion
- [ ] Create `/oanda_bot/risk/kelly.py`
- [ ] Modify `broker.place_risk_managed_order()` to use Kelly
- [ ] Add callback to `BaseStrategy.update_trade_result()`
- [ ] Add config to `.env`
- [ ] Write unit tests
- [ ] Run backtest comparison
- [ ] Paper trade for 1 week

### Feature 2: Volatility Sizing
- [ ] Create `/oanda_bot/risk/volatility_sizing.py`
- [ ] Update `broker.place_risk_managed_order()` for vol adjustment
- [ ] Track ATR in `main.py` bar handler
- [ ] Add config to `.env`
- [ ] Write unit tests
- [ ] Backtest on volatile period (March 2020)
- [ ] Verify size inversely correlates with ATR

### Feature 3: Multi-Timeframe
- [ ] Create `/oanda_bot/analysis/multi_timeframe.py`
- [ ] Add filter to `handle_signal()` in `main.py`
- [ ] Implement caching (15-min TTL)
- [ ] Add dashboard page for HTF trends
- [ ] Add config to `.env`
- [ ] Write unit tests
- [ ] Backtest with/without filter
- [ ] Verify win rate improvement

### Feature 4: Walk-Forward
- [ ] Create `/oanda_bot/optimization/walk_forward.py`
- [ ] Create CLI script
- [ ] Add visualization (equity curves)
- [ ] Run on EUR_USD H1
- [ ] Calculate efficiency ratio
- [ ] Verify ratio > 0.5

### Feature 5: Attribution
- [ ] Create `/oanda_bot/analysis/attribution.py`
- [ ] Add trade logging to position close logic
- [ ] Create Streamlit dashboard page
- [ ] Add export functionality
- [ ] Test with historical trades
- [ ] Verify totals match overall P&L

---

## Rollback Procedures

### Instant Rollback (< 1 minute)
```bash
# Disable all Phase 3 features
USE_KELLY_SIZING=0
USE_VOLATILITY_SIZING=0
USE_MTF_FILTER=0
USE_ATTRIBUTION=0
USE_LSTM=0
USE_RL_SELECTOR=0

# Restart bot
docker-compose restart bot
# OR
systemctl restart oanda-bot
```

### Partial Rollback
```bash
# Disable just one feature
USE_KELLY_SIZING=0  # Revert to fixed 2% risk

# No code changes needed
```

### Full Rollback to Phase 2
```bash
# Git rollback (if needed)
git checkout main
git pull origin phase2

# Rebuild
docker-compose down
docker-compose build
docker-compose up -d
```

---

## Performance Benchmarks

### Expected Results (After Phase 3A)

**Baseline (Phase 2):**
- CAGR: 15%
- Sharpe: 1.2
- Max Drawdown: 12%
- Win Rate: 52%

**Phase 3A (Features 1-3):**
- CAGR: 17-20% (+2-5%)
- Sharpe: 1.6-1.8 (+0.4-0.6)
- Max Drawdown: 9-10% (-2-3%)
- Win Rate: 57-60% (+5-8%)

**If metrics are worse:** Disable features one by one to identify issue

---

## Troubleshooting

### Kelly Sizing Issues
**Problem:** Position sizes too large
**Solution:**
- Reduce `FRACTIONAL_KELLY` (try 0.15)
- Lower `MAX_KELLY` cap (try 0.3)
- Increase `MIN_KELLY_TRADES` (try 50)

**Problem:** Not using Kelly (falling back to fixed)
**Solution:**
- Check strategy has >30 trades
- Verify statistics are updating
- Check logs for Kelly calculations

### Volatility Sizing Issues
**Problem:** Sizes not adjusting
**Solution:**
- Verify ATR is being passed to broker
- Check `atr_history` is populating
- Ensure `USE_VOLATILITY_SIZING=1`

**Problem:** Sizes too small in low volatility
**Solution:**
- Lower `VOL_MIN_MULTIPLIER` (try 0.5)
- Increase `VOL_MAX_MULTIPLIER` (try 3.0)

### Multi-Timeframe Issues
**Problem:** Rejecting too many trades
**Solution:**
- Set `MTF_REQUIRE_ALL=0` (majority vote)
- Reduce `MTF_TIMEFRAMES` to just H4
- Lower trend strength threshold

**Problem:** Cache not working (too many API calls)
**Solution:**
- Check cache TTL (`MTF_CACHE_TTL=900`)
- Verify cache keys are correct
- Add logging to cache hits/misses

---

## Monitoring Metrics

### Key Performance Indicators

**Daily:**
- Total P&L vs baseline
- Sharpe ratio (rolling 30 days)
- Max drawdown
- Win rate

**Weekly:**
- Strategy attribution (top performers)
- Pair attribution (best/worst)
- Position size distribution
- Kelly fractions per strategy

**Monthly:**
- Walk-forward efficiency ratio
- LSTM accuracy (if enabled)
- RL strategy selection patterns (if enabled)
- Parameter drift analysis

### Alert Thresholds

**Critical (Immediate Action):**
- Sharpe ratio < 0.8 (baseline was 1.2)
- Max drawdown > 15% (baseline was 12%)
- Win rate < 47% (baseline was 52%)

**Warning (Review in 24h):**
- Sharpe ratio < 1.0
- Max drawdown > 13%
- Win rate < 50%

**Info (Monitor):**
- Any metric 10% worse than baseline
- Position sizes outside normal range
- Strategy selection concentration (RL)

---

## Support & Contacts

**Documentation:**
- Full Plan: `PHASE3_IMPLEMENTATION_PLAN.md`
- Summary: `PHASE3_SUMMARY.md`
- This Quick Ref: `PHASE3_QUICK_REFERENCE.md`

**Code Structure:**
```
oanda_bot/
├── risk/              # Features 1-2
├── analysis/          # Features 3, 5
├── optimization/      # Feature 4
├── ml/                # Feature 6 (optional)
└── rl/                # Feature 7 (optional)
```

**Key Contacts:**
- Architecture Questions → See `ARCHITECTURE.md`
- Deployment Issues → See `DEPLOYMENT.md`
- API Issues → Check OANDA docs
- ML/RL Questions → Consult ML specialist

---

## Final Checklist Before Going Live

### Pre-Deployment
- [ ] All unit tests passing
- [ ] Backtest shows improvement
- [ ] Paper trading successful (1-2 weeks)
- [ ] Code reviewed and documented
- [ ] Environment variables configured
- [ ] Monitoring/alerts set up
- [ ] Rollback plan tested

### Gradual Rollout
- [ ] Week 1: Enable Kelly only
- [ ] Week 2: Add Volatility Sizing
- [ ] Week 3: Add Multi-Timeframe Filter
- [ ] Week 4: Enable Attribution
- [ ] Week 5+: Monitor and optimize

### Success Validation
- [ ] CAGR improved vs Phase 2
- [ ] Sharpe ratio improved
- [ ] Max drawdown reduced or stable
- [ ] Win rate improved
- [ ] No unexpected issues for 2+ weeks

**If all checks pass:** Full deployment approved
**If any check fails:** Debug, fix, and re-test before proceeding

---

**Remember:** Start with Features 1-3 (Phase 3A). They provide 80% of the benefit with 20% of the complexity!
