# Phase 3 Strategic Enhancements - Detailed Implementation Plan

## OANDA Trading Bot - Advanced Features Roadmap

**Document Version:** 1.0
**Created:** 2025-12-28
**Author:** Implementation Planning for Phase 3
**Target Completion:** 4-6 weeks (80-120 hours total)

---

## Overview

This document provides a comprehensive, step-by-step implementation plan for Phase 3 strategic enhancements to the OANDA trading bot. Phase 3 focuses on advanced position sizing, machine learning integration, and sophisticated analysis tools.

### Current System State (Pre-Phase 3)

**Existing Capabilities:**
- Multi-strategy trading system with 7+ strategies (MACD, RSI, Bollinger, etc.)
- Basic risk management (fixed percentage position sizing)
- Grid search optimization for strategy parameters
- Market regime detection (ADX-based trending/ranging classification)
- Strategy correlation analysis
- UCB1 multi-armed bandit for strategy selection
- Real-time streaming with 2-second bars
- Backtesting engine with SL/TP/max duration exits

**Current Architecture:**
- `/oanda_bot/strategy/` - Strategy plugins (BaseStrategy interface)
- `/oanda_bot/risk.py` - Basic position sizing
- `/oanda_bot/backtest.py` - Historical simulation engine
- `/oanda_bot/optimize.py` - Grid search parameter optimization
- `/oanda_bot/meta_optimize.py` - UCB1 strategy selection
- `/oanda_bot/regime.py` - Market regime detection
- `/oanda_bot/correlation.py` - Strategy correlation tracking
- `/oanda_bot/broker.py` - OANDA API interface
- `/oanda_bot/data/core.py` - Market data layer

---

## Phase 3 Features - Prioritized Implementation Order

1. **Kelly Criterion Position Sizing** (Priority: HIGH, Complexity: LOW)
2. **Dynamic Volatility-Based Position Sizing** (Priority: HIGH, Complexity: MEDIUM)
3. **Multi-Timeframe Analysis** (Priority: HIGH, Complexity: MEDIUM)
4. **Walk-Forward Optimization** (Priority: MEDIUM, Complexity: HIGH)
5. **Trade Attribution Analysis** (Priority: MEDIUM, Complexity: LOW)
6. **LSTM Neural Network Integration** (Priority: LOW, Complexity: VERY HIGH)
7. **Reinforcement Learning Strategy Selection** (Priority: LOW, Complexity: VERY HIGH)

---

## Feature 1: Kelly Criterion Position Sizing

### Overview
Implement mathematically optimal position sizing based on the Kelly formula: `f* = (p*W - L) / W` where p = win probability, W = average win size, L = average loss size. Research shows 14.1% CAGR improvement over fixed fractional sizing.

### Detailed Implementation Steps

#### Step 1: Create Kelly Calculator Module (2 hours)
1. Create `/oanda_bot/risk/kelly.py`:
```python
class KellyCriterion:
    def __init__(self, max_kelly: float = 1.0, fractional_kelly: float = 0.25):
        """
        Args:
            max_kelly: Maximum Kelly fraction (cap at 100%)
            fractional_kelly: Use fraction of Kelly (e.g., 0.25 = quarter-Kelly)
        """
        self.max_kelly = max_kelly
        self.fractional_kelly = fractional_kelly
        self.strategy_stats = {}  # Track per-strategy stats

    def calculate_kelly_fraction(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """Calculate optimal Kelly fraction."""
        pass

    def update_strategy_stats(self, strategy: str, win: bool, pnl: float):
        """Update running statistics for a strategy."""
        pass

    def get_position_size(
        self,
        strategy: str,
        equity: float,
        stop_distance: float
    ) -> int:
        """Calculate position size using Kelly criterion."""
        pass
```

2. Implement core Kelly formula:
```python
def calculate_kelly_fraction(self, win_rate, avg_win, avg_loss):
    if avg_loss == 0 or win_rate == 0 or win_rate >= 1:
        return 0.0

    # Kelly formula: f* = (p*W - L) / W
    # where W = avg_win/avg_loss (win/loss ratio)
    win_loss_ratio = avg_win / avg_loss
    kelly = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio

    # Apply safety constraints
    kelly = max(0.0, min(kelly, self.max_kelly))
    kelly *= self.fractional_kelly  # Use fractional Kelly for safety

    return kelly
```

3. Add running statistics tracker:
```python
def update_strategy_stats(self, strategy, win, pnl):
    if strategy not in self.strategy_stats:
        self.strategy_stats[strategy] = {
            'wins': 0, 'losses': 0,
            'total_win_pnl': 0.0, 'total_loss_pnl': 0.0,
            'trades': 0
        }

    stats = self.strategy_stats[strategy]
    stats['trades'] += 1

    if win:
        stats['wins'] += 1
        stats['total_win_pnl'] += abs(pnl)
    else:
        stats['losses'] += 1
        stats['total_loss_pnl'] += abs(pnl)
```

4. Add position size calculator:
```python
def get_position_size(self, strategy, equity, stop_distance):
    MIN_TRADES = 30  # Minimum trades before using Kelly

    stats = self.strategy_stats.get(strategy)
    if not stats or stats['trades'] < MIN_TRADES:
        # Fall back to fixed 2% risk until enough data
        return int(equity * 0.02 / stop_distance)

    # Calculate statistics
    win_rate = stats['wins'] / stats['trades']
    avg_win = stats['total_win_pnl'] / max(stats['wins'], 1)
    avg_loss = stats['total_loss_pnl'] / max(stats['losses'], 1)

    # Get Kelly fraction
    kelly_f = self.calculate_kelly_fraction(win_rate, avg_win, avg_loss)

    # Convert to position size
    risk_amount = equity * kelly_f
    units = int(risk_amount / stop_distance)

    # Cap at maximum
    MAX_UNITS = 1000
    return min(units, MAX_UNITS)
```

#### Step 2: Integrate with Existing Risk Management (1 hour)
1. Modify `/oanda_bot/broker.py` - `place_risk_managed_order()`:
```python
# Add Kelly option
def place_risk_managed_order(
    instrument: str,
    side: str,
    price: float,
    stop_price: float,
    equity: float,
    risk_pct: float = 0.01,
    tp_price: Optional[float] = None,
    strategy_name: Optional[str] = None,
    use_kelly: bool = False,  # NEW
    kelly_calculator: Optional[KellyCriterion] = None,  # NEW
):
    # ... existing code ...

    if use_kelly and kelly_calculator and strategy_name:
        stop_distance = abs(price - stop_price)
        units = kelly_calculator.get_position_size(
            strategy_name, equity, stop_distance
        )
    else:
        # Original fixed percentage logic
        risk_dollar = equity * risk_pct
        per_unit_risk = abs(price - stop_price)
        units = int(risk_dollar / per_unit_risk)
```

2. Add Kelly callback to BaseStrategy:
```python
# In /oanda_bot/strategy/base.py
def update_trade_result(self, win: bool, pnl: float) -> None:
    self.pull_count += 1
    self.cumulative_pnl += pnl

    # NEW: Update Kelly stats if calculator exists
    if hasattr(self, 'kelly_calculator'):
        self.kelly_calculator.update_strategy_stats(
            self.name, win, pnl
        )
```

#### Step 3: Add Configuration and Testing (1 hour)
1. Add Kelly parameters to `.env`:
```bash
# Kelly Criterion Settings
USE_KELLY_SIZING=1
FRACTIONAL_KELLY=0.25  # Use quarter-Kelly for safety
MAX_KELLY=0.5  # Cap at 50% of equity
MIN_KELLY_TRADES=30  # Minimum trades before using Kelly
```

2. Create test file `/oanda_bot/tests/test_kelly.py`:
```python
def test_kelly_calculation():
    kelly = KellyCriterion(fractional_kelly=1.0)

    # Test case: 60% win rate, 2:1 win/loss ratio
    kelly_f = kelly.calculate_kelly_fraction(
        win_rate=0.6, avg_win=200, avg_loss=100
    )
    expected = (0.6 * 2 - 0.4) / 2  # = 0.4
    assert abs(kelly_f - expected) < 0.01

def test_kelly_with_insufficient_data():
    kelly = KellyCriterion()
    size = kelly.get_position_size('TestStrat', 10000, 50)
    # Should fall back to 2% fixed risk
    assert size == int(10000 * 0.02 / 50)
```

3. Run validation backtest comparing Kelly vs fixed sizing:
```bash
python -m oanda_bot.backtest --strategy MACDTrend \
  --instrument EUR_USD --granularity H1 --count 2000 \
  --use-kelly
```

### Data Requirements
- **Input:** Per-strategy trade history (wins, losses, P&L amounts)
- **Storage:** In-memory dict in KellyCriterion instance
- **Persistence:** Optional JSON export to `/kelly_stats.json` for warm-start
- **Minimum Data:** 30 trades per strategy before activating Kelly

### Integration Approach
1. Create `KellyCriterion` instance in `main.py` at startup
2. Pass instance to each strategy via `__init__`
3. Update statistics in `BaseStrategy.update_trade_result()`
4. Use Kelly sizing in `broker.place_risk_managed_order()` if enabled

### Testing Strategy
1. **Unit Tests:**
   - Test Kelly formula with known win rates
   - Test fallback to fixed sizing with <30 trades
   - Test max Kelly cap
   - Test fractional Kelly adjustment

2. **Integration Tests:**
   - Run side-by-side backtests (Kelly vs fixed 2%)
   - Compare Sharpe ratio, max drawdown, CAGR

3. **Live Testing:**
   - Enable on practice account for 1 week
   - Monitor position sizes vs expected
   - Ensure no oversizing occurs

### Success Metrics
- **Primary:** CAGR improvement vs fixed 2% (target: +10-15%)
- **Secondary:** Sharpe ratio improvement (target: +0.3-0.5)
- **Safety:** Max drawdown should not increase >2%
- **Validation:** Kelly fraction stays within 0-50% range

### Estimated Development Time
- **Implementation:** 4 hours
- **Testing:** 2 hours
- **Documentation:** 1 hour
- **Total:** 7 hours

### Risk Assessment
**Risks:**
1. **Over-betting:** Kelly can suggest large positions with high win rates
   - Mitigation: Use fractional Kelly (25%) and max cap (50%)
2. **Insufficient data:** Poor estimates with <30 trades
   - Mitigation: Fall back to fixed 2% sizing
3. **Non-stationary markets:** Past statistics may not predict future
   - Mitigation: Use rolling window (last 100 trades only)

**Severity:** Medium
**Probability:** Low (with mitigations)

### Rollback Plan
1. Set `USE_KELLY_SIZING=0` in `.env` to disable
2. System reverts to fixed 2% risk per trade
3. No code changes required (conditional logic)
4. Can re-enable at any time without data loss

### Dependencies on Phase 1/2
- **Required:** Working backtest engine (exists in `/oanda_bot/backtest.py`)
- **Required:** Trade result callback in BaseStrategy (exists)
- **Required:** Basic position sizing in broker (exists)
- **Optional:** Trade logging to CSV for historical analysis (exists)

