# Backward-compat shim — module moved to services/sync/garmin_webhook_auth.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.sync.garmin_webhook_auth")
_sys.modules[__name__] = _real
