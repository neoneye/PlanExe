# worker_plan_database

Subclass of the `worker_plan` service that runs the PlanExe pipeline against the shared Postgres database.

- Polls `TaskItem` rows, marks them processing, and runs the pipeline.
- Reports state/progress back to the DB and posts confirmations to MachAI.
- Uses the same `planexe` code as `worker_plan`, plus the shared `database_api` models.

## Docker usage
- Build/run with docker compose: `docker compose up --build worker_plan_database`
- Reads `SQLALCHEMY_DATABASE_URI` when provided, otherwise builds one from:
  - `PLANEXE_WORKER_PLAN_DB_HOST|PORT|NAME|USER|PASSWORD`
  - falls back to the `database_postgres` service defaults (`planexe/planexe` on port 5432)
- Volumes mounted in compose: `./run` (pipeline output), `./log` (rotating worker logs), `.env`, `llm_config.json`
- Entrypoint: `python -m worker_plan_database.app`
