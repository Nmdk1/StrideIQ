# Backward-compat shim — module moved to services/sync/ingestion_state.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.sync.ingestion_state")
_sys.modules[__name__] = _real
