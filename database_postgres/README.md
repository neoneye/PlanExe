# Database Postgres

Database container for PlanExe. Used as a queue mechanism for planning tasks. The `worker_plan_database` listens for an incoming task, and runs PlanExe and then goes back to listen for more incoming tasks.

In a **single user** environment, then this is overkill. The file system is sufficient.

In a **multi user** environment, then there are many moving parts, and here a database is relevant.

- Build/run via `docker compose up database_postgres` (or `docker compose build database_postgres`).
- Defaults: `PLANEXE_POSTGRES_USER=planexe`, `PLANEXE_POSTGRES_PASSWORD=planexe`, `PLANEXE_POSTGRES_DB=planexe` (override with env or `.env`).
- Ports: `${PLANEXE_POSTGRES_PORT:-5432}` on the host mapped to `5432` in the container. Set `PLANEXE_POSTGRES_PORT` in `.env` or your shell to avoid clashes.
- Data: persisted in the named volume `database_postgres_data`.

## Choose a host port

The default PostgreSQL port is 5432. On developer machines, this port is often already occupied by a local PostgreSQL installation:

- **macOS**: Postgres.app (a popular menu-bar Postgres that auto-starts), Homebrew PostgreSQL (`brew install postgresql`), or pgAdmin's bundled server
- **Linux**: System PostgreSQL installed via `apt install postgresql`, `dnf install postgresql-server`, etc.
- **Windows**: PostgreSQL installer, pgAdmin, or other database tools

If port 5432 is in use, Docker will fail to start `database_postgres` with a "port already in use" error.

**Solution**: Set `PLANEXE_POSTGRES_PORT` to a different value before starting the container:

```bash
export PLANEXE_POSTGRES_PORT=5433
docker compose up database_postgres
```

Or add it to your `.env` file to make it permanent:
```
PLANEXE_POSTGRES_PORT=5433
```

Replace `5433` with any free host port you prefer.

**Important**: This only affects the HOST port mapping (how you access Postgres from your machine). Inside Docker, containers always communicate with each other on the internal port 5432—this is hardcoded and not affected by `PLANEXE_POSTGRES_PORT`.

## Verify the container

- Check status: `docker compose ps database_postgres`
- Shell in to confirm Postgres is the right one: `docker compose exec database_postgres psql -U planexe -d planexe`

## DBeaver

For managing the database, I recommend using the `DBeaver Community` app, which is open source.

https://github.com/dbeaver/dbeaver

Connect with host `localhost`, port `${PLANEXE_POSTGRES_PORT:-5432}`, database `planexe`, user `planexe`, password `planexe` (or whatever you set in `.env`).

### Railway + DBeaver

DBeaver cannot connect via the Railway CLI tunnel (`railway ssh`/`connect`), because the CLI does not provide a traditional TCP port forward. Instead, use Railway's TCP Proxy feature.

#### 1. Enable TCP Proxy in Railway

1. Go to your Railway dashboard → `database_postgres` service
2. Navigate to **Settings** → **Networking** → **Public Networking**
3. Add a **TCP Proxy** with port `5432`
4. Railway will assign a hostname and port, e.g., `subsubdomain.subdomain.example.com:12345`

> **Warning**: Only enable TCP Proxy after setting a secure password (see below).

> **Warning**: The TCP Proxy connection is **unencrypted**. Railway's TCP Proxy forwards raw TCP traffic without adding TLS, and the `postgres:16-alpine` image doesn't have SSL enabled by default. Your password and data travel in plain text. Consider disabling TCP Proxy when not in use, or configure SSL on the PostgreSQL container for production use.

#### 2. Set a secure password

The default password `planexe` is too easy to guess. PostgreSQL only sets the password on first initialization, so if the database already exists:

1. Connect with the current password
2. Run: `ALTER USER planexe WITH PASSWORD 'your-secure-password';`
3. Update `POSTGRES_PASSWORD` in Railway's environment variables to match

#### 3. Connect with DBeaver

In DBeaver, create a new PostgreSQL connection with **"Connect by: Host"**:

| Field | Value |
|-------|-------|
| Host | Your TCP Proxy hostname (e.g., `subsubdomain.subdomain.example.com`) |
| Port | Your assigned port (e.g., `12345`, NOT 5432) |
| Database | `planexe` |
| Username | `planexe` |
| Password | Your secure password |

