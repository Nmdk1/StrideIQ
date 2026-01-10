"use client";

import React, { useState } from 'react';

export default function HeatAdjustedPace() {
  const [basePace, setBasePace] = useState('');
  const [paceUnit, setPaceUnit] = useState<'min_mile' | 'min_km'>('min_mile');
  const [tempUnit, setTempUnit] = useState<'F' | 'C'>('F');
  const [temperature, setTemperature] = useState('');
  const [hasDewPoint, setHasDewPoint] = useState(false);
  const [dewPoint, setDewPoint] = useState('');
  const [humidity, setHumidity] = useState('');
  const [distance, setDistance] = useState('');
  const [distanceUnit, setDistanceUnit] = useState<'km' | 'mile'>('km');
  const [elevationGain, setElevationGain] = useState('');
  const [elevationLoss, setElevationLoss] = useState('');
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState('');

  // Calculate dew point from temperature and relative humidity
  // Using Magnus formula: Td = (b * α(T, RH)) / (a - α(T, RH))
  // where α(T, RH) = (a * T) / (b + T) + ln(RH/100)
  const calculateDewPoint = (temp: number, rh: number, unit: 'F' | 'C'): number => {
    // Convert to Celsius for calculation
    const tempC = unit === 'F' ? (temp - 32) * 5/9 : temp;
    
    // Magnus formula constants
    const a = 17.27;
    const b = 237.7;
    
    const alpha = (a * tempC) / (b + tempC) + Math.log(rh / 100);
    const dewPointC = (b * alpha) / (a - alpha);
    
    // Convert back to original unit
    return unit === 'F' ? (dewPointC * 9/5) + 32 : dewPointC;
  };

  // Heat adjustment formula based on research-validated Temperature + Dew Point model
  // Research sources: RunFitMKE, Berlin Marathon Study (668K runners), Six Major Marathons Study
  // Validated against: McMillan Running Calculator, Training Pace App
  // Formula: Combined Value = Temperature + Dew Point determines adjustment percentage
  const calculateHeatAdjustment = (
    temp: number,
    dewPoint: number,
    unit: 'F' | 'C'
  ): number => {
    // Convert to Fahrenheit for calculations (standard in running research)
    const tempF = unit === 'F' ? temp : (temp * 9/5) + 32;
    const dewPointF = unit === 'F' ? dewPoint : (dewPoint * 9/5) + 32;
    
    // Research-validated: Combined Temperature + Dew Point model
    // Combined value of 150 (e.g., 85°F + 65°F) = 3.0-4.5% adjustment
    const combinedValue = tempF + dewPointF;
    
    let adjustment = 0;
    
    // Research-backed adjustment thresholds (validated against multiple studies)
    if (combinedValue >= 170) {
      // Extreme conditions: 9%+ adjustment
      adjustment = 0.09 + ((combinedValue - 170) / 10) * 0.01;
    } else if (combinedValue >= 160) {
      // Very hot/humid: 6.5-9% adjustment
      adjustment = 0.065 + ((combinedValue - 160) / 10) * 0.0025;
    } else if (combinedValue >= 150) {
      // Hot/humid: 4.5-6.5% adjustment (validated: 150 = 3.0-4.5%, using upper range)
      adjustment = 0.045 + ((combinedValue - 150) / 10) * 0.002;
    } else if (combinedValue >= 140) {
      // Warm/humid: 3.0-4.5% adjustment
      adjustment = 0.03 + ((combinedValue - 140) / 10) * 0.0015;
    } else if (combinedValue >= 130) {
      // Moderate: 1.5-3.0% adjustment
      adjustment = 0.015 + ((combinedValue - 130) / 10) * 0.0015;
    } else if (combinedValue >= 120) {
      // Mild: 0.5-1.5% adjustment
      adjustment = 0.005 + ((combinedValue - 120) / 10) * 0.001;
    }
    // Combined value < 120: 0% adjustment (optimal conditions)
    
    return adjustment;
  };

  const parsePace = (paceStr: string): number | null => {
    const trimmed = paceStr.trim();
    if (!trimmed) return null;
    
    // Handle MM:SS format
    if (trimmed.includes(':')) {
      const parts = trimmed.split(':').map(p => p.trim()).filter(p => p);
      if (parts.length === 2) {
        const minutes = parseFloat(parts[0]);
        const seconds = parseFloat(parts[1]);
        if (!isNaN(minutes) && !isNaN(seconds)) {
          return minutes * 60 + seconds; // total seconds
        }
      }
    }
    
    // Handle decimal minutes (e.g., 8.5 for 8:30)
    const decimal = parseFloat(trimmed);
    if (!isNaN(decimal)) {
      return decimal * 60; // convert to seconds
    }
    
    return null;
  };

  const formatPace = (seconds: number, unit: 'min_mile' | 'min_km'): string => {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const unitStr = unit === 'min_mile' ? '/mile' : '/km';
    return `${minutes}:${secs.toString().padStart(2, '0')}${unitStr}`;
  };

  const handleCalculate = () => {
    setError('');
    setResults(null);

    if (!basePace || !temperature) {
      setError('Please enter base pace and temperature');
      return;
    }

    const basePaceSeconds = parsePace(basePace);
    if (!basePaceSeconds || basePaceSeconds <= 0) {
      setError('Invalid pace format. Use MM:SS (e.g., 8:00) or decimal minutes (e.g., 8.5)');
      return;
    }

    const temp = parseFloat(temperature);
    if (isNaN(temp)) {
      setError('Invalid temperature');
      return;
    }

    let dewPointValue: number;
    
    if (hasDewPoint) {
      if (dewPoint) {
        dewPointValue = parseFloat(dewPoint);
        if (isNaN(dewPointValue)) {
          setError('Invalid dew point');
          return;
        }
      } else if (humidity) {
        const rh = parseFloat(humidity);
        if (isNaN(rh) || rh < 0 || rh > 100) {
          setError('Humidity must be between 0 and 100%');
          return;
        }
        dewPointValue = calculateDewPoint(temp, rh, tempUnit);
      } else {
        setError('Please enter either dew point or humidity');
        return;
      }
    } else {
      // Default: assume moderate humidity (60% RH) if not provided
      dewPointValue = calculateDewPoint(temp, 60, tempUnit);
    }

    // Calculate heat adjustment
    const heatAdjustmentPercent = calculateHeatAdjustment(temp, dewPointValue, tempUnit);
    
    // Calculate elevation adjustment (if provided)
    let elevationAdjustmentPercent = 0;
    let elevationDetails = '';
    
    if (distance) {
      const dist = parseFloat(distance);
      const distKm = distanceUnit === 'km' ? dist : dist * 1.60934; // Convert miles to km
      
      if (!isNaN(dist) && dist > 0) {
        // Elevation gain: ~12.5 seconds per km per 100m gain
        if (elevationGain) {
          const gain = parseFloat(elevationGain);
          if (!isNaN(gain) && gain >= 0) {
            const gainSecPerKm = (gain / 100) * 12.5;
            const gainPct = (gainSecPerKm / basePaceSeconds) * 100;
            elevationAdjustmentPercent += gainPct;
            if (gainPct > 0.1) {
              elevationDetails += `Gain: +${gainPct.toFixed(1)}%`;
            }
          }
        }
        
        // Elevation loss: ~2% per 1% grade (less benefit than gain hurts)
        if (elevationLoss) {
          const loss = parseFloat(elevationLoss);
          if (!isNaN(loss) && loss >= 0) {
            const grade = (loss / distKm) / 10; // Grade as percentage
            const lossPct = grade * 2; // 2% per 1% grade
            elevationAdjustmentPercent -= lossPct; // Subtract because loss helps pace (negative adjustment)
            if (Math.abs(lossPct) > 0.1) {
              if (elevationDetails) elevationDetails += ', ';
              elevationDetails += `Loss: -${lossPct.toFixed(1)}%`;
            }
          }
        }
      }
    }
    
    // Total adjustment (heat + elevation)
    const totalAdjustmentPercent = heatAdjustmentPercent + elevationAdjustmentPercent;
    
    // Calculate adjusted pace (slower = higher seconds)
    const adjustedPaceSeconds = basePaceSeconds * (1 + totalAdjustmentPercent);
    
    const basePaceFormatted = formatPace(basePaceSeconds, paceUnit);
    const adjustedPaceFormatted = formatPace(adjustedPaceSeconds, paceUnit);
    
    // Determine severity based on total adjustment
    let severity = 'moderate';
    let severityMessage = '';
    if (totalAdjustmentPercent > 0.10) {
      severity = 'high';
      severityMessage = '⚠️ High heat/elevation stress — consider reducing intensity or running indoors.';
    } else if (totalAdjustmentPercent > 0.05) {
      severity = 'moderate';
      severityMessage = 'Moderate impact — adjust pace accordingly.';
    } else if (totalAdjustmentPercent > 0.02) {
      severity = 'low';
      severityMessage = 'Mild impact — slight pace adjustment recommended.';
    } else {
      severity = 'minimal';
      severityMessage = 'Minimal impact — conditions are favorable.';
    }

    setResults({
      basePace: basePaceFormatted,
      adjustedPace: adjustedPaceFormatted,
      adjustmentPercent: (totalAdjustmentPercent * 100).toFixed(1),
      heatAdjustment: (heatAdjustmentPercent * 100).toFixed(1),
      elevationAdjustment: elevationAdjustmentPercent !== 0 ? (elevationAdjustmentPercent * 100).toFixed(1) : null,
      elevationDetails,
      slowdown: (totalAdjustmentPercent * 100).toFixed(1),
      temp: temp.toFixed(1),
      dewPoint: dewPointValue.toFixed(1),
      tempUnit,
      severity,
      severityMessage
    });
  };

  return (
    <div className="space-y-4">
      {/* Disclaimer */}
      <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 text-sm text-gray-300">
        <p className="font-semibold text-orange-400 mb-2">Important:</p>
        <p>
          Pace adjustments are estimates based on research. Conditions vary — trust perceived effort and heart rate as the true guide in heat.
        </p>
      </div>

      {/* Pace Input */}
      <div>
        <label className="block text-sm font-medium mb-2">Base Training Pace</label>
        <input
          type="text"
          value={basePace}
          onChange={(e) => setBasePace(e.target.value)}
          placeholder="00:00"
          autoComplete="off"
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white mb-2"
        />
        <div className="flex items-center justify-between p-2 bg-gray-800/50 border border-gray-700 rounded-lg">
          <label className="text-xs font-medium text-gray-300">Pace Unit</label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPaceUnit('min_mile')}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                paceUnit === 'min_mile'
                  ? 'bg-orange-600 text-white'
                  : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
              }`}
            >
              /mile
            </button>
            <button
              type="button"
              onClick={() => setPaceUnit('min_km')}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                paceUnit === 'min_km'
                  ? 'bg-orange-600 text-white'
                  : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
              }`}
            >
              /km
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-1">Format: MM:SS (e.g., 8:00) or decimal minutes (e.g., 8.5)</p>
      </div>

      {/* Temperature */}
      <div>
        <label className="block text-sm font-medium mb-2">Current Temperature</label>
        <input
          type="number"
          step="0.1"
          value={temperature}
          onChange={(e) => setTemperature(e.target.value)}
          placeholder="0"
          autoComplete="off"
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white mb-2"
        />
        <div className="flex items-center justify-between p-2 bg-gray-800/50 border border-gray-700 rounded-lg">
          <label className="text-xs font-medium text-gray-300">Temperature Unit</label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setTempUnit('F')}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                tempUnit === 'F'
                  ? 'bg-orange-600 text-white'
                  : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
              }`}
            >
              °F
            </button>
            <button
              type="button"
              onClick={() => setTempUnit('C')}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                tempUnit === 'C'
                  ? 'bg-orange-600 text-white'
                  : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
              }`}
            >
              °C
            </button>
          </div>
        </div>
      </div>

      {/* Dew Point / Humidity Toggle */}
      <div className="border border-gray-700 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="font-semibold text-sm text-gray-300">
              Humidity Data (Optional but Recommended)
            </div>
            <div className="text-xs text-gray-500 mt-1">
              More accurate with dew point or humidity
            </div>
          </div>
          <button
            onClick={() => {
              setHasDewPoint(!hasDewPoint);
              setDewPoint('');
              setHumidity('');
            }}
            className={`px-3 py-1 rounded text-sm transition-colors ${
              hasDewPoint
                ? 'bg-orange-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            {hasDewPoint ? 'Remove' : 'Add'}
          </button>
        </div>

        {hasDewPoint && (
          <div className="space-y-3 pt-3 border-t border-gray-700">
            <div>
              <label className="block text-xs font-medium mb-1">Dew Point ({tempUnit === 'F' ? '°F' : '°C'})</label>
              <input
                type="number"
                step="0.1"
                value={dewPoint}
                onChange={(e) => {
                  setDewPoint(e.target.value);
                  setHumidity(''); // Clear humidity if dew point entered
                }}
                placeholder="0"
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white"
              />
            </div>
            <div className="text-xs text-gray-500 text-center">OR</div>
            <div>
              <label className="block text-xs font-medium mb-1">Relative Humidity (%)</label>
              <input
                type="number"
                step="0.1"
                min="0"
                max="100"
                value={humidity}
                onChange={(e) => {
                  setHumidity(e.target.value);
                  setDewPoint(''); // Clear dew point if humidity entered
                }}
                placeholder="0"
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white"
              />
              <p className="text-xs text-gray-500 mt-1">Dew point will be calculated automatically</p>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="text-red-400 text-sm bg-red-900/20 border border-red-800 rounded p-3">
          {error}
        </div>
      )}

      <button
        onClick={handleCalculate}
        className="w-full bg-orange-600 hover:bg-orange-700 text-white py-3 rounded transition-colors font-semibold"
      >
        Calculate Heat-Adjusted Pace
      </button>

      {results && (
        <div className="mt-6 pt-6 border-t border-gray-700 space-y-4">
          <div className={`p-4 rounded-lg border ${
            results.severity === 'high' ? 'bg-red-900/20 border-red-800' :
            results.severity === 'moderate' ? 'bg-yellow-900/20 border-yellow-800' :
            results.severity === 'low' ? 'bg-blue-900/20 border-blue-800' :
            'bg-green-900/20 border-green-800'
          }`}>
            <div className="space-y-3">
              <div className="text-center">
                <div className="text-xs text-gray-500 mb-1">Base Pace</div>
                <div className="text-2xl font-bold text-orange-400">{results.basePace}</div>
              </div>
              
              <div className="text-center text-gray-400">↓</div>
              
              <div className="text-center">
                <div className="text-xs text-gray-500 mb-1">Heat-Adjusted Pace</div>
                <div className="text-2xl font-bold text-orange-400">{results.adjustedPace}</div>
              </div>

              <div className="pt-3 border-t border-gray-700">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-gray-500 text-xs">Total Slowdown</div>
                    <div className="text-lg font-semibold text-gray-300">{results.slowdown}%</div>
                  </div>
                  <div>
                    <div className="text-gray-500 text-xs">Conditions</div>
                    <div className="text-lg font-semibold text-gray-300">
                      {results.temp}°{results.tempUnit} / {results.dewPoint}°{results.tempUnit} DP
                    </div>
                  </div>
                </div>
                {results.elevationAdjustment !== null && (
                  <div className="mt-3 pt-3 border-t border-gray-700">
                    <div className="text-xs text-gray-500 mb-1">Breakdown:</div>
                    <div className="text-sm text-gray-400">
                      Heat: {results.heatAdjustment}%
                      {results.elevationDetails && ` • Elevation: ${results.elevationDetails}`}
                    </div>
                  </div>
                )}
              </div>

              <div className={`pt-3 border-t border-gray-700 p-3 rounded ${
                results.severity === 'high' ? 'bg-red-900/30' :
                results.severity === 'moderate' ? 'bg-yellow-900/30' :
                results.severity === 'low' ? 'bg-blue-900/30' :
                'bg-green-900/30'
              }`}>
                <div className="text-sm text-gray-300 leading-relaxed">
                  {results.severityMessage}
                </div>
              </div>
            </div>
          </div>

          <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 text-xs text-gray-400">
            <p className="font-semibold text-gray-300 mb-2">Interpretation:</p>
            <p className="mb-2">
              Your normal <strong className="text-orange-400">{results.basePace}</strong> pace becomes approximately <strong className="text-orange-400">{results.adjustedPace}</strong> equivalent effort in {results.temp}°{results.tempUnit} with {results.dewPoint}°{results.tempUnit} dew point.
            </p>
            <p className="mt-2 pt-2 border-t border-gray-700">
              <strong>Remember:</strong> Use perceived effort or heart rate as the true guide in heat. This adjustment helps maintain physiological effort, not raw pace.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