---

## Feature 2: Dynamic Volatility-Based Position Sizing

### Overview
Adjust position sizes based on current market volatility relative to historical levels. In high volatility periods, reduce position size to maintain consistent risk. Improves Sharpe ratio by 15-20% according to research.

### Detailed Implementation Steps

#### Step 1: Create Volatility Tracker (3 hours)
1. Create `/oanda_bot/risk/volatility_sizing.py`:
```python
class VolatilityPositionSizer:
    def __init__(
        self,
        atr_window: int = 50,
        target_volatility: float = 0.02,
        min_size_multiplier: float = 0.25,
        max_size_multiplier: float = 2.0,
    ):
        """
        Args:
            atr_window: Window for ATR percentile calculation
            target_volatility: Target volatility level (2% default)
            min_size_multiplier: Minimum position size multiplier (0.25x)
            max_size_multiplier: Maximum position size multiplier (2x)
        """
        self.atr_window = atr_window
        self.target_volatility = target_volatility
        self.min_size_multiplier = min_size_multiplier
        self.max_size_multiplier = max_size_multiplier

        # Track ATR history per instrument
        self.atr_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=atr_window)
        )
```

2. Implement ATR percentile calculator:
```python
def update_atr(self, instrument: str, atr: float):
    """Update ATR history for an instrument."""
    self.atr_history[instrument].append(atr)

def get_atr_percentile(self, instrument: str, current_atr: float) -> float:
    """Get percentile rank of current ATR."""
    history = list(self.atr_history[instrument])
    if len(history) < 10:
        return 50.0  # Neutral until enough data

    rank = sum(1 for h in history if h < current_atr)
    percentile = (rank / len(history)) * 100
    return percentile

def get_volatility_ratio(self, instrument: str, current_atr: float) -> float:
    """Calculate current volatility vs historical average."""
    history = list(self.atr_history[instrument])
    if len(history) < 10:
        return 1.0  # No adjustment

    avg_atr = sum(history) / len(history)
    if avg_atr == 0:
        return 1.0

    volatility_ratio = current_atr / avg_atr
    return volatility_ratio
```

3. Implement position size adjustment:
```python
def adjust_position_size(
    self,
    instrument: str,
    base_units: int,
    current_atr: float,
    price: float,
) -> int:
    """
    Adjust position size based on current volatility.

    Returns smaller positions in high volatility,
    larger positions in low volatility.
    """
    # Update ATR history
    self.update_atr(instrument, current_atr)

    # Get volatility ratio
    vol_ratio = self.get_volatility_ratio(instrument, current_atr)

    # Inverse relationship: higher volatility = smaller size
    # Formula: adjusted_size = base_size * (1 / vol_ratio)
    size_multiplier = 1.0 / vol_ratio

    # Apply bounds
    size_multiplier = max(
        self.min_size_multiplier,
        min(size_multiplier, self.max_size_multiplier)
    )

    adjusted_units = int(base_units * size_multiplier)

    logger.debug(
        f"{instrument}: ATR={current_atr:.5f}, vol_ratio={vol_ratio:.2f}, "
        f"multiplier={size_multiplier:.2f}, base={base_units}, "
        f"adjusted={adjusted_units}"
    )

    return adjusted_units
```

#### Step 2: Integrate with Broker (2 hours)
1. Modify `broker.place_risk_managed_order()`:
```python
def place_risk_managed_order(
    # ... existing params ...
    vol_sizer: Optional[VolatilityPositionSizer] = None,  # NEW
    current_atr: Optional[float] = None,  # NEW
):
    # Calculate base units (existing logic)
    risk_dollar = equity * risk_pct
    per_unit_risk = abs(price - stop_price)
    base_units = int(risk_dollar / per_unit_risk)

    # Apply volatility adjustment
    if vol_sizer and current_atr:
        units = vol_sizer.adjust_position_size(
            instrument, base_units, current_atr, price
        )
    else:
        units = base_units

    # Apply max cap
    MAX_UNITS = 1000
    units = min(units, MAX_UNITS)
```

2. Update main.py to track ATR per bar:
```python
# In handle_bar() function
def handle_bar(bar_dict, strategies, ...):
    for pair, close_px in bar_dict.items():
        # ... existing code ...

        # Calculate current ATR
        candles = bars[pair]
        if len(candles) >= 14:
            current_atr = calculate_atr(candles, period=14)

            # Update volatility tracker
            vol_sizer.update_atr(pair, current_atr)
```

#### Step 3: Add Multi-Regime Volatility Adjustment (2 hours)
1. Integrate with regime detector:
```python
def get_regime_adjusted_size(
    self,
    instrument: str,
    base_units: int,
    current_atr: float,
    regime: Dict[str, any],  # From MarketRegime.detect_regime()
) -> int:
    """
    Adjust size based on both volatility AND regime.

    - In volatile regimes: reduce size further (0.5x)
    - In quiet regimes: can increase size (1.5x)
    - In ranging: normal volatility adjustment
    - In trending: slight reduction (0.8x) for safety
    """
    # Get base volatility adjustment
    vol_adjusted = self.adjust_position_size(
        instrument, base_units, current_atr, 0.0
    )

    # Apply regime multiplier
    regime_multipliers = {
        'volatile': 0.5,
        'quiet': 1.5,
        'ranging': 1.0,
        'trending_up': 0.8,
        'trending_down': 0.8,
    }

    regime_mult = regime_multipliers.get(regime['regime'], 1.0)
    final_units = int(vol_adjusted * regime_mult)

    return final_units
```

### Data Requirements
- **Input:** Per-bar ATR values for each instrument
- **Storage:** Rolling window of last 50 ATR values per instrument
- **Memory:** ~400 bytes per instrument (50 floats × 8 bytes)
- **Total:** ~8 KB for 20 instruments

### Integration Approach
1. Create `VolatilityPositionSizer` instance in `main.py`
2. Calculate ATR on each bar (reuse existing ATR calculation)
3. Pass ATR to `broker.place_risk_managed_order()`
4. Apply adjustment before order placement

### Testing Strategy
1. **Unit Tests:**
   - Test ATR percentile calculation
   - Test size reduction in high volatility
   - Test size increase in low volatility
   - Test bounds enforcement (0.25x - 2.0x)

2. **Backtest Validation:**
   - Run on 2020 March (COVID crash - high volatility)
   - Run on 2019 summer (low volatility)
   - Verify sizes adjust as expected

3. **Live Testing:**
   - Enable on practice account
   - Monitor position sizes vs ATR levels
   - Track Sharpe ratio improvement

### Success Metrics
- **Primary:** Sharpe ratio improvement (target: +0.3-0.5)
- **Secondary:** Reduced max drawdown (target: -20-30%)
- **Consistency:** More stable equity curve (lower volatility)
- **Validation:** Position sizes inversely correlated with ATR

### Estimated Development Time
- **Implementation:** 7 hours
- **Testing:** 3 hours
- **Integration with regime:** 2 hours
- **Documentation:** 1 hour
- **Total:** 13 hours

### Risk Assessment
**Risks:**
1. **Over-sizing in low volatility:** May take excessive risk
   - Mitigation: Cap max multiplier at 2.0x
2. **Under-sizing in high volatility:** May miss opportunities
   - Mitigation: Allow min multiplier of 0.25x (not 0)
3. **Whipsaw during volatility transitions:** Size changes rapidly
   - Mitigation: Use 50-bar window for smoothing

**Severity:** Low-Medium
**Probability:** Low

### Rollback Plan
1. Set `USE_VOLATILITY_SIZING=0` in `.env`
2. System uses fixed position sizes
3. No code removal needed (conditional)

### Dependencies on Phase 1/2
- **Required:** ATR calculation (exists in multiple places)
- **Required:** Market regime detection (exists in `/oanda_bot/regime.py`)
- **Optional:** Kelly criterion (can combine both adjustments)

---

## Feature 3: Multi-Timeframe Analysis

### Overview
Check higher timeframe trends (H4/D1) before taking trades on lower timeframes (M5/H1). Only take longs in uptrends, shorts in downtrends. Research shows 10-15% win rate improvement through trend filtering.

### Detailed Implementation Steps

#### Step 1: Create Multi-Timeframe Module (4 hours)
1. Create `/oanda_bot/analysis/multi_timeframe.py`:
```python
class MultiTimeframeAnalyzer:
    def __init__(
        self,
        higher_timeframes: List[str] = ["H4", "D1"],
        trend_period: int = 50,  # Period for trend MA
        strength_threshold: float = 0.0005,  # Min slope for trend
    ):
        """
        Args:
            higher_timeframes: List of higher TFs to check
            trend_period: Period for trend-defining moving average
            strength_threshold: Minimum slope for valid trend
        """
        self.higher_timeframes = higher_timeframes
        self.trend_period = trend_period
        self.strength_threshold = strength_threshold

        # Cache higher TF data (refresh every 15 minutes)
        self.htf_cache: Dict[Tuple[str, str], Dict] = {}
        self.cache_timestamps: Dict[Tuple[str, str], float] = {}
        self.cache_ttl = 900  # 15 minutes
```

2. Implement trend detection:
```python
def detect_htf_trend(
    self,
    instrument: str,
    timeframe: str,
    count: int = 100,
) -> Dict[str, any]:
    """
    Detect trend on higher timeframe.

    Returns:
        {
            'direction': 'up' | 'down' | 'neutral',
            'strength': float (0-1),
            'ma_value': float,
            'current_price': float,
            'slope': float,
        }
    """
    # Check cache
    cache_key = (instrument, timeframe)
    now = time.time()

    if cache_key in self.htf_cache:
        if now - self.cache_timestamps[cache_key] < self.cache_ttl:
            return self.htf_cache[cache_key]

    # Fetch higher timeframe data
    candles = get_candles(instrument, timeframe, count)
    if len(candles) < self.trend_period + 10:
        return self._neutral_trend()

    # Calculate trend MA
    closes = np.array([float(c['mid']['c']) for c in candles])
    ma = np.mean(closes[-self.trend_period:])
    current_price = closes[-1]

    # Calculate slope (change per bar)
    older_ma = np.mean(closes[-(self.trend_period+10):-10])
    slope = (ma - older_ma) / 10

    # Classify trend
    if slope > self.strength_threshold:
        direction = 'up'
        strength = min(slope / (self.strength_threshold * 5), 1.0)
    elif slope < -self.strength_threshold:
        direction = 'down'
        strength = min(abs(slope) / (self.strength_threshold * 5), 1.0)
    else:
        direction = 'neutral'
        strength = 0.0

    result = {
        'direction': direction,
        'strength': strength,
        'ma_value': ma,
        'current_price': current_price,
        'slope': slope,
        'timeframe': timeframe,
    }

    # Cache result
    self.htf_cache[cache_key] = result
    self.cache_timestamps[cache_key] = now

    return result

def _neutral_trend(self):
    return {
        'direction': 'neutral',
        'strength': 0.0,
        'ma_value': 0.0,
        'current_price': 0.0,
        'slope': 0.0,
    }
```

