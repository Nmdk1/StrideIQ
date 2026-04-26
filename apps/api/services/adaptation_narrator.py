# Backward-compat shim — module moved to services/intelligence/adaptation_narrator.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.intelligence.adaptation_narrator")
_sys.modules[__name__] = _real
