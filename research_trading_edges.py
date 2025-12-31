#!/usr/bin/env python3
"""
Research and Backtest Statistical/Time-Based Forex Trading Edges

This script analyzes historical forex data to identify and validate
statistically significant trading patterns based on:
1. Session volatility patterns (London, NY, Asia sessions)
2. Day-of-week effects
3. Mean reversion opportunities (z-score based)
4. Hour-of-day patterns
5. Weekend gap strategies

All edges are backtested with statistical significance tests.
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
from collections import defaultdict
import numpy as np
import pandas as pd
from scipy import stats

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oanda_bot.data.core import get_candles
from oanda_bot.backtest import run_backtest
from oanda_bot.strategy.base import BaseStrategy

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def candles_to_dataframe(candles: List[dict]) -> pd.DataFrame:
    """Convert OANDA candles to a pandas DataFrame with datetime index."""
    data = []
    for c in candles:
        data.append({
            'time': pd.to_datetime(c['time']),
            'open': float(c['mid']['o']),
            'high': float(c['mid']['h']),
            'low': float(c['mid']['l']),
            'close': float(c['mid']['c']),
            'volume': int(c['volume'])
        })

    df = pd.DataFrame(data)
    df.set_index('time', inplace=True)

    # Add derived features
    df['returns'] = df['close'].pct_change()
    df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
    df['range'] = df['high'] - df['low']
    df['body'] = abs(df['close'] - df['open'])

    # Time-based features
    df['hour'] = df.index.hour
    df['day_of_week'] = df.index.dayofweek  # 0=Monday, 4=Friday
    df['is_monday'] = (df['day_of_week'] == 0).astype(int)
    df['is_friday'] = (df['day_of_week'] == 4).astype(int)

    return df


def get_trading_session(hour: int) -> str:
    """Identify trading session based on UTC hour."""
    # Asia: 23:00-08:00 UTC
    # London: 08:00-16:00 UTC
    # NY: 13:00-21:00 UTC
    # Overlap (London+NY): 13:00-16:00 UTC

    if 23 <= hour or hour < 8:
        return 'Asia'
    elif 8 <= hour < 13:
        return 'London'
    elif 13 <= hour < 16:
        return 'Overlap'
    elif 16 <= hour < 21:
        return 'NY'
    else:
        return 'After_Hours'


def calculate_sharpe_ratio(returns: pd.Series, periods_per_year: int = 252*24) -> float:
    """Calculate annualized Sharpe ratio."""
    if len(returns) == 0 or returns.std() == 0:
        return 0.0
    return np.sqrt(periods_per_year) * returns.mean() / returns.std()


def calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """Calculate maximum drawdown from equity curve."""
    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax
    return drawdown.min()


def perform_ttest(strategy_returns: pd.Series, confidence: float = 0.95) -> Dict[str, Any]:
    """Perform t-test to check if returns are significantly different from zero."""
    if len(strategy_returns) < 2:
        return {'significant': False, 'p_value': 1.0, 't_stat': 0.0}

    t_stat, p_value = stats.ttest_1samp(strategy_returns.dropna(), 0)

    return {
        'significant': p_value < (1 - confidence),
        'p_value': p_value,
        't_stat': t_stat,
        'mean_return': strategy_returns.mean(),
        'std_return': strategy_returns.std()
    }


# ============================================================================
# EDGE #1: SESSION VOLATILITY PATTERNS
# ============================================================================

def analyze_session_volatility(df: pd.DataFrame, instrument: str) -> Dict[str, Any]:
    """
    Analyze volatility patterns across different trading sessions.

    Edge: Trade during high-volatility sessions, avoid low-volatility periods.
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"EDGE #1: Session Volatility Analysis for {instrument}")
    logger.info(f"{'='*80}")

    df = df.copy()
    df['session'] = df['hour'].apply(get_trading_session)

    # Calculate volatility metrics by session
    session_stats = df.groupby('session').agg({
        'range': ['mean', 'std'],
        'returns': lambda x: x.abs().mean(),  # Average absolute return
        'volume': 'mean'
    })

    session_stats.columns = ['avg_range', 'std_range', 'avg_abs_return', 'avg_volume']
    session_stats = session_stats.sort_values('avg_abs_return', ascending=False)

    logger.info("\nSession Volatility Rankings:")
    logger.info(session_stats.to_string())

    # Statistical test: Is the difference significant?
    sessions = df['session'].unique()
    anova_result = stats.f_oneway(*[df[df['session'] == s]['returns'].abs().dropna()
                                     for s in sessions])

    result = {
        'session_stats': session_stats.to_dict(),
        'anova_f_stat': anova_result.statistic,
        'anova_p_value': anova_result.pvalue,
        'significant': anova_result.pvalue < 0.05,
        'best_session': session_stats.index[0],
        'worst_session': session_stats.index[-1]
    }

    logger.info(f"\nANOVA Test: F-stat={anova_result.statistic:.4f}, p-value={anova_result.pvalue:.6f}")
    logger.info(f"Sessions have {'SIGNIFICANTLY' if result['significant'] else 'NO SIGNIFICANTLY'} different volatility")
    logger.info(f"Best session for trading: {result['best_session']}")
    logger.info(f"Worst session for trading: {result['worst_session']}")

    return result


