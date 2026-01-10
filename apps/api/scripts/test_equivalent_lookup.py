#!/usr/bin/env python3
"""Test equivalent race time lookup."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.vdot_lookup import get_vdot_lookup_tables, get_equivalent_race_times

tables = get_vdot_lookup_tables()
equiv_lookup = tables.get("equivalent_performance_lookup", {})

print("Testing equivalent lookup:")
print(f"Keys available: {sorted([float(k) for k in equiv_lookup.keys()])[:10]}...")

# Test VDOT 50.0
vdot_50 = equiv_lookup.get(50.0)
print(f"\nVDOT 50.0 direct lookup: {vdot_50 is not None}")
if vdot_50:
    print(f"  5K: {vdot_50.get('race_times_formatted', {}).get('5K')}")

# Test via function
equiv_50 = get_equivalent_race_times(50.0)
print(f"\nVDOT 50.0 via function: {equiv_50 is not None}")
if equiv_50:
    print(f"  5K: {equiv_50.get('race_times_formatted', {}).get('5K')}")

# Test VDOT 49.0
equiv_49 = get_equivalent_race_times(49.0)
print(f"\nVDOT 49.0 via function: {equiv_49 is not None}")
if equiv_49:
    print(f"  5K: {equiv_49.get('race_times_formatted', {}).get('5K')}")

