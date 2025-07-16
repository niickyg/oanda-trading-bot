# Base image for runtime
FROM python:3.9.18-slim AS base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Development stage with dev dependencies
FROM base AS dev
COPY dev_requirements.txt .
RUN pip install --no-cache-dir -r dev_requirements.txt
COPY setup.py .
COPY . .
RUN pip install --no-cache-dir -e .

# Production stage
FROM base AS prod
COPY . .

# Healthcheck for container orchestrators
HEALTHCHECK --interval=30s --timeout=5s \
  CMD curl --fail http://localhost:8000/health || exit 1

# Default command: run in live mode
CMD ["python", "main.py", "--mode", "live"]
