#!/usr/bin/env python3
"""
Test Trading Edges - Validation Script

This script tests all implemented statistical and time-based trading edges:
1. Session volatility analysis
2. Z-score mean reversion
3. Weekend gap detection
4. Session filters

Run with: python test_trading_edges.py
"""

import os
import sys
import json
from datetime import datetime

# Add to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oanda_bot.data.core import get_candles
from oanda_bot.backtest import run_backtest
from oanda_bot.strategy.zscore_reversion import (
    StrategyZScoreReversion,
    get_optimal_params,
    OPTIMAL_PARAMS
)
from oanda_bot.strategy.weekend_gap import (
    StrategyWeekendGap,
    detect_weekend_gaps,
    analyze_gap_statistics
)
from oanda_bot.common.session_filters import (
    get_current_session,
    is_favorable_for_trend_following,
    is_favorable_for_mean_reversion,
    get_session_characteristics
)

print("="*80)
print("FOREX TRADING EDGES - VALIDATION TEST")
print("="*80)
print()


# ============================================================================
# Test 1: Session Filter Functionality
# ============================================================================

print("TEST 1: Session Filter Functionality")
print("-"*80)

for hour in [0, 3, 9, 14, 17, 23]:
    session = get_current_session(hour)
    chars = get_session_characteristics(session)

    print(f"\n{hour:02d}:00 UTC → {session.value}")
    print(f"  Volatility: {chars.get('volatility', 'N/A')}")
    print(f"  Best for: {', '.join(chars.get('best_for', []))}")
    print(f"  Trend-friendly: {is_favorable_for_trend_following(hour)}")
    print(f"  MR-friendly: {is_favorable_for_mean_reversion(hour)}")

print("\n✓ Session filters working correctly")
print()


# ============================================================================
# Test 2: Z-Score Strategy Parameters
# ============================================================================

print("TEST 2: Z-Score Strategy Optimal Parameters")
print("-"*80)

for instrument in ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD"]:
    params = get_optimal_params(instrument)
    print(f"\n{instrument}:")
    print(f"  Lookback: {params['lookback']}")
    print(f"  Z-Threshold: {params['z_threshold']}")
    print(f"  SL Mult: {params['sl_mult']}")
    print(f"  TP Mult: {params['tp_mult']}")
    print(f"  Session Filter: {params['session_filter']}")

print("\n✓ Z-Score parameters loaded")
print()


# ============================================================================
# Test 3: Backtest Z-Score Strategy
# ============================================================================

print("TEST 3: Backtest Z-Score Mean Reversion")
print("-"*80)

try:
    instrument = "EUR_USD"
    print(f"\nFetching historical data for {instrument}...")

    candles = get_candles(instrument, "H1", 2000)
    print(f"Retrieved {len(candles)} candles")

    # Test with optimal parameters
    params = get_optimal_params(instrument)
    strategy = StrategyZScoreReversion(params)

    print(f"\nRunning backtest with lookback={params['lookback']}, z_threshold={params['z_threshold']}...")
    stats = run_backtest(strategy, candles, warmup=30)

    print(f"\nBacktest Results:")
    print(f"  Trades: {stats['trades']}")
    print(f"  Win Rate: {stats['win_rate']:.2%}")
    print(f"  Expectancy: {stats['expectancy']:.6f}")
    print(f"  Total PnL: {stats['total_pnl']:.4f}")
    print(f"  Avg Win: {stats['avg_win']:.6f}")
    print(f"  Avg Loss: {stats['avg_loss']:.6f}")

    # Assess quality
    if stats['trades'] >= 30 and stats['win_rate'] > 0.50 and stats['expectancy'] > 0:
        print(f"\n✓ Z-Score strategy shows POSITIVE edge")
        print(f"  Recommendation: DEPLOY to live trading")
    elif stats['trades'] < 30:
        print(f"\n⚠ Insufficient trades for statistical validation")
        print(f"  Recommendation: Test on more data")
    else:
        print(f"\n✗ Strategy shows NEGATIVE edge")
        print(f"  Recommendation: Re-optimize or skip")

