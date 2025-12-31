# Bot Status & Configuration Notes for Future Claude Sessions

**Last Updated**: 2025-12-29 08:35 UTC
**Status**: ✅ OPERATIONAL - Bot is trading live in paper mode

## Recent Critical Fix (2025-12-29)

### Issue
Bot was running but not executing any trades despite strategies generating signals.

### Root Cause
`MIN_ATR_THRESHOLD = 0.0005` (5 pips) was too high for 2-second bars. Actual ATR on 2-second timeframe is 0.0001-0.0003 (1-3 pips), so **100% of trading signals were being blocked** by the volatility filter.

### Solution
Changed `MIN_ATR_THRESHOLD` from `0.0005` to `0.0001` in `oanda_bot/main.py:341`

```python
MIN_ATR_THRESHOLD = 0.0001  # ultra-low for 2-second bars (1 pip)
```

### Verification
After fix, bot immediately executed 5 trades in 2 minutes and hit max position limit.

## Current Configuration

### Trading Parameters
- **Timeframe**: 2-second bars (ultra-fast scalping)
- **BAR_SECONDS**: 2
- **MIN_ATR_THRESHOLD**: 0.0001 (1 pip) - CRITICAL for 2-second bars
- **Max Positions**: 5 total concurrent positions
- **Max Per Pair**: 1 position per pair
- **Cooldown**: 30 seconds between signals per pair/strategy
- **Mode**: Paper trading with $1000 starting equity

### Active Strategies (4)
1. **TrendMA** - Currently most active, generating majority of signals
2. **MicroReversion** - Active on EUR_CAD
3. **RSIReversion** - Active
4. **OrderFlow** - Active

### Inactive Strategies (2)
- BollingerSqueeze - Disabled
- VolatilityGrid - Fails with 'close' error on validation

### Trading Pairs (10)
EUR_USD, USD_JPY, GBP_USD, AUD_USD, USD_CAD, EUR_CAD, GBP_CAD, EUR_AUD, AUD_NZD, USD_CHF

### Risk Management
- **Stop Loss**: 2x ATR
- **Take Profit**: 3x ATR
- **Position Size**: 1000 units per trade (fixed)
- **Emergency Stop**: Max drawdown protection enabled

## Key Files

### Main Trading Logic
- `/home/user0/oandabot16/oanda_bot/oanda_bot/main.py`
  - Line 341: MIN_ATR_THRESHOLD (CRITICAL - must stay at 0.0001 for 2s bars)
  - Line 676: ATR rejection logging
  - Line 794-801: Bar processing counter
  - Line 857-868: Signal generation logging

### Configuration
- `/home/user0/oandabot16/oanda_bot/live_config.json` - Current strategy params
- `/home/user0/oandabot16/oanda_bot/shared/best_params.json` - Optimized params (hot-swapped by researcher)

### Logs
- `/home/user0/oandabot16/oanda_bot/bot_live_output.log` - Current session logs
- `/home/user0/oandabot16/oanda_bot/live_trading.log` - Historical logs
- `/home/user0/oandabot16/oanda_bot/trades_log.csv` - Trade execution history

## Docker Setup

```yaml
services:
  bot:           # Main trading bot
    - Port 8001:8000
    - Healthcheck: curl localhost:8000/health every 30s
    - Command: python -m oanda_bot.main

  researcher:    # Optimization loop (runs every 30 min)
    - Optimizes strategies on EUR_USD, USD_JPY (M5, 1500 bars)
    - Updates /shared/best_params.json for hot-swap
```

### Restart Commands
```bash
docker build -t localhost/oanda-bot:latest .
docker-compose up -d --force-recreate bot
docker-compose logs -f --tail=50 bot
```

## Known Issues

1. **VolatilityGrid Strategy** - Fails validation with KeyError: 'close'
   - Status: Disabled, not blocking trading
   - Location: Validation backtest in main.py startup

2. **Deprecation Warning** - `datetime.utcnow()` in main.py:691
   - Status: Non-critical, scheduled for removal in future Python version
   - Fix: Replace with `datetime.now(datetime.UTC)`

## Important Notes for Future Sessions

### DO NOT Change These Without Understanding Impact:
- ✋ **MIN_ATR_THRESHOLD**: Calibrated for 2-second bars, don't increase
- ✋ **BAR_SECONDS**: Changing this requires recalibrating MIN_ATR_THRESHOLD
- ✋ **Max positions**: Set to 5 for risk management

### Debugging Checklist if Bot Stops Trading:
1. Check `docker-compose logs bot` for [BLOCKED-ATR] messages
2. Verify MIN_ATR_THRESHOLD is still 0.0001
3. Check bar processing counter is incrementing
4. Look for [SIGNAL] messages (strategies generating signals)
5. Verify ATR values in logs (should be 0.0001-0.0003 for 2s bars)

### Recent Performance (2025-12-29 08:33)
```
Trades executed in first 2 minutes:
- GBP_USD SELL @ 1.34846 (ATR: 0.00026)
- USD_CHF BUY @ 0.78894 (ATR: 0.00012)
- EUR_CAD BUY @ 1.61112 (ATR: 0.00024)
- AUD_NZD SELL @ 1.15338 (ATR: 0.00020)
- GBP_CAD SELL @ 1.84518 (ATR: 0.00030)
```
All trades had proper SL/TP, hit max position limit as expected.

## Architecture Notes

The bot uses:
- **OANDA PricingStream API** for real-time tick data
- **2-second OHLC aggregation** from ticks
- **StrategyManager** coordinating multiple strategies
- **JSON structured logging** with pythonJsonLogger
- **CSV trade logging** for performance tracking
- **Docker containerization** with health checks
- **Hot-swap config** from researcher optimization loop

## Next Steps (if requested by user)

Potential improvements not yet implemented:
- [ ] Monitor 24-hour performance metrics
- [ ] Fix VolatilityGrid strategy KeyError
- [ ] Replace deprecated datetime.utcnow()
- [ ] Analyze P/L by strategy
- [ ] Consider dynamic position sizing
- [ ] Scale to live trading (requires user approval)