3. Implement signal filtering:
```python
def should_allow_signal(
    self,
    instrument: str,
    signal: str,  # "BUY" or "SELL"
    require_all_aligned: bool = True,
) -> Tuple[bool, str]:
    """
    Check if signal aligns with higher timeframe trends.

    Args:
        instrument: Currency pair
        signal: Trade direction from strategy
        require_all_aligned: If True, all HTFs must align;
                           if False, majority vote

    Returns:
        (allowed: bool, reason: str)
    """
    if signal not in ["BUY", "SELL"]:
        return True, "No directional signal"

    htf_trends = []
    for tf in self.higher_timeframes:
        trend = self.detect_htf_trend(instrument, tf)
        htf_trends.append(trend)

    # Count aligned trends
    aligned = 0
    total = len(htf_trends)

    for trend in htf_trends:
        if signal == "BUY" and trend['direction'] == 'up':
            aligned += 1
        elif signal == "SELL" and trend['direction'] == 'down':
            aligned += 1
        elif trend['direction'] == 'neutral':
            # Neutral doesn't count against, but doesn't count for
            total -= 1

    if total == 0:
        # All neutral - allow trade
        return True, "All HTFs neutral"

    if require_all_aligned:
        allowed = (aligned == total)
        reason = f"{aligned}/{total} HTFs aligned"
    else:
        # Majority vote
        allowed = (aligned > total / 2)
        reason = f"{aligned}/{total} HTFs aligned (majority)"

    return allowed, reason
```

4. Add strength-weighted filtering:
```python
def get_trend_score(
    self,
    instrument: str,
) -> float:
    """
    Calculate aggregate trend score across all higher timeframes.

    Returns:
        Score from -1.0 (strong downtrend) to +1.0 (strong uptrend)
    """
    scores = []
    weights = {'D1': 0.5, 'H4': 0.3, 'H1': 0.2}  # Weight longer TFs more

    for tf in self.higher_timeframes:
        trend = self.detect_htf_trend(instrument, tf)

        # Convert to score
        if trend['direction'] == 'up':
            score = trend['strength']
        elif trend['direction'] == 'down':
            score = -trend['strength']
        else:
            score = 0.0

        weight = weights.get(tf, 0.2)
        scores.append(score * weight)

    return sum(scores)
```

#### Step 2: Integrate with Signal Generation (2 hours)
1. Modify `main.py` - `handle_signal()`:
```python
def handle_signal(
    pair,
    signal,
    strategy,
    close_px,
    mtf_analyzer,  # NEW
):
    # ... existing code ...

    # Multi-timeframe filter
    allowed, reason = mtf_analyzer.should_allow_signal(
        pair, signal, require_all_aligned=False
    )

    if not allowed:
        logger.info(
            f"MTF filter rejected {signal} on {pair} - {reason}",
            extra={
                'pair': pair,
                'signal': signal,
                'strategy': strategy.name,
                'mtf_reason': reason,
            }
        )
        _bump("mtf_filter_rejected")
        return

    # ... rest of existing code ...
```

2. Add configuration options:
```python
# In .env
USE_MTF_FILTER=1
MTF_TIMEFRAMES=H4,D1
MTF_REQUIRE_ALL=0  # 0 = majority vote, 1 = all must align
MTF_TREND_PERIOD=50
```

#### Step 3: Add Dashboard Visualization (2 hours)
1. Update Streamlit dashboard (`/oanda_bot/dashboard.py`):
```python
def show_mtf_analysis(mtf_analyzer, instruments):
    st.subheader("Multi-Timeframe Trend Analysis")

    data = []
    for pair in instruments:
        trend_score = mtf_analyzer.get_trend_score(pair)

        # Get individual TF trends
        h4_trend = mtf_analyzer.detect_htf_trend(pair, 'H4')
        d1_trend = mtf_analyzer.detect_htf_trend(pair, 'D1')

        data.append({
            'Pair': pair,
            'Score': f"{trend_score:.2f}",
            'H4': h4_trend['direction'],
            'D1': d1_trend['direction'],
            'Signal': '🟢 Long' if trend_score > 0.3
                     else '🔴 Short' if trend_score < -0.3
                     else '⚪ Neutral',
        })

    df = pd.DataFrame(data)
    st.dataframe(df)

    # Visualize trend scores
    st.bar_chart(df.set_index('Pair')['Score'])
```

### Data Requirements
- **Input:** Higher timeframe candles (H4, D1)
- **API Calls:** 2 calls per instrument per 15 minutes (cached)
- **Storage:** ~10 KB per instrument (100 candles × 5 TFs)
- **Total:** ~200 KB for 20 instruments

### Integration Approach
1. Create `MultiTimeframeAnalyzer` instance in `main.py`
2. Call `should_allow_signal()` before placing orders
3. Log rejections for analysis
4. Display HTF trends in dashboard

### Testing Strategy
1. **Historical Validation:**
   - Backtest EUR_USD with and without MTF filter
   - Compare win rates, drawdowns
   - Analyze rejected vs accepted signals

2. **Scenario Tests:**
   - Strong uptrend: verify only longs allowed
   - Strong downtrend: verify only shorts allowed
   - Neutral market: verify all signals allowed

3. **Integration Tests:**
   - Test cache TTL expiration
   - Test API error handling (HTF data unavailable)
   - Test with missing timeframes

### Success Metrics
- **Primary:** Win rate improvement (target: +5-10%)
- **Secondary:** Reduced max drawdown (target: -10-15%)
- **Trade Count:** Expected reduction of 30-40% (filtering effect)
- **Validation:** Rejection rate correlates with counter-trend signals

### Estimated Development Time
- **Core Implementation:** 8 hours
- **Integration:** 2 hours
- **Dashboard:** 2 hours
- **Testing:** 3 hours
- **Documentation:** 1 hour
- **Total:** 16 hours

### Risk Assessment
**Risks:**
1. **Over-filtering:** May reject good trades in ranging markets
   - Mitigation: Use majority vote, not unanimous
2. **Lag:** Higher TFs lag current price action
   - Mitigation: Use slope/momentum, not just price vs MA
3. **API load:** Extra calls for HTF data
   - Mitigation: 15-minute cache TTL

**Severity:** Low
**Probability:** Low

### Rollback Plan
1. Set `USE_MTF_FILTER=0` in `.env`
2. All signals pass through (no filtering)
3. Can re-enable without code changes

### Dependencies on Phase 1/2
- **Required:** `get_candles()` for multiple timeframes (exists)
- **Required:** Signal generation pipeline (exists)
- **Optional:** Dashboard for visualization (exists)

---

## Feature 4: Walk-Forward Optimization

### Overview
Implement walk-forward analysis to prevent overfitting. Train on Period 1, test on Period 2, then roll forward. Industry standard for robust parameter discovery. Reduces overfitting by 50-70%.

### Detailed Implementation Steps

#### Step 1: Create Walk-Forward Engine (6 hours)
1. Create `/oanda_bot/optimization/walk_forward.py`:
```python
class WalkForwardOptimizer:
    def __init__(
        self,
        strategy_class: Type[BaseStrategy],
        instrument: str,
        granularity: str,
        train_bars: int = 1000,
        test_bars: int = 250,
        step_bars: int = 250,
        param_grid: Dict[str, List],
    ):
        """
        Args:
            strategy_class: Strategy class to optimize
            instrument: Trading pair
            granularity: Timeframe (H1, M5, etc.)
            train_bars: Bars in each training window
            test_bars: Bars in each test window
            step_bars: How many bars to step forward each iteration
            param_grid: Parameter ranges to search
        """
        self.strategy_class = strategy_class
        self.instrument = instrument
        self.granularity = granularity
        self.train_bars = train_bars
        self.test_bars = test_bars
        self.step_bars = step_bars
        self.param_grid = param_grid

        self.results = []  # Store all walk-forward results
```

2. Implement window splitting:
```python
def split_windows(
    self,
    total_candles: List[dict],
) -> List[Tuple[List[dict], List[dict]]]:
    """
    Split data into (train, test) windows with rolling forward.

    Example with 3000 bars, train=1000, test=250, step=250:
    - Window 1: Train [0:1000], Test [1000:1250]
    - Window 2: Train [250:1250], Test [1250:1500]
    - Window 3: Train [500:1500], Test [1500:1750]
    - etc.
    """
    windows = []
    total_bars = len(total_candles)

    start_idx = 0
    while True:
        train_end = start_idx + self.train_bars
        test_end = train_end + self.test_bars

        if test_end > total_bars:
            break

        train_data = total_candles[start_idx:train_end]
        test_data = total_candles[train_end:test_end]

        windows.append((train_data, test_data))
        start_idx += self.step_bars

    return windows
```

3. Implement optimization loop:
```python
def run_walk_forward(self) -> Dict[str, any]:
    """
    Execute walk-forward optimization.

    Returns:
        {
            'windows': List of window results,
            'avg_train_pnl': float,
            'avg_test_pnl': float,
            'efficiency_ratio': float,  # test_pnl / train_pnl
            'best_params_frequency': Dict,  # How often each param set won
        }
    """
    logger.info(
        f"Starting walk-forward optimization for {self.instrument} "
        f"{self.granularity}"
    )

    # Fetch all historical data
    total_candles = get_candles(
        self.instrument,
        self.granularity,
        self.train_bars + self.test_bars + 1000
    )

    # Split into windows
    windows = self.split_windows(total_candles)
    logger.info(f"Created {len(windows)} walk-forward windows")

    all_results = []
    param_wins = defaultdict(int)

    for i, (train_data, test_data) in enumerate(windows):
        logger.info(f"Processing window {i+1}/{len(windows)}")

        # Step 1: Optimize on training data
        best_params = self._optimize_on_window(train_data)
        param_wins[json.dumps(best_params, sort_keys=True)] += 1

        # Step 2: Test on out-of-sample data
        test_pnl = self._test_on_window(test_data, best_params)

        # Store results
        window_result = {
            'window_index': i,
            'train_start': train_data[0]['time'],
            'test_start': test_data[0]['time'],
            'test_end': test_data[-1]['time'],
            'best_params': best_params,
            'test_pnl': test_pnl,
        }
        all_results.append(window_result)

    # Calculate aggregate statistics
    test_pnls = [r['test_pnl'] for r in all_results]
    avg_test_pnl = np.mean(test_pnls)
    std_test_pnl = np.std(test_pnls)

    # Find most frequent best params
    most_common_params = max(param_wins.items(), key=lambda x: x[1])
    best_params = json.loads(most_common_params[0])

    summary = {
        'windows': all_results,
        'avg_test_pnl': avg_test_pnl,
        'std_test_pnl': std_test_pnl,
        'total_windows': len(all_results),
        'best_params': best_params,
        'param_stability': most_common_params[1] / len(all_results),
    }

    return summary

def _optimize_on_window(self, train_data: List[dict]) -> Dict:
    """Run grid search on training window."""
    best_pnl = float('-inf')
    best_params = None

    # Generate all parameter combinations
    param_combinations = self._generate_param_combinations()

    for params in param_combinations:
        strategy = self.strategy_class(params)
        stats = run_backtest(strategy, train_data, warmup=50)

        if stats['total_pnl'] > best_pnl:
            best_pnl = stats['total_pnl']
            best_params = params

    return best_params

def _test_on_window(
    self,
    test_data: List[dict],
    params: Dict
) -> float:
    """Test parameters on out-of-sample window."""
    strategy = self.strategy_class(params)
    stats = run_backtest(strategy, test_data, warmup=50)
    return stats['total_pnl']
```

