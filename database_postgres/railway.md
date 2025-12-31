# Railway Configuration

No env vars provided to Railway.

## Volume

The `database_postgres` service has a volume named `database_postgres_data`.

It's defined in `docker-compose.yml`, like below.
```
database_postgres_data:/var/lib/postgresql/data
```

Railway read my `docker-compose.yml` when I dragndrop it first time. I doubt that Railway syncs with it. 
In case there are changes to `docker-compose.yml`, then the developer will manually have to make similar changes inside Railway.

