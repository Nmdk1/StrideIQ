"use client";

import React, { useState } from 'react';

type TabType = 'race_paces' | 'training' | 'equivalent';

export default function VDOTCalculator() {
  const [raceTime, setRaceTime] = useState('');
  const [distance, setDistance] = useState('5000');
  const [distanceUnit, setDistanceUnit] = useState<'km' | 'mile'>('km');
  const [results, setResults] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('race_paces');
  
  // Distance options in meters
  const distanceOptions = distanceUnit === 'km' 
    ? [
        { value: '5000', label: '5K' },
        { value: '10000', label: '10K' },
        { value: '21097.5', label: 'Half Marathon' },
        { value: '42195', label: 'Marathon' }
      ]
    : [
        { value: '1609.34', label: 'One Mile' },
        { value: '5000', label: '5K' },
        { value: '10000', label: '10K' },
        { value: '21097.5', label: 'Half Marathon' },
        { value: '42195', label: 'Marathon' }
      ];

  const handleCalculate = async (e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    
    console.log('VDOT Calculator: handleCalculate called', { raceTime, distance });
    
    if (!raceTime || !distance) {
      console.log('VDOT Calculator: Missing input');
      setError('Please enter a race time');
      return;
    }
    
    setLoading(true);
    setError(null);
    setResults(null);
    
    try {
      console.log('VDOT Calculator: Making API request...');
      // Parse time (MM:SS or HH:MM:SS)
      const timeParts = raceTime.split(':').map(Number);
      let totalSeconds = 0;
      if (timeParts.length === 2) {
        totalSeconds = timeParts[0] * 60 + timeParts[1];
      } else if (timeParts.length === 3) {
        totalSeconds = timeParts[0] * 3600 + timeParts[1] * 60 + timeParts[2];
      } else {
        setError('Invalid time format. Use MM:SS or HH:MM:SS');
        setLoading(false);
        return;
      }

      if (totalSeconds <= 0) {
        setError('Time must be greater than 0');
        setLoading(false);
        return;
      }

      const response = await fetch(`http://localhost:8000/v1/public/vdot/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          distance_meters: parseFloat(distance),
          time_seconds: totalSeconds
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        setError(errorData.detail || `Error: ${response.status} ${response.statusText}`);
        setLoading(false);
        return;
      }

      const data = await response.json();
      console.log('VDOT Calculator: Response received', data);
      setResults(data);
      setActiveTab('race_paces'); // Reset to first tab
    } catch (error: any) {
      console.error('Error calculating VDOT:', error);
      setError(error.message || 'Failed to connect to server. Please check your connection.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Explanation & Disclaimer */}
      <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-3 text-xs text-gray-300">
        <div className="flex items-start gap-2">
          <svg className="w-4 h-4 text-orange-500 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
          <div>
            <span className="font-semibold text-orange-400">Fitness Score:</span> A measure of your current running fitness based on proven training principles. Enter a recent race time to get your fitness score and personalized training paces (Easy, Marathon, Threshold, Interval, Repetition) for optimal improvement.
            <div className="mt-2 pt-2 border-t border-gray-700 text-gray-500 text-xs">
              <div className="font-semibold mb-1">Disclaimer:</div>
              <div>Based on publicly available formulas from Dr. Jack Daniels&rsquo; research. Not affiliated with VDOT O2 or The Run SMART Project.</div>
            </div>
          </div>
        </div>
      </div>

      {/* Input Section */}
      <div>
        <label className="block text-sm font-medium mb-2">Race Distance</label>
        <select
          value={distance}
          onChange={(e) => setDistance(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white"
        >
          <option value="1609.34">One Mile</option>
          <option value="5000">5K</option>
          <option value="10000">10K</option>
          <option value="21097.5">Half Marathon</option>
          <option value="42195">Marathon</option>
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">Race Time (MM:SS or HH:MM:SS)</label>
        <input
          type="text"
          value={raceTime}
          onChange={(e) => setRaceTime(e.target.value)}
          placeholder="00:00:00"
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white"
        />
      </div>

      <button
        type="button"
        onClick={handleCalculate}
        disabled={loading}
        className="w-full bg-orange-600 hover:bg-orange-700 text-white py-2 rounded transition-colors disabled:opacity-50"
      >
        {loading ? 'Calculating...' : 'Calculate VDOT'}
      </button>

      {error && (
        <div className="mt-4 p-3 bg-red-900/50 border border-red-700 rounded text-red-200 text-sm">
          {error}
        </div>
      )}

      {/* Results Section */}
      {results && (
        <div className="mt-6 pt-6 border-t border-gray-700">
          {/* Fitness Score Display */}
          <div className="mb-6 text-center">
            <div className="text-4xl font-bold text-orange-500 mb-1">
              {results.vdot?.toFixed(1)}
            </div>
            <div className="text-sm text-gray-400">Fitness Score</div>
            {results.input && (
              <div className="text-xs text-gray-500 mt-2">
                {results.input.distance_name} {results.input.time_formatted} ({results.input.pace_mi} /mi)
              </div>
            )}
          </div>

          {/* Tabs */}
          <div className="flex border-b border-gray-700 mb-4">
            <button
              onClick={() => setActiveTab('race_paces')}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === 'race_paces'
                  ? 'border-b-2 border-orange-500 text-orange-500'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              Race Paces
            </button>
            <button
              onClick={() => setActiveTab('training')}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === 'training'
                  ? 'border-b-2 border-orange-500 text-orange-500'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              Training
            </button>
            <button
              onClick={() => setActiveTab('equivalent')}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === 'equivalent'
                  ? 'border-b-2 border-orange-500 text-orange-500'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              Equivalent
            </button>
          </div>

          {/* Race Paces Tab */}
          {activeTab === 'race_paces' && results.race_paces && results.race_paces.length > 0 && (
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="font-semibold text-gray-400">Distance</div>
                <div className="font-semibold text-gray-400">Pace</div>
                {results.race_paces.map((race: any) => (
                  <React.Fragment key={race.distance}>
                    <div className="text-gray-300">{race.distance}</div>
                    <div className="font-mono text-orange-400">{race.pace_mi} /mi</div>
                  </React.Fragment>
                ))}
              </div>
            </div>
          )}

          {/* Training Tab */}
          {activeTab === 'training' && results.training && (
            <div className="space-y-6">
              {/* Per Mile/Km Training Paces */}
              {results.training.per_mile_km && Object.keys(results.training.per_mile_km).length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-gray-400 mb-2">Type</div>
                  <div className="grid grid-cols-3 gap-3 text-xs">
                    <div className="text-gray-500"></div>
                    <div className="text-center text-gray-400 font-semibold">1 Mi</div>
                    <div className="text-center text-gray-400 font-semibold">1 Km</div>
                    
                    {results.training.per_mile_km.easy && (
                      <>
                        <div className="text-gray-300">Easy</div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.per_mile_km.easy.mi || '--'}
                        </div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.per_mile_km.easy.km || '--'}
                        </div>
                      </>
                    )}
                    
                    {results.training.per_mile_km.marathon && (
                      <>
                        <div className="text-gray-300">Marathon</div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.per_mile_km.marathon.mi || '--'}
                        </div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.per_mile_km.marathon.km || '--'}
                        </div>
                      </>
                    )}
                    
                    {results.training.per_mile_km.threshold && (
                      <>
                        <div className="text-gray-300">Threshold</div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.per_mile_km.threshold.mi || '--'}
                        </div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.per_mile_km.threshold.km || '--'}
                        </div>
                      </>
                    )}
                    
                    {results.training.per_mile_km.interval && (
                      <>
                        <div className="text-gray-300">Interval</div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.per_mile_km.interval.mi || '--'}
                        </div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.per_mile_km.interval.km || '--'}
                        </div>
                      </>
                    )}
                    
                    {results.training.per_mile_km.repetition && (
                      <>
                        <div className="text-gray-300">Repetition</div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.per_mile_km.repetition.mi || '--'}
                        </div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.per_mile_km.repetition.km || '--'}
                        </div>
                      </>
                    )}
                  </div>
                </div>
              )}

              {/* Interval Distances (1200m, 800m, 600m) */}
              {results.training.interval_distances && Object.keys(results.training.interval_distances).length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-gray-400 mb-2">Type</div>
                  <div className="grid grid-cols-4 gap-2 text-xs">
                    <div className="text-gray-500"></div>
                    <div className="text-center text-gray-400 font-semibold">1200m</div>
                    <div className="text-center text-gray-400 font-semibold">800m</div>
                    <div className="text-center text-gray-400 font-semibold">600m</div>
                    
                    {results.training.interval_distances.threshold && (
                      <>
                        <div className="text-gray-300">Threshold</div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.interval_distances.threshold['1200m'] || '--'}
                        </div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.interval_distances.threshold['800m'] || '--'}
                        </div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.interval_distances.threshold['600m'] || '--'}
                        </div>
                      </>
                    )}
                    
                    {results.training.interval_distances.interval && (
                      <>
                        <div className="text-gray-300">Interval</div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.interval_distances.interval['1200m'] || '--'}
                        </div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.interval_distances.interval['800m'] || '--'}
                        </div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.interval_distances.interval['600m'] || '--'}
                        </div>
                      </>
                    )}
                    
                    {results.training.interval_distances.repetition && (
                      <>
                        <div className="text-gray-300">Repetition</div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.interval_distances.repetition['1200m'] || '--'}
                        </div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.interval_distances.repetition['800m'] || '--'}
                        </div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.interval_distances.repetition['600m'] || '--'}
                        </div>
                      </>
                    )}
                  </div>
                </div>
              )}

              {/* Short Intervals (400m, 300m, 200m) */}
              {results.training.short_intervals && Object.keys(results.training.short_intervals).length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-gray-400 mb-2">Type</div>
                  <div className="grid grid-cols-4 gap-2 text-xs">
                    <div className="text-gray-500"></div>
                    <div className="text-center text-gray-400 font-semibold">400m</div>
                    <div className="text-center text-gray-400 font-semibold">300m</div>
                    <div className="text-center text-gray-400 font-semibold">200m</div>
                    
                    {results.training.short_intervals.interval && (
                      <>
                        <div className="text-gray-300">Interval</div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.short_intervals.interval['400m'] || '--'}
                        </div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.short_intervals.interval['300m'] || '--'}
                        </div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.short_intervals.interval['200m'] || '--'}
                        </div>
                      </>
                    )}
                    
                    {results.training.short_intervals.repetition && (
                      <>
                        <div className="text-gray-300">Repetition</div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.short_intervals.repetition['400m'] || '--'}
                        </div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.short_intervals.repetition['300m'] || '--'}
                        </div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.short_intervals.repetition['200m'] || '--'}
                        </div>
                      </>
                    )}
                    
                    {results.training.short_intervals.fast_reps && (
                      <>
                        <div className="text-gray-300">Fast Reps</div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.short_intervals.fast_reps['400m'] || '--'}
                        </div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.short_intervals.fast_reps['300m'] || '--'}
                        </div>
                        <div className="font-mono text-center text-orange-400">
                          {results.training.short_intervals.fast_reps['200m'] || '--'}
                        </div>
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Equivalent Tab */}
          {activeTab === 'equivalent' && results.equivalent && results.equivalent.length > 0 && (
            <div className="space-y-2">
              <div className="grid grid-cols-3 gap-3 text-xs">
                <div className="font-semibold text-gray-400">Race</div>
                <div className="font-semibold text-gray-400">Time</div>
                <div className="font-semibold text-gray-400">Pace/Mi</div>
                {results.equivalent.map((race: any) => (
                  <React.Fragment key={race.race}>
                    <div className="text-gray-300">{race.race}</div>
                    <div className="font-mono text-orange-400">{race.time_formatted}</div>
                    <div className="font-mono text-orange-400">{race.pace_mi}</div>
                  </React.Fragment>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
