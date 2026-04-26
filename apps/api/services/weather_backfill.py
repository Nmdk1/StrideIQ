# Backward-compat shim — module moved to services/sync/weather_backfill.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.sync.weather_backfill")
_sys.modules[__name__] = _real
