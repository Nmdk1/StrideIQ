#!/usr/bin/env python3
"""Test VDOT accuracy with exact values."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.vdot_calculator import calculate_training_paces
from services.vdot_lookup import get_training_paces_from_vdot

def test_exact_vdot_50():
    """Test exact VDOT 50 paces."""
    print("Testing VDOT 50 (exact reference):")
    paces = calculate_training_paces(50.0)
    
    expected = {
        "easy": "8:15",
        "marathon": "7:00",
        "threshold": "6:35",
        "interval": "6:15",
        "repetition": "5:55"
    }
    
    print("\nTraining Paces:")
    for pace_type, expected_pace in expected.items():
        actual = paces.get(pace_type, {}).get("mi", "N/A")
        match = "✅" if actual == expected_pace else "❌"
        print(f"  {pace_type.upper()}: {actual} (expected {expected_pace}) {match}")
    
    # Also test lookup directly
    print("\nDirect Lookup Test:")
    lookup_paces = get_training_paces_from_vdot(50.0)
    if lookup_paces:
        print(f"  E: {lookup_paces.get('e_pace')} (expected 8:15) {'✅' if lookup_paces.get('e_pace') == '8:15' else '❌'}")
        print(f"  M: {lookup_paces.get('m_pace')} (expected 7:00) {'✅' if lookup_paces.get('m_pace') == '7:00' else '❌'}")
        print(f"  T: {lookup_paces.get('t_pace')} (expected 6:35) {'✅' if lookup_paces.get('t_pace') == '6:35' else '❌'}")
        print(f"  I: {lookup_paces.get('i_pace')} (expected 6:15) {'✅' if lookup_paces.get('i_pace') == '6:15' else '❌'}")
        print(f"  R: {lookup_paces.get('r_pace')} (expected 5:55) {'✅' if lookup_paces.get('r_pace') == '5:55' else '❌'}")

if __name__ == "__main__":
    test_exact_vdot_50()

