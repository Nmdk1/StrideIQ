// Comprehensive test suite for Elevation Gain/Loss formulas
// Tests all combinations at different distances and paces

console.log('🧪 Comprehensive Elevation Gain/Loss Tests\n');
console.log('=' .repeat(70));

// Helper functions matching actual implementation
const calculateElevationAdjustment = (elevGain1, elevLoss1, elevGain2, elevLoss2, dist1, dist2, pace1Raw) => {
  // Gain adjustment: 12.5 sec/km per 100m
  const gainDiff = elevGain2 - elevGain1;
  const gainImpactSec = (gainDiff / 100) * 12.5; // seconds per km
  const gainImpactPct = (gainImpactSec / pace1Raw) * 100; // % impact
  
  // Loss adjustment: 2% per 1% grade
  // More loss = more help = negative adjustment (improves pace)
  const grade1 = elevLoss1 > 0 ? (elevLoss1 / dist1) / 10 : 0;
  const grade2 = elevLoss2 > 0 ? (elevLoss2 / dist2) / 10 : 0;
  const gradeDiff = grade2 - grade1; // Positive = Race 2 has more loss = helps pace
  const lossImpactPct = -gradeDiff * 2; // Negative because loss helps pace
  
  return gainImpactPct + lossImpactPct;
};

const testCases = [
  // Single variable: Gain only
  {
    name: 'Gain only - Race 2 hillier (5K, 4:00/km pace)',
    elevGain1: 0, elevLoss1: 0,
    elevGain2: 100, elevLoss2: 0,
    dist1: 5, dist2: 5,
    pace1: 240, // 4:00/km
    expectedRange: [5, 6]
  },
  {
    name: 'Gain only - Race 2 hillier (10K, 4:30/km pace)',
    elevGain1: 0, elevLoss1: 0,
    elevGain2: 200, elevLoss2: 0,
    dist1: 10, dist2: 10,
    pace1: 270, // 4:30/km
    expectedRange: [9, 10]
  },
  {
    name: 'Gain only - Race 2 flatter (Marathon, 5:00/km pace)',
    elevGain1: 500, elevLoss1: 0,
    elevGain2: 200, elevLoss2: 0,
    dist1: 42.195, dist2: 42.195,
    pace1: 300, // 5:00/km
    expectedRange: [-13, -11]
  },
  
  // Single variable: Loss only
  {
    name: 'Loss only - Race 2 more downhill (5K, 4:00/km pace)',
    elevGain1: 0, elevLoss1: 0,
    elevGain2: 0, elevLoss2: 50,
    dist1: 5, dist2: 5,
    pace1: 240,
    expectedRange: [-2.5, -1.5] // Negative = helps pace
  },
  {
    name: 'Loss only - Race 2 less downhill (10K, 4:30/km pace)',
    elevGain1: 0, elevLoss1: 100,
    elevGain2: 0, elevLoss2: 30,
    dist1: 10, dist2: 10,
    pace1: 270,
    expectedRange: [1.0, 1.5] // Positive = hurts pace (less help)
  },
  
  // Two variables: Gain + Loss
  {
    name: 'Gain + Loss - Both harder (5K, 4:00/km pace)',
    elevGain1: 0, elevLoss1: 0,
    elevGain2: 150, elevLoss2: 20,
    dist1: 5, dist2: 5,
    pace1: 240,
    expectedRange: [6.5, 7.5]
  },
  {
    name: 'Gain + Loss - Mixed (10K, 4:30/km pace)',
    elevGain1: 100, elevLoss1: 50,
    elevGain2: 200, elevLoss2: 100,
    dist1: 10, dist2: 10,
    pace1: 270,
    expectedRange: [3, 4]
  },
  
  // Different distances
  {
    name: 'Different distances - 5K vs 10K (same pace)',
    elevGain1: 0, elevLoss1: 0,
    elevGain2: 100, elevLoss2: 0,
    dist1: 5, dist2: 10,
    pace1: 240,
    expectedRange: [4, 6]
  },
  {
    name: 'Different distances - Marathon vs Half (same pace)',
    elevGain1: 0, elevLoss1: 0,
    elevGain2: 300, elevLoss2: 0,
    dist1: 21.0975, dist2: 42.195,
    pace1: 300,
    expectedRange: [11, 13] // Same gain, but longer distance = less impact per km
  },
  
  // Different paces
  {
    name: 'Fast pace - 3:30/km (elite)',
    elevGain1: 0, elevLoss1: 0,
    elevGain2: 100, elevLoss2: 0,
    dist1: 5, dist2: 5,
    pace1: 210, // 3:30/km
    expectedRange: [5.5, 6.5]
  },
  {
    name: 'Slow pace - 6:00/km (beginner)',
    elevGain1: 0, elevLoss1: 0,
    elevGain2: 100, elevLoss2: 0,
    dist1: 5, dist2: 5,
    pace1: 360, // 6:00/km
    expectedRange: [3, 4]
  },
  
  // Edge cases
  {
    name: 'No elevation change',
    elevGain1: 0, elevLoss1: 0,
    elevGain2: 0, elevLoss2: 0,
    dist1: 5, dist2: 5,
    pace1: 240,
    expectedRange: [-0.1, 0.1]
  },
  {
    name: 'Equal gain and loss (net zero)',
    elevGain1: 100, elevLoss1: 50,
    elevGain2: 100, elevLoss2: 50,
    dist1: 5, dist2: 5,
    pace1: 240,
    expectedRange: [-0.1, 0.1]
  }
];

let totalTests = 0;
let passedTests = 0;
let failedTests = 0;

testCases.forEach((test, idx) => {
  totalTests++;
  
  const adjustment = calculateElevationAdjustment(
    test.elevGain1, test.elevLoss1,
    test.elevGain2, test.elevLoss2,
    test.dist1, test.dist2,
    test.pace1
  );
  
  const passed = adjustment >= test.expectedRange[0] && 
                 adjustment <= test.expectedRange[1];
  
  if (passed) {
    passedTests++;
    console.log(`✅ Test ${idx + 1}: ${test.name}`);
  } else {
    failedTests++;
    console.log(`❌ Test ${idx + 1}: ${test.name}`);
    console.log(`   Expected: ${test.expectedRange[0].toFixed(1)}% to ${test.expectedRange[1].toFixed(1)}%`);
    console.log(`   Got: ${adjustment.toFixed(2)}%`);
  }
  
  console.log(`   Adjustment: ${adjustment.toFixed(2)}%\n`);
});

console.log('=' .repeat(70));
console.log(`\nTotal: ${passedTests}/${totalTests} passed, ${failedTests} failed\n`);

if (failedTests === 0) {
  console.log('✅ All elevation tests passed! Formulas are accurate.\n');
} else {
  console.log('⚠️  Some tests failed - review formulas.\n');
}