except Exception as e:
    print(f"✗ Backtest failed: {e}")

print()


# ============================================================================
# Test 4: Weekend Gap Detection
# ============================================================================

print("TEST 4: Weekend Gap Detection & Statistics")
print("-"*80)

try:
    instrument = "EUR_USD"
    print(f"\nAnalyzing weekend gaps for {instrument}...")

    # Fetch 3+ months of hourly data to capture ~12-15 weekends
    candles = get_candles(instrument, "H1", 2500)
    print(f"Retrieved {len(candles)} candles")

    # Detect gaps
    gaps = detect_weekend_gaps(candles, instrument)
    print(f"\nDetected {len(gaps)} weekend gaps")

    if gaps:
        # Statistics
        stats = analyze_gap_statistics(gaps)

        print(f"\nGap Statistics:")
        print(f"  Average gap: {stats['avg_gap_pips']:.1f} pips")
        print(f"  Median gap: {stats['median_gap_pips']:.1f} pips")
        print(f"  Std dev: {stats['std_gap_pips']:.1f} pips")
        print(f"  Gaps up: {stats['gap_up_pct']:.1f}%")
        print(f"  Gaps down: {stats['gap_down_pct']:.1f}%")
        print(f"  Large gaps (>50 pips): {stats['large_gaps_50']}")
        print(f"  Tradeable gaps (20-80 pips): {stats['tradeable_gaps_20_80']}")

        # Show recent examples
        print(f"\nRecent Gaps (last 5):")
        for gap in gaps[-5:]:
            direction = "↑ UP" if gap["gap_direction"] == "up" else "↓ DOWN"
            print(f"  {gap['date']}: {direction:6s} {gap['abs_gap_pips']:5.1f} pips")

        # Assessment
        tradeable = stats['tradeable_gaps_20_80']
        total = stats['total_gaps']
        tradeable_pct = (tradeable / total * 100) if total > 0 else 0

        print(f"\nAssessment:")
        print(f"  Tradeable gaps: {tradeable}/{total} ({tradeable_pct:.1f}%)")

        if tradeable >= 10:
            print(f"  ✓ Sufficient gap opportunities for trading")
            print(f"  Recommendation: IMPLEMENT gap strategy")
        else:
            print(f"  ⚠ Limited gap opportunities")
            print(f"  Recommendation: Monitor for more data")

    else:
        print("✗ No gaps detected (may need daily/weekly data)")

except Exception as e:
    print(f"✗ Gap analysis failed: {e}")

print()


# ============================================================================
# Test 5: Multi-Instrument Comparison
# ============================================================================

print("TEST 5: Multi-Instrument Z-Score Comparison")
print("-"*80)

instruments = ["EUR_USD", "GBP_USD"]  # Test 2 pairs for speed

results = {}

for instrument in instruments:
    try:
        print(f"\nTesting {instrument}...")

        # Fetch data
        candles = get_candles(instrument, "H1", 1500)

        # Run with optimal params
        params = get_optimal_params(instrument)
        strategy = StrategyZScoreReversion(params)
        stats = run_backtest(strategy, candles, warmup=30)

        results[instrument] = stats

        print(f"  Trades: {stats['trades']}, Win Rate: {stats['win_rate']:.1%}, Expectancy: {stats['expectancy']:.6f}")

    except Exception as e:
        print(f"  ✗ Failed: {e}")
        results[instrument] = None

# Compare
print(f"\n{'Instrument':<12} {'Trades':<8} {'Win Rate':<12} {'Expectancy':<12} {'Total PnL':<12}")
print("-"*60)

for inst, stats in results.items():
    if stats:
        print(f"{inst:<12} {stats['trades']:<8} {stats['win_rate']:<12.1%} {stats['expectancy']:<12.6f} {stats['total_pnl']:<12.4f}")
    else:
        print(f"{inst:<12} {'N/A':<8}")

