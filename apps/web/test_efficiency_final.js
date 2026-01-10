// Final comprehensive test suite for Efficiency Context Checker
// Tests ALL combinations: heat/dew point, elevation, effort (wind removed)

console.log('🧪 Final Efficiency Context Checker Tests\n');
console.log('=' .repeat(70));

// Helper functions matching actual implementation
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

const calculateAdjustments = (race1, race2, pace1Raw) => {
  let adjustedChange = 0;
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
      adjustedChange -= effortDiff;
      adjustments.push(`Effort: ${effortDiff.toFixed(2)}%`);
    }
  }
  
  return { adjustedChange, adjustments };
};

const testCases = [
  // Single variable tests
  {
    name: 'Heat only - Race 2 hotter',
    race1: { temp: 60, dewPoint: 50, elevation: null, effort: 'race' },
    race2: { temp: 80, dewPoint: 65, elevation: null, effort: 'race' },
    pace1: 240,
    expectedRange: [7.5, 9.0] // Raw 5% + heat adjustment 3.08% = ~8%
  },
  {
    name: 'Heat only - Race 2 cooler',
    race1: { temp: 85, dewPoint: 75, elevation: null, effort: 'race' },
    race2: { temp: 65, dewPoint: 55, elevation: null, effort: 'race' },
    pace1: 240,
    expectedRange: [-2, 0] // Raw 5% + heat adjustment -6% = ~-1%
  },
  {
    name: 'Elevation only - Race 2 hillier',
    race1: { temp: 70, dewPoint: 60, elevation: 0, effort: 'race' },
    race2: { temp: 70, dewPoint: 60, elevation: 200, effort: 'race' },
    pace1: 240,
    expectedRange: [10, 12] // Raw 5% + elevation 6.25% = ~11%
  },
  {
    name: 'Elevation only - Race 2 flatter',
    race1: { temp: 70, dewPoint: 60, elevation: 300, effort: 'race' },
    race2: { temp: 70, dewPoint: 60, elevation: 50, effort: 'race' },
    pace1: 240,
    expectedRange: [-4, -1] // Raw 5% + elevation -7.81% = ~-3%
  },
  {
    name: 'Effort only - Race 2 easier',
    race1: { temp: 70, dewPoint: 60, elevation: null, effort: 'race' },
    race2: { temp: 70, dewPoint: 60, elevation: null, effort: 'easy' },
    pace1: 240,
    expectedRange: [-12, -8]
  },
  
  // Two variable combinations
  {
    name: 'Heat + Elevation - Both harder',
    race1: { temp: 60, dewPoint: 50, elevation: 0, effort: 'race' },
    race2: { temp: 85, dewPoint: 70, elevation: 150, effort: 'race' },
    pace1: 240,
    expectedRange: [13, 15] // Raw 5% + heat 4.6% + elevation 4.69% = ~14%
  },
  {
    name: 'Heat + Effort - Hotter but easier effort',
    race1: { temp: 70, dewPoint: 60, elevation: null, effort: 'race' },
    race2: { temp: 90, dewPoint: 75, elevation: null, effort: 'moderate' },
    pace1: 240,
    expectedRange: [4, 6] // Raw 5% + heat 5.13% - effort 5% = ~5%
  },
  {
    name: 'Elevation + Effort - Hillier but easier effort',
    race1: { temp: 70, dewPoint: 60, elevation: 0, effort: 'race' },
    race2: { temp: 70, dewPoint: 60, elevation: 200, effort: 'moderate' },
    pace1: 240,
    expectedRange: [5, 7] // Raw 5% + elevation 6.25% - effort 5% = ~6%
  },
  
  // Three variable combinations
  {
    name: 'Heat + Elevation + Effort - All factors',
    race1: { temp: 60, dewPoint: 50, elevation: 0, effort: 'race' },
    race2: { temp: 85, dewPoint: 70, elevation: 200, effort: 'hard' },
    pace1: 240,
    expectedRange: [19, 22] // Raw 5% + heat 4.6% + elevation 6.25% - effort -5% = ~21%
  },
  
  // Edge cases
  {
    name: 'No context - Raw change only',
    race1: { temp: null, dewPoint: null, elevation: null, effort: null },
    race2: { temp: null, dewPoint: null, elevation: null, effort: null },
    pace1: 240,
    pace2: 228,
    expectedRange: [4.9, 5.1]
  },
  {
    name: 'Partial - Only heat',
    race1: { temp: 70, dewPoint: 60, elevation: null, effort: null },
    race2: { temp: 85, dewPoint: 70, elevation: null, effort: null },
    pace1: 240,
    expectedRange: [7.5, 9.0] // Raw 5% + heat 3.1% = ~8%
  },
  {
    name: 'Partial - Only elevation',
    race1: { temp: null, dewPoint: null, elevation: 0, effort: null },
    race2: { temp: null, dewPoint: null, elevation: 150, effort: null },
    pace1: 240,
    expectedRange: [9, 10] // Raw 5% + elevation 4.69% = ~10%
  }
];

let totalTests = 0;
let passedTests = 0;
let failedTests = 0;

testCases.forEach((test, idx) => {
  totalTests++;
  
  const pace1Raw = test.pace1;
  const pace2Raw = test.pace2 || (pace1Raw * 0.95);
  const rawChange = ((pace1Raw - pace2Raw) / pace1Raw) * 100;
  
  const { adjustedChange, adjustments } = calculateAdjustments(
    test.race1,
    test.race2,
    pace1Raw
  );
  
  const finalAdjustedChange = rawChange + adjustedChange;
  
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
  
  console.log(`   Raw: ${rawChange.toFixed(2)}%`);
  if (adjustments.length > 0) {
    console.log(`   Adjustments: ${adjustments.join(', ')}`);
  }
  console.log(`   Final: ${finalAdjustedChange.toFixed(2)}%\n`);
});

console.log('=' .repeat(70));
console.log(`\nTotal: ${passedTests}/${totalTests} passed, ${failedTests} failed\n`);

if (failedTests === 0) {
  console.log('✅ All tests passed! Formulas are accurate.\n');
} else {
  console.log('⚠️  Some tests failed - review formulas.\n');
}

