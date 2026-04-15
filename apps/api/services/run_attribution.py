# Backward-compat shim — module moved to services/intelligence/run_attribution.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.intelligence.run_attribution")
_sys.modules[__name__] = _real
