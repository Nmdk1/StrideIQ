# Backward-compat shim — module moved to services/intelligence/n1_insight_generator.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.intelligence.n1_insight_generator")
_sys.modules[__name__] = _real
