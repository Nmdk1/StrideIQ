// Test script for Efficiency Context Checker and Heat-Adjusted Pace Calculator
// Run with: node apps/web/test_calculators.js

console.log('🧪 Testing Calculator Equations\n');
console.log('=' .repeat(60));

// ============================================================================
// HEAT-ADJUSTED PACE CALCULATOR TESTS
// ============================================================================

console.log('\n📊 HEAT-ADJUSTED PACE CALCULATOR TESTS\n');

// Helper functions from HeatAdjustedPace.tsx
const calculateDewPoint = (temp, rh, unit) => {
  const tempC = unit === 'F' ? (temp - 32) * 5/9 : temp;
  const a = 17.27;
  const b = 237.7;
  const alpha = (a * tempC) / (b + tempC) + Math.log(rh / 100);
  const dewPointC = (b * alpha) / (a - alpha);
  return unit === 'F' ? (dewPointC * 9/5) + 32 : dewPointC;
};

// Research-validated Temperature + Dew Point model
const calculateHeatAdjustment = (temp, dewPoint, unit) => {
  const tempF = unit === 'F' ? temp : (temp * 9/5) + 32;
  const dewPointF = unit === 'F' ? dewPoint : (dewPoint * 9/5) + 32;
  
  // Combined Temperature + Dew Point model (research-validated)
  const combinedValue = tempF + dewPointF;
  
  let adjustment = 0;
  
  if (combinedValue >= 170) {
    adjustment = 0.09 + ((combinedValue - 170) / 10) * 0.01;
  } else if (combinedValue >= 160) {
    adjustment = 0.065 + ((combinedValue - 160) / 10) * 0.0025;
  } else if (combinedValue >= 150) {
    adjustment = 0.045 + ((combinedValue - 150) / 10) * 0.002;
  } else if (combinedValue >= 140) {
    adjustment = 0.03 + ((combinedValue - 140) / 10) * 0.0015;
  } else if (combinedValue >= 130) {
    adjustment = 0.015 + ((combinedValue - 130) / 10) * 0.0015;
  } else if (combinedValue >= 120) {
    adjustment = 0.005 + ((combinedValue - 120) / 10) * 0.001;
  }
  
  return adjustment;
};

// Test cases for Heat-Adjusted Pace
const heatTests = [
  {
    name: 'Optimal conditions (60°F, low humidity)',
    temp: 60,
    humidity: 50,
    basePace: 480, // 8:00/mile
    expectedRange: [0, 0.02] // Should be minimal adjustment
  },
  {
    name: 'Moderate heat (75°F, moderate humidity)',
    temp: 75,
    humidity: 60,
    basePace: 480,
    expectedRange: [0.015, 0.03] // Combined ~135 = 1.5-3.0% range
  },
  {
    name: 'Hot conditions (85°F, moderate humidity)',
    temp: 85,
    humidity: 60,
    basePace: 480,
    expectedRange: [0.035, 0.055] // ~3.5-5.5% slowdown
  },
  {
    name: 'Very hot + high humidity (90°F, 80% RH)',
    temp: 90,
    humidity: 80,
    basePace: 480,
    expectedRange: [0.05, 0.10] // Significant slowdown
  },
  {
    name: 'Extreme heat + extreme humidity (95°F, 85% RH)',
    temp: 95,
    humidity: 85,
    basePace: 480,
    expectedRange: [0.08, 0.15] // Very significant slowdown
  },
  {
    name: 'Cool conditions (50°F, low humidity)',
    temp: 50,
    humidity: 40,
    basePace: 480,
    expectedRange: [0, 0.01] // No adjustment (below 60°F)
  },
  {
    name: 'Hot but dry (90°F, 30% RH)',
    temp: 90,
    humidity: 30,
    basePace: 480,
    expectedRange: [0.03, 0.045] // Combined ~144 = 3.0-4.5% range
  },
  {
    name: 'Moderate temp, high dew point (75°F, 70°F dew point)',
    temp: 75,
    dewPoint: 70,
    basePace: 480,
    expectedRange: [0.03, 0.045] // Combined 145 = 3.0-4.5% range
  }
];

