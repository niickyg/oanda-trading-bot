"""
integrations.py
---------------

Integration utilities for new features in main.py.

Provides helper functions to integrate:
- Market regime detection
- Strategy correlation analysis
- Enhanced monitoring

Usage in main.py:
    from oanda_bot.integrations import setup_enhancements, enhance_signal_handling
"""

from typing import Dict, Optional, List
import logging
from .regime import MarketRegime
from .correlation import StrategyCorrelationAnalyzer

logger = logging.getLogger(__name__)

# Global instances (initialized by setup_enhancements)
regime_detector: Optional[MarketRegime] = None
correlation_analyzer: Optional[StrategyCorrelationAnalyzer] = None


def setup_enhancements():
    """
    Initialize enhanced features.

    Call this once during bot startup in main.py:
        from oanda_bot.integrations import setup_enhancements
        setup_enhancements()
    """
    global regime_detector, correlation_analyzer

    logger.info("Setting up enhanced features...")

    # Initialize market regime detector
    regime_detector = MarketRegime(
        adx_period=14,
        adx_trending_threshold=25.0,
        volatility_window=50,
    )
    logger.info("Market regime detector initialized")

    # Initialize correlation analyzer
    correlation_analyzer = StrategyCorrelationAnalyzer(window_size=500)
    logger.info("Strategy correlation analyzer initialized")


def get_market_regime(pair: str, candles: list, current_atr: float) -> Dict:
    """
    Detect market regime for a currency pair.

    Args:
        pair: Currency pair (e.g., "EUR_USD")
        candles: List of OANDA candle dictionaries
        current_atr: Current ATR value

    Returns:
        Regime dictionary from MarketRegime.detect_regime()
    """
    if regime_detector is None:
        logger.warning("Regime detector not initialized, call setup_enhancements() first")
        return {"regime": "ranging"}

    try:
        regime = regime_detector.detect_regime(candles, current_atr)
        return regime
    except Exception as e:
        logger.error(f"Error detecting regime for {pair}: {e}", exc_info=True)
        return {"regime": "ranging"}


def should_enable_strategy_for_regime(
    strategy_name: str,
    regime: Dict,
) -> bool:
    """
    Check if strategy should be enabled in current regime.

    Args:
        strategy_name: Name of the strategy
        regime: Regime dictionary

    Returns:
        True if strategy should be enabled
    """
    if regime_detector is None:
        return True  # Default to enabled

    try:
        return regime_detector.should_enable_strategy(strategy_name, regime)
    except Exception as e:
        logger.error(f"Error checking regime compatibility: {e}", exc_info=True)
        return True


def log_strategy_signal(
    pair: str,
    strategy_name: str,
    signal: Optional[str],
    timestamp: float,
) -> None:
    """
    Log a strategy signal for correlation tracking.

    Args:
        pair: Currency pair
        strategy_name: Strategy name
        signal: "BUY", "SELL", or None
        timestamp: Unix timestamp
    """
    if correlation_analyzer is None:
        return

    try:
        correlation_analyzer.log_signal(pair, strategy_name, signal, timestamp)
    except Exception as e:
        logger.error(f"Error logging signal: {e}", exc_info=True)


def log_trade_outcome(strategy_name: str, win: bool, pnl: float) -> None:
    """
    Log trade outcome for correlation analysis.

    Args:
        strategy_name: Strategy name
        win: True if profitable
        pnl: Profit/loss amount
    """
    if correlation_analyzer is None:
        return

    try:
        correlation_analyzer.log_trade_outcome(strategy_name, win, pnl)
    except Exception as e:
        logger.error(f"Error logging trade outcome: {e}", exc_info=True)


def get_strategy_portfolio_recommendation(
    max_strategies: int = 5,
) -> List[tuple]:
    """
    Get recommended strategy portfolio based on correlation.

    Args:
        max_strategies: Maximum strategies to recommend

    Returns:
        List of (strategy_name, weight) tuples
    """
    if correlation_analyzer is None:
        logger.warning("Correlation analyzer not initialized")
        return []

    try:
        portfolio = correlation_analyzer.recommend_strategy_portfolio(
            max_strategies=max_strategies,
            min_correlation=0.5,
        )
        return portfolio
    except Exception as e:
        logger.error(f"Error getting portfolio recommendation: {e}", exc_info=True)
        return []


def export_correlation_report(filepath: str = "correlation_report.json") -> None:
    """
    Export strategy correlation analysis to file.

    Args:
        filepath: Path to save report
    """
    if correlation_analyzer is None:
        logger.warning("Correlation analyzer not initialized")
        return

    try:
        correlation_analyzer.calculate_correlation_matrix()
        correlation_analyzer.export_correlation_report(filepath)
        logger.info(f"Exported correlation report to {filepath}")
    except Exception as e:
        logger.error(f"Error exporting correlation report: {e}", exc_info=True)


def enhance_signal_handling(
    pair: str,
    strategy_name: str,
    signal: Optional[str],
    candles: list,
    current_atr: float,
    timestamp: float,
) -> tuple:
    """
    Enhanced signal handling with regime detection and correlation tracking.

    This is a drop-in enhancement for the signal processing in main.py.

    Args:
        pair: Currency pair
        strategy_name: Strategy name
        signal: Strategy signal ("BUY", "SELL", or None)
        candles: Historical candles for regime detection
        current_atr: Current ATR value
        timestamp: Current timestamp

    Returns:
        Tuple of (should_execute, regime_info)
        - should_execute: bool, whether to execute this signal
        - regime_info: dict with regime details
    """
    # Log the signal for correlation analysis
    log_strategy_signal(pair, strategy_name, signal, timestamp)

    # No signal to process
    if not signal:
        return False, {}

    # Detect market regime
    regime = get_market_regime(pair, candles, current_atr)

    # Check if strategy is appropriate for current regime
    should_execute = should_enable_strategy_for_regime(strategy_name, regime)

    if not should_execute:
        logger.debug(
            f"{pair} | {strategy_name} | Signal {signal} skipped due to regime: {regime['regime']}"
        )

    return should_execute, regime


def periodic_correlation_update(interval_seconds: int = 1800):
    """
    Periodically export correlation reports.

    Call this in a background thread:
        Thread(target=periodic_correlation_update, daemon=True).start()

    Args:
        interval_seconds: How often to export (default 30 minutes)
    """
    import time

    while True:
        try:
            time.sleep(interval_seconds)
            export_correlation_report()
            logger.info("Periodic correlation report exported")
        except Exception as e:
            logger.error(f"Error in periodic correlation update: {e}", exc_info=True)


def get_regime_statistics() -> Dict:
    """
    Get statistics about recent market regimes.

    Returns:
        Dictionary with regime distribution statistics
    """
    if regime_detector is None:
        return {}

    try:
        stats = regime_detector.get_regime_statistics()
        return stats
    except Exception as e:
        logger.error(f"Error getting regime statistics: {e}", exc_info=True)
        return {}


def print_correlation_matrix() -> str:
    """
    Get formatted correlation matrix for logging.

    Returns:
        Formatted correlation matrix string
    """
    if correlation_analyzer is None:
        return "Correlation analyzer not initialized"

    try:
        return correlation_analyzer.print_correlation_matrix()
    except Exception as e:
        logger.error(f"Error printing correlation matrix: {e}", exc_info=True)
        return "Error generating correlation matrix"
