

# oanda_bot

A Forex trading bot with an automated, self‑improving loop.

## Self‑Improving Loop

This project features a self‑improving cycle that continuously refines strategy parameters and risk controls:

1. **Logging**  
   Each run of the bot appends trade results and performance metrics to `trades.log` for later review.

2. **Nightly Optimization**  
   A daily cron job invokes `optimize.py` at 2 AM local time to search for the highest‐performing parameter set against recent candle data.

3. **Loading Parameters**  
   On startup, the bot loads the last‐saved `best_params.json` and applies these optimized parameters for signal generation.

4. **Adaptive Risk Control**  
   During live trading, the bot maintains a rolling window of the last 100 trades. It calculates the current win rate; if it drops below 50%, the risk fraction is reduced to 0.5%, otherwise it uses 1%.

## Cron Job Setup

To schedule the nightly optimization, add this entry to your crontab (edit with `crontab -e`):

```cron
# Run optimize.py every day at 2:00 AM
0 2 * * * cd /Users/nickguerriero/Projects/oanda_bot && .venv/bin/python optimize.py >> optimize.log 2>&1
```