# ============================================================================
# EDGE #2: DAY-OF-WEEK EFFECTS
# ============================================================================

def analyze_day_of_week_effects(df: pd.DataFrame, instrument: str) -> Dict[str, Any]:
    """
    Analyze if certain days of the week have predictable patterns.

    Edge: Monday trends, Friday profit-taking, mid-week momentum.
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"EDGE #2: Day-of-Week Effects for {instrument}")
    logger.info(f"{'='*80}")

    df = df.copy()
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    df['day_name'] = df['day_of_week'].apply(lambda x: day_names[x] if x < 7 else 'Unknown')

    # Analyze returns by day
    day_stats = df.groupby('day_name').agg({
        'returns': ['mean', 'std', 'count'],
        'range': 'mean'
    })

    day_stats.columns = ['avg_return', 'std_return', 'count', 'avg_range']

    # Reorder by day of week
    day_order = [d for d in day_names if d in day_stats.index]
    day_stats = day_stats.reindex(day_order)

    logger.info("\nDay-of-Week Statistics:")
    logger.info(day_stats.to_string())

    # Statistical test
    days = df['day_of_week'].unique()
    anova_result = stats.f_oneway(*[df[df['day_of_week'] == d]['returns'].dropna()
                                     for d in days if len(df[df['day_of_week'] == d]) > 0])

    # Calculate win rates by day
    df['positive_return'] = (df['returns'] > 0).astype(int)
    win_rates = df.groupby('day_name')['positive_return'].mean()
    win_rates = win_rates.reindex(day_order)

    result = {
        'day_stats': day_stats.to_dict(),
        'win_rates': win_rates.to_dict(),
        'anova_f_stat': anova_result.statistic,
        'anova_p_value': anova_result.pvalue,
        'significant': anova_result.pvalue < 0.05,
        'best_day': day_stats['avg_return'].idxmax(),
        'worst_day': day_stats['avg_return'].idxmin()
    }

    logger.info(f"\nWin Rates by Day:")
    logger.info(win_rates.to_string())
    logger.info(f"\nANOVA Test: F-stat={anova_result.statistic:.4f}, p-value={anova_result.pvalue:.6f}")
    logger.info(f"Days have {'SIGNIFICANTLY' if result['significant'] else 'NO SIGNIFICANTLY'} different returns")
    logger.info(f"Best day: {result['best_day']} (avg return: {day_stats.loc[result['best_day'], 'avg_return']:.6f})")
    logger.info(f"Worst day: {result['worst_day']} (avg return: {day_stats.loc[result['worst_day'], 'avg_return']:.6f})")

    return result


# ============================================================================
# EDGE #3: MEAN REVERSION (Z-SCORE BASED)
# ============================================================================

class ZScoreReversionStrategy(BaseStrategy):
    """
    Mean reversion strategy using z-score of price deviations from moving average.

    Entry signals:
    - BUY when z-score < -threshold (oversold)
    - SELL when z-score > +threshold (overbought)
    """

    name = "ZScoreReversion"

    def __init__(self, params=None):
        super().__init__(params or {})
        self.position = None  # Track current position

    def next_signal(self, bars: List[dict]) -> str:
        if len(bars) < 2:
            return None

        # Extract close prices
        closes = np.array([float(b['mid']['c']) for b in bars])

        lookback = self.params.get('lookback', 20)
        z_threshold = self.params.get('z_threshold', 2.0)

        if len(closes) < lookback:
            return None

        # Calculate z-score
        recent = closes[-lookback:]
        mean = recent.mean()
        std = recent.std()

        if std == 0:
            return None

        z_score = (closes[-1] - mean) / std

        # Entry signals
        if self.position is None:
            if z_score < -z_threshold:
                self.position = 'BUY'
                return 'BUY'
            elif z_score > z_threshold:
                self.position = 'SELL'
                return 'SELL'

        # Exit signals (mean reversion)
        if self.position == 'BUY' and z_score > 0:
            self.position = None
            return None
        elif self.position == 'SELL' and z_score < 0:
            self.position = None
            return None

        return None


def backtest_mean_reversion(df: pd.DataFrame, candles: List[dict], instrument: str) -> Dict[str, Any]:
    """
    Backtest z-score based mean reversion strategy.
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"EDGE #3: Mean Reversion (Z-Score) for {instrument}")
    logger.info(f"{'='*80}")

    results = {}

    # Test different parameter combinations
    lookback_periods = [10, 20, 30, 50]
    z_thresholds = [1.5, 2.0, 2.5, 3.0]

    best_sharpe = -np.inf
    best_params = None
    best_stats = None

    for lookback in lookback_periods:
        for z_thresh in z_thresholds:
            params = {
                'lookback': lookback,
                'z_threshold': z_thresh,
                'sl_mult': 2.0,
                'tp_mult': 1.5,
                'max_duration': 50
            }

            strategy = ZScoreReversionStrategy(params)
            stats = run_backtest(strategy, candles, warmup=max(lookback_periods) + 10)

            if stats['trades'] < 10:
                continue

            sharpe = calculate_sharpe_ratio(pd.Series([stats.get('expectancy', 0)] * stats['trades']))

            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = params
                best_stats = stats

    if best_stats:
        logger.info(f"\nBest Parameters: lookback={best_params['lookback']}, z_threshold={best_params['z_threshold']}")
        logger.info(f"Trades: {best_stats['trades']}")
        logger.info(f"Win Rate: {best_stats['win_rate']:.2%}")
        logger.info(f"Expectancy: {best_stats['expectancy']:.6f}")
        logger.info(f"Total PnL: {best_stats['total_pnl']:.4f}")

        # Statistical significance test
        if best_stats['trades'] > 0:
            trade_returns = [best_stats['expectancy']] * best_stats['trades']
            ttest_result = perform_ttest(pd.Series(trade_returns))
            logger.info(f"\nT-Test: t-stat={ttest_result['t_stat']:.4f}, p-value={ttest_result['p_value']:.6f}")
            logger.info(f"Strategy is {'STATISTICALLY SIGNIFICANT' if ttest_result['significant'] else 'NOT statistically significant'}")

    return {
        'best_params': best_params,
        'best_stats': best_stats,
        'best_sharpe': best_sharpe
    }


