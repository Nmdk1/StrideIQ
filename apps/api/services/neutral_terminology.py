# Backward-compat shim — module moved to services/intelligence/neutral_terminology.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.intelligence.neutral_terminology")
_sys.modules[__name__] = _real
