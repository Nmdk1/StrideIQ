#!/usr/bin/env python3
"""Test API response format."""
import sys
sys.path.insert(0, '/app')

from services.rpi_enhanced import calculate_rpi_enhanced

# Test with user's race
result = calculate_rpi_enhanced(21097.5, 5234)  # Half marathon 1:27:14

print("API RESPONSE FORMAT TEST")
print("=" * 60)
print(f"RPI: {result.get('rpi')}")
print()

training = result.get('training', {})
per_mile_km = training.get('per_mile_km', {})

print("EASY PACE FORMAT:")
easy = per_mile_km.get('easy', {})
print(f"  mi: {easy.get('mi')}")
print(f"  km: {easy.get('km')}")
print(f"  display_mi: {easy.get('display_mi')}")
print(f"  display_km: {easy.get('display_km')}")
print()

print("OTHER PACES:")
for pace_type in ['marathon', 'threshold', 'interval', 'repetition']:
    pace = per_mile_km.get(pace_type, {})
    print(f"  {pace_type}: {pace.get('mi')} /mi, {pace.get('km')} /km")
