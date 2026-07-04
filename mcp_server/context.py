"""Flask app bridge: the MCP server imports the service layer directly and
runs it inside an app context — never HTTP to the web app (skill rule)."""
_app = None


def get_app():
    global _app
    if _app is None:
        from app import create_app

        _app = create_app()
    return _app