Click **Test Connection** to verify.

#### 4. Security check

Try connecting with password `planexe`. If it succeeds, the password hasn't been changed yet—go back to step 2.

See `railway.md` for more details.

## SSL (Future Plan)

The current setup uses unencrypted connections. For production use with public TCP Proxy exposure, SSL/TLS should be enabled to encrypt traffic between clients and the database.

### What's needed

#### 1. Generate SSL certificates

You'll need a certificate and private key. Options:
- **Self-signed**: Quick for internal use, but clients must trust the certificate manually
- **Let's Encrypt**: Free, but requires domain validation (complex for raw TCP)
- **Commercial CA**: Trusted by default, but costs money

Example self-signed certificate generation:

```bash
openssl req -new -x509 -days 365 -nodes \
  -out server.crt \
  -keyout server.key \
  -subj "/CN=database_postgres"
```

#### 2. Update the Dockerfile

Add the certificates and configure PostgreSQL to use them:

```dockerfile
FROM postgres:16-alpine

# ... existing ENV statements ...

# Copy SSL certificates
COPY server.crt /var/lib/postgresql/server.crt
COPY server.key /var/lib/postgresql/server.key

# Set correct permissions (required by PostgreSQL)
RUN chmod 600 /var/lib/postgresql/server.key && \
    chown postgres:postgres /var/lib/postgresql/server.crt /var/lib/postgresql/server.key

# Enable SSL in PostgreSQL
RUN echo "ssl = on" >> /usr/local/share/postgresql/postgresql.conf.sample && \
    echo "ssl_cert_file = '/var/lib/postgresql/server.crt'" >> /usr/local/share/postgresql/postgresql.conf.sample && \
    echo "ssl_key_file = '/var/lib/postgresql/server.key'" >> /usr/local/share/postgresql/postgresql.conf.sample
```

#### 3. Configure DBeaver for SSL

In DBeaver's connection settings:

1. Go to the **SSL** tab
2. Check **"Use SSL"**
3. Set **SSL mode**:
   - `require` — Encrypt connection, don't verify certificate
   - `verify-ca` — Encrypt and verify certificate against a CA
   - `verify-full` — Encrypt, verify certificate, and check hostname
4. For self-signed certs, you may need to import the CA/certificate or set **"Trust all certificates"**

#### 4. Enforce SSL on the server (optional)

To reject unencrypted connections, add to `pg_hba.conf`:

```
# Require SSL for all remote connections
hostssl all all 0.0.0.0/0 scram-sha-256
```

### Resources

- [PostgreSQL SSL Documentation](https://www.postgresql.org/docs/current/ssl-tcp.html)
- [pg_hba.conf Documentation](https://www.postgresql.org/docs/current/auth-pg-hba-conf.html)

## Railway backup to local file

Use `database_postgres/download_backup.py` to stream a compressed dump from the Railway `database_postgres` service to your machine.

Prereq: Railway CLI installed and logged in.

```
python database_postgres/download_backup.py
```

- Runs `railway link` (skip with `--skip-link` if already linked).
- Streams `pg_dump -F c -Z9` via `railway ssh` and writes `YYYYMMDD-HHMM.dump` in the current directory.
- Options:
  - `--user` Postgres user (default: `$PLANEXE_POSTGRES_USER` or `planexe`)
  - `--db` Postgres database (default: `$PLANEXE_POSTGRES_DB` or `planexe`)
  - `--output-dir path` Directory for the dump file
  - `--filename name.dump` Override dump filename
  - `--service other_service` Railway service name
  - `--skip-link` Skip `railway link` if already linked

### Restore a backup locally

Run a Postgres you can reach (for example `docker compose up database_postgres` on your machine), then restore the custom-format dump:

```bash
PGPASSWORD=planexe pg_restore \
  -h localhost \
  -p 5432 \
  -U planexe \
  -d planexe \
  /path/to/19841231-2359.dump
```

- The dump is custom format (`pg_dump -F c`), so use `pg_restore`, not `psql`.
- Ensure the target database exists; add `-c` to drop objects before recreating them if you want a clean restore.
- If you changed credentials/DB name in `.env` or Railway, use those here.