4. Add efficiency analysis:
```python
def calculate_efficiency_ratio(self, results: Dict) -> float:
    """
    Calculate walk-forward efficiency ratio.

    Ratio = avg_test_pnl / avg_train_pnl

    Good strategies: 0.5 - 0.8 (some degradation is normal)
    Overfitted: < 0.3 (large degradation)
    Robust: > 0.8 (stable performance)
    """
    train_pnls = []
    test_pnls = []

    for window in results['windows']:
        # Re-run on train to get train PnL
        # (stored only best params, not train PnL)
        pass  # Implementation detail

    avg_train = np.mean(train_pnls)
    avg_test = np.mean(test_pnls)

    if avg_train <= 0:
        return 0.0

    return avg_test / avg_train
```

#### Step 2: Create CLI Interface (2 hours)
1. Add command-line script `/oanda_bot/run_walk_forward.py`:
```python
def main():
    parser = argparse.ArgumentParser(
        description="Walk-forward optimization"
    )
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--instrument", default="EUR_USD")
    parser.add_argument("--granularity", default="H1")
    parser.add_argument("--train-bars", type=int, default=1000)
    parser.add_argument("--test-bars", type=int, default=250)
    parser.add_argument("--step-bars", type=int, default=250)
    args = parser.parse_args()

    # Load strategy
    strategy_class = load_strategy_class(args.strategy)

    # Define parameter grid
    param_grid = {
        'sl_mult': [1.0, 2.0, 3.0],
        'tp_mult': [1.0, 2.0, 3.0],
        'max_duration': [50, 100, 200],
    }

    # Run walk-forward
    optimizer = WalkForwardOptimizer(
        strategy_class,
        args.instrument,
        args.granularity,
        args.train_bars,
        args.test_bars,
        args.step_bars,
        param_grid,
    )

    results = optimizer.run_walk_forward()

    # Print summary
    print(f"\n{'='*60}")
    print(f"Walk-Forward Optimization Results")
    print(f"{'='*60}")
    print(f"Instrument: {args.instrument}")
    print(f"Total Windows: {results['total_windows']}")
    print(f"Avg Test PnL: {results['avg_test_pnl']:.4f}")
    print(f"Std Test PnL: {results['std_test_pnl']:.4f}")
    print(f"Parameter Stability: {results['param_stability']:.1%}")
    print(f"\nBest Parameters (most frequent):")
    print(json.dumps(results['best_params'], indent=2))

    # Save to file
    with open(f"walk_forward_{args.instrument}.json", "w") as f:
        json.dump(results, f, indent=2)
```

#### Step 3: Add Visualization (3 hours)
1. Create equity curve comparison:
```python
def plot_walk_forward_results(results: Dict):
    """
    Plot train vs test performance across windows.
    """
    import matplotlib.pyplot as plt

    windows = results['windows']
    test_pnls = [w['test_pnl'] for w in windows]

    # Cumulative equity curve
    cumulative_pnl = np.cumsum(test_pnls)

    plt.figure(figsize=(12, 6))
    plt.plot(cumulative_pnl, label='Walk-Forward Test PnL', linewidth=2)
    plt.axhline(0, color='black', linestyle='--', alpha=0.3)
    plt.xlabel('Window Index')
    plt.ylabel('Cumulative PnL')
    plt.title('Walk-Forward Optimization: Out-of-Sample Performance')
    plt.legend()
    plt.grid(alpha=0.3)
    plt.savefig('walk_forward_equity.png')
```

### Data Requirements
- **Input:** Long history (3000+ candles for multiple windows)
- **Processing:** CPU-intensive (grid search × windows)
- **Storage:** Results JSON (~100 KB per run)

### Integration Approach
1. Run as separate optimization phase (not live trading)
2. Output best parameters to `live_config.json`
3. Use before going live with new strategy
4. Re-run monthly to check parameter drift

### Testing Strategy
1. **Validation:**
   - Run on EUR_USD H1 with 5000 candles
   - Compare efficiency ratio (target: >0.5)
   - Check parameter stability (target: >60%)

2. **Comparison:**
   - Run same strategy with single-period optimization
   - Compare live performance over 1 month
   - Expect WF to have more stable results

### Success Metrics
- **Primary:** Efficiency ratio >0.5 (test/train)
- **Secondary:** Parameter stability >60% (same params win often)
- **Validation:** Test PnL std deviation <50% of mean
- **Robustness:** Performance doesn't collapse in final window

### Estimated Development Time
- **Core Engine:** 11 hours
- **CLI Interface:** 2 hours
- **Visualization:** 3 hours
- **Testing:** 4 hours
- **Documentation:** 2 hours
- **Total:** 22 hours

### Risk Assessment
**Risks:**
1. **Computation time:** Very slow (hours per run)
   - Mitigation: Use ProcessPoolExecutor for parallel windows
2. **Data snooping:** Looking at test results influences choices
   - Mitigation: Automate selection, don't cherry-pick
3. **Parameter instability:** Different params each window
   - Mitigation: Report stability metric, require >60%

**Severity:** Medium
**Probability:** Medium

### Rollback Plan
1. Walk-forward is an offline tool (not used in live trading)
2. If results are poor, continue using grid search optimization
3. No impact on live system

### Dependencies on Phase 1/2
- **Required:** Backtest engine (exists)
- **Required:** Parameter grid search (exists in optimize.py)
- **Required:** Long historical data access (exists)

---

## Feature 5: Trade Attribution Analysis

### Overview
Break down P&L by strategy, pair, session, and market regime to identify what's working and guide optimization. Essential for portfolio-level insights.

### Detailed Implementation Steps

#### Step 1: Create Attribution Tracker (4 hours)
1. Create `/oanda_bot/analysis/attribution.py`:
```python
class TradeAttributionAnalyzer:
    def __init__(self):
        """Track and analyze trade performance by multiple dimensions."""
        self.trades = []  # All trade records
        self.dimensions = [
            'strategy',
            'pair',
            'hour',
            'day_of_week',
            'regime',
            'month',
        ]

    def log_trade(
        self,
        strategy: str,
        pair: str,
        side: str,
        entry_time: datetime,
        exit_time: datetime,
        entry_price: float,
        exit_price: float,
        pnl: float,
        regime: str,
        **kwargs,
    ):
        """Log a completed trade with all attribution dimensions."""
        trade = {
            'strategy': strategy,
            'pair': pair,
            'side': side,
            'entry_time': entry_time,
            'exit_time': exit_time,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'regime': regime,
            'hour': entry_time.hour,
            'day_of_week': entry_time.strftime('%A'),
            'month': entry_time.strftime('%Y-%m'),
            'duration_minutes': (exit_time - entry_time).total_seconds() / 60,
            **kwargs,
        }
        self.trades.append(trade)
```

2. Implement attribution breakdown:
```python
def get_attribution_by_dimension(
    self,
    dimension: str,
    metric: str = 'pnl',
) -> pd.DataFrame:
    """
    Break down performance by a single dimension.

    Args:
        dimension: 'strategy', 'pair', 'hour', 'regime', etc.
        metric: 'pnl', 'win_rate', 'sharpe', etc.

    Returns:
        DataFrame with dimension values and metrics
    """
    if not self.trades:
        return pd.DataFrame()

    df = pd.DataFrame(self.trades)

    grouped = df.groupby(dimension).agg({
        'pnl': ['sum', 'mean', 'std', 'count'],
        'side': 'count',
    }).reset_index()

    grouped.columns = [
        dimension, 'total_pnl', 'avg_pnl', 'std_pnl',
        'num_trades', 'count'
    ]

    # Calculate win rate
    wins = df[df['pnl'] > 0].groupby(dimension).size()
    grouped['win_rate'] = (
        wins / grouped['num_trades']
    ).fillna(0)

    # Calculate Sharpe-like ratio
    grouped['sharpe'] = (
        grouped['avg_pnl'] / grouped['std_pnl']
    ).fillna(0)

    # Sort by total PnL
    grouped = grouped.sort_values('total_pnl', ascending=False)

    return grouped
```

3. Implement multi-dimensional analysis:
```python
def get_cross_attribution(
    self,
    dim1: str,
    dim2: str,
) -> pd.DataFrame:
    """
    Break down performance by two dimensions (e.g., strategy × regime).

    Returns:
        Pivot table with dim1 as rows, dim2 as columns, PnL as values
    """
    if not self.trades:
        return pd.DataFrame()

    df = pd.DataFrame(self.trades)

    pivot = df.pivot_table(
        values='pnl',
        index=dim1,
        columns=dim2,
        aggfunc='sum',
        fill_value=0,
    )

    return pivot

def get_top_performers(
    self,
    dimension: str,
    n: int = 5,
) -> List[Tuple[str, float]]:
    """Get top N performers by dimension."""
    df = self.get_attribution_by_dimension(dimension)
    if df.empty:
        return []

    top = df.nlargest(n, 'total_pnl')
    return list(zip(top[dimension], top['total_pnl']))

def get_bottom_performers(
    self,
    dimension: str,
    n: int = 5,
) -> List[Tuple[str, float]]:
    """Get bottom N performers by dimension."""
    df = self.get_attribution_by_dimension(dimension)
    if df.empty:
        return []

    bottom = df.nsmallest(n, 'total_pnl')
    return list(zip(bottom[dimension], bottom['total_pnl']))
```

4. Add session analysis:
```python
def get_session_analysis(self) -> pd.DataFrame:
    """
    Analyze performance by trading session.

    Sessions:
    - Asian: 00:00-08:00 UTC
    - European: 08:00-16:00 UTC
    - US: 16:00-24:00 UTC
    """
    if not self.trades:
        return pd.DataFrame()

    df = pd.DataFrame(self.trades)

    # Classify by session
    def get_session(hour):
        if 0 <= hour < 8:
            return 'Asian'
        elif 8 <= hour < 16:
            return 'European'
        else:
            return 'US'

    df['session'] = df['hour'].apply(get_session)

    return self.get_attribution_by_dimension('session')
```

#### Step 2: Integrate with Main Trading Loop (2 hours)
1. Update `main.py` to log trade results:
```python
# After trade closes (in position monitoring logic)
def on_trade_close(
    strategy_name,
    pair,
    side,
    entry_time,
    exit_time,
    entry_price,
    exit_price,
    pnl,
    regime,
):
    attribution_analyzer.log_trade(
        strategy=strategy_name,
        pair=pair,
        side=side,
        entry_time=entry_time,
        exit_time=exit_time,
        entry_price=entry_price,
        exit_price=exit_price,
        pnl=pnl,
        regime=regime,
    )

    # Optionally: save to disk periodically
    if len(attribution_analyzer.trades) % 100 == 0:
        attribution_analyzer.save_to_file('attribution_data.json')
```

