# OANDA Bot Deployment Guide

Comprehensive guide for deploying the OANDA trading bot in production environments.

---

## Table of Contents

1. [Production Checklist](#production-checklist)
2. [Security Best Practices](#security-best-practices)
3. [Docker Deployment](#docker-deployment)
4. [Monitoring Setup](#monitoring-setup)
5. [Backup Strategies](#backup-strategies)
6. [Disaster Recovery](#disaster-recovery)
7. [Scaling Considerations](#scaling-considerations)
8. [Maintenance](#maintenance)

---

## Production Checklist

Before deploying to production, ensure all items are complete:

### Pre-Deployment

- [ ] **Testing**
  - [ ] Run full backtest suite on 2+ years of data
  - [ ] Test on practice account for minimum 2 weeks
  - [ ] Verify all strategies produce positive expectancy
  - [ ] Confirm win rate meets target thresholds (50-60%)
  - [ ] Test with small capital first ($100-$500)

- [ ] **Configuration**
  - [ ] `.env` file properly configured with live credentials
  - [ ] `OANDA_ENV=live` for production
  - [ ] `RISK_FRAC` set conservatively (0.01-0.02)
  - [ ] `live_config.json` optimized for current market conditions
  - [ ] Error webhook configured for alerts

- [ ] **Security**
  - [ ] API token stored securely (not in Git)
  - [ ] Environment files have correct permissions (600)
  - [ ] Docker secrets configured if using Swarm/Kubernetes
  - [ ] Network access restricted (firewall rules)
  - [ ] SSL/TLS enabled for all external connections

- [ ] **Infrastructure**
  - [ ] Server has adequate resources (2+ CPU cores, 4GB+ RAM)
  - [ ] Disk space monitored (logs can grow to 50MB)
  - [ ] Stable network connection (latency <100ms to OANDA)
  - [ ] Backup power supply (UPS) if on-premises
  - [ ] Automated restart on failure (systemd, Docker restart policy)

- [ ] **Monitoring**
  - [ ] Log aggregation configured (ELK, Grafana, etc.)
  - [ ] Health check endpoint accessible
  - [ ] Alert channels set up (email, Slack, SMS)
  - [ ] Performance dashboard accessible
  - [ ] Backup verification automated

- [ ] **Documentation**
  - [ ] Runbook prepared for common issues
  - [ ] Contact list for emergencies
  - [ ] Access credentials documented (securely)
  - [ ] Change management process defined

### Post-Deployment

- [ ] Monitor continuously for first 24 hours
- [ ] Verify trades execute as expected
- [ ] Check error logs for anomalies
- [ ] Confirm health endpoint responds
- [ ] Validate backup process completes
- [ ] Test alert notifications
- [ ] Review initial performance metrics

---

## Security Best Practices

### Credential Management

#### DO

✅ Use environment variables for secrets
✅ Rotate API tokens every 90 days
✅ Use separate credentials for practice and live
✅ Store `.env` files with 600 permissions
✅ Use Docker secrets or Kubernetes secrets in production
✅ Implement IP whitelisting if OANDA supports it

#### DON'T

❌ Commit `.env` or credentials to Git
❌ Share API tokens via chat/email
❌ Use the same token across environments
❌ Store credentials in code or config files
❌ Log API tokens in application logs

### File Permissions

```bash
# Secure sensitive files
chmod 600 .env
chmod 600 live_config.json
chmod 600 best_params.json

# Verify permissions
ls -la | grep -E "\.(env|json)"
```

### Docker Security

```bash
# Run as non-root user (add to Dockerfile)
FROM python:3.9.18-slim
RUN useradd -m -u 1000 botuser
USER botuser

# Limit container resources
docker run \
  --memory=512m \
  --cpus=1.0 \
  --read-only \
  --security-opt=no-new-privileges \
  localhost/oanda-bot:latest

# Use Docker secrets (Swarm mode)
echo "your_token_here" | docker secret create oanda_token -
```

### Network Security

```bash
# Configure firewall (example: UFW on Ubuntu)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 8000/tcp # Health check
sudo ufw enable

# Restrict Docker network (docker-compose.yml)
networks:
  bot_network:
    driver: bridge
    internal: false  # Set true if no external access needed
```

### API Rate Limiting

OANDA limits to 60 requests/minute. The bot respects this with:

- Retry logic with exponential backoff
- Request throttling in `data/core.py`
- Cool-down periods between trades

Monitor rate limit errors in logs:
```bash
grep "rate limit" live_trading.log
```

---

## Docker Deployment

### Single Server Deployment

#### Step 1: Prepare Environment

```bash
# Create project directory
mkdir -p /opt/oanda-bot
cd /opt/oanda-bot

# Copy files
cp -r /home/user0/oandabot16/oanda_bot/* .

# Create .env file
cp .env.example .env
vim .env  # Configure with production values
```

#### Step 2: Build Image

```bash
# Build production image
docker build -t localhost/oanda-bot:latest .

# Verify image
docker images | grep oanda-bot
```

#### Step 3: Start Services

```bash
# Start with docker-compose
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f bot
```

#### Step 4: Verify Deployment

```bash
# Check health endpoint
curl http://localhost:8000/health

# Monitor logs
docker-compose logs -f bot | grep "trade.executed"

# Check resource usage
docker stats oanda_bot_bot_1
```

### Multi-Container Setup

For advanced deployments with separate services:

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  bot:
    image: localhost/oanda-bot:latest
    container_name: oanda_bot_prod
    env_file:
      - .env
    environment:
      CONFIG_PATH: /shared/best_params.json
    volumes:
      - ./shared:/shared:Z
      - ./logs:/app/logs:Z
      - ./trades:/app/trades:Z
    ports:
      - "8000:8000"
    networks:
      - bot_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 60s
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 256M

  researcher:
    image: localhost/oanda-bot:latest
    container_name: oanda_researcher
    env_file:
      - .env
    command: >
      bash -c "while true; do
                 python -m oanda_bot.optimize \
                   --instruments EUR_USD USD_JPY GBP_USD \
                   --granularity M5 \
                   --count 1500 \
                   --min_trades 30 \
                   --target_win_rate 0.55 &&
                 cp live_config.json /shared/best_params.json;
                 sleep 1800;
               done"
    volumes:
      - ./shared:/shared:Z
    networks:
      - bot_network
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    container_name: oanda_prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:Z
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - bot_network
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: oanda_grafana
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/dashboards:/etc/grafana/provisioning/dashboards:Z
    ports:
      - "3000:3000"
    networks:
      - bot_network
    restart: unless-stopped
    depends_on:
      - prometheus

networks:
  bot_network:
    driver: bridge

volumes:
  prometheus_data:
  grafana_data:
```

Start with:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes Deployment

For high-availability deployments:

```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: oanda-bot
  namespace: trading
spec:
  replicas: 1  # Single instance for trading bot
  selector:
    matchLabels:
      app: oanda-bot
  template:
    metadata:
      labels:
        app: oanda-bot
    spec:
      containers:
      - name: bot
        image: localhost/oanda-bot:latest
        imagePullPolicy: Always
        env:
        - name: OANDA_TOKEN
          valueFrom:
            secretKeyRef:
              name: oanda-credentials
              key: token
        - name: OANDA_ACCOUNT_ID
          valueFrom:
            secretKeyRef:
              name: oanda-credentials
              key: account_id
        - name: OANDA_ENV
          value: "live"
        - name: RISK_FRAC
          value: "0.02"
        ports:
        - containerPort: 8000
          name: health
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        volumeMounts:
        - name: config
          mountPath: /shared
        - name: logs
          mountPath: /app/logs
      volumes:
      - name: config
        persistentVolumeClaim:
          claimName: oanda-config-pvc
      - name: logs
        persistentVolumeClaim:
          claimName: oanda-logs-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: oanda-bot-service
  namespace: trading
spec:
  selector:
    app: oanda-bot
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: ClusterIP
```

Create secrets:
```bash
kubectl create namespace trading

kubectl create secret generic oanda-credentials \
  --from-literal=token=YOUR_TOKEN \
  --from-literal=account_id=YOUR_ACCOUNT_ID \
  --namespace=trading

kubectl apply -f kubernetes/deployment.yaml
```

---

## Monitoring Setup

### Logging

#### Structured Logs

All logs use JSON format for easy parsing:

```json
{
  "asctime": "2025-12-25 10:30:15",
  "levelname": "INFO",
  "name": "oanda_bot.main",
  "message": "trade.executed",
  "instrument": "EUR_USD",
  "side": "BUY",
  "units": 500,
  "entry": 1.08123,
  "stop_loss": 1.07800,
  "take_profit": 1.08800
}
```

#### Log Aggregation

**Option 1: ELK Stack**

```yaml
# docker-compose.elk.yml
version: '3.8'
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports:
      - "9200:9200"
    volumes:
      - es_data:/usr/share/elasticsearch/data

  logstash:
    image: docker.elastic.co/logstash/logstash:8.11.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
      - ../logs:/logs
    depends_on:
      - elasticsearch

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch

volumes:
  es_data:
```

**Option 2: Grafana Loki**

```yaml
# docker-compose.loki.yml
version: '3.8'
services:
  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    volumes:
      - ./loki-config.yaml:/etc/loki/local-config.yaml
      - loki_data:/loki

  promtail:
    image: grafana/promtail:latest
    volumes:
      - ./promtail-config.yaml:/etc/promtail/config.yml
      - ../logs:/logs
    depends_on:
      - loki

volumes:
  loki_data:
```

### Metrics

#### Prometheus Configuration

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'oanda-bot'
    static_configs:
      - targets: ['bot:8000']
```

#### Custom Metrics Export

Add to `main.py`:

```python
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Metrics
trades_total = Counter('trades_total', 'Total trades executed', ['pair', 'side', 'strategy'])
equity_gauge = Gauge('account_equity', 'Current account equity')
drawdown_gauge = Gauge('drawdown_percentage', 'Current drawdown percentage')
trade_duration = Histogram('trade_duration_seconds', 'Trade duration')

# Start metrics server
start_http_server(8001)  # Separate port for metrics
```

### Alerting

#### Webhook Alerts (Slack Example)

Configure in `.env`:
```bash
ERROR_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

The bot automatically sends alerts for:
- Startup/shutdown events
- Critical errors
- Drawdown exceeding thresholds

#### Email Alerts

Add to `main.py`:

```python
import smtplib
from email.mime.text import MIMEText

def send_email_alert(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = 'bot@example.com'
    msg['To'] = 'admin@example.com'

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login('bot@example.com', os.getenv('EMAIL_PASSWORD'))
    server.send_message(msg)
    server.quit()
```

#### Prometheus Alertmanager

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  receiver: 'slack'
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h

receivers:
- name: 'slack'
  slack_configs:
  - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
    channel: '#trading-alerts'
    title: 'OANDA Bot Alert'
    text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'

inhibit_rules:
- source_match:
    severity: 'critical'
  target_match:
    severity: 'warning'
  equal: ['alertname']
```

---

## Backup Strategies

### What to Back Up

1. **Configuration Files**
   - `.env` (encrypted!)
   - `live_config.json`
   - `best_params.json`

2. **Trade Data**
   - `trades_log.csv`
   - `live_trading.log` (recent)

3. **Application State**
   - Strategy parameters
   - Position state (if persisted)

### Automated Backup Script

```bash
#!/bin/bash
# backup.sh - Daily backup script

BACKUP_DIR=/backups/oanda-bot
DATE=$(date +%Y%m%d)
BACKUP_PATH=$BACKUP_DIR/$DATE

# Create backup directory
mkdir -p $BACKUP_PATH

# Backup configuration (encrypted)
tar -czf $BACKUP_PATH/config.tar.gz \
  .env live_config.json best_params.json | \
  gpg --encrypt --recipient admin@example.com > $BACKUP_PATH/config.tar.gz.gpg

# Backup trade logs
cp trades_log.csv $BACKUP_PATH/
gzip $BACKUP_PATH/trades_log.csv

# Backup recent trading logs (last 7 days)
find . -name "live_trading.log*" -mtime -7 -exec cp {} $BACKUP_PATH/ \;

# Upload to S3 (or other cloud storage)
aws s3 sync $BACKUP_PATH s3://my-bucket/oanda-bot-backups/$DATE/

# Cleanup old backups (keep 30 days)
find $BACKUP_DIR -type d -mtime +30 -exec rm -rf {} \;

echo "Backup completed: $BACKUP_PATH"
```

Schedule with cron:
```bash
# Run daily at 2 AM
0 2 * * * /opt/oanda-bot/backup.sh >> /var/log/oanda-backup.log 2>&1
```

### Database Backup (if using one)

If you add database persistence:

```bash
# PostgreSQL example
pg_dump -U postgres trading_db | gzip > backup-$(date +%Y%m%d).sql.gz

# MongoDB example
mongodump --db trading_db --out /backups/mongo-$(date +%Y%m%d)
```

---

## Disaster Recovery

### Recovery Time Objective (RTO)

Target: **< 15 minutes** to restore bot to operational state

### Recovery Point Objective (RPO)

Target: **< 24 hours** data loss maximum (daily backups)

### Recovery Procedures

#### Scenario 1: Bot Crash

```bash
# Check if container is running
docker-compose ps

# View recent logs
docker-compose logs --tail=100 bot

# Restart bot
docker-compose restart bot

# If restart fails, check logs for errors
docker-compose logs bot | grep ERROR

# Nuclear option: rebuild and restart
docker-compose down
docker-compose up -d --build
```

#### Scenario 2: Data Corruption

```bash
# Stop bot
docker-compose down

# Restore from latest backup
cd /opt/oanda-bot
tar -xzf /backups/oanda-bot/$(date +%Y%m%d)/config.tar.gz

# Verify configuration
cat live_config.json

# Restart bot
docker-compose up -d
```

#### Scenario 3: Server Failure

```bash
# On new server:

# 1. Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# 2. Restore application
mkdir -p /opt/oanda-bot
cd /opt/oanda-bot

# 3. Download from S3
aws s3 sync s3://my-bucket/oanda-bot-backups/latest/ .

# 4. Decrypt configuration
gpg --decrypt config.tar.gz.gpg | tar -xz

# 5. Pull Docker image
docker pull localhost/oanda-bot:latest

# 6. Start services
docker-compose up -d

# 7. Verify
curl http://localhost:8000/health
```

#### Scenario 4: OANDA API Outage

```bash
# Bot will automatically retry with exponential backoff
# Monitor logs for recovery
docker-compose logs -f bot | grep "retry"

# If extended outage, consider stopping bot
docker-compose stop bot

# Resume when service restored
docker-compose start bot
```

### Runbook Template

```markdown
# Issue: [Description]

## Symptoms
- [What you observe]

## Diagnosis
1. Check [logs/metrics/endpoint]
2. Verify [configuration/credentials]

## Resolution
1. [Step 1]
2. [Step 2]
3. [Step 3]

## Verification
- [ ] Health check returns OK
- [ ] No errors in logs
- [ ] Trades executing normally

## Prevention
- [How to prevent recurrence]
```

---

## Scaling Considerations

### Vertical Scaling (Single Server)

**Current Resource Usage**:
- CPU: 5-50% (idle to optimization)
- Memory: ~200MB per instance
- Disk: 50MB (logs)
- Network: <1 Mbps

**Scaling Up**:
```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '4.0'
      memory: 4G
```

**When to Scale Up**:
- Adding more currency pairs (>20)
- Adding more strategies (>10)
- Running continuous optimization
- High-frequency trading (<1s bars)

### Horizontal Scaling (Multi-Instance)

**⚠️ WARNING**: Do NOT run multiple instances against the same OANDA account. This will cause:
- Duplicate orders
- Position conflicts
- Account violations

**Safe Multi-Instance Patterns**:

1. **Strategy Sharding**: Each instance runs different strategies
   ```bash
   # Instance 1: Trend strategies
   docker-compose -f compose.trends.yml up -d

   # Instance 2: Mean reversion strategies
   docker-compose -f compose.reversion.yml up -d
   ```

2. **Pair Sharding**: Each instance trades different pairs
   ```bash
   # Instance 1: EUR pairs
   ACTIVE_PAIRS=EUR_USD,EUR_GBP,EUR_AUD docker-compose up -d

   # Instance 2: GBP pairs
   ACTIVE_PAIRS=GBP_USD,GBP_JPY,GBP_AUD docker-compose up -d
   ```

3. **Account Separation**: Each instance uses different OANDA account
   ```bash
   # Account 1
   OANDA_ACCOUNT_ID=account1 docker-compose up -d

   # Account 2
   OANDA_ACCOUNT_ID=account2 docker-compose up -d
   ```

### Load Balancing

Not applicable for trading bot (stateful, single account).

For dashboard/monitoring only:
```yaml
# nginx.conf
upstream oanda_dashboard {
    server dashboard1:8501;
    server dashboard2:8501;
}

server {
    listen 80;
    location / {
        proxy_pass http://oanda_dashboard;
    }
}
```

---

## Maintenance

### Regular Tasks

#### Daily
- [ ] Check health endpoint
- [ ] Review error logs
- [ ] Monitor trade performance
- [ ] Verify backups completed

#### Weekly
- [ ] Review strategy performance
- [ ] Check drawdown trends
- [ ] Analyze win rates by pair/strategy
- [ ] Update parameter optimization if needed

#### Monthly
- [ ] Rotate API tokens (every 90 days recommended)
- [ ] Review and archive old logs
- [ ] Update Docker images
- [ ] Re-optimize all strategies
- [ ] Review resource usage trends

#### Quarterly
- [ ] Full system backup test (restore and verify)
- [ ] Security audit (dependencies, credentials)
- [ ] Performance review and tuning
- [ ] Disaster recovery drill

### Updating the Bot

```bash
# 1. Backup current state
./backup.sh

# 2. Pull latest code
cd /opt/oanda-bot
git pull origin main

# 3. Rebuild Docker image
docker-compose build

# 4. Test on practice account first
OANDA_ENV=practice docker-compose up -d

# 5. Monitor for issues
docker-compose logs -f bot

# 6. If stable, deploy to live
docker-compose down
OANDA_ENV=live docker-compose up -d
```

### Log Rotation

```bash
# /etc/logrotate.d/oanda-bot
/opt/oanda-bot/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 root root
    sharedscripts
    postrotate
        docker-compose restart bot
    endscript
}
```

### Dependency Updates

```bash
# Check for security updates
pip list --outdated

# Update specific package
pip install --upgrade oandapyV20

# Update all packages
pip install -r requirements.txt --upgrade

# Test thoroughly before deploying!
pytest
```

---

## Performance Optimization

### Database (if added)

For persistent storage of trades:

```python
# Use connection pooling
from sqlalchemy import create_engine
engine = create_engine(
    'postgresql://user:pass@localhost/trading',
    pool_size=10,
    max_overflow=20
)
```

### API Efficiency

```python
# Batch candle requests where possible
instruments = ["EUR_USD", "GBP_USD", "USD_JPY"]
with ThreadPoolExecutor(max_workers=3) as executor:
    futures = [executor.submit(get_candles, inst) for inst in instruments]
    results = [f.result() for f in futures]
```

### Memory Optimization

```python
# Limit deque sizes to prevent memory growth
history = {p: deque(maxlen=300) for p in PAIRS}  # Already done
atr_history = {p: deque(maxlen=30) for p in PAIRS}  # Already done
```

---

## Troubleshooting Production Issues

### High CPU Usage

**Diagnosis**:
```bash
docker stats
top -p $(pgrep -f "python -m oanda_bot.main")
```

**Common Causes**:
- Continuous optimization running
- Too many strategies/pairs
- Infinite loop in strategy code

**Resolution**:
- Reduce optimization frequency
- Disable underperforming strategies
- Profile code with `cProfile`

### High Memory Usage

**Diagnosis**:
```bash
docker stats
ps aux | grep python | awk '{print $6}'  # Memory in KB
```

**Common Causes**:
- Memory leak in strategy
- Too much historical data cached
- Log files not rotating

**Resolution**:
- Review deque maxlen settings
- Enable log rotation
- Restart bot periodically

### Network Latency

**Diagnosis**:
```bash
ping api-fxtrade.oanda.com
traceroute api-fxtrade.oanda.com
```

**Optimal Latency**: <100ms

**Resolution**:
- Deploy closer to OANDA servers (AWS us-east-1)
- Use wired connection, not WiFi
- Check for ISP throttling

### Disk Space

**Diagnosis**:
```bash
df -h
du -sh /opt/oanda-bot/logs/*
```

**Resolution**:
```bash
# Clean old logs
find /opt/oanda-bot/logs -name "*.log*" -mtime +30 -delete

# Compress logs
gzip /opt/oanda-bot/logs/*.log

# Adjust log rotation
vim /etc/logrotate.d/oanda-bot
```

---

## Support Contacts

### Critical Issues

**Priority 1** (Trading stopped, data loss):
- Contact: Nick Guerriero
- Email: nickguerriero@example.com
- Phone: [Emergency contact]
- Response Time: <2 hours

### Non-Critical Issues

**Priority 2** (Performance degradation):
- Email: support@example.com
- Response Time: <24 hours

### OANDA Support

- Practice Account: https://www.oanda.com/support/
- Live Account: Your dedicated account manager
- API Issues: api@oanda.com

---

## Compliance & Regulatory

### Trading Records

Maintain for minimum **7 years**:
- All trades (CSV logs)
- Strategy configurations at time of trade
- Account statements from OANDA
- Optimization results

### Audit Trail

Structured logs provide complete audit trail:
- Who: Strategy name
- What: Trade details (pair, side, units, prices)
- When: ISO timestamp
- Why: Signal from strategy

### Risk Disclosure

Ensure compliance with:
- Local financial regulations
- OANDA terms of service
- Algorithmic trading guidelines
- Risk disclosure requirements

---

## Final Checklist

Before going live:

- [ ] All tests passing
- [ ] Practice account profitable for 2+ weeks
- [ ] Backups automated and verified
- [ ] Monitoring and alerts configured
- [ ] Runbooks prepared for common issues
- [ ] Risk limits appropriate for capital
- [ ] Security best practices implemented
- [ ] Disaster recovery tested
- [ ] Team trained on operations
- [ ] Emergency contacts documented

---

**Remember**: Start small, monitor closely, scale gradually.

**Good luck!** 🚀

---

**Last Updated**: 2025-12-25
**Version**: 0.1.0
