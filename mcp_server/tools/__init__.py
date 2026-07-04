from . import lesen, reporting, writes


def register_all(mcp):
    lesen.register(mcp)
    reporting.register(mcp)
    writes.register(mcp)