#### Step 3: Create Reporting Dashboard (3 hours)
1. Add attribution page to Streamlit dashboard:
```python
def show_attribution_analysis(analyzer):
    st.title("Trade Attribution Analysis")

    # Overall summary
    st.header("Summary")
    if analyzer.trades:
        total_pnl = sum(t['pnl'] for t in analyzer.trades)
        total_trades = len(analyzer.trades)
        wins = sum(1 for t in analyzer.trades if t['pnl'] > 0)

        col1, col2, col3 = st.columns(3)
        col1.metric("Total PnL", f"${total_pnl:.2f}")
        col2.metric("Total Trades", total_trades)
        col3.metric("Win Rate", f"{wins/total_trades:.1%}")

    # By Strategy
    st.header("Performance by Strategy")
    strategy_df = analyzer.get_attribution_by_dimension('strategy')
    st.dataframe(strategy_df)

    # By Pair
    st.header("Performance by Pair")
    pair_df = analyzer.get_attribution_by_dimension('pair')
    st.dataframe(pair_df)

    # By Hour
    st.header("Performance by Hour of Day")
    hour_df = analyzer.get_attribution_by_dimension('hour')
    st.bar_chart(hour_df.set_index('hour')['total_pnl'])

    # By Regime
    st.header("Performance by Market Regime")
    regime_df = analyzer.get_attribution_by_dimension('regime')
    st.dataframe(regime_df)

    # Cross-attribution: Strategy × Regime
    st.header("Strategy Performance by Regime")
    cross_df = analyzer.get_cross_attribution('strategy', 'regime')
    st.dataframe(cross_df)

    # Top/Bottom performers
    st.header("Top & Bottom Performers")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top 5 Strategy-Pair Combos")
        # Create strategy-pair dimension
        # ... implementation

    with col2:
        st.subheader("Bottom 5 Strategy-Pair Combos")
        # ... implementation
```

2. Add export functionality:
```python
def export_attribution_report(
    analyzer,
    filepath: str = 'attribution_report.html',
):
    """Generate HTML report with all attribution breakdowns."""
    import plotly.express as px
    import plotly.graph_objects as go

    # Generate all charts
    charts = []

    # PnL by strategy
    strategy_df = analyzer.get_attribution_by_dimension('strategy')
    fig1 = px.bar(
        strategy_df,
        x='strategy',
        y='total_pnl',
        title='PnL by Strategy'
    )
    charts.append(fig1.to_html())

    # PnL by hour
    hour_df = analyzer.get_attribution_by_dimension('hour')
    fig2 = px.line(
        hour_df,
        x='hour',
        y='total_pnl',
        title='PnL by Hour of Day'
    )
    charts.append(fig2.to_html())

    # Heatmap: Strategy × Regime
    cross_df = analyzer.get_cross_attribution('strategy', 'regime')
    fig3 = px.imshow(
        cross_df,
        title='Strategy Performance by Regime',
        labels=dict(x='Regime', y='Strategy', color='PnL'),
    )
    charts.append(fig3.to_html())

    # Combine into HTML
    html_content = f"""
    <html>
    <head><title>Trade Attribution Report</title></head>
    <body>
        <h1>Trade Attribution Analysis</h1>
        <p>Generated: {datetime.now()}</p>
        {''.join(charts)}
    </body>
    </html>
    """

    with open(filepath, 'w') as f:
        f.write(html_content)
```

### Data Requirements
- **Input:** Trade records from CSV or live tracking
- **Storage:** In-memory list + JSON persistence
- **Size:** ~500 bytes per trade × 1000 trades = 500 KB

### Integration Approach
1. Create `TradeAttributionAnalyzer` instance at startup
2. Log each trade when position closes
3. Persist to JSON every 100 trades
4. Display in dashboard on-demand

### Testing Strategy
1. **Unit Tests:**
   - Test attribution calculations with synthetic data
   - Test multi-dimensional aggregation
   - Test session classification

2. **Integration Tests:**
   - Load historical trades from CSV
   - Generate attribution report
   - Verify totals match

### Success Metrics
- **Usability:** Dashboard loads in <2 seconds
- **Insights:** Identify top 3 profitable strategies
- **Actionable:** Disable bottom 20% of strategy-pair combos
- **Validation:** Attribution totals match overall P&L

### Estimated Development Time
- **Core Tracker:** 9 hours
- **Dashboard Integration:** 3 hours
- **Testing:** 2 hours
- **Documentation:** 1 hour
- **Total:** 15 hours

### Risk Assessment
**Risks:**
1. **Data volume:** Large trade history slows analysis
   - Mitigation: Use pandas for efficient aggregation
2. **Missing dimensions:** Forget to log important attributes
   - Mitigation: Capture all fields upfront

**Severity:** Low
**Probability:** Low

### Rollback Plan
- Attribution is read-only analysis (no impact on trading)
- Can disable dashboard page without affecting bot

### Dependencies on Phase 1/2
- **Required:** Trade logging to CSV (exists)
- **Required:** Regime detection (exists for regime dimension)
- **Optional:** Dashboard framework (exists)

---

## Feature 6: LSTM Neural Network Integration

### Overview
Use Long Short-Term Memory (LSTM) neural networks for price prediction to augment existing strategies. Research shows 70% directional accuracy with proper feature engineering. **Note:** This is an advanced feature with high complexity.

### Detailed Implementation Steps

#### Step 1: Setup ML Infrastructure (4 hours)
1. Add dependencies to `requirements.txt`:
```
tensorflow>=2.15.0
scikit-learn>=1.3.0
pandas>=2.0.0
numpy>=1.24.0
```

2. Create `/oanda_bot/ml/` directory structure:
```
oanda_bot/ml/
├── __init__.py
├── lstm_predictor.py
├── feature_engineering.py
├── data_preprocessor.py
├── model_trainer.py
└── models/  (saved model checkpoints)
```

3. Create base infrastructure:
```python
# /oanda_bot/ml/__init__.py
from .lstm_predictor import LSTMPredictor
from .feature_engineering import FeatureEngineer
from .data_preprocessor import DataPreprocessor

__all__ = ['LSTMPredictor', 'FeatureEngineer', 'DataPreprocessor']
```

#### Step 2: Implement Feature Engineering (6 hours)
1. Create `/oanda_bot/ml/feature_engineering.py`:
```python
class FeatureEngineer:
    """
    Transform raw OHLC data into ML-ready features.

    Features to include:
    - Technical indicators (RSI, MACD, ATR, Bollinger Bands)
    - Price transforms (returns, log returns, z-scores)
    - Temporal features (hour, day of week, month)
    - Regime indicators (trend strength, volatility percentile)
    """

    def __init__(self):
        self.feature_names = []
        self.scaler = None

    def engineer_features(
        self,
        candles: List[dict],
    ) -> np.ndarray:
        """
        Convert candles to feature matrix.

        Returns:
            Array of shape (n_samples, n_features)
        """
        df = self._candles_to_dataframe(candles)

        # Price features
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        df['high_low_ratio'] = df['high'] / df['low']

        # Technical indicators
        df['rsi'] = self._calculate_rsi(df['close'], 14)
        df['macd'], df['macd_signal'] = self._calculate_macd(df['close'])
        df['atr'] = self._calculate_atr(df['high'], df['low'], df['close'])
        df['bb_upper'], df['bb_lower'] = self._calculate_bollinger(
            df['close'], 20, 2
        )
        df['bb_position'] = (df['close'] - df['bb_lower']) / (
            df['bb_upper'] - df['bb_lower']
        )

        # Moving averages
        for period in [5, 10, 20, 50, 200]:
            df[f'ma_{period}'] = df['close'].rolling(period).mean()
            df[f'price_vs_ma_{period}'] = (
                df['close'] - df[f'ma_{period}']
            ) / df[f'ma_{period}']

        # Volatility features
        df['volatility_20'] = df['returns'].rolling(20).std()
        df['volatility_percentile'] = df['volatility_20'].rolling(50).apply(
            lambda x: percentileofscore(x, x.iloc[-1])
        )

        # Temporal features (cyclical encoding)
        if 'time' in df.columns:
            df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
            df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
            df['dow_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
            df['dow_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)

        # Volume features (if available)
        if 'volume' in df.columns:
            df['volume_ma'] = df['volume'].rolling(20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma']

        # Drop NaN rows
        df = df.dropna()

        # Select feature columns
        feature_cols = [
            col for col in df.columns
            if col not in ['time', 'open', 'high', 'low', 'close', 'volume']
        ]

        features = df[feature_cols].values
        self.feature_names = feature_cols

        return features

    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    # ... implement other indicator calculations ...
```

