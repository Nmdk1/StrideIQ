# Backward-compat shim — module moved to services/sync/fit_parser.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.sync.fit_parser")
_sys.modules[__name__] = _real
