# Testing Guide

## Running Tests

### Backend Tests (pytest)

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_rpi_calculator.py

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test
pytest tests/test_rpi_calculator.py::TestRPICalculation::test_5k_20_minutes

# Verbose output
pytest -v
```

### Frontend Tests (Jest)

```bash
cd apps/web

# Install dependencies first
npm install

# Run all tests
npm test

# Run in watch mode
npm run test:watch

# Run with coverage
npm run test:coverage
```

## Test Structure

### Backend Tests (`apps/api/tests/`)

- `test_rpi_calculator.py` - RPI/Training Pace Calculator tests
- `test_age_grading.py` - WMA Age-Grading Calculator tests
- `test_heat_adjusted_pace.py` - Heat-Adjusted Pace Calculator tests
- `test_api_endpoints.py` - API endpoint integration tests

### Frontend Tests (`apps/web/__tests__/`)

- Component tests for React components
- Calculator logic tests
- UI interaction tests

## What's Tested

### Calculator Logic
- ✅ RPI calculation from race times
- ✅ Training pace calculations (E/M/T/I/R)
- ✅ Equivalent race time calculations
- ✅ Age-grading percentage calculations
- ✅ Equivalent open time calculations
- ✅ Heat/humidity adjustments
- ✅ Elevation gain/loss adjustments
- ✅ Effort level adjustments
- ✅ Unit conversions (km/miles, °F/°C)

### API Endpoints
- ✅ Request/response validation
- ✅ Error handling
- ✅ Input validation
- ✅ Edge cases

### Edge Cases
- ✅ Zero/negative inputs
- ✅ Very fast/slow times
- ✅ Very short/long distances
- ✅ Extreme ages
- ✅ Boundary conditions

## Adding New Tests

1. **Backend**: Add test functions to appropriate test file in `apps/api/tests/`
2. **Frontend**: Add test files to `apps/web/__tests__/`
3. Follow naming convention: `test_*.py` (backend) or `*.test.tsx` (frontend)
4. Use descriptive test names: `test_what_it_tests_when_condition`

## Continuous Integration

Tests should be run before:
- Committing code
- Creating pull requests
- Deploying to production