#### Step 3: Create LSTM Model (8 hours)
1. Create `/oanda_bot/ml/lstm_predictor.py`:
```python
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

class LSTMPredictor:
    """
    LSTM model for price direction prediction.

    Architecture:
    - Input: Sequence of features (e.g., last 60 bars)
    - LSTM layers: 2-3 stacked layers with dropout
    - Output: Binary classification (up/down) or regression (price change)
    """

    def __init__(
        self,
        sequence_length: int = 60,
        n_features: int = 30,
        lstm_units: List[int] = [128, 64, 32],
        dropout: float = 0.2,
        learning_rate: float = 0.001,
        prediction_type: str = 'classification',  # or 'regression'
    ):
        self.sequence_length = sequence_length
        self.n_features = n_features
        self.lstm_units = lstm_units
        self.dropout = dropout
        self.learning_rate = learning_rate
        self.prediction_type = prediction_type

        self.model = None
        self.history = None

    def build_model(self):
        """Build LSTM architecture."""
        model = keras.Sequential()

        # First LSTM layer
        model.add(layers.LSTM(
            self.lstm_units[0],
            return_sequences=True,
            input_shape=(self.sequence_length, self.n_features)
        ))
        model.add(layers.Dropout(self.dropout))

        # Middle LSTM layers
        for units in self.lstm_units[1:-1]:
            model.add(layers.LSTM(units, return_sequences=True))
            model.add(layers.Dropout(self.dropout))

        # Last LSTM layer
        model.add(layers.LSTM(self.lstm_units[-1], return_sequences=False))
        model.add(layers.Dropout(self.dropout))

        # Dense layers
        model.add(layers.Dense(32, activation='relu'))
        model.add(layers.Dropout(self.dropout))

        # Output layer
        if self.prediction_type == 'classification':
            # Binary classification: up (1) or down (0)
            model.add(layers.Dense(1, activation='sigmoid'))
            loss = 'binary_crossentropy'
            metrics = ['accuracy']
        else:
            # Regression: predict price change
            model.add(layers.Dense(1, activation='linear'))
            loss = 'mse'
            metrics = ['mae']

        # Compile
        optimizer = keras.optimizers.Adam(learning_rate=self.learning_rate)
        model.compile(optimizer=optimizer, loss=loss, metrics=metrics)

        self.model = model
        return model

    def prepare_sequences(
        self,
        features: np.ndarray,
        targets: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert features and targets into sequences for LSTM.

        Args:
            features: Array of shape (n_samples, n_features)
            targets: Array of shape (n_samples,) - binary or continuous

        Returns:
            X: Array of shape (n_sequences, sequence_length, n_features)
            y: Array of shape (n_sequences,)
        """
        X, y = [], []

        for i in range(len(features) - self.sequence_length):
            X.append(features[i:i+self.sequence_length])
            y.append(targets[i+self.sequence_length])

        return np.array(X), np.array(y)

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        epochs: int = 50,
        batch_size: int = 32,
        early_stopping_patience: int = 10,
    ):
        """Train the LSTM model."""
        if self.model is None:
            self.build_model()

        # Callbacks
        early_stop = keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=early_stopping_patience,
            restore_best_weights=True,
        )

        reduce_lr = keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=5,
            min_lr=1e-6,
        )

        # Train
        self.history = self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=epochs,
            batch_size=batch_size,
            callbacks=[early_stop, reduce_lr],
            verbose=1,
        )

        return self.history

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions on new data."""
        if self.model is None:
            raise ValueError("Model not built or loaded")

        predictions = self.model.predict(X, verbose=0)

        if self.prediction_type == 'classification':
            # Return probabilities
            return predictions
        else:
            # Return price changes
            return predictions

    def predict_direction(self, X: np.ndarray) -> str:
        """
        Predict next price direction for a single sequence.

        Returns:
            "BUY", "SELL", or None
        """
        if self.prediction_type != 'classification':
            raise ValueError("Use classification model for direction prediction")

        # Ensure X has batch dimension
        if X.ndim == 2:
            X = X.reshape(1, self.sequence_length, self.n_features)

        prob = self.predict(X)[0, 0]

        # Require confidence threshold
        CONFIDENCE_THRESHOLD = 0.6

        if prob > CONFIDENCE_THRESHOLD:
            return "BUY"
        elif prob < (1 - CONFIDENCE_THRESHOLD):
            return "SELL"
        else:
            return None

    def save_model(self, filepath: str):
        """Save model to disk."""
        if self.model is None:
            raise ValueError("No model to save")
        self.model.save(filepath)

    def load_model(self, filepath: str):
        """Load model from disk."""
        self.model = keras.models.load_model(filepath)
```

#### Step 4: Create Training Pipeline (6 hours)
1. Create `/oanda_bot/ml/model_trainer.py`:
```python
class LSTMTrainer:
    """
    End-to-end pipeline for training LSTM models.
    """

    def __init__(
        self,
        instrument: str,
        granularity: str,
        sequence_length: int = 60,
        train_size: int = 5000,
        val_size: int = 1000,
    ):
        self.instrument = instrument
        self.granularity = granularity
        self.sequence_length = sequence_length
        self.train_size = train_size
        self.val_size = val_size

        self.feature_engineer = FeatureEngineer()
        self.predictor = None

    def load_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """Load and prepare training data."""
        # Fetch historical candles
        total_candles = get_candles(
            self.instrument,
            self.granularity,
            self.train_size + self.val_size + 500
        )

        # Engineer features
        features = self.feature_engineer.engineer_features(total_candles)

        # Create targets (next bar direction)
        closes = np.array([float(c['mid']['c']) for c in total_candles])
        # Remove first n rows to align with features (due to indicators)
        n_dropped = len(closes) - len(features)
        closes = closes[n_dropped:]

        # Binary targets: 1 if next close > current close, else 0
        targets = (closes[1:] > closes[:-1]).astype(int)
        features = features[:-1]  # Remove last row (no target)

        return features, targets

    def train_model(
        self,
        epochs: int = 50,
        batch_size: int = 32,
    ) -> Dict[str, any]:
        """
        Train LSTM model and return performance metrics.
        """
        # Load data
        logger.info("Loading training data...")
        features, targets = self.load_data()

        # Split train/val
        split_idx = self.train_size
        X_train_raw = features[:split_idx]
        y_train_raw = targets[:split_idx]
        X_val_raw = features[split_idx:split_idx+self.val_size]
        y_val_raw = targets[split_idx:split_idx+self.val_size]

        # Normalize features
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        X_train_raw = scaler.fit_transform(X_train_raw)
        X_val_raw = scaler.transform(X_val_raw)

        # Create LSTM predictor
        n_features = X_train_raw.shape[1]
        self.predictor = LSTMPredictor(
            sequence_length=self.sequence_length,
            n_features=n_features,
        )

        # Prepare sequences
        logger.info("Creating sequences...")
        X_train, y_train = self.predictor.prepare_sequences(
            X_train_raw, y_train_raw
        )
        X_val, y_val = self.predictor.prepare_sequences(
            X_val_raw, y_val_raw
        )

        logger.info(f"Train shape: {X_train.shape}, Val shape: {X_val.shape}")

        # Train
        logger.info("Training model...")
        history = self.predictor.train(
            X_train, y_train,
            X_val, y_val,
            epochs=epochs,
            batch_size=batch_size,
        )

        # Evaluate
        val_accuracy = history.history['val_accuracy'][-1]
        train_accuracy = history.history['accuracy'][-1]

        metrics = {
            'train_accuracy': train_accuracy,
            'val_accuracy': val_accuracy,
            'epochs_trained': len(history.history['loss']),
        }

        logger.info(f"Training complete: {metrics}")

        # Save model
        model_path = f"oanda_bot/ml/models/{self.instrument}_{self.granularity}.h5"
        self.predictor.save_model(model_path)
        logger.info(f"Model saved to {model_path}")

        return metrics
```

2. Create CLI for training:
```bash
# /oanda_bot/train_lstm.py
python -m oanda_bot.ml.model_trainer \
  --instrument EUR_USD \
  --granularity H1 \
  --epochs 50 \
  --batch-size 32
```

#### Step 5: Integrate with Trading System (4 hours)
1. Create hybrid strategy combining LSTM + traditional:
```python
# /oanda_bot/strategy/lstm_hybrid.py
class StrategyLSTMHybrid(BaseStrategy):
    """
    Hybrid strategy: use LSTM prediction + MACD confirmation.

    Entry logic:
    1. LSTM predicts direction with >60% confidence
    2. MACD aligns with LSTM prediction
    3. Enter trade in predicted direction
    """

    name = "LSTMHybrid"

    def __init__(self, params):
        super().__init__(params)

        # Load LSTM model
        instrument = params.get('instrument', 'EUR_USD')
        granularity = params.get('granularity', 'H1')
        model_path = f"oanda_bot/ml/models/{instrument}_{granularity}.h5"

        self.lstm_predictor = LSTMPredictor()
        self.lstm_predictor.load_model(model_path)

        self.feature_engineer = FeatureEngineer()
        self.sequence_length = 60

    def next_signal(self, bars):
        if len(bars) < self.sequence_length + 50:
            return None

        # Get LSTM prediction
        features = self.feature_engineer.engineer_features(bars)
        recent_features = features[-self.sequence_length:]

        lstm_signal = self.lstm_predictor.predict_direction(recent_features)

        if lstm_signal is None:
            return None

        # Get MACD confirmation
        closes = np.array([float(b['mid']['c']) for b in bars])
        macd, signal_line = self._calculate_macd(closes)

        macd_bullish = macd[-1] > signal_line[-1]
        macd_bearish = macd[-1] < signal_line[-1]

        # Require alignment
        if lstm_signal == "BUY" and macd_bullish:
            return "BUY"
        elif lstm_signal == "SELL" and macd_bearish:
            return "SELL"

        return None
```

### Data Requirements
- **Training Data:** 5000-10000 bars per instrument
- **Features:** 30-50 features per bar
- **Model Size:** 5-10 MB per saved model
- **GPU:** Optional but recommended (10x speedup)

### Integration Approach
1. **Offline:** Train models weekly on historical data
2. **Online:** Load pre-trained models at startup
3. **Hybrid:** Combine LSTM signals with traditional strategies
4. **Fallback:** If model unavailable, use traditional only

### Testing Strategy
1. **Backtest Validation:**
   - Train on 2020-2022, test on 2023
   - Compare accuracy vs buy-and-hold
   - Target: >55% directional accuracy

2. **Walk-Forward:**
   - Retrain monthly on rolling window
   - Test next month's performance
   - Ensure no degradation

3. **Live Testing:**
   - Paper trade for 1 month
   - Compare LSTM signals vs actual outcomes
   - Monitor prediction confidence distribution

### Success Metrics
- **Primary:** Directional accuracy >60% (out-of-sample)
- **Secondary:** Sharpe ratio improvement when using LSTM
- **Validation:** Model maintains >55% accuracy over 3 months
- **Robustness:** Performance stable across different pairs

### Estimated Development Time
- **Infrastructure:** 28 hours
- **Testing & Tuning:** 8 hours
- **Integration:** 4 hours
- **Documentation:** 3 hours
- **Total:** 43 hours

### Risk Assessment
**Risks:**
1. **Overfitting:** Model memorizes training data
   - Mitigation: Early stopping, dropout, walk-forward validation
2. **Data leakage:** Future data used in features
   - Mitigation: Careful feature engineering, no look-ahead bias
3. **Concept drift:** Markets change, model becomes stale
   - Mitigation: Monthly retraining, performance monitoring
4. **Computational cost:** Training is slow
   - Mitigation: Train offline, load pre-trained models

**Severity:** High
**Probability:** Medium-High (ML is inherently risky)

### Rollback Plan
1. Disable LSTM strategy in `live_config.json`
2. Remove from active strategy list
3. Fall back to traditional strategies only
4. No data loss (models are saved externally)

### Dependencies on Phase 1/2
- **Required:** Historical data access (exists)
- **Required:** Feature calculation (indicators exist)
- **Required:** Strategy plugin system (exists)
- **New:** TensorFlow/Keras installation

---

## Feature 7: Reinforcement Learning Strategy Selection

### Overview
Use Deep Q-Network (DQN) to learn optimal strategy deployment based on market state. Research shows 2.87 Sharpe ratio improvement. **This is the most advanced feature.**

### Detailed Implementation Steps

