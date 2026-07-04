"""Blueprint registration. One module per feature area (spec §8)."""
from flask import Flask


def register_blueprints(app: Flask) -> None:
    from blueprints.uebersicht import bp as uebersicht_bp
    from blueprints.depots import bp as depots_bp
    from blueprints.bestand import bp as bestand_bp
    from blueprints.kaeufe import bp as kaeufe_bp
    from blueprints.verkaeufe import bp as verkaeufe_bp
    from blueprints.zahlungen import bp as zahlungen_bp
    from blueprints.dividenden import bp as dividenden_bp
    from blueprints.steuern import bp as steuern_bp
    from blueprints.transaktionen import bp as transaktionen_bp
    from blueprints.snapshots import bp as snapshots_bp
    from blueprints.instrumente import bp as instrumente_bp
    from blueprints.kurse import bp as kurse_bp
    from blueprints.kurs_setup import bp as kurs_setup_bp
    from blueprints.export import bp as export_bp
    from blueprints.einstellungen import bp as einstellungen_bp
    from blueprints.pwa import bp as pwa_bp

    for bp in (
        uebersicht_bp,
        depots_bp,
        bestand_bp,
        kaeufe_bp,
        verkaeufe_bp,
        zahlungen_bp,
        dividenden_bp,
        steuern_bp,
        transaktionen_bp,
        snapshots_bp,
        instrumente_bp,
        kurse_bp,
        kurs_setup_bp,
        export_bp,
        einstellungen_bp,
        pwa_bp,
    ):
        app.register_blueprint(bp)
