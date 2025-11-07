from __future__ import annotations

from pathlib import Path

from flask import Flask, render_template


TEMPLATE_DIR = Path(__file__).parent / "templates"


def create_app() -> Flask:
    """
    Instantiate a Flask app that renders the split-panel editor shell.
    """
    app = Flask(__name__, template_folder=str(TEMPLATE_DIR))

    @app.route("/")
    def index() -> str:
        return render_template("edit_index.html")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