#### Step 1: Define RL Environment (8 hours)
1. Create `/oanda_bot/rl/trading_env.py`:
```python
import gym
from gym import spaces

class TradingEnvironment(gym.Env):
    """
    OpenAI Gym environment for strategy selection.

    State Space:
    - Current market regime (trending/ranging/volatile)
    - Recent strategy performance (last 10 trades per strategy)
    - Current equity and drawdown
    - ATR percentile
    - Correlation matrix summary

    Action Space:
    - Select which strategy to enable (discrete: 0-6 for 7 strategies)

    Reward:
    - Immediate: PnL from trades placed by selected strategy
    - Shaped: Penalize high correlation, reward diversification
    """

    def __init__(
        self,
        strategies: List[BaseStrategy],
        initial_equity: float = 10000,
        max_steps: int = 1000,
    ):
        super().__init__()

        self.strategies = strategies
        self.n_strategies = len(strategies)
        self.initial_equity = initial_equity
        self.max_steps = max_steps

        # State space: continuous values
        # [regime_encoded, atr_pct, drawdown, equity_ratio,
        #  strategy_0_recent_pnl, ..., strategy_N_recent_pnl,
        #  correlation_0_1, correlation_0_2, ...]
        state_dim = (
            5 +  # Market state features
            self.n_strategies +  # Strategy performance
            (self.n_strategies * (self.n_strategies - 1)) // 2  # Correlations
        )

        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(state_dim,),
            dtype=np.float32
        )

        # Action space: select a strategy (discrete)
        self.action_space = spaces.Discrete(self.n_strategies)

        # Internal state
        self.equity = initial_equity
        self.peak_equity = initial_equity
        self.step_count = 0
        self.trade_history = []

    def reset(self):
        """Reset environment to initial state."""
        self.equity = self.initial_equity
        self.peak_equity = self.initial_equity
        self.step_count = 0
        self.trade_history = []

        return self._get_state()

    def _get_state(self) -> np.ndarray:
        """Construct state vector from current market conditions."""
        # Market regime (one-hot encoded)
        regime_encoded = self._encode_regime(self.current_regime)

        # Market volatility
        atr_pct = self.current_atr_percentile / 100.0

        # Portfolio state
        drawdown = (self.peak_equity - self.equity) / self.peak_equity
        equity_ratio = self.equity / self.initial_equity

        # Recent strategy performance (average PnL last 10 trades)
        strategy_pnls = []
        for strat in self.strategies:
            recent = [
                t['pnl'] for t in self.trade_history[-10:]
                if t['strategy'] == strat.name
            ]
            avg_pnl = np.mean(recent) if recent else 0.0
            strategy_pnls.append(avg_pnl / 100.0)  # Normalize

        # Strategy correlations (from correlation analyzer)
        correlations = self._get_correlation_vector()

        # Combine into state
        state = np.concatenate([
            regime_encoded,
            [atr_pct, drawdown, equity_ratio],
            strategy_pnls,
            correlations,
        ]).astype(np.float32)

        return state

    def step(self, action: int):
        """
        Execute one step: enable selected strategy, simulate trades.

        Args:
            action: Index of strategy to enable

        Returns:
            observation, reward, done, info
        """
        selected_strategy = self.strategies[action]

        # Simulate trades from this strategy over next time period
        # (In backtest, this would run strategy on next N bars)
        trade_pnl = self._simulate_strategy(selected_strategy)

        # Update equity
        self.equity += trade_pnl
        self.peak_equity = max(self.peak_equity, self.equity)

        # Calculate reward
        reward = self._calculate_reward(trade_pnl, action)

        # Check if done
        self.step_count += 1
        done = (
            self.step_count >= self.max_steps or
            self.equity <= self.initial_equity * 0.5  # 50% drawdown
        )

        # Get new state
        next_state = self._get_state()

        # Info
        info = {
            'equity': self.equity,
            'strategy': selected_strategy.name,
            'pnl': trade_pnl,
        }

        return next_state, reward, done, info

    def _calculate_reward(self, trade_pnl: float, action: int) -> float:
        """
        Shaped reward function.

        Components:
        1. Trade PnL (primary)
        2. Drawdown penalty
        3. Diversification bonus (select different strategies)
        """
        # Base reward: PnL
        reward = trade_pnl / 100.0  # Normalize

        # Penalize drawdown
        drawdown = (self.peak_equity - self.equity) / self.peak_equity
        reward -= drawdown * 10

        # Bonus for selecting underutilized strategy
        recent_selections = [
            t['strategy_idx'] for t in self.trade_history[-20:]
        ]
        if recent_selections:
            selection_freq = recent_selections.count(action) / len(recent_selections)
            # Bonus if selected <20% of time
            if selection_freq < 0.2:
                reward += 0.1

        return reward

    def _simulate_strategy(self, strategy: BaseStrategy) -> float:
        """
        Simulate running strategy for next time window.
        Returns aggregate PnL.
        """
        # In real implementation, this would:
        # 1. Run strategy.next_signal() on next N bars
        # 2. Simulate trades with SL/TP
        # 3. Return total PnL

        # Placeholder: sample from strategy's historical distribution
        if hasattr(strategy, 'cumulative_pnl'):
            mu = strategy.cumulative_pnl / max(strategy.pull_count, 1)
            sigma = 50  # Assume volatility
            pnl = np.random.normal(mu, sigma)
        else:
            pnl = np.random.normal(0, 50)

        return pnl
```

#### Step 2: Implement DQN Agent (10 hours)
1. Create `/oanda_bot/rl/dqn_agent.py`:
```python
import tensorflow as tf
from tensorflow import keras
from collections import deque
import random

class DQNAgent:
    """
    Deep Q-Network agent for strategy selection.

    Architecture:
    - Input: State vector (market + strategy performance)
    - Hidden: 3 dense layers (256, 128, 64 units)
    - Output: Q-values for each strategy (action)
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        learning_rate: float = 0.001,
        gamma: float = 0.95,
        epsilon: float = 1.0,
        epsilon_decay: float = 0.995,
        epsilon_min: float = 0.01,
        memory_size: int = 10000,
    ):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma  # Discount factor
        self.epsilon = epsilon  # Exploration rate
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min

        # Experience replay memory
        self.memory = deque(maxlen=memory_size)

        # Q-networks
        self.model = self._build_model(learning_rate)
        self.target_model = self._build_model(learning_rate)
        self.update_target_model()

    def _build_model(self, learning_rate):
        """Build neural network for Q-function approximation."""
        model = keras.Sequential([
            layers.Input(shape=(self.state_dim,)),
            layers.Dense(256, activation='relu'),
            layers.Dropout(0.2),
            layers.Dense(128, activation='relu'),
            layers.Dropout(0.2),
            layers.Dense(64, activation='relu'),
            layers.Dense(self.action_dim, activation='linear'),
        ])

        optimizer = keras.optimizers.Adam(learning_rate=learning_rate)
        model.compile(optimizer=optimizer, loss='mse')

        return model

    def update_target_model(self):
        """Copy weights from model to target_model."""
        self.target_model.set_weights(self.model.get_weights())

    def remember(self, state, action, reward, next_state, done):
        """Store experience in replay memory."""
        self.memory.append((state, action, reward, next_state, done))

    def act(self, state, explore=True):
        """
        Select action using epsilon-greedy policy.

        Args:
            state: Current state vector
            explore: If False, always exploit (greedy)

        Returns:
            Action index
        """
        if explore and np.random.random() < self.epsilon:
            # Explore: random action
            return np.random.randint(self.action_dim)

        # Exploit: choose best action based on Q-values
        q_values = self.model.predict(state.reshape(1, -1), verbose=0)[0]
        return np.argmax(q_values)

    def replay(self, batch_size=32):
        """
        Train on a random batch from experience replay.

        This implements Q-learning update:
        Q(s, a) = r + gamma * max_a' Q(s', a')
        """
        if len(self.memory) < batch_size:
            return

        # Sample random batch
        batch = random.sample(self.memory, batch_size)

        # Prepare training data
        states = np.array([exp[0] for exp in batch])
        actions = np.array([exp[1] for exp in batch])
        rewards = np.array([exp[2] for exp in batch])
        next_states = np.array([exp[3] for exp in batch])
        dones = np.array([exp[4] for exp in batch])

        # Current Q-values
        current_q = self.model.predict(states, verbose=0)

        # Next Q-values (from target network)
        next_q = self.target_model.predict(next_states, verbose=0)

        # Update Q-values using Bellman equation
        for i in range(batch_size):
            if dones[i]:
                target_q = rewards[i]
            else:
                target_q = rewards[i] + self.gamma * np.max(next_q[i])

            current_q[i][actions[i]] = target_q

        # Train model
        self.model.fit(states, current_q, epochs=1, verbose=0)

        # Decay epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def save(self, filepath):
        """Save model weights."""
        self.model.save_weights(filepath)

    def load(self, filepath):
        """Load model weights."""
        self.model.load_weights(filepath)
        self.update_target_model()
```

#### Step 3: Create Training Loop (6 hours)
1. Create `/oanda_bot/rl/train_dqn.py`:
```python
def train_dqn(
    strategies: List[BaseStrategy],
    episodes: int = 1000,
    max_steps: int = 500,
    batch_size: int = 32,
    update_target_every: int = 10,
):
    """
    Train DQN agent to select optimal strategies.

    Args:
        strategies: List of strategy instances
        episodes: Number of training episodes
        max_steps: Max steps per episode
        batch_size: Replay batch size
        update_target_every: Episodes between target network updates
    """
    env = TradingEnvironment(strategies, max_steps=max_steps)

    state_dim = env.observation_space.shape[0]
    action_dim = env.action_space.n

    agent = DQNAgent(state_dim, action_dim)

    episode_rewards = []

    for episode in range(episodes):
        state = env.reset()
        episode_reward = 0

        for step in range(max_steps):
            # Select action
            action = agent.act(state, explore=True)

            # Execute action
            next_state, reward, done, info = env.step(action)

            # Store experience
            agent.remember(state, action, reward, next_state, done)

            # Train on replay buffer
            agent.replay(batch_size)

            episode_reward += reward
            state = next_state

            if done:
                break

        episode_rewards.append(episode_reward)

        # Update target network
        if episode % update_target_every == 0:
            agent.update_target_model()

        # Logging
        if episode % 50 == 0:
            avg_reward = np.mean(episode_rewards[-50:])
            logger.info(
                f"Episode {episode}/{episodes}, "
                f"Avg Reward: {avg_reward:.2f}, "
                f"Epsilon: {agent.epsilon:.3f}"
            )

    # Save trained agent
    agent.save('oanda_bot/rl/models/dqn_strategy_selector.h5')

    return agent, episode_rewards
```

#### Step 4: Integrate with Live Trading (4 hours)
1. Create RL-based strategy selector:
```python
# /oanda_bot/strategy/rl_selector.py
class RLStrategySelector:
    """
    Use trained DQN to select which strategy to enable.
    """

    def __init__(self, strategies: List[BaseStrategy]):
        self.strategies = strategies

        # Load trained DQN agent
        state_dim = self._calculate_state_dim()
        action_dim = len(strategies)

        self.agent = DQNAgent(state_dim, action_dim)
        self.agent.load('oanda_bot/rl/models/dqn_strategy_selector.h5')

        # Always exploit (no exploration in live)
        self.agent.epsilon = 0

    def select_strategy(
        self,
        market_state: Dict,
        strategy_performance: Dict,
    ) -> BaseStrategy:
        """
        Select best strategy based on current market state.

        Args:
            market_state: Dict with regime, ATR, etc.
            strategy_performance: Recent PnL per strategy

        Returns:
            Selected strategy instance
        """
        # Construct state vector
        state = self._encode_state(market_state, strategy_performance)

        # Get action from agent
        action_idx = self.agent.act(state, explore=False)

        selected = self.strategies[action_idx]

        logger.info(
            f"RL selected strategy: {selected.name}",
            extra={'state': market_state, 'action': action_idx}
        )

        return selected
```

