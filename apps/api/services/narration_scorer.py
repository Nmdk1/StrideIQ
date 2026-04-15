# Backward-compat shim — module moved to services/intelligence/narration_scorer.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.intelligence.narration_scorer")
_sys.modules[__name__] = _real
