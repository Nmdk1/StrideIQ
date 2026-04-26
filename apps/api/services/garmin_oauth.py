# Backward-compat shim — module moved to services/sync/garmin_oauth.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.sync.garmin_oauth")
_sys.modules[__name__] = _real
