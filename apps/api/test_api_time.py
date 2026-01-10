#!/usr/bin/env python3
"""Test if API returns duration_formatted"""
import requests
import json

r = requests.get('http://localhost:8000/v1/activities')
data = r.json()

if data:
    act = data[0]
    print("Sample activity fields:")
    print(f"  duration_formatted: {act.get('duration_formatted')}")
    print(f"  moving_time: {act.get('moving_time')}")
    print(f"  pace_per_mile: {act.get('pace_per_mile')}")
    print(f"\nAll keys in response:")
    for key in sorted(act.keys()):
        print(f"  - {key}")
else:
    print("No activities found")


