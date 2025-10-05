FROM python:3.12-slim

# Install system dependencies for psycopg2 and build tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better cache)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Streamlit config to run in container
ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501

# Ensure scripts are executable
RUN chmod +x scripts/start.sh scripts/wait-for-postgres.sh || true

EXPOSE 8501

ENTRYPOINT ["/bin/bash", "scripts/start.sh"]
