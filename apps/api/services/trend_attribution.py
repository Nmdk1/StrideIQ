# Backward-compat shim — module moved to services/intelligence/trend_attribution.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.intelligence.trend_attribution")
_sys.modules[__name__] = _real
