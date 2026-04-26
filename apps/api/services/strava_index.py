# Backward-compat shim — module moved to services/sync/strava_index.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.sync.strava_index")
_sys.modules[__name__] = _real
