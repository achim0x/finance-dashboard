"""PWA routes (skill reference pwa.md): service worker served from the app
root with `Service-Worker-Allowed: /` plus the offline fallback page."""
from flask import Blueprint, current_app, render_template

bp = Blueprint("pwa", __name__)


@bp.route("/sw.js")
def service_worker():
    resp = current_app.send_static_file("sw.js")
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"  # never cache the SW itself
    return resp


@bp.route("/offline")
def offline():
    return render_template("errors/offline.html")
