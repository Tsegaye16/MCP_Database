#!/usr/bin/env bash
set -euo pipefail

# Wait for Postgres using Python and SQLAlchemy against DATABASE_URL
python - <<'PY'
import os, sys, time
from sqlalchemy import create_engine

database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("DATABASE_URL is not set; cannot wait for database.")
    sys.exit(1)

engine = create_engine(database_url, pool_pre_ping=True)

while True:
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        print("Database is ready.")
        break
    except Exception as e:
        print("Waiting for database...", str(e))
        time.sleep(1)
PY