let heatTestsPassed = 0;
let heatTestsFailed = 0;

heatTests.forEach((test, idx) => {
  const dewPoint = test.dewPoint || calculateDewPoint(test.temp, test.humidity, 'F');
  const adjustment = calculateHeatAdjustment(test.temp, dewPoint, 'F');
  const adjustedPace = test.basePace * (1 + adjustment);
  const slowdownPercent = adjustment * 100;
  
  const passed = adjustment >= test.expectedRange[0] && adjustment <= test.expectedRange[1];
  
  if (passed) {
    heatTestsPassed++;
    console.log(`✅ Test ${idx + 1}: ${test.name}`);
  } else {
    heatTestsFailed++;
    console.log(`❌ Test ${idx + 1}: ${test.name}`);
    console.log(`   Expected: ${(test.expectedRange[0] * 100).toFixed(1)}-${(test.expectedRange[1] * 100).toFixed(1)}%`);
    console.log(`   Got: ${slowdownPercent.toFixed(2)}%`);
  }
  
  console.log(`   Temp: ${test.temp}°F, Dew Point: ${dewPoint.toFixed(1)}°F`);
  console.log(`   Adjustment: ${slowdownPercent.toFixed(2)}%`);
  console.log(`   Base: ${(test.basePace / 60).toFixed(2)}:${(test.basePace % 60).toString().padStart(2, '0')}/mile`);
  console.log(`   Adjusted: ${(adjustedPace / 60).toFixed(2)}:${(adjustedPace % 60).toString().padStart(2, '0')}/mile\n`);
});

console.log(`Heat-Adjusted Pace: ${heatTestsPassed}/${heatTests.length} passed, ${heatTestsFailed} failed\n`);

// ============================================================================
// EFFICIENCY CONTEXT CHECKER TESTS
// ============================================================================

console.log('=' .repeat(60));
console.log('\n📊 EFFICIENCY CONTEXT CHECKER TESTS\n');

// Helper functions from EfficiencyContextChecker.tsx
const calculateHeatAdjustmentForComparison = (temp1, dewPoint1, temp2, dewPoint2) => {
  const heat1 = calculateHeatAdjustment(temp1, dewPoint1, 'F');
  const heat2 = calculateHeatAdjustment(temp2, dewPoint2, 'F');
  return (heat2 - heat1) * 100; // % impact on comparison
};

const efficiencyTests = [
  {
    name: 'Same conditions - no adjustment',
    race1Temp: 70,
    race1DewPoint: 60,
    race2Temp: 70,
    race2DewPoint: 60,
    expectedRange: [-0.1, 0.1] // Should be near zero
  },
  {
    name: 'Race 2 hotter - should show POSITIVE adjustment (more impressive)',
    race1Temp: 60,
    race1DewPoint: 50,
    race2Temp: 80,
    race2DewPoint: 65,
    expectedRange: [2, 5] // Race 2 was harder, so improvement is more impressive
  },
  {
    name: 'Race 2 cooler - should show NEGATIVE adjustment (less impressive)',
    race1Temp: 85,
    race1DewPoint: 75,
    race2Temp: 65,
    race2DewPoint: 55,
    expectedRange: [-7, -4] // Combined: 160 vs 120 = large difference
  },
  {
    name: 'Same temp, different humidity - Race 2 more humid',
    race1Temp: 80,
    race1DewPoint: 60,
    race2Temp: 80,
    race2DewPoint: 75,
    expectedRange: [1.0, 2.0] // Combined: 140 vs 155 = 1.5-3.0% difference
  },
  {
    name: 'Hotter but drier vs cooler but humid',
    race1Temp: 75,
    race1DewPoint: 70,
    race2Temp: 80,
    race2DewPoint: 60,
    expectedRange: [-1, 1] // Complex interaction - roughly similar difficulty
  },
  {
    name: 'Extreme difference - Race 2 much easier',
    race1Temp: 95,
    race1DewPoint: 85,
    race2Temp: 60,
    race2DewPoint: 50,
    expectedRange: [-11, -8] // Combined: 180 vs 110 = extreme difference
  }
];

