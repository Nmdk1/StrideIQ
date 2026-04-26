# Backward-compat shim — module moved to services/sync/garmin_ingestion_health.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.sync.garmin_ingestion_health")
_sys.modules[__name__] = _real
