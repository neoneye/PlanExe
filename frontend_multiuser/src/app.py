import logging
import os
from typing import Tuple

from flask import Flask, jsonify, render_template_string
import psycopg2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


def get_db_config() -> dict:
    """Return DB settings, defaulting to the compose Postgres container."""
    return {
        "host": os.environ.get("PLANEXE_FRONTEND_MULTIUSER_DB_HOST", "database_postgres"),
        "port": int(os.environ.get("PLANEXE_FRONTEND_MULTIUSER_DB_PORT", "5432")),
        "dbname": os.environ.get("PLANEXE_FRONTEND_MULTIUSER_DB_NAME", os.environ.get("POSTGRES_DB", "planexe")),
        "user": os.environ.get("PLANEXE_FRONTEND_MULTIUSER_DB_USER", os.environ.get("POSTGRES_USER", "planexe")),
        "password": os.environ.get("PLANEXE_FRONTEND_MULTIUSER_DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "planexe")),
    }


def ping_database(config: dict) -> Tuple[bool, str]:
    """Attempt to run a simple SELECT 1 against Postgres."""
    try:
        with psycopg2.connect(
            host=config["host"],
            port=config["port"],
            dbname=config["dbname"],
            user=config["user"],
            password=config["password"],
            connect_timeout=3,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True, "Database responded to SELECT 1."
    except Exception as exc:  # pragma: no cover - simple runtime probe
        return False, f"Unable to reach database: {exc}"


TEMPLATE = """
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>Frontend Multiuser</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem; color: #1b1b1b; }
    .card { border: 1px solid #ddd; padding: 1.5rem; border-radius: 8px; max-width: 520px; }
    button { padding: 0.5rem 1rem; font-size: 1rem; cursor: pointer; }
    #result { margin-top: 1rem; white-space: pre-wrap; }
    .muted { color: #555; }
  </style>
</head>
<body>
  <div class=\"card\">
    <h1>Frontend Multiuser</h1>
    <p class=\"muted\">Ping the Postgres instance to confirm it is reachable from this container.</p>
    <p><strong>Target database</strong><br>
      Host: {{ config.host }}:{{ config.port }}<br>
      Database: {{ config.dbname }}<br>
      User: {{ config.user }}
    </p>
    <button id=\"ping-btn\" type=\"button\">Ping database</button>
    <div id=\"result\" class=\"muted\"></div>
  </div>
  <script>
    const button = document.getElementById('ping-btn');
    const result = document.getElementById('result');
    button.addEventListener('click', async () => {
      result.textContent = 'Pinging...';
      try {
        const response = await fetch('/ping', { method: 'POST' });
        const data = await response.json();
        const status = data.ok ? 'OK' : 'Error';
        result.textContent = status + ': ' + data.message;
      } catch (err) {
        result.textContent = 'Error: ' + err;
      }
    });
  </script>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def home():
    cfg = get_db_config()
    safe_cfg = {k: v for k, v in cfg.items() if k != "password"}
    return render_template_string(TEMPLATE, config=safe_cfg)


@app.route("/ping", methods=["POST"])
def ping():
    cfg = get_db_config()
    ok, message = ping_database(cfg)
    safe_cfg = {k: v for k, v in cfg.items() if k != "password"}
    status_code = 200 if ok else 500
    return jsonify({"ok": ok, "message": message, "config": safe_cfg}), status_code


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    host = os.environ.get("PLANEXE_FRONTEND_MULTIUSER_HOST", "0.0.0.0")
    port = 5000
    logger.info("Starting Frontend Multiuser on %s:%s", host, port)
    app.run(host=host, port=port)
