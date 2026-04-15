# Backward-compat shim — module moved to services/intelligence/moment_narrator.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.intelligence.moment_narrator")
_sys.modules[__name__] = _real
