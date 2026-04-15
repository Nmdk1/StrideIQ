# Backward-compat shim — module moved to services/intelligence/narrative_translator.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.intelligence.narrative_translator")
_sys.modules[__name__] = _real