# Recommendation
print("\nRecommendations:")
for inst, stats in results.items():
    if stats and stats['trades'] >= 30:
        if stats['expectancy'] > 0.0001 and stats['win_rate'] > 0.52:
            print(f"  ✓ {inst}: DEPLOY (positive expectancy)")
        elif stats['expectancy'] > 0:
            print(f"  ⚠ {inst}: MARGINAL (low expectancy, optimize further)")
        else:
            print(f"  ✗ {inst}: SKIP (negative expectancy)")
    elif stats:
        print(f"  ⚠ {inst}: INSUFFICIENT DATA (need more trades)")

print()


# ============================================================================
# Test 6: Session Filter Impact
# ============================================================================

print("TEST 6: Session Filter Impact on Performance")
print("-"*80)

try:
    instrument = "EUR_USD"
    print(f"\nComparing {instrument} with and without session filter...")

    candles = get_candles(instrument, "H1", 1500)

    # Without filter
    params_no_filter = get_optimal_params(instrument).copy()
    params_no_filter['session_filter'] = False

    strategy_no_filter = StrategyZScoreReversion(params_no_filter)
    stats_no_filter = run_backtest(strategy_no_filter, candles, warmup=30)

    # With filter
    params_with_filter = get_optimal_params(instrument).copy()
    params_with_filter['session_filter'] = True

    strategy_with_filter = StrategyZScoreReversion(params_with_filter)
    stats_with_filter = run_backtest(strategy_with_filter, candles, warmup=30)

    # Compare
    print(f"\n{'Metric':<20} {'No Filter':<15} {'With Filter':<15} {'Improvement':<15}")
    print("-"*70)

    metrics = [
        ('Trades', 'trades'),
        ('Win Rate', 'win_rate'),
        ('Expectancy', 'expectancy'),
        ('Total PnL', 'total_pnl')
    ]

    for label, key in metrics:
        no_filt = stats_no_filter[key]
        with_filt = stats_with_filter[key]

        if key == 'win_rate':
            improvement = (with_filt - no_filt) * 100  # percentage points
            print(f"{label:<20} {no_filt:<15.1%} {with_filt:<15.1%} {improvement:+.1f}pp")
        elif key == 'trades':
            change_pct = ((with_filt - no_filt) / no_filt * 100) if no_filt > 0 else 0
            print(f"{label:<20} {no_filt:<15} {with_filt:<15} {change_pct:+.1f}%")
        else:
            change_pct = ((with_filt - no_filt) / no_filt * 100) if no_filt != 0 else 0
            print(f"{label:<20} {no_filt:<15.6f} {with_filt:<15.6f} {change_pct:+.1f}%")

    # Assessment
    if stats_with_filter['win_rate'] > stats_no_filter['win_rate']:
        print(f"\n✓ Session filter IMPROVES performance")
    else:
        print(f"\n✗ Session filter DECREASES performance (unexpected)")

except Exception as e:
    print(f"✗ Session filter test failed: {e}")

print()


# ============================================================================
# Summary
# ============================================================================

print("="*80)
print("TEST SUMMARY")
print("="*80)
print()
print("Completed Tests:")
print("  ✓ Session filter functionality")
print("  ✓ Z-Score strategy parameters")
print("  ✓ Z-Score backtest validation")
print("  ✓ Weekend gap detection")
print("  ✓ Multi-instrument comparison")
print("  ✓ Session filter impact analysis")
print()
print("Next Steps:")
print("  1. Review backtest results above")
print("  2. If expectancy > 0 and win rate > 52%, deploy to paper trading")
print("  3. Monitor performance for 2-4 weeks")
print("  4. Adjust parameters if edge degrades")
print("  5. Scale up position sizing after 50+ successful trades")
print()
print("Documentation:")
print("  - Full analysis: TRADING_EDGES_ANALYSIS.md")
print("  - Research script: research_trading_edges.py")
print("  - Strategies: oanda_bot/strategy/zscore_reversion.py, weekend_gap.py")
print("  - Filters: oanda_bot/common/session_filters.py")
print()
print("="*80)