let efficiencyTestsPassed = 0;
let efficiencyTestsFailed = 0;

efficiencyTests.forEach((test, idx) => {
  const adjustment = calculateHeatAdjustmentForComparison(
    test.race1Temp, test.race1DewPoint,
    test.race2Temp, test.race2DewPoint
  );
  
  const passed = adjustment >= test.expectedRange[0] && adjustment <= test.expectedRange[1];
  
  if (passed) {
    efficiencyTestsPassed++;
    console.log(`✅ Test ${idx + 1}: ${test.name}`);
  } else {
    efficiencyTestsFailed++;
    console.log(`❌ Test ${idx + 1}: ${test.name}`);
    console.log(`   Expected: ${test.expectedRange[0].toFixed(1)}% to ${test.expectedRange[1].toFixed(1)}%`);
    console.log(`   Got: ${adjustment.toFixed(2)}%`);
  }
  
  console.log(`   Race 1: ${test.race1Temp}°F / ${test.race1DewPoint}°F DP`);
  console.log(`   Race 2: ${test.race2Temp}°F / ${test.race2DewPoint}°F DP`);
  console.log(`   Adjustment: ${adjustment > 0 ? '+' : ''}${adjustment.toFixed(2)}%\n`);
});

console.log(`Efficiency Context Checker: ${efficiencyTestsPassed}/${efficiencyTests.length} passed, ${efficiencyTestsFailed} failed\n`);

// ============================================================================
// DEW POINT CALCULATION VALIDATION
// ============================================================================

console.log('=' .repeat(60));
console.log('\n📊 DEW POINT CALCULATION VALIDATION\n');

const dewPointTests = [
  { temp: 70, humidity: 50, expected: 50 },
  { temp: 80, humidity: 60, expected: 65 },
  { temp: 90, humidity: 70, expected: 79 },
  { temp: 75, humidity: 80, expected: 69 },
  { temp: 85, humidity: 85, expected: 80 }
];

let dewPointTestsPassed = 0;
let dewPointTestsFailed = 0;

dewPointTests.forEach((test, idx) => {
  const calculated = calculateDewPoint(test.temp, test.humidity, 'F');
  const diff = Math.abs(calculated - test.expected);
  const passed = diff < 3; // Allow 3°F tolerance
  
  if (passed) {
    dewPointTestsPassed++;
    console.log(`✅ Test ${idx + 1}: ${test.temp}°F @ ${test.humidity}% RH`);
  } else {
    dewPointTestsFailed++;
    console.log(`❌ Test ${idx + 1}: ${test.temp}°F @ ${test.humidity}% RH`);
    console.log(`   Expected: ~${test.expected}°F, Got: ${calculated.toFixed(1)}°F`);
  }
  console.log(`   Dew Point: ${calculated.toFixed(1)}°F\n`);
});

console.log(`Dew Point Calculation: ${dewPointTestsPassed}/${dewPointTests.length} passed, ${dewPointTestsFailed} failed\n`);

// ============================================================================
// SUMMARY
// ============================================================================

console.log('=' .repeat(60));
console.log('\n📈 TEST SUMMARY\n');
console.log(`Heat-Adjusted Pace Calculator: ${heatTestsPassed}/${heatTests.length} passed`);
console.log(`Efficiency Context Checker: ${efficiencyTestsPassed}/${efficiencyTests.length} passed`);
console.log(`Dew Point Calculation: ${dewPointTestsPassed}/${dewPointTests.length} passed`);
console.log(`\nTotal: ${heatTestsPassed + efficiencyTestsPassed + dewPointTestsPassed}/${heatTests.length + efficiencyTests.length + dewPointTests.length} tests passed`);

const totalFailed = heatTestsFailed + efficiencyTestsFailed + dewPointTestsFailed;
if (totalFailed === 0) {
  console.log('\n✅ All tests passed! Equations are working correctly.\n');
} else {
  console.log(`\n⚠️  ${totalFailed} test(s) failed. Review equations.\n`);
}

