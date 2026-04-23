# Backward-compat shim — Activity queries live in services/intelligence/correlation_engine.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.intelligence.correlation_engine")
_sys.modules[__name__] = _real
