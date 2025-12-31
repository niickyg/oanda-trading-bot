"""
regime.py
---------

Market regime detection for adaptive strategy selection.

Classifies market conditions as:
- Trending (strong directional movement)
- Ranging (sideways consolidation)
- Volatile (high ATR)
- Quiet (low ATR)

Enables regime-aware strategy selection:
- MACD/Trend strategies work best in trending markets
- RSI/Mean-reversion strategies work best in ranging markets
"""

from typing import Dict, Optional, Tuple
import numpy as np
from collections import deque
import logging

logger = logging.getLogger(__name__)


class MarketRegime:
    """Market regime classification and tracking."""

    # Regime constants
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    QUIET = "quiet"

    def __init__(
        self,
        adx_period: int = 14,
        adx_trending_threshold: float = 25.0,
        volatility_window: int = 50,
        volatility_percentile_high: float = 75.0,
        volatility_percentile_low: float = 25.0,
    ):
        """
        Initialize regime detector.

        Args:
            adx_period: Period for ADX calculation
            adx_trending_threshold: ADX above this = trending market
            volatility_window: Window for volatility percentile calculation
            volatility_percentile_high: Percentile threshold for "volatile"
            volatility_percentile_low: Percentile threshold for "quiet"
        """
        self.adx_period = adx_period
        self.adx_trending_threshold = adx_trending_threshold
        self.volatility_window = volatility_window
        self.volatility_percentile_high = volatility_percentile_high
        self.volatility_percentile_low = volatility_percentile_low

        # Track historical regimes for analysis
        self.regime_history: deque = deque(maxlen=1000)
        self.atr_history: deque = deque(maxlen=volatility_window)

    def calculate_adx(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        period: int = 14,
    ) -> Tuple[float, float, float]:
        """
        Calculate ADX (Average Directional Index) and +DI/-DI.

        Returns:
            Tuple of (adx, plus_di, minus_di)
        """
        if len(highs) < period + 1:
            return 0.0, 0.0, 0.0

        # Calculate True Range
        high_low = highs[1:] - lows[1:]
        high_close = np.abs(highs[1:] - closes[:-1])
        low_close = np.abs(lows[1:] - closes[:-1])
        tr = np.maximum(high_low, np.maximum(high_close, low_close))

        # Calculate directional movement
        up_move = highs[1:] - highs[:-1]
        down_move = lows[:-1] - lows[1:]

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        # Smooth with Wilder's moving average
        def wilders_smooth(arr, period):
            result = np.zeros_like(arr)
            result[period - 1] = arr[:period].mean()
            for i in range(period, len(arr)):
                result[i] = (result[i - 1] * (period - 1) + arr[i]) / period
            return result

        tr_smooth = wilders_smooth(tr, period)
        plus_dm_smooth = wilders_smooth(plus_dm, period)
        minus_dm_smooth = wilders_smooth(minus_dm, period)

        # Calculate DI
        plus_di = 100 * plus_dm_smooth / tr_smooth
        minus_di = 100 * minus_dm_smooth / tr_smooth

        # Calculate DX and ADX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = wilders_smooth(dx, period)

        return float(adx[-1]), float(plus_di[-1]), float(minus_di[-1])

    def calculate_atr_percentile(self, current_atr: float) -> float:
        """
        Calculate what percentile the current ATR is in.

        Args:
            current_atr: Current ATR value

        Returns:
            Percentile (0-100)
        """
        if len(self.atr_history) < 10:
            return 50.0  # neutral until enough data

        atr_array = np.array(self.atr_history)
        percentile = (atr_array < current_atr).sum() / len(atr_array) * 100
        return float(percentile)

    def detect_regime(
        self,
        candles: list,
        current_atr: Optional[float] = None,
    ) -> Dict[str, any]:
        """
        Detect current market regime from candle data.

        Args:
            candles: List of OANDA candle dictionaries
            current_atr: Current ATR value (optional, will calculate if not provided)

        Returns:
            Dictionary with:
            {
                "regime": str,  # primary regime classification
                "adx": float,
                "plus_di": float,
                "minus_di": float,
                "atr_percentile": float,
                "is_trending": bool,
                "is_ranging": bool,
                "is_volatile": bool,
                "is_quiet": bool,
                "trend_direction": str,  # "up", "down", or "none"
            }
        """
        if len(candles) < self.adx_period + 2:
            return self._default_regime()

        # Extract OHLC data
        highs = np.array([float(c["mid"]["h"]) for c in candles], dtype=np.float64)
        lows = np.array([float(c["mid"]["l"]) for c in candles], dtype=np.float64)
        closes = np.array([float(c["mid"]["c"]) for c in candles], dtype=np.float64)

        # Calculate ADX
        adx, plus_di, minus_di = self.calculate_adx(highs, lows, closes, self.adx_period)

        # Calculate or use provided ATR
        if current_atr is None:
            # Simple ATR calculation
            high_low = highs[1:] - lows[1:]
            high_close = np.abs(highs[1:] - closes[:-1])
            low_close = np.abs(lows[1:] - closes[:-1])
            tr = np.maximum(high_low, np.maximum(high_close, low_close))
            current_atr = float(tr[-self.adx_period:].mean())

        # Track ATR for percentile calculation
        self.atr_history.append(current_atr)
        atr_percentile = self.calculate_atr_percentile(current_atr)

        # Classify regime
        is_trending = adx > self.adx_trending_threshold
        is_volatile = atr_percentile > self.volatility_percentile_high
        is_quiet = atr_percentile < self.volatility_percentile_low
        is_ranging = not is_trending and not is_volatile and not is_quiet

        # Determine primary regime
        if is_trending:
            if plus_di > minus_di:
                regime = self.TRENDING_UP
                trend_direction = "up"
            else:
                regime = self.TRENDING_DOWN
                trend_direction = "down"
        elif is_volatile:
            regime = self.VOLATILE
            trend_direction = "none"
        elif is_quiet:
            regime = self.QUIET
            trend_direction = "none"
        else:
            regime = self.RANGING
            trend_direction = "none"

        result = {
            "regime": regime,
            "adx": adx,
            "plus_di": plus_di,
            "minus_di": minus_di,
            "atr_percentile": atr_percentile,
            "is_trending": is_trending,
            "is_ranging": is_ranging,
            "is_volatile": is_volatile,
            "is_quiet": is_quiet,
            "trend_direction": trend_direction,
        }

        self.regime_history.append(result)
        logger.debug(
            f"Regime detected: {regime}, ADX={adx:.1f}, ATR%ile={atr_percentile:.1f}"
        )

        return result

    def _default_regime(self) -> Dict[str, any]:
        """Return default regime when insufficient data."""
        return {
            "regime": self.RANGING,
            "adx": 0.0,
            "plus_di": 0.0,
            "minus_di": 0.0,
            "atr_percentile": 50.0,
            "is_trending": False,
            "is_ranging": True,
            "is_volatile": False,
            "is_quiet": False,
            "trend_direction": "none",
        }

    def should_enable_strategy(self, strategy_name: str, regime: Dict[str, any]) -> bool:
        """
        Determine if a strategy should be enabled in the current regime.

        Args:
            strategy_name: Name of the strategy
            regime: Regime dictionary from detect_regime()

        Returns:
            True if strategy should be enabled
        """
        # Map strategies to their preferred regimes
        strategy_preferences = {
            "MACDTrend": ["trending_up", "trending_down"],
            "TrendMA": ["trending_up", "trending_down"],
            "Breakout": ["volatile", "trending_up", "trending_down"],
            "RSIReversion": ["ranging", "quiet"],
            "BollingerSqueeze": ["ranging", "volatile"],
            "VolatilityGrid": ["volatile"],
        }

        preferred_regimes = strategy_preferences.get(strategy_name, [])

        # If no preference defined, enable by default
        if not preferred_regimes:
            return True

        # Enable if current regime matches any preferred regime
        return regime["regime"] in preferred_regimes

    def get_regime_statistics(self) -> Dict[str, any]:
        """
        Get statistics about recent regime distribution.

        Returns:
            Dictionary with regime percentages and counts
        """
        if not self.regime_history:
            return {}

        regimes = [r["regime"] for r in self.regime_history]
        total = len(regimes)

        stats = {
            "total_samples": total,
            "trending_up_pct": regimes.count(self.TRENDING_UP) / total * 100,
            "trending_down_pct": regimes.count(self.TRENDING_DOWN) / total * 100,
            "ranging_pct": regimes.count(self.RANGING) / total * 100,
            "volatile_pct": regimes.count(self.VOLATILE) / total * 100,
            "quiet_pct": regimes.count(self.QUIET) / total * 100,
        }

        # Add average ADX per regime
        for regime_type in [self.TRENDING_UP, self.TRENDING_DOWN, self.RANGING,
                            self.VOLATILE, self.QUIET]:
            regime_samples = [r for r in self.regime_history if r["regime"] == regime_type]
            if regime_samples:
                avg_adx = np.mean([r["adx"] for r in regime_samples])
                stats[f"{regime_type}_avg_adx"] = float(avg_adx)

        return stats
