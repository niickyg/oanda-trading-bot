#!/bin/bash
# Monitor bot performance with moderate settings

echo "=== Starting Bot Monitor ==="
echo "Time: $(date)"
echo ""

# Count initial trades
INITIAL_TRADES=$(docker exec oanda_bot-bot-1 cat /app/trades_log.csv | wc -l)
echo "Initial trades in log: $INITIAL_TRADES"
echo ""

# Monitor for 12 minutes (720 seconds)
for i in {1..24}; do
    echo "=== Checkpoint $i ($(date +%H:%M:%S)) ==="

    # Recent signals and trades
    echo "Last 10 signals/trades:"
    docker logs oanda_bot-bot-1 --tail 200 2>&1 | grep -E "\[SIGNAL\]|trade\.executed|trade\.closed" | tail -10
    echo ""

    # Trade count
    CURRENT_TRADES=$(docker exec oanda_bot-bot-1 cat /app/trades_log.csv | wc -l)
    NEW_TRADES=$((CURRENT_TRADES - INITIAL_TRADES))
    echo "New trades executed: $NEW_TRADES"
    echo ""

    # Check for errors
    ERROR_COUNT=$(docker logs oanda_bot-bot-1 --tail 200 2>&1 | grep -c "ERROR")
    WARNING_COUNT=$(docker logs oanda_bot-bot-1 --tail 200 2>&1 | grep -c "WARNING")
    echo "Recent errors: $ERROR_COUNT, warnings: $WARNING_COUNT"
    echo ""

    # Strategy breakdown
    echo "Strategy signal breakdown (last 100 signals):"
    docker logs oanda_bot-bot-1 --tail 500 2>&1 | grep "\[SIGNAL\]" | tail -100 | awk '{print $6}' | sort | uniq -c | sort -rn
    echo ""

    echo "---"
    sleep 30
done

echo "=== Monitor Complete ==="
