# Backward-compat shim — module moved to services/sync/activity_deduplication.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.sync.activity_deduplication")
_sys.modules[__name__] = _real
