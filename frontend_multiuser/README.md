# frontend_multiuser

Minimal web UI that has a button that pings `database_postgres` with `SELECT 1` when you click **Ping database**.

## Quickstart
- `docker compose up frontend_multiuser`
- Open http://localhost:${PLANEXE_FRONTEND_MULTIUSER_PORT:-5001}/ and hit **Ping database** (defaults use `database_postgres` on 5432 with `planexe/planexe`).

In my case I had to do this:

```bash
export PLANEXE_FRONTEND_MULTIUSER_PORT=5001
docker compose up frontend_multiuser
```

Visit http://localhost:5001/ in the browser.

## Config (env)
- `PLANEXE_FRONTEND_MULTIUSER_PORT`: host port mapped to container 5000 (default 5001).
- `PLANEXE_FRONTEND_MULTIUSER_HOST`: bind address inside the container (default 0.0.0.0). Container port is fixed at 5000.
- `PLANEXE_FRONTEND_MULTIUSER_DB_HOST|PORT|NAME|USER|PASSWORD`: Postgres connection (defaults follow `POSTGRES_*` or `planexe`).

## Run without compose
```bash
cd frontend_multiuser
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PLANEXE_FRONTEND_MULTIUSER_DB_HOST=localhost
export PLANEXE_FRONTEND_MULTIUSER_DB_PORT=${PLANEXE_POSTGRES_PORT:-5432}
python app.py
```
Visit http://localhost:5000
