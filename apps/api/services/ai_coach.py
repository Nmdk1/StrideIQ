"""Backward-compatibility shim - ai_coach.py moved to services/coaching/ package."""
import importlib as _il
import sys as _sys

_real = _il.import_module("services.coaching")
_sys.modules[__name__] = _real
