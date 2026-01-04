# Railway Configuration for `database_postgres`

## Environment Variables

Create a shared environment variable named `PLANEXE_POSTGRES_PASSWORD` with a random password (e.g., a UUID).

The `database_postgres` environment vars should include:

```
PLANEXE_POSTGRES_PASSWORD="${{shared.PLANEXE_POSTGRES_PASSWORD}}"
```

> **Note**: The `PLANEXE_POSTGRES_PASSWORD` environment variable is for reference/documentation purposes in Railway. Since the database was initialized with the default password, you must manually change the password using `ALTER USER` (see below). The environment variable alone won't update an existing database password.

## Changing Password After Initial Setup

PostgreSQL only sets the password on **first initialization**. If the database was already created with the default `planexe` password, changing the environment variable won't update the existing password.

To change the password on an existing database:

1. Connect using the current password (e.g., via DBeaver)
2. Run this SQL command:

```sql
ALTER USER planexe WITH PASSWORD 'your-new-secure-password';
```

3. Update the `POSTGRES_PASSWORD` environment variable in Railway to match

## Verifying the Connection

After setup, verify your connection is secure:

1. Open DBeaver and create a new PostgreSQL connection
2. Use the TCP Proxy hostname and port from Railway (see Networking section below)
3. Enter credentials:
   - **Database**: `planexe`
   - **Username**: `planexe`
   - **Password**: Your secure password (NOT the default `planexe`)
4. Click **Test Connection** — it should succeed
5. **Security check**: Try connecting with password `planexe` — it should **fail**. If it succeeds, the password hasn't been changed yet.

## Volume

The `database_postgres` service has a volume named `database_postgres_data`.

It's defined in `docker-compose.yml`, like below.
```
database_postgres_data:/var/lib/postgresql/data
```

Railway read my `docker-compose.yml` when I dragndrop it first time. I doubt that Railway syncs with it. 
In case there are changes to `docker-compose.yml`, then the developer will manually have to make similar changes inside Railway.

## Settings -> Networking -> TCP Proxy

Expose the database to the public internet.

> **Warning**: Only enable TCP Proxy after you have set a secure password. The default `planexe` password is too easy to guess.

> **Warning**: The TCP Proxy connection is **unencrypted**. Railway's TCP Proxy forwards raw TCP traffic without adding TLS, and the `postgres:16-alpine` image doesn't have SSL enabled by default. Your password and data travel in plain text. Consider disabling TCP Proxy when not actively using it.

1. Go to **Settings** → **Networking** → **Public Networking**
2. Add a **TCP Proxy** with port `5432`

Afterwards the TCP Proxy settings will show something like:

```
subsubdomain.subdomain.example.com:12345 -> :5432
```

Use this hostname and port to connect from external tools like DBeaver:

| Field | Value |
|-------|-------|
| Host | `subsubdomain.subdomain.example.com` (your actual Railway hostname) |
| Port | `12345` (your assigned port, not 5432) |
| Database | `planexe` |
| Username | `planexe` |
| Password | Your secure password |

