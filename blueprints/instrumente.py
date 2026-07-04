"""Instrument routes (spec §7/§8): search (JSON for the buy form) and create."""
from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from domain.enums import Kategorie
from services.instrumente import instrument_anlegen, parse_instrument, suchen
from utils.fehler import ValidierungsFehler
from utils.flash import flash_errors, flash_ok

bp = Blueprint("instrumente", __name__, url_prefix="/instrumente")


@bp.route("/suche")
def suche():
    """JSON search by ISIN/WKN/name (used by the buy/sell forms)."""
    treffer = suchen(request.args.get("q", ""))
    return jsonify(
        [
            {
                "id": i.id,
                "isin": i.isin,
                "wkn": i.wkn,
                "name": i.name,
                "kategorie": i.kategorie,
                "waehrung": i.waehrung,
            }
            for i in treffer
        ]
    )


@bp.route("/neu", methods=["GET", "POST"])
def neu():
    if request.method == "POST":
        fields, errors = parse_instrument(request.form)
        if errors:
            flash_errors(errors)
        else:
            try:
                instrument = instrument_anlegen(fields)
                flash_ok("instrument.angelegt")
                depot_id = request.args.get("depot_id", type=int)
                if depot_id:
                    return redirect(
                        url_for("kaeufe.neu", depot_id=depot_id, instrument_id=instrument.id)
                    )
                return redirect(url_for("uebersicht.index"))
            except ValidierungsFehler as fehler:
                flash_errors(fehler.meldungen)
    return render_template(
        "instrumente/form.html",
        form=request.form,
        kategorien=[k.value for k in Kategorie],
        depot_id=request.args.get("depot_id", type=int),
    )
