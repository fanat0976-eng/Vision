FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy source
COPY vision/ vision/
COPY run.py .
COPY config.json* .

# Expose ports
EXPOSE 8080 8081

# Run gateway
CMD ["python", "run.py", "gateway"]
