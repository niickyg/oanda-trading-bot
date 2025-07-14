# Base image for runtime
FROM python:3.9-slim as base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Development stage with dev dependencies
FROM base as dev
COPY dev_requirements.txt .
RUN pip install --no-cache-dir -r dev_requirements.txt
COPY . .

# Production stage
FROM base as prod
COPY . .

# Healthcheck for container orchestrators
HEALTHCHECK --interval=30s --timeout=5s \
  CMD curl --fail http://localhost:8000/health || exit 1

# Default command: run in live mode
CMD ["python", "main.py", "--mode", "live"]
