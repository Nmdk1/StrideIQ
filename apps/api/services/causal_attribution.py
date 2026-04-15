# Backward-compat shim — module moved to services/intelligence/causal_attribution.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.intelligence.causal_attribution")
_sys.modules[__name__] = _real