2. Modify main.py to use RL selector:
```python
if USE_RL_SELECTOR:
    rl_selector = RLStrategySelector(all_strategies)

    # Each bar, let RL choose which strategy to use
    selected_strategy = rl_selector.select_strategy(
        market_state={
            'regime': regime_detector.detect_regime(bars[pair]),
            'atr_percentile': vol_sizer.get_atr_percentile(pair, current_atr),
            'equity': equity,
            'drawdown': drawdown,
        },
        strategy_performance=strategy_pnl_tracker,
    )

    # Evaluate only the selected strategy
    signal = selected_strategy.next_signal(bars[pair])
```

### Data Requirements
- **Training Data:** 50+ episodes × 500 steps = 25,000 state transitions
- **State Vector:** ~50-100 dimensions
- **Model Size:** 10-20 MB
- **Replay Buffer:** 10,000 experiences × 400 bytes = 4 MB

### Integration Approach
1. **Offline Training:** Train DQN on historical simulations
2. **Evaluation:** Backtest with RL selector vs UCB1 baseline
3. **Live Deployment:** Load trained model, use in production
4. **Continuous Learning:** Optionally retrain monthly on new data

### Testing Strategy
1. **Simulation:**
   - Train on 1000 episodes
   - Compare final Sharpe vs random/UCB1
   - Target: 20% improvement

2. **Backtest:**
   - Test RL selector on unseen data
   - Compare strategy selection patterns
   - Verify diversification

3. **Live Paper Trading:**
   - Run for 1 month on practice account
   - Monitor strategy switching frequency
   - Ensure stable performance

### Success Metrics
- **Primary:** Sharpe ratio >2.5 (research target: 2.87)
- **Secondary:** Lower drawdown vs static allocation
- **Diversification:** Uses >3 strategies regularly
- **Robustness:** Performance stable across different market regimes

### Estimated Development Time
- **RL Infrastructure:** 28 hours
- **Training & Tuning:** 10 hours
- **Integration:** 4 hours
- **Testing:** 6 hours
- **Documentation:** 3 hours
- **Total:** 51 hours

### Risk Assessment
**Risks:**
1. **Training instability:** DQN may not converge
   - Mitigation: Use Double DQN, prioritized replay
2. **Overfitting to training environment:** Poor generalization
   - Mitigation: Diverse training scenarios, domain randomization
3. **Computational cost:** Very expensive to train
   - Mitigation: Train on GPU, reuse pre-trained models
4. **Explainability:** Hard to understand why RL chooses strategies
   - Mitigation: Log Q-values, analyze state-action patterns

**Severity:** Very High
**Probability:** High (RL is experimental)

### Rollback Plan
1. Disable RL selector: `USE_RL_SELECTOR=0`
2. Fall back to UCB1 or static allocation
3. No data loss (models saved externally)
4. Can re-enable after retraining

### Dependencies on Phase 1/2
- **Required:** Multiple strategies (exist)
- **Required:** Market regime detection (exists)
- **Required:** Strategy performance tracking (exists)
- **New:** OpenAI Gym, TensorFlow

---

## Implementation Timeline

### Phase 3A: Foundation (Weeks 1-2)
**Total: 35 hours**

1. **Kelly Criterion Position Sizing** (7 hours)
   - Week 1, Days 1-2
   - Highest ROI, lowest risk
   - Foundation for all position sizing

2. **Dynamic Volatility Sizing** (13 hours)
   - Week 1, Days 3-5
   - High impact on Sharpe ratio
   - Synergizes with Kelly

3. **Trade Attribution Analysis** (15 hours)
   - Week 2, Days 1-3
   - Critical for understanding performance
   - Guides optimization decisions

### Phase 3B: Analysis & Optimization (Weeks 3-4)
**Total: 38 hours**

4. **Multi-Timeframe Analysis** (16 hours)
   - Week 3, Days 1-3
   - Improves win rate significantly
   - Lower risk than ML approaches

5. **Walk-Forward Optimization** (22 hours)
   - Week 3, Day 4 - Week 4, Day 2
   - Prevents overfitting
   - Industry best practice

### Phase 3C: Machine Learning (Weeks 5-6+)
**Total: 94 hours** (Optional - High Risk/High Reward)

6. **LSTM Neural Network** (43 hours)
   - Week 5-6
   - Experimental, high complexity
   - Requires ML expertise

7. **Reinforcement Learning** (51 hours)
   - Week 7-8
   - Most advanced feature
   - Research-grade implementation

---

## Dependencies & Prerequisites

### Required Before Phase 3
- Working backtest engine (EXISTS)
- Strategy plugin system (EXISTS)
- Trade logging to CSV (EXISTS)
- Risk management framework (EXISTS)
- OANDA API integration (EXISTS)
- Market regime detection (EXISTS)
- Strategy correlation tracking (EXISTS)

### New Dependencies Required

#### For All Features (1-5):
```bash
# Already in requirements.txt
numpy>=1.24.0
pandas>=2.0.0
scipy>=1.11.0
matplotlib>=3.7.0
plotly>=5.14.0
```

#### For LSTM (Feature 6):
```bash
tensorflow>=2.15.0
scikit-learn>=1.3.0
keras>=2.15.0
```

#### For RL (Feature 7):
```bash
tensorflow>=2.15.0
gym>=0.26.0
stable-baselines3>=2.0.0  # Optional: pre-built RL algorithms
```

---

## Testing Strategy

### Unit Testing (Each Feature)
- Test mathematical calculations (Kelly, volatility ratios)
- Test data structures (attribution storage, LSTM sequences)
- Test edge cases (zero trades, missing data, NaN values)
- Target: >90% code coverage

### Integration Testing
- Test feature interactions (Kelly + volatility sizing)
- Test with existing strategies
- Test with live data stream
- Ensure no performance degradation

### Backtest Validation
- Run before/after comparisons on historical data
- Measure Sharpe ratio, max drawdown, CAGR
- Ensure improvements are statistically significant (t-test)
- Test across multiple currency pairs and timeframes

### Live Testing Phases
1. **Paper Trading (2 weeks):** Practice account, full features
2. **Limited Live (2 weeks):** Real money, small positions (10% of normal)
3. **Full Live (ongoing):** Normal position sizing, continuous monitoring

---

## Rollback & Risk Mitigation

### Feature Flags (Environment Variables)
All Phase 3 features controlled via `.env`:
```bash
USE_KELLY_SIZING=1
USE_VOLATILITY_SIZING=1
USE_MTF_FILTER=1
USE_WALK_FORWARD=0  # Offline tool
USE_ATTRIBUTION=1  # Read-only
USE_LSTM=0  # Experimental
USE_RL_SELECTOR=0  # Experimental
```

### Gradual Rollout
1. Enable one feature at a time
2. Monitor for 1 week
3. Compare metrics vs baseline
4. If degradation: disable and debug

### Emergency Rollback
- All features can be disabled without code changes
- System reverts to Phase 2 behavior
- No data loss (all features are additive)

### Monitoring & Alerts
- Set up alerts for:
  - Sharpe ratio drop >20%
  - Max drawdown exceeds threshold
  - Win rate drop >10%
  - Position sizing anomalies (>2x normal)

---

## Success Criteria

### Overall Phase 3 Goals
- **CAGR:** +15-25% vs Phase 2
- **Sharpe Ratio:** +0.5-1.0 improvement
- **Max Drawdown:** -20-30% reduction
- **Win Rate:** +5-10% improvement
- **Robustness:** Stable performance across 3+ months

### Feature-Specific Targets

| Feature | Primary Metric | Target |
|---------|---------------|--------|
| Kelly Criterion | CAGR | +10-15% |
| Volatility Sizing | Sharpe Ratio | +0.3-0.5 |
| Multi-Timeframe | Win Rate | +5-10% |
| Walk-Forward | Overfitting Reduction | Efficiency >0.5 |
| Attribution | Insights | Identify top 3 performers |
| LSTM | Directional Accuracy | >60% |
| RL | Sharpe Ratio | >2.5 |

---

## Resource Requirements

### Development Time
- **Phase 3A:** 35 hours (1-2 developers × 1-2 weeks)
- **Phase 3B:** 38 hours (1-2 developers × 2 weeks)
- **Phase 3C:** 94 hours (1-2 ML specialists × 4-5 weeks)
- **Total:** 167 hours (~4-6 weeks with 1 developer, 2-3 weeks with 2)

### Computational Resources
- **CPU:** 8+ cores recommended for parallel optimization
- **RAM:** 16 GB minimum, 32 GB for ML features
- **GPU:** Optional for LSTM/RL (10x training speedup)
- **Storage:** 50 GB for models, data, logs

### Infrastructure
- **Cloud:** AWS/GCP for ML training (optional)
- **Database:** Consider PostgreSQL for attribution analysis (optional)
- **Monitoring:** Grafana + Prometheus for metrics (recommended)

---

## Recommended Implementation Order

### Highest ROI, Lowest Risk (Do First)
1. **Kelly Criterion** - Easy win, proven math
2. **Volatility Sizing** - High Sharpe improvement
3. **Attribution Analysis** - Critical insights
4. **Multi-Timeframe** - Proven win rate boost

### Medium Priority (Do Next)
5. **Walk-Forward** - Professional-grade robustness

### Experimental (Do Last, If at All)
6. **LSTM** - High risk, requires ML expertise
7. **RL** - Research-grade, very experimental

### Suggested 4-Week Sprint Plan

**Week 1: Position Sizing**
- Days 1-2: Kelly Criterion
- Days 3-5: Volatility Sizing

**Week 2: Analysis**
- Days 1-3: Attribution Analysis
- Days 4-5: Testing & Integration

**Week 3: Multi-Timeframe**
- Days 1-3: Core Implementation
- Days 4-5: Dashboard & Testing

**Week 4: Walk-Forward**
- Days 1-4: Implementation
- Day 5: Documentation & Review

**Weeks 5-8 (Optional): ML Features**
- Only if team has ML expertise
- Start with LSTM (simpler than RL)
- Budget 2x estimated time for debugging

---

## Conclusion

Phase 3 represents a significant evolution from basic algorithmic trading to professional-grade quantitative finance. The features are ordered by risk-adjusted return:

**High ROI, Low Risk (Do Now):**
- Kelly Criterion
- Volatility Sizing
- Multi-Timeframe
- Attribution

**Medium ROI, Medium Risk (Do Soon):**
- Walk-Forward Optimization

**Experimental (Research Only):**
- LSTM Neural Networks
- Reinforcement Learning

**Recommended Approach:** Implement Features 1-5 over 4 weeks for a robust, production-ready system. Consider Features 6-7 only if you have dedicated ML expertise and can afford the risk of experimental features.

The incremental nature of this plan allows you to:
- Build on proven techniques first
- Validate each feature independently
- Rollback easily if issues arise
- Scale complexity gradually

Good luck with Phase 3!
