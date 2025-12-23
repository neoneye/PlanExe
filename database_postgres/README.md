# database_postgres

Postgres container for PlanExe. Intended for future use as a queue/event store.

In a **single user** environment, then this is overkill. The file system is sufficient.

In a **multi user** environment, then there are many moving parts, and here a database is relevant.

- Build/run via `docker compose up database_postgres` (or `docker compose build database_postgres`).
- Defaults: `POSTGRES_USER=planexe`, `POSTGRES_PASSWORD=planexe`, `POSTGRES_DB=planexe` (override with env or `.env`).
- Ports: `${PLANEXE_POSTGRES_PORT:-5432}` on the host mapped to `5432` in the container. Set `PLANEXE_POSTGRES_PORT` in `.env` or your shell to avoid clashes.
- Data: persisted in the named volume `database_postgres_data`.

## Choose a host port

If another Postgres is already using the default postgres port 5432, set `PLANEXE_POSTGRES_PORT` before starting the container:

```bash
export PLANEXE_POSTGRES_PORT=5555
docker compose up database_postgres
```

Replace `5555` with any free host port you prefer.

## Verify the container

- Check status: `docker compose ps database_postgres`
- Shell in to confirm Postgres is the right one: `docker compose exec database_postgres psql -U planexe -d planexe`

## DBeaver

For managing the database, I recommend using the `DBeaver Community` app, which is open source.

https://github.com/dbeaver/dbeaver

Connect with host `localhost`, port `${PLANEXE_POSTGRES_PORT:-5432}`, database `planexe`, user `planexe`, password `planexe` (or whatever you set in `.env`).