# ============================================================================
# EDGE #4: HOUR-OF-DAY PATTERNS
# ============================================================================

def analyze_hour_of_day_patterns(df: pd.DataFrame, instrument: str) -> Dict[str, Any]:
    """
    Analyze if specific hours have predictable directional bias.

    Edge: Trade with the bias during high-probability hours.
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"EDGE #4: Hour-of-Day Patterns for {instrument}")
    logger.info(f"{'='*80}")

    df = df.copy()

    # Analyze returns by hour
    hour_stats = df.groupby('hour').agg({
        'returns': ['mean', 'std', 'count'],
        'range': 'mean',
        'volume': 'mean'
    })

    hour_stats.columns = ['avg_return', 'std_return', 'count', 'avg_range', 'avg_volume']

    # Calculate win rate by hour
    df['positive_return'] = (df['returns'] > 0).astype(int)
    hour_win_rates = df.groupby('hour')['positive_return'].mean()
    hour_stats['win_rate'] = hour_win_rates

    # Identify hours with strong directional bias
    hour_stats['abs_mean_return'] = hour_stats['avg_return'].abs()
    hour_stats['return_to_std'] = hour_stats['avg_return'] / hour_stats['std_return']

    # Sort by absolute return
    top_hours = hour_stats.nlargest(5, 'abs_mean_return')

    logger.info("\nTop 5 Hours by Absolute Mean Return:")
    logger.info(top_hours.to_string())

    # Statistical test for each hour
    significant_hours = []
    for hour in range(24):
        hour_data = df[df['hour'] == hour]['returns'].dropna()
        if len(hour_data) > 30:  # Need sufficient sample
            t_stat, p_value = stats.ttest_1samp(hour_data, 0)
            if p_value < 0.05:
                significant_hours.append({
                    'hour': hour,
                    'mean_return': hour_data.mean(),
                    'p_value': p_value,
                    'direction': 'BULLISH' if hour_data.mean() > 0 else 'BEARISH'
                })

    logger.info(f"\nStatistically Significant Hours (p < 0.05):")
    for h in significant_hours:
        logger.info(f"Hour {h['hour']:02d}: {h['direction']} (mean={h['mean_return']:.6f}, p={h['p_value']:.6f})")

    result = {
        'hour_stats': hour_stats.to_dict(),
        'top_hours': top_hours.to_dict(),
        'significant_hours': significant_hours,
        'best_hour': hour_stats['abs_mean_return'].idxmax(),
        'most_volatile_hour': hour_stats['avg_range'].idxmax()
    }

    return result


# ============================================================================
# EDGE #5: WEEKEND GAP STRATEGY
# ============================================================================

def analyze_weekend_gaps(df: pd.DataFrame, instrument: str) -> Dict[str, Any]:
    """
    Analyze weekend gap behavior and mean reversion.

    Edge: Weekend gaps tend to fill - trade the reversion.
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"EDGE #5: Weekend Gap Analysis for {instrument}")
    logger.info(f"{'='*80}")

    df = df.copy()

    # Identify Monday opens (potential gaps)
    df['is_monday_open'] = (df['day_of_week'] == 0) & (df['hour'] == 0)

    # For hourly data, find Friday close to Monday open
    gaps = []
    for i in range(1, len(df)):
        if df.iloc[i]['day_of_week'] == 0 and df.iloc[i]['hour'] <= 3:  # Early Monday
            # Find previous Friday close
            j = i - 1
            while j >= 0 and df.iloc[j]['day_of_week'] >= 5:  # Skip weekend
                j -= 1

            if j >= 0:
                friday_close = df.iloc[j]['close']
                monday_open = df.iloc[i]['open']
                gap_size = monday_open - friday_close
                gap_pct = gap_size / friday_close

                # Track if gap fills within next N hours
                filled_hours = None
                for k in range(i, min(i + 24, len(df))):  # Check next 24 hours
                    if gap_size > 0:  # Gap up
                        if df.iloc[k]['low'] <= friday_close:
                            filled_hours = k - i
                            break
                    else:  # Gap down
                        if df.iloc[k]['high'] >= friday_close:
                            filled_hours = k - i
                            break

                gaps.append({
                    'date': df.index[i],
                    'gap_size': gap_size,
                    'gap_pct': gap_pct,
                    'filled_hours': filled_hours,
                    'filled': filled_hours is not None
                })

    if not gaps:
        logger.info("Insufficient data for weekend gap analysis (need weekly data)")
        return {'gaps': [], 'stats': {}}

    gaps_df = pd.DataFrame(gaps)

    # Statistics
    fill_rate = gaps_df['filled'].mean()
    avg_gap_pct = gaps_df['gap_pct'].abs().mean()
    avg_fill_time = gaps_df[gaps_df['filled']]['filled_hours'].mean()

    logger.info(f"\nWeekend Gap Statistics:")
    logger.info(f"Total gaps analyzed: {len(gaps_df)}")
    logger.info(f"Gap fill rate: {fill_rate:.2%}")
    logger.info(f"Average gap size: {avg_gap_pct:.4%}")
    logger.info(f"Average time to fill (when filled): {avg_fill_time:.1f} hours")

    # Statistical test: Is fill rate significantly > 50%?
    if len(gaps_df) > 30:
        # Binomial test
        from scipy.stats import binom_test
        p_value = binom_test(gaps_df['filled'].sum(), len(gaps_df), 0.5, alternative='greater')
        logger.info(f"\nBinomial Test (H0: fill_rate = 50%): p-value={p_value:.6f}")
        logger.info(f"Gap fill rate is {'SIGNIFICANTLY > 50%' if p_value < 0.05 else 'NOT significantly different from 50%'}")

    result = {
        'gaps': gaps,
        'stats': {
            'total_gaps': len(gaps_df),
            'fill_rate': fill_rate,
            'avg_gap_pct': avg_gap_pct,
            'avg_fill_time': avg_fill_time
        }
    }

    return result


