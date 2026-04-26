# Backward-compat shim — module moved to services/sync/strava_ingest.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.sync.strava_ingest")
_sys.modules[__name__] = _real
