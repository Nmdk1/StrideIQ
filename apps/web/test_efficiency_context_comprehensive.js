// Comprehensive test suite for Efficiency Context Checker
// Tests ALL combinations of variables: heat/dew point, elevation, wind, effort

console.log('🧪 Comprehensive Efficiency Context Checker Tests\n');
console.log('=' .repeat(70));

// Helper functions matching the actual implementation
const calculateDewPoint = (temp, rh) => {
  const tempC = (temp - 32) * 5/9;
  const a = 17.27;
  const b = 237.7;
  const alpha = (a * tempC) / (b + tempC) + Math.log(rh / 100);
  const dewPointC = (b * alpha) / (a - alpha);
  return (dewPointC * 9/5) + 32;
};

const calculateHeatAdjustment = (temp, dewPoint) => {
  const combinedValue = temp + dewPoint;
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

// Test all variable combinations
let totalTests = 0;
let passedTests = 0;
let failedTests = 0;

// Test Case Structure:
// { name, race1: {temp, dewPoint, elevation, wind, effort}, race2: {...}, expectedRange }

const testCases = [
  // ===== SINGLE VARIABLE TESTS =====
  {
    name: 'Heat only - Race 2 hotter',
    race1: { temp: 60, dewPoint: 50, elevation: 0, wind: 0, effort: 'race' },
    race2: { temp: 80, dewPoint: 65, elevation: 0, wind: 0, effort: 'race' },
    pace1: 240, // 4:00/km
    expectedRange: [2.5, 4.0] // Should show positive adjustment
  },
  {
    name: 'Heat only - Race 2 cooler',
    race1: { temp: 85, dewPoint: 75, elevation: 0, wind: 0, effort: 'race' },
    race2: { temp: 65, dewPoint: 55, elevation: 0, wind: 0, effort: 'race' },
    pace1: 240,
    expectedRange: [-7, -4] // Should show negative adjustment
  },
  {
    name: 'Elevation only - Race 2 hillier',
    race1: { temp: 70, dewPoint: 60, elevation: 0, wind: 0, effort: 'race' },
    race2: { temp: 70, dewPoint: 60, elevation: 200, wind: 0, effort: 'race' },
    pace1: 240,
    expectedRange: [10, 20] // ~15 seconds/km for 200m = ~6-8% at 4:00/km pace
  },
  {
    name: 'Elevation only - Race 2 flatter',
    race1: { temp: 70, dewPoint: 60, elevation: 300, wind: 0, effort: 'race' },
    race2: { temp: 70, dewPoint: 60, elevation: 50, wind: 0, effort: 'race' },
    pace1: 240,
    expectedRange: [-12, -8] // Negative adjustment (easier conditions)
  },
  {
    name: 'Wind only - Race 2 more headwind',
    race1: { temp: 70, dewPoint: 60, elevation: 0, wind: 0, effort: 'race' },
    race2: { temp: 70, dewPoint: 60, elevation: 0, wind: 15, effort: 'race' },
    pace1: 240,
    expectedRange: [2.5, 4.5] // ~2-3% per 10mph headwind
  },
  {
    name: 'Wind only - Race 2 less headwind',
    race1: { temp: 70, dewPoint: 60, elevation: 0, wind: 20, effort: 'race' },
    race2: { temp: 70, dewPoint: 60, elevation: 0, wind: 5, effort: 'race' },
    pace1: 240,
    expectedRange: [-4.5, -2.5] // Negative adjustment
  },
  {
    name: 'Effort only - Race 2 easier effort',
    race1: { temp: 70, dewPoint: 60, elevation: 0, wind: 0, effort: 'race' },
    race2: { temp: 70, dewPoint: 60, elevation: 0, wind: 0, effort: 'easy' },
    pace1: 240,
    expectedRange: [-12, -8] // Easier effort = slower pace expected
  },
  
  // ===== TWO VARIABLE COMBINATIONS =====
  {
    name: 'Heat + Elevation - Race 2 hotter and hillier',
    race1: { temp: 60, dewPoint: 50, elevation: 0, wind: 0, effort: 'race' },
    race2: { temp: 85, dewPoint: 70, elevation: 150, wind: 0, effort: 'race' },
    pace1: 240,
    expectedRange: [8, 15] // Both factors make Race 2 harder
  },
  {
    name: 'Heat + Wind - Race 2 hotter with headwind',
    race1: { temp: 65, dewPoint: 55, elevation: 0, wind: 0, effort: 'race' },
    race2: { temp: 85, dewPoint: 70, elevation: 0, wind: 12, effort: 'race' },
    pace1: 240,
    expectedRange: [5, 9] // Heat + wind combine
  },
  {
    name: 'Elevation + Wind - Race 2 hillier with headwind',
    race1: { temp: 70, dewPoint: 60, elevation: 0, wind: 0, effort: 'race' },
    race2: { temp: 70, dewPoint: 60, elevation: 100, wind: 10, effort: 'race' },
    pace1: 240,
    expectedRange: [5, 9] // Elevation + wind combine
  },
  {
    name: 'Heat + Effort - Race 2 hotter but easier effort',
    race1: { temp: 70, dewPoint: 60, elevation: 0, wind: 0, effort: 'race' },
    race2: { temp: 90, dewPoint: 75, elevation: 0, wind: 0, effort: 'moderate' },
    pace1: 240,
    expectedRange: [-2, 2] // Heat makes it harder, but easier effort offsets
  },
  
  // ===== THREE VARIABLE COMBINATIONS =====
  {
    name: 'Heat + Elevation + Wind - All factors harder',
    race1: { temp: 60, dewPoint: 50, elevation: 0, wind: 0, effort: 'race' },
    race2: { temp: 85, dewPoint: 70, elevation: 200, wind: 15, effort: 'race' },
    pace1: 240,
    expectedRange: [12, 20] // All three combine
  },
  {
    name: 'Heat + Elevation + Effort - Complex interaction',
    race1: { temp: 70, dewPoint: 60, elevation: 50, wind: 0, effort: 'race' },
    race2: { temp: 90, dewPoint: 75, elevation: 250, wind: 0, effort: 'hard' },
    pace1: 240,
    expectedRange: [8, 15] // Heat + elevation harder, but harder effort
  },
  
  // ===== FOUR VARIABLE COMBINATIONS =====
  {
    name: 'All variables - Race 2 much harder',
    race1: { temp: 60, dewPoint: 50, elevation: 0, wind: 0, effort: 'race' },
    race2: { temp: 90, dewPoint: 80, elevation: 300, wind: 20, effort: 'race' },
    pace1: 240,
    expectedRange: [15, 25] // Extreme combination
  },
  {
    name: 'All variables - Mixed conditions',
    race1: { temp: 80, dewPoint: 70, elevation: 100, wind: 10, effort: 'race' },
    race2: { temp: 70, dewPoint: 60, elevation: 50, wind: 5, effort: 'moderate' },
    pace1: 240,
    expectedRange: [-8, -2] // Race 2 easier overall
  },
  
  // ===== EDGE CASES =====
  {
    name: 'No context - Should show raw pace change only',
    race1: { temp: null, dewPoint: null, elevation: null, wind: null, effort: null },
    race2: { temp: null, dewPoint: null, elevation: null, wind: null, effort: null },
    pace1: 240,
    pace2: 228, // 5% faster
    expectedRange: [4.9, 5.1] // Raw change only
  },
  {
    name: 'Partial context - Only heat provided',
    race1: { temp: 70, dewPoint: 60, elevation: null, wind: null, effort: null },
    race2: { temp: 85, dewPoint: 70, elevation: null, wind: null, effort: null },
    pace1: 240,
    expectedRange: [2, 5] // Only heat adjustment
  }
];

// Calculate adjustments (matching actual implementation)
const calculateAdjustments = (race1, race2, pace1Raw) => {
  let adjustedChange = 0; // Start with raw change (will be set by caller)
  const adjustments = [];
  
  // Heat adjustment
  if (race1.temp && race2.temp) {
    let dewPoint1 = race1.dewPoint;
    let dewPoint2 = race2.dewPoint;
    
    if (!dewPoint1 && race1.humidity) {
      dewPoint1 = calculateDewPoint(race1.temp, race1.humidity);
    } else if (!dewPoint1) {
      dewPoint1 = calculateDewPoint(race1.temp, 60);
    }
    
    if (!dewPoint2 && race2.humidity) {
      dewPoint2 = calculateDewPoint(race2.temp, race2.humidity);
    } else if (!dewPoint2) {
      dewPoint2 = calculateDewPoint(race2.temp, 60);
    }
    
    const heat1 = calculateHeatAdjustment(race1.temp, dewPoint1);
    const heat2 = calculateHeatAdjustment(race2.temp, dewPoint2);
    const heatDiff = (heat2 - heat1) * 100;
    
    if (Math.abs(heatDiff) > 0.1) {
      adjustedChange += heatDiff;
      adjustments.push(`Heat: ${heatDiff.toFixed(2)}%`);
    }
  }
  
  // Elevation adjustment: ~7.5 sec/km per 100m gain
  if (race1.elevation !== null && race2.elevation !== null) {
    const elevDiff = race2.elevation - race1.elevation;
    const elevImpact = (elevDiff / 100) * 7.5; // seconds per km
    const paceImpact = (elevImpact / pace1Raw) * 100; // % impact
    
    if (Math.abs(paceImpact) > 0.1) {
      adjustedChange += paceImpact;
      adjustments.push(`Elevation: ${paceImpact.toFixed(2)}%`);
    }
  }
  
  // Wind adjustment: ~2.5% per 10 mph headwind
  if (race1.wind !== null && race2.wind !== null) {
    const windDiff = race2.wind - race1.wind; // positive = more headwind in race 2
    const windImpact = (windDiff / 10) * 2.5; // % impact
    
    if (Math.abs(windImpact) > 0.1) {
      adjustedChange += windImpact;
      adjustments.push(`Wind: ${windImpact.toFixed(2)}%`);
    }
  }
  
  // Effort adjustment
  if (race1.effort && race2.effort && race1.effort !== race2.effort) {
    const effortMap = {
      'easy': 0.15,
      'moderate': 0.05,
      'hard': -0.05,
      'race': 0
    };
    const effort1 = effortMap[race1.effort] || 0;
    const effort2 = effortMap[race2.effort] || 0;
    const effortDiff = (effort2 - effort1) * 100;
    
    if (Math.abs(effortDiff) > 0.1) {
      adjustedChange -= effortDiff; // Note: subtract because easier effort = slower pace
      adjustments.push(`Effort: ${effortDiff.toFixed(2)}%`);
    }
  }
  
  return { adjustedChange, adjustments };
};

// Run tests
console.log('\n📊 COMPREHENSIVE VARIABLE COMBINATION TESTS\n');

testCases.forEach((test, idx) => {
  totalTests++;
  
  // Calculate raw pace change if pace2 provided, otherwise assume 5% improvement
  const pace1Raw = test.pace1;
  const pace2Raw = test.pace2 || (pace1Raw * 0.95); // 5% faster if not specified
  const rawChange = ((pace1Raw - pace2Raw) / pace1Raw) * 100;
  
  // Calculate adjustments
  const { adjustedChange: adjustment, adjustments } = calculateAdjustments(
    test.race1,
    test.race2,
    pace1Raw
  );
  
  const finalAdjustedChange = rawChange + adjustment;
  
  // Check if within expected range
  const passed = finalAdjustedChange >= test.expectedRange[0] && 
                 finalAdjustedChange <= test.expectedRange[1];
  
  if (passed) {
    passedTests++;
    console.log(`✅ Test ${idx + 1}: ${test.name}`);
  } else {
    failedTests++;
    console.log(`❌ Test ${idx + 1}: ${test.name}`);
    console.log(`   Expected: ${test.expectedRange[0].toFixed(1)}% to ${test.expectedRange[1].toFixed(1)}%`);
    console.log(`   Got: ${finalAdjustedChange.toFixed(2)}%`);
  }
  
  console.log(`   Raw change: ${rawChange.toFixed(2)}%`);
  if (adjustments.length > 0) {
    console.log(`   Adjustments: ${adjustments.join(', ')}`);
    console.log(`   Net adjustment: ${adjustment.toFixed(2)}%`);
  }
  console.log(`   Final adjusted: ${finalAdjustedChange.toFixed(2)}%\n`);
});

// Summary
console.log('=' .repeat(70));
console.log('\n📈 TEST SUMMARY\n');
console.log(`Total Tests: ${totalTests}`);
console.log(`Passed: ${passedTests}`);
console.log(`Failed: ${failedTests}`);
console.log(`\n${failedTests === 0 ? '✅ All tests passed!' : '⚠️  Some tests failed - review formulas.'}\n`);

