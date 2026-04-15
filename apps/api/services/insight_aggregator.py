# Backward-compat shim — module moved to services/intelligence/insight_aggregator.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.intelligence.insight_aggregator")
_sys.modules[__name__] = _real
