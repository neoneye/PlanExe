FROM postgres:16-alpine

# Default creds for dev deploys; override via env vars in production.
ENV POSTGRES_USER=planexe \
    POSTGRES_PASSWORD=planexe \
    POSTGRES_DB=planexe

# Keep PGDATA inside the mounted volume but off the mount root to avoid lost+found errors.
ENV PGDATA=/var/lib/postgresql/data/pgdata
