# Backward-compat shim — module moved to services/intelligence/workout_narrative_generator.py
import importlib as _il, sys as _sys
_real = _il.import_module("services.intelligence.workout_narrative_generator")
_sys.modules[__name__] = _real
