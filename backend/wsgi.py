"""
WSGI entry point for production servers (gunicorn, waitress).

`app.py` deliberately leaves its module-level `app` as None unless Flask's CLI
set FLASK_RUN_FROM_CLI, so importing it does not connect to MongoDB during a
test collection. A production server needs a real application object, so this
module builds one explicitly:

    gunicorn wsgi:app

Kept separate so `app.py` keeps working exactly as before for local runs.
"""

from app import create_app

app = create_app()
