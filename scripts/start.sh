#!/usr/bin/env bash
set -euo pipefail

# Wait for Postgres
./scripts/wait-for-postgres.sh

# Create tables and seed data
python - <<'PY'
from database import Base, engine
from seed_data import seed_data
from database import SessionLocal

Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    seed_data(db)
finally:
    db.close()
PY

# Run Streamlit app
exec streamlit run app.py --server.port=${STREAMLIT_SERVER_PORT:-8501} --server.address=${STREAMLIT_SERVER_ADDRESS:-0.0.0.0}
