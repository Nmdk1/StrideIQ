# Backward-compat shim — module moved to services/intelligence/correlation_persistence.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.intelligence.correlation_persistence")
_sys.modules[__name__] = _real