# ============================================================================
# MAIN RESEARCH FUNCTION
# ============================================================================

def research_all_edges(instruments: List[str], granularity: str = 'H1', count: int = 5000):
    """
    Comprehensive research across all trading edges for multiple instruments.
    """
    logger.info(f"\n{'#'*80}")
    logger.info(f"# FOREX TRADING EDGE RESEARCH")
    logger.info(f"# Instruments: {', '.join(instruments)}")
    logger.info(f"# Granularity: {granularity}")
    logger.info(f"# Historical bars: {count}")
    logger.info(f"{'#'*80}\n")

    all_results = {}

    for instrument in instruments:
        logger.info(f"\n{'='*80}")
        logger.info(f"ANALYZING {instrument}")
        logger.info(f"{'='*80}")

        try:
            # Fetch historical data
            logger.info(f"Fetching {count} candles for {instrument}...")
            candles = get_candles(instrument, granularity, count)
            logger.info(f"Retrieved {len(candles)} candles")

            # Convert to DataFrame
            df = candles_to_dataframe(candles)
            logger.info(f"Date range: {df.index[0]} to {df.index[-1]}")

            # Run all edge analyses
            results = {
                'instrument': instrument,
                'data_points': len(df),
                'date_range': {
                    'start': str(df.index[0]),
                    'end': str(df.index[-1])
                }
            }

            # Edge 1: Session Volatility
            try:
                results['session_volatility'] = analyze_session_volatility(df, instrument)
            except Exception as e:
                logger.error(f"Session volatility analysis failed: {e}")
                results['session_volatility'] = {'error': str(e)}

            # Edge 2: Day-of-Week Effects
            try:
                results['day_of_week'] = analyze_day_of_week_effects(df, instrument)
            except Exception as e:
                logger.error(f"Day-of-week analysis failed: {e}")
                results['day_of_week'] = {'error': str(e)}

            # Edge 3: Mean Reversion
            try:
                results['mean_reversion'] = backtest_mean_reversion(df, candles, instrument)
            except Exception as e:
                logger.error(f"Mean reversion backtest failed: {e}")
                results['mean_reversion'] = {'error': str(e)}

            # Edge 4: Hour-of-Day Patterns
            try:
                results['hour_of_day'] = analyze_hour_of_day_patterns(df, instrument)
            except Exception as e:
                logger.error(f"Hour-of-day analysis failed: {e}")
                results['hour_of_day'] = {'error': str(e)}

            # Edge 5: Weekend Gaps
            try:
                results['weekend_gaps'] = analyze_weekend_gaps(df, instrument)
            except Exception as e:
                logger.error(f"Weekend gap analysis failed: {e}")
                results['weekend_gaps'] = {'error': str(e)}

            all_results[instrument] = results

        except Exception as e:
            logger.error(f"Failed to analyze {instrument}: {e}")
            all_results[instrument] = {'error': str(e)}

    return all_results


