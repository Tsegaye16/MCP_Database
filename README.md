## MCP – Database Chatbot (Streamlit + PostgreSQL)

A simple natural‑language chatbot that answers questions using your database. It uses:

- Streamlit for the chat UI
- LangChain + Gemini for NL → SQL generation and execution
- SQLAlchemy + PostgreSQL for storage
- Docker Compose for one‑command local deployment

### Features

- Natural‑language queries over relational data (users, products, orders, order_items)
- Non‑technical responses: no SQL or internal tool names shown
- Built‑in sidebar guide with schema overview and suggested questions
- Idempotent seeding on startup (safe to re‑run)

### Project Structure

- `app.py` – Streamlit chatbot app
- `models.py` – SQLAlchemy models and relationships
- `database.py` – DB engine/session setup
- `seed_data.py` – Creates tables and seeds sample data
- `test.py` – LangGraph/LangChain experimentation (optional)
- `scripts/start.sh` – Container entrypoint: wait → migrate/seed → run app
- `scripts/wait-for-postgres.sh` – Waits for DB readiness using SQLAlchemy
- `Dockerfile`, `docker-compose.yml`, `.dockerignore` – Containerization

### Database Schema (overview)

- `users` (`user_id`, `name`, `email`, `hobby`, `job`, `age`)
- `products` (`product_id`, `name`, `category`, `price`, `stock`)
- `orders` (`order_id`, `user_id`, `order_date`, `status`, `total_amount`)
- `order_items` (`order_item_id`, `order_id`, `product_id`, `quantity`, `unit_price`)

Relationships:

- User 1‑to‑many Orders (`orders.user_id → users.user_id`)
- Order 1‑to‑many OrderItems (`order_items.order_id → orders.order_id`)
- Product 1‑to‑many OrderItems (`order_items.product_id → products.product_id`)

### Prerequisites

- Python 3.12+ (for local runs)
- Docker & Docker Compose (for containerized runs)
- Google Generative AI API key (Gemini)

### Environment Variables

- `DATABASE_URL` – SQLAlchemy URL (e.g. `postgresql+psycopg2://user:pass@host:5432/dbname`)
- `GOOGLE_API_KEY` – Your Gemini API key

You can copy `.env.example` to `.env` and fill in values (Compose passes them to the app).

### Run with Docker (recommended)

1. Set your API key in the environment (PowerShell example):

```powershell
$Env:GOOGLE_API_KEY="your_key_here"
```

2. Build and start:

```bash
docker compose up --build
```

3. Open the app:

```
http://localhost:8501
```

The app waits for Postgres, creates tables, seeds data, then starts Streamlit.

Stop with Ctrl+C. To run detached: `docker compose up -d`.

### Run locally (without Docker)

1. Create and activate a virtual environment (optional but recommended)

```bash
python -m venv .venv
# PowerShell: .\.venv\Scripts\Activate.ps1
# bash/zsh: source .venv/bin/activate
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Set environment variables (using a local Postgres or any SQLAlchemy‑compatible DB)

```powershell
$Env:DATABASE_URL = "postgresql+psycopg2://appuser:applocal@localhost:5432/appdb"
$Env:GOOGLE_API_KEY = "your_key_here"
```

4. Initialize DB and seed data

```bash
python seed_data.py
```

5. Start the app

```bash
streamlit run app.py
```

6. Open `http://localhost:8501`.

### Using the Chatbot

Try questions like:

- "How many users are in the system?"
- "What are the top 3 most expensive products?"
- "Show total sales amount by user."
- "How many orders did Jane Smith place, and what's the total spent?"
- "List orders with their items and totals for John Doe."

Tips:

- Be specific (names, categories, date ranges, statuses like `completed`, `shipped`).
- Ask for aggregations (sum, average, count, top N). The bot handles joins for you.

### Troubleshooting

- App waiting for DB
  - `docker compose logs app -f` to see live logs
  - Verify Compose `DATABASE_URL` for the app is `postgresql+psycopg2://appuser:applocal@db:5432/appdb`
  - Ensure your API key is exported in the shell where you run `docker compose`
- Permission on scripts
  - If entrypoint fails, ensure scripts are executable then rebuild:
    - `git update-index --chmod=+x scripts/start.sh scripts/wait-for-postgres.sh`
- Local run cannot connect
  - Confirm your local `DATABASE_URL` points to a running DB
