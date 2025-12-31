"""
common/session_filters.py
--------------------------

Trading session identification and filtering utilities.

Forex markets exhibit distinct volatility and behavior patterns across
different global trading sessions. This module provides utilities to:

1. Identify current trading session
2. Filter strategies by optimal session
3. Adjust position sizing based on session volatility
4. Calculate session-specific statistics

Sessions (UTC)
--------------
- Asia:    23:00-08:00 (Tokyo, Singapore, Hong Kong)
- London:  08:00-13:00 (European markets)
- Overlap: 13:00-16:00 (London + NY, highest liquidity)
- NY:      16:00-21:00 (US markets after London close)
- After:   21:00-23:00 (Low liquidity)
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Dict
from enum import Enum


class TradingSession(Enum):
    """Enumeration of forex trading sessions."""
    ASIA = "Asia"
    LONDON = "London"
    OVERLAP = "Overlap"
    NY = "NY"
    AFTER_HOURS = "After_Hours"


# ============================================================================
# Session Identification
# ============================================================================

def get_current_session(hour: Optional[int] = None) -> TradingSession:
    """
    Identify current trading session based on UTC hour.

    Parameters
    ----------
    hour : int, optional
        Hour in UTC (0-23). If None, uses current UTC time.

    Returns
    -------
    TradingSession
        Current trading session enum.

    Examples
    --------
    >>> get_current_session(9)   # 09:00 UTC
    <TradingSession.LONDON: 'London'>

    >>> get_current_session(14)  # 14:00 UTC
    <TradingSession.OVERLAP: 'Overlap'>

    >>> get_current_session(2)   # 02:00 UTC
    <TradingSession.ASIA: 'Asia'>
    """
    if hour is None:
        hour = datetime.utcnow().hour

    # Session boundaries (UTC)
    if 23 <= hour or hour < 8:
        return TradingSession.ASIA
    elif 8 <= hour < 13:
        return TradingSession.LONDON
    elif 13 <= hour < 16:
        return TradingSession.OVERLAP
    elif 16 <= hour < 21:
        return TradingSession.NY
    else:  # 21:00-23:00
        return TradingSession.AFTER_HOURS


def is_high_volatility_session(hour: Optional[int] = None) -> bool:
    """
    Check if current time is a high-volatility trading session.

    High volatility sessions: London, Overlap, NY (08:00-21:00 UTC)

    Parameters
    ----------
    hour : int, optional
        Hour in UTC. If None, uses current time.

    Returns
    -------
    bool
        True if high volatility session, False otherwise.
    """
    session = get_current_session(hour)
    return session in [TradingSession.LONDON, TradingSession.OVERLAP, TradingSession.NY]


def is_low_volatility_session(hour: Optional[int] = None) -> bool:
    """
    Check if current time is a low-volatility trading session.

    Low volatility sessions: Asia, After Hours

    Parameters
    ----------
    hour : int, optional
        Hour in UTC. If None, uses current time.

    Returns
    -------
    bool
        True if low volatility session, False otherwise.
    """
    session = get_current_session(hour)
    return session in [TradingSession.ASIA, TradingSession.AFTER_HOURS]


def is_overlap_session(hour: Optional[int] = None) -> bool:
    """
    Check if current time is London/NY overlap (13:00-16:00 UTC).

    This is the highest liquidity and volatility period.

    Parameters
    ----------
    hour : int, optional
        Hour in UTC. If None, uses current time.

    Returns
    -------
    bool
        True if overlap session, False otherwise.
    """
    if hour is None:
        hour = datetime.utcnow().hour
    return 13 <= hour < 16


# ============================================================================
# Strategy-Specific Session Filters
# ============================================================================

def is_favorable_for_trend_following(hour: Optional[int] = None) -> bool:
    """
    Check if current session is favorable for trend-following strategies.

    Best sessions: London, Overlap, NY (08:00-21:00 UTC)
    These periods have strong directional moves and good liquidity.

    Parameters
    ----------
    hour : int, optional
        Hour in UTC. If None, uses current time.

    Returns
    -------
    bool
        True if favorable for trends, False otherwise.
    """
    if hour is None:
        hour = datetime.utcnow().hour
    return 8 <= hour < 21


def is_favorable_for_mean_reversion(hour: Optional[int] = None) -> bool:
    """
    Check if current session is favorable for mean reversion strategies.

    Best session: Asia (23:00-08:00 UTC)
    Range-bound behavior with lower volatility suits mean reversion.

    Parameters
    ----------
    hour : int, optional
        Hour in UTC. If None, uses current time.

    Returns
    -------
    bool
        True if favorable for mean reversion, False otherwise.
    """
    if hour is None:
        hour = datetime.utcnow().hour
    return (23 <= hour) or (hour < 8)


def is_favorable_for_breakout(hour: Optional[int] = None) -> bool:
    """
    Check if current session is favorable for breakout strategies.

    Best sessions: London open (08:00-10:00) and Overlap (13:00-16:00 UTC)

    Parameters
    ----------
    hour : int, optional
        Hour in UTC. If None, uses current time.

    Returns
    -------
    bool
        True if favorable for breakouts, False otherwise.
    """
    if hour is None:
        hour = datetime.utcnow().hour

    # London open or Overlap
    return (8 <= hour < 10) or (13 <= hour < 16)


def is_favorable_for_scalping(hour: Optional[int] = None) -> bool:
    """
    Check if current session is favorable for scalping strategies.

    Best session: Overlap (13:00-16:00 UTC)
    Highest liquidity, tightest spreads, rapid price movements.

    Parameters
    ----------
    hour : int, optional
        Hour in UTC. If None, uses current time.

    Returns
    -------
    bool
        True if favorable for scalping, False otherwise.
    """
    return is_overlap_session(hour)


# ============================================================================
# Position Sizing by Session
# ============================================================================

def get_session_volatility_multiplier(hour: Optional[int] = None) -> float:
    """
    Get position sizing multiplier based on session volatility.

    Higher volatility = lower position size (same dollar risk).
    Lower volatility = higher position size.

    Parameters
    ----------
    hour : int, optional
        Hour in UTC. If None, uses current time.

    Returns
    -------
    float
        Position size multiplier (0.5 to 1.5)

    Examples
    --------
    Overlap session (high vol):     0.7x position size
    London/NY session (medium vol): 1.0x position size
    Asia session (low vol):         1.2x position size
    """
    session = get_current_session(hour)

    # Multipliers based on typical volatility
    multipliers = {
        TradingSession.OVERLAP: 0.7,      # Highest volatility -> reduce size
        TradingSession.LONDON: 0.9,       # High volatility
        TradingSession.NY: 1.0,           # Medium-high volatility
        TradingSession.ASIA: 1.2,         # Low volatility -> increase size
        TradingSession.AFTER_HOURS: 0.5,  # Very low liquidity -> reduce size
    }

    return multipliers.get(session, 1.0)


def get_session_spread_cost_multiplier(hour: Optional[int] = None) -> float:
    """
    Get expected spread cost multiplier by session.

    Tighter spreads during high liquidity = lower costs.
    Wider spreads during low liquidity = higher costs.

    Parameters
    ----------
    hour : int, optional
        Hour in UTC. If None, uses current time.

    Returns
    -------
    float
        Spread multiplier relative to average (0.8 to 2.0)
    """
    session = get_current_session(hour)

    spread_multipliers = {
        TradingSession.OVERLAP: 0.8,      # Tightest spreads
        TradingSession.LONDON: 0.9,       # Tight spreads
        TradingSession.NY: 1.0,           # Average spreads
        TradingSession.ASIA: 1.3,         # Wider spreads
        TradingSession.AFTER_HOURS: 2.0,  # Very wide spreads
    }

    return spread_multipliers.get(session, 1.0)


# ============================================================================
# Session Statistics Helper
# ============================================================================

def get_session_characteristics(session: Optional[TradingSession] = None) -> Dict[str, any]:
    """
    Get detailed characteristics of a trading session.

    Parameters
    ----------
    session : TradingSession, optional
        Session to query. If None, uses current session.

    Returns
    -------
    dict
        Session characteristics including:
        - name: Session name
        - hours_utc: Hour range in UTC
        - volatility: "High", "Medium", "Low"
        - liquidity: "High", "Medium", "Low"
        - spread: Typical spread multiplier
        - best_for: List of strategy types
    """
    if session is None:
        session = get_current_session()

    characteristics = {
        TradingSession.ASIA: {
            "name": "Asia",
            "hours_utc": "23:00-08:00",
            "volatility": "Low",
            "liquidity": "Medium",
            "spread": 1.3,
            "best_for": ["Mean Reversion", "Range Trading"],
            "avoid": ["Breakout", "Trend Following"],
        },
        TradingSession.LONDON: {
            "name": "London",
            "hours_utc": "08:00-13:00",
            "volatility": "High",
            "liquidity": "High",
            "spread": 0.9,
            "best_for": ["Trend Following", "Breakout"],
            "avoid": ["Mean Reversion"],
        },
        TradingSession.OVERLAP: {
            "name": "Overlap (London + NY)",
            "hours_utc": "13:00-16:00",
            "volatility": "Very High",
            "liquidity": "Very High",
            "spread": 0.8,
            "best_for": ["Scalping", "Breakout", "Momentum"],
            "avoid": ["Range Trading"],
        },
        TradingSession.NY: {
            "name": "New York",
            "hours_utc": "16:00-21:00",
            "volatility": "Medium-High",
            "liquidity": "High",
            "spread": 1.0,
            "best_for": ["Trend Following", "News Trading"],
            "avoid": [],
        },
        TradingSession.AFTER_HOURS: {
            "name": "After Hours",
            "hours_utc": "21:00-23:00",
            "volatility": "Low",
            "liquidity": "Low",
            "spread": 2.0,
            "best_for": [],
            "avoid": ["All strategies - poor liquidity"],
        },
    }

    return characteristics.get(session, {})


# ============================================================================
# Strategy Filter Decorator
# ============================================================================

def session_filter(strategy_type: str):
    """
    Decorator to add session filtering to strategy methods.

    Parameters
    ----------
    strategy_type : str
        "trend", "mean_reversion", "breakout", "scalping"

    Examples
    --------
    @session_filter("trend")
    def next_signal(self, bars):
        # Will only execute during favorable sessions
        return signal
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            hour = datetime.utcnow().hour

            # Check if favorable session
            if strategy_type == "trend":
                if not is_favorable_for_trend_following(hour):
                    return None
            elif strategy_type == "mean_reversion":
                if not is_favorable_for_mean_reversion(hour):
                    return None
            elif strategy_type == "breakout":
                if not is_favorable_for_breakout(hour):
                    return None
            elif strategy_type == "scalping":
                if not is_favorable_for_scalping(hour):
                    return None

            # Execute strategy if session is favorable
            return func(*args, **kwargs)

        return wrapper
    return decorator


# ============================================================================
# Quick Test
# ============================================================================

if __name__ == "__main__":
    print("Session Filter Utilities - Test\n")
    print("="*60)

    for test_hour in [0, 3, 6, 9, 12, 14, 17, 20, 22]:
        session = get_current_session(test_hour)
        chars = get_session_characteristics(session)

        print(f"\n{test_hour:02d}:00 UTC → {session.value}")
        print(f"  Volatility: {chars.get('volatility', 'N/A')}")
        print(f"  Liquidity: {chars.get('liquidity', 'N/A')}")
        print(f"  Best for: {', '.join(chars.get('best_for', []))}")

        # Check filters
        print(f"  Trend following: {'✓' if is_favorable_for_trend_following(test_hour) else '✗'}")
        print(f"  Mean reversion: {'✓' if is_favorable_for_mean_reversion(test_hour) else '✗'}")
        print(f"  Breakout: {'✓' if is_favorable_for_breakout(test_hour) else '✗'}")

    print("\n" + "="*60)
