# Backward-compat shim — module moved to services/intelligence/correlation_layers.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.intelligence.correlation_layers")
_sys.modules[__name__] = _real
