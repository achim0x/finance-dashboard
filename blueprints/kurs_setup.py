"""Setup page (spec §6.6/§6.10): price provider per price group, FX provider,
credentials (encrypted), polling interval, pytr 2FA login flow and the
availability test (spec §6.7). Not depot-scoped; linked from the dashboard.
"""
from flask import Blueprint, redirect, render_template, request, url_for

from domain.enums import Kursgruppe
from services import waehrung as waehrung_service
from services.depots import alle_depots
from services.kurse import (
    depot_testen,
    einstellung_lesen,
    einstellung_speichern,
    pytr_login_abschliessen,
    pytr_login_starten,
    pytr_session_status,
)
from utils.fehler import ValidierungsFehler
from utils.flash import flash_errors, flash_ok

bp = Blueprint("kurs_setup", __name__, url_prefix="/setup")


def _seite(testergebnisse=None, test_depot_id=None):
    return render_template(
        "kurs_setup/index.html",
        gruppen=[einstellung_lesen(g) for g in Kursgruppe],
        fx=waehrung_service.einstellung_lesen(),
        pytr_status=pytr_session_status(),
        depots=alle_depots(),
        testergebnisse=testergebnisse,
        test_depot_id=test_depot_id,
    )


@bp.route("")
def index():
    return _seite()


@bp.route("/kursgruppe/<gruppe>", methods=["POST"])
def kursgruppe_speichern(gruppe):
    try:
        kursgruppe = Kursgruppe(gruppe)
    except ValueError:
        return redirect(url_for(".index"))
    credentials = {
        schluessel[len("cred_"):]: wert
        for schluessel, wert in request.form.items()
        if schluessel.startswith("cred_")
    }
    try:
        einstellung_speichern(
            kursgruppe,
            provider_name=request.form.get("provider_name", ""),
            credentials=credentials,
            intervall=request.form.get("intervall", type=int) or 300,
            aktiv=bool(request.form.get("aktiv")),
        )
        flash_ok("kurse.setup.gespeichert")
    except ValidierungsFehler as fehler:
        flash_errors(fehler.meldungen)
    return redirect(url_for(".index"))


@bp.route("/fx", methods=["POST"])
def fx_speichern():
    credentials = {
        schluessel[len("cred_"):]: wert
        for schluessel, wert in request.form.items()
        if schluessel.startswith("cred_")
    }
    try:
        waehrung_service.einstellung_speichern(
            provider_name=request.form.get("provider_name", ""),
            credentials=credentials,
            intervall=request.form.get("intervall", type=int) or 3600,
            aktiv=bool(request.form.get("aktiv")),
        )
        flash_ok("kurse.setup.gespeichert")
    except ValidierungsFehler as fehler:
        flash_errors(fehler.meldungen)
    return redirect(url_for(".index"))


@bp.route("/pytr/login", methods=["POST"])
def pytr_login():
    """Step 1: trigger the TR login; TR sends the 4-digit code (spec §6.6)."""
    try:
        if pytr_login_starten():
            flash_ok("kurse.setup.pytr_login_gestartet")
        else:
            flash_errors(["kurse.setup.pytr_login_fehler"])
    except ValidierungsFehler as fehler:
        flash_errors(fehler.meldungen)
    return redirect(url_for(".index"))


@bp.route("/pytr/code", methods=["POST"])
def pytr_code():
    """Step 2: complete the login with the 2FA code (never stored)."""
    try:
        if pytr_login_abschliessen(request.form.get("code", "")):
            flash_ok("kurse.setup.pytr_angemeldet_ok")
        else:
            flash_errors(["kurse.setup.pytr_code_fehler"])
    except ValidierungsFehler as fehler:
        flash_errors(fehler.meldungen)
    return redirect(url_for(".index"))


@bp.route("/test", methods=["POST"])
def test():
    """Availability test (spec §6.7): query all instruments of the chosen
    depot; writes nothing (REQ-KURS-TEST)."""
    depot_id = request.form.get("depot_id", type=int)
    if not depot_id:
        return redirect(url_for(".index"))
    return _seite(testergebnisse=depot_testen(depot_id), test_depot_id=depot_id)
