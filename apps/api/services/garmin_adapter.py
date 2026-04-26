# Backward-compat shim — module moved to services/sync/garmin_adapter.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.sync.garmin_adapter")
_sys.modules[__name__] = _real
