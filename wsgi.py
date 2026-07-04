"""Production WSGI entry point (run behind a TLS reverse proxy).

Example (waitress):  waitress-serve --listen=127.0.0.1:8080 wsgi:app
Example (mod_wsgi):  point WSGIScriptAlias at this file.
"""
from app import create_app

app = create_app()
