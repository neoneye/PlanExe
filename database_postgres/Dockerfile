FROM postgres:16-alpine

# Default creds for dev deploys; override via env vars in production.
ENV PLANEXE_POSTGRES_USER=planexe \
    PLANEXE_POSTGRES_PASSWORD=planexe \
    PLANEXE_POSTGRES_DB=planexe \
    POSTGRES_USER=${PLANEXE_POSTGRES_USER} \
    POSTGRES_PASSWORD=${PLANEXE_POSTGRES_PASSWORD} \
    POSTGRES_DB=${PLANEXE_POSTGRES_DB}

# Keep PGDATA inside the mounted volume but off the mount root to avoid lost+found errors.
ENV PGDATA=/var/lib/postgresql/data/pgdata
