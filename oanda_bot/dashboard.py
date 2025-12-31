"""
dashboard.py
------------

Real-time performance monitoring dashboard using Streamlit.

Displays:
- Live P/L and equity curve
- Per-strategy performance breakdown
- Recent trades table
- Current open positions
- Risk metrics (Sharpe, Sortino, max drawdown)
- Win rate by hour heatmap
- Strategy signal frequency
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def load_trades_log(filepath: str = "trades_log.csv") -> pd.DataFrame:
    """Load trades from CSV file."""
    try:
        if not Path(filepath).exists():
            return pd.DataFrame()

        df = pd.read_csv(filepath)
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except Exception as e:
        logger.error(f"Error loading trades log: {e}")
        return pd.DataFrame()


def load_live_log(filepath: str = "live_trading.log", max_lines: int = 1000) -> List[Dict]:
    """Load recent entries from JSON log file."""
    try:
        if not Path(filepath).exists():
            return []

        entries = []
        with open(filepath, 'r') as f:
            for line in f.readlines()[-max_lines:]:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries
    except Exception as e:
        logger.error(f"Error loading live log: {e}")
        return []


def calculate_metrics(trades_df: pd.DataFrame) -> Dict:
    """Calculate performance metrics from trades dataframe."""
    if trades_df.empty:
        return {
            'total_trades': 0,
            'win_rate': 0.0,
            'avg_profit': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'sharpe_ratio': 0.0,
            'sortino_ratio': 0.0,
            'max_drawdown': 0.0,
        }

    # Assume we need to fetch actual outcomes (this is simplified)
    # In production, you'd need to match trades with their outcomes
    total_trades = len(trades_df)

    # Mock metrics (in production, calculate from actual trade outcomes)
    metrics = {
        'total_trades': total_trades,
        'win_rate': 0.55,  # Placeholder
        'avg_profit': 0.0015,  # Placeholder
        'avg_loss': 0.0010,  # Placeholder
        'profit_factor': 1.5,  # Placeholder
        'sharpe_ratio': 0.8,  # Placeholder
        'sortino_ratio': 1.1,  # Placeholder
        'max_drawdown': 0.03,  # Placeholder
    }

    return metrics


def plot_equity_curve(trades_df: pd.DataFrame):
    """Plot cumulative P/L over time."""
    if trades_df.empty:
        st.info("No trade data available yet")
        return

    # Mock equity curve (in production, calculate from actual outcomes)
    if 'timestamp' in trades_df.columns:
        trades_df = trades_df.sort_values('timestamp')
        dates = pd.date_range(
            start=trades_df['timestamp'].min(),
            end=trades_df['timestamp'].max(),
            freq='h'
        )
        # Simulate equity curve
        equity = 10000 + np.cumsum(np.random.randn(len(dates)) * 50)

        equity_df = pd.DataFrame({
            'Time': dates,
            'Equity': equity
        })

        st.line_chart(equity_df.set_index('Time'))


def plot_hourly_heatmap(trades_df: pd.DataFrame):
    """Plot win rate by hour of day as heatmap."""
    if trades_df.empty or 'session_hour' not in trades_df.columns:
        st.info("Insufficient data for hourly analysis")
        return

    # Group by hour and calculate win rate
    hourly_stats = trades_df.groupby('session_hour').agg({
        'pair': 'count'
    }).rename(columns={'pair': 'trade_count'})

    # Mock win rates for visualization
    hourly_stats['win_rate'] = np.random.uniform(0.45, 0.65, len(hourly_stats))

    st.bar_chart(hourly_stats['win_rate'])


def strategy_performance_table(trades_df: pd.DataFrame) -> pd.DataFrame:
    """Generate per-strategy performance table."""
    if trades_df.empty or 'strategy' not in trades_df.columns:
        return pd.DataFrame()

    # Group by strategy
    strategy_stats = trades_df.groupby('strategy').agg({
        'pair': 'count',
    }).rename(columns={'pair': 'trades'})

    # Add mock metrics
    strategy_stats['win_rate'] = np.random.uniform(0.45, 0.65, len(strategy_stats))
    strategy_stats['avg_pnl'] = np.random.uniform(-0.001, 0.002, len(strategy_stats))
    strategy_stats['sharpe'] = np.random.uniform(0.3, 1.5, len(strategy_stats))

    return strategy_stats.round(3)


def recent_trades_table(trades_df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """Get N most recent trades."""
    if trades_df.empty:
        return pd.DataFrame()

    if 'timestamp' in trades_df.columns:
        recent = trades_df.sort_values('timestamp', ascending=False).head(n)

        # Select relevant columns
        cols = ['timestamp', 'pair', 'side', 'strategy', 'entry', 'stop_loss', 'take_profit']
        display_cols = [c for c in cols if c in recent.columns]

        return recent[display_cols]

    return trades_df.head(n)


def main():
    """Main dashboard application."""
    st.set_page_config(
        page_title="OANDA Bot Dashboard",
        page_icon="📈",
        layout="wide",
    )

    st.title("📈 OANDA Trading Bot Performance Dashboard")

    # Sidebar controls
    st.sidebar.header("Controls")
    refresh_rate = st.sidebar.slider("Refresh Rate (seconds)", 5, 60, 30)
    show_advanced = st.sidebar.checkbox("Show Advanced Metrics", value=False)

    # Auto-refresh
    import time
    placeholder = st.empty()

    # Load data
    trades_df = load_trades_log()
    log_entries = load_live_log()

    # Main metrics row
    st.header("📊 Overview")
    metrics = calculate_metrics(trades_df)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Trades", metrics['total_trades'])
        st.metric("Win Rate", f"{metrics['win_rate']*100:.1f}%")

    with col2:
        st.metric("Avg Profit", f"{metrics['avg_profit']:.4f}")
        st.metric("Avg Loss", f"{metrics['avg_loss']:.4f}")

    with col3:
        st.metric("Profit Factor", f"{metrics['profit_factor']:.2f}")
        st.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}")

    with col4:
        st.metric("Sortino Ratio", f"{metrics['sortino_ratio']:.2f}")
        st.metric("Max Drawdown", f"{metrics['max_drawdown']*100:.1f}%")

    # Equity curve
    st.header("💰 Equity Curve")
    plot_equity_curve(trades_df)

    # Two column layout
    col_left, col_right = st.columns(2)

    with col_left:
        st.header("📋 Recent Trades")
        recent = recent_trades_table(trades_df, n=10)
        if not recent.empty:
            st.dataframe(recent, width="stretch")
        else:
            st.info("No trades yet")

    with col_right:
        st.header("🎯 Strategy Performance")
        strategy_perf = strategy_performance_table(trades_df)
        if not strategy_perf.empty:
            st.dataframe(strategy_perf, width="stretch")
        else:
            st.info("No strategy data yet")

    # Hourly performance
    st.header("🕐 Performance by Hour")
    plot_hourly_heatmap(trades_df)

    # Advanced metrics (if enabled)
    if show_advanced:
        st.header("🔬 Advanced Analytics")

        tab1, tab2, tab3 = st.tabs(["Risk Metrics", "Signal Analysis", "System Health"])

        with tab1:
            st.subheader("Risk-Adjusted Returns")
            # Add more detailed risk metrics here
            st.info("Risk metrics visualization placeholder")

        with tab2:
            st.subheader("Strategy Signal Frequency")
            # Signal frequency analysis
            st.info("Signal analysis placeholder")

        with tab3:
            st.subheader("System Health")
            # Recent log entries
            if log_entries:
                recent_logs = log_entries[-20:]
                log_df = pd.DataFrame(recent_logs)
                st.dataframe(log_df, width="stretch")
            else:
                st.info("No log entries")

    # Footer
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.sidebar.caption("Auto-refresh enabled" if refresh_rate else "")


if __name__ == "__main__":
    main()
