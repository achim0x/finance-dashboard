"""Snapshot routes (spec §7): create named snapshots, compare two (REQ-SNAPSHOT)."""
from flask import Blueprint, redirect, render_template, request, session, url_for

from services.depots import get_depot_or_404
from services.snapshots import (
    snapshot_erstellen,
    snapshot_loeschen,
    snapshots_fuer_depot,
    vergleich,
)
from utils.fehler import ValidierungsFehler
from utils.flash import flash_errors, flash_ok

bp = Blueprint("snapshots", __name__, url_prefix="/depots/<int:depot_id>/snapshots")


@bp.route("")
def index(depot_id):
    depot = get_depot_or_404(depot_id)
    session["aktuelles_depot_id"] = depot.id
    return render_template(
        "snapshots/index.html", depot=depot, snapshots=snapshots_fuer_depot(depot_id)
    )


@bp.route("/neu", methods=["POST"])
def neu(depot_id):
    depot = get_depot_or_404(depot_id)
    try:
        snapshot_erstellen(depot, request.form.get("name", ""), request.form.get("notiz"))
        flash_ok("snapshot.erstellt")
    except ValidierungsFehler as fehler:
        flash_errors(fehler.meldungen)
    return redirect(url_for(".index", depot_id=depot_id))


@bp.route("/<int:snapshot_id>/loeschen", methods=["POST"])
def loeschen(depot_id, snapshot_id):
    get_depot_or_404(depot_id)
    try:
        snapshot_loeschen(snapshot_id)
        flash_ok("snapshot.geloescht")
    except ValidierungsFehler as fehler:
        flash_errors(fehler.meldungen)
    return redirect(url_for(".index", depot_id=depot_id))


@bp.route("/vergleich")
def vergleich_route(depot_id):
    depot = get_depot_or_404(depot_id)
    a_id = request.args.get("a", type=int)
    b_id = request.args.get("b", type=int)
    if not a_id or not b_id:
        flash_errors(["fehler.snapshot_auswahl"])
        return redirect(url_for(".index", depot_id=depot_id))
    try:
        daten = vergleich(a_id, b_id)
    except ValidierungsFehler as fehler:
        flash_errors(fehler.meldungen)
        return redirect(url_for(".index", depot_id=depot_id))
    return render_template("snapshots/vergleich.html", depot=depot, daten=daten)