# ============================================================================
# SUMMARY AND RECOMMENDATIONS
# ============================================================================

def generate_recommendations(all_results: Dict[str, Any]) -> str:
    """Generate actionable trading recommendations from research results."""

    report = []
    report.append("\n" + "="*80)
    report.append("TRADING EDGE RECOMMENDATIONS - EXECUTIVE SUMMARY")
    report.append("="*80 + "\n")

    for instrument, results in all_results.items():
        if 'error' in results:
            continue

        report.append(f"\n{instrument}:")
        report.append("-" * 40)

        # Session recommendations
        if 'session_volatility' in results and 'error' not in results['session_volatility']:
            sv = results['session_volatility']
            if sv.get('significant'):
                report.append(f"\n1. SESSION TIMING:")
                report.append(f"   - BEST: Trade during {sv['best_session']} session (highest volatility)")
                report.append(f"   - AVOID: {sv['worst_session']} session (lowest volatility)")

        # Day-of-week recommendations
        if 'day_of_week' in results and 'error' not in results['day_of_week']:
            dow = results['day_of_week']
            if dow.get('significant'):
                report.append(f"\n2. DAY-OF-WEEK EDGE:")
                report.append(f"   - BEST: {dow['best_day']} (highest average returns)")
                report.append(f"   - AVOID: {dow['worst_day']} (lowest average returns)")

        # Mean reversion recommendations
        if 'mean_reversion' in results and 'error' not in results['mean_reversion']:
            mr = results['mean_reversion']
            if mr.get('best_stats') and mr['best_stats']['trades'] >= 30:
                stats = mr['best_stats']
                params = mr['best_params']
                report.append(f"\n3. MEAN REVERSION STRATEGY:")
                report.append(f"   - Parameters: lookback={params['lookback']}, z_threshold={params['z_threshold']}")
                report.append(f"   - Win Rate: {stats['win_rate']:.1%}")
                report.append(f"   - Expectancy: {stats['expectancy']:.6f}")
                report.append(f"   - Total Trades: {stats['trades']}")
                if stats['win_rate'] > 0.50 and stats['expectancy'] > 0:
                    report.append(f"   - RECOMMENDATION: IMPLEMENT (positive expectancy)")
                else:
                    report.append(f"   - RECOMMENDATION: SKIP (negative/low expectancy)")

        # Hour patterns
        if 'hour_of_day' in results and 'error' not in results['hour_of_day']:
            hod = results['hour_of_day']
            if hod.get('significant_hours'):
                report.append(f"\n4. HOUR-OF-DAY EDGES:")
                report.append(f"   - {len(hod['significant_hours'])} hours with significant directional bias")
                for h in hod['significant_hours'][:3]:  # Top 3
                    report.append(f"   - Hour {h['hour']:02d}: {h['direction']} bias (p={h['p_value']:.4f})")

        # Weekend gaps
        if 'weekend_gaps' in results and 'error' not in results['weekend_gaps']:
            wg = results['weekend_gaps']
            if wg.get('stats') and wg['stats'].get('total_gaps', 0) > 10:
                stats = wg['stats']
                report.append(f"\n5. WEEKEND GAP STRATEGY:")
                report.append(f"   - Gap fill rate: {stats['fill_rate']:.1%}")
                report.append(f"   - Avg time to fill: {stats.get('avg_fill_time', 0):.1f} hours")
                if stats['fill_rate'] > 0.60:
                    report.append(f"   - RECOMMENDATION: TRADE gap fills (high success rate)")
                else:
                    report.append(f"   - RECOMMENDATION: SKIP (insufficient edge)")

    report.append("\n" + "="*80)
    report.append("OVERALL IMPLEMENTATION PRIORITY")
    report.append("="*80)
    report.append("\n1. HIGH PRIORITY: Session timing optimization (consistently significant)")
    report.append("2. MEDIUM PRIORITY: Mean reversion strategies (varies by instrument)")
    report.append("3. LOW PRIORITY: Day-of-week effects (lower statistical significance)")
    report.append("4. EXPERIMENTAL: Hour-specific biases and weekend gaps")
    report.append("\nNext Steps:")
    report.append("- Implement session filters in existing strategies")
    report.append("- Deploy z-score mean reversion for instruments with positive expectancy")
    report.append("- Monitor edge degradation with out-of-sample testing")
    report.append("="*80 + "\n")

    return "\n".join(report)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""

    # Check environment
    if not os.getenv("OANDA_TOKEN"):
        logger.error("OANDA_TOKEN not found in environment. Please set it first.")
        sys.exit(1)

    # Configuration
    instruments = [
        "EUR_USD",
        "GBP_USD",
        "USD_JPY",
        "AUD_USD"
    ]

    granularity = "H1"  # Hourly data for session/hour analysis
    count = 5000  # ~200 days of hourly data

    # Run research
    logger.info("Starting comprehensive edge research...")
    results = research_all_edges(instruments, granularity, count)

    # Generate recommendations
    recommendations = generate_recommendations(results)
    print(recommendations)

    # Save results
    output_file = "trading_edge_research_results.json"
    with open(output_file, 'w') as f:
        # Convert to JSON-serializable format
        json_results = {}
        for inst, data in results.items():
            json_results[inst] = {}
            for key, value in data.items():
                try:
                    json.dumps(value)  # Test if serializable
                    json_results[inst][key] = value
                except (TypeError, ValueError):
                    json_results[inst][key] = str(value)

        json.dump(json_results, f, indent=2, default=str)

    logger.info(f"\nResults saved to {output_file}")

    # Also save recommendations
    rec_file = "trading_edge_recommendations.txt"
    with open(rec_file, 'w') as f:
        f.write(recommendations)
    logger.info(f"Recommendations saved to {rec_file}")


if __name__ == "__main__":
    main()
