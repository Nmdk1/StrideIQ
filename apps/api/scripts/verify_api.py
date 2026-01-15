"""Verify API age-grading calculation matches official calculator."""

import requests

print('=== API VERIFICATION - ALAN JONES 2025 FACTORS ===')
print()

# Test 1: Age 79, 5K 27:14 (user's critical test case)
print('TEST 1: Age 79, 5K 27:14')
print('-' * 50)
response = requests.post(
    'http://localhost:8000/v1/public/age-grade',
    json={
        'age': 79,
        'sex': 'M',
        'distance_meters': 5000,
        'time_seconds': 1634  # 27:14
    }
)
data = response.json()

print(f'Our Results:')
print(f'  Performance %: {data.get("performance_percentage")}%')
print(f'  WMA Factor: {1/data.get("age_factor", 1):.4f}')
print(f'  Age Standard: {data.get("age_standard_formatted")}')
print()
print('Expected (Official):')
print('  Performance %: 74.3%')
print('  WMA Factor: 0.6334')
print('  Age Standard: 20:14.1')
print()

pct_ok_1 = abs(data.get('performance_percentage', 0) - 74.3) < 0.5
print(f'Result: {"PASS" if pct_ok_1 else "FAIL"} (diff: {abs(data.get("performance_percentage", 0) - 74.3):.2f}%)')
print()

# Test 2: Age 55, 5K 18:53
print('TEST 2: Age 55, 5K 18:53')
print('-' * 50)
response = requests.post(
    'http://localhost:8000/v1/public/age-grade',
    json={
        'age': 55,
        'sex': 'M',
        'distance_meters': 5000,
        'time_seconds': 1133  # 18:53
    }
)
data = response.json()

print(f'Our Results:')
print(f'  Performance %: {data.get("performance_percentage")}%')
print(f'  WMA Factor: {1/data.get("age_factor", 1):.4f}')
print(f'  Age Standard: {data.get("age_standard_formatted")}')
print()
print('Expected (Official):')
print('  Performance %: 80.65%')
print('  WMA Factor: 0.8425')
print()

pct_ok_2 = abs(data.get('performance_percentage', 0) - 80.65) < 0.5
print(f'Result: {"PASS" if pct_ok_2 else "FAIL"} (diff: {abs(data.get("performance_percentage", 0) - 80.65):.2f}%)')
print()

print('=' * 50)
if pct_ok_1 and pct_ok_2:
    print('ALL TESTS PASSED!')
else:
    print('SOME TESTS FAILED!')
