"use client";

import React, { useState } from 'react';

export default function WMACalculator() {
  const [age, setAge] = useState('');
  const [gender, setGender] = useState('M');
  const [distance, setDistance] = useState('5000');
  const [time, setTime] = useState('');
  const [results, setResults] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCalculate = async (e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    
    console.log('WMA Calculator: handleCalculate called', { age, gender, distance, time });
    
    if (!age || !time) {
      console.log('WMA Calculator: Missing input');
      setError('Please enter age and time');
      return;
    }
    
    setLoading(true);
    setError(null);
    setResults(null);
    
    try {
      console.log('WMA Calculator: Making API request...');
      // Parse time
      const timeParts = time.split(':').map(Number);
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

      const ageNum = parseInt(age);
      if (isNaN(ageNum) || ageNum < 0 || ageNum > 120) {
        setError('Age must be between 0 and 120');
        setLoading(false);
        return;
      }

      const response = await fetch(`http://localhost:8000/v1/public/age-grade/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          age: ageNum,
          sex: gender,
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
      console.log('WMA Calculator: Response received', data);
      setResults(data);
    } catch (error: any) {
      console.error('Error calculating age-grade:', error);
      setError(error.message || 'Failed to connect to server. Please check your connection.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Age-Grading Explanation */}
      <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-3 text-xs text-gray-300">
        <div className="flex items-start gap-2">
          <svg className="w-4 h-4 text-orange-500 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
          <div>
            <span className="font-semibold text-orange-400">Age-Grading:</span> Compares your performance to world-record standards for your age and gender. A score of 100% equals a world record. This lets you compare performances across ages and distances—your 60% at age 50 might be equivalent to a 75% performance at age 30.
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-2">Age</label>
          <input
            type="number"
            value={age}
            onChange={(e) => setAge(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-2">Gender</label>
          <select
            value={gender}
            onChange={(e) => setGender(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white"
          >
            <option value="M">Male</option>
            <option value="F">Female</option>
          </select>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">Distance</label>
        <select
          value={distance}
          onChange={(e) => setDistance(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white"
        >
          <option value="5000">5K</option>
          <option value="10000">10K</option>
          <option value="21097.5">Half Marathon</option>
          <option value="42195">Marathon</option>
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">Time (MM:SS or HH:MM:SS)</label>
        <input
          type="text"
          value={time}
          onChange={(e) => setTime(e.target.value)}
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
        {loading ? 'Calculating...' : 'Calculate Age-Grade'}
      </button>

      {error && (
        <div className="mt-4 p-3 bg-red-900/50 border border-red-700 rounded text-red-200 text-sm">
          {error}
        </div>
      )}

      {results && (
        <div className="mt-6 pt-6 border-t border-gray-700">
          <div className="mb-4">
            <div className="text-3xl font-bold text-orange-500">
              {results.performance_percentage?.toFixed(1)}%
            </div>
            <div className="text-sm text-gray-400">Age-Graded Performance</div>
          </div>
          
          {results.equivalent_time && (
            <div className="text-sm text-gray-300">
              Equivalent open performance: <span className="font-mono">{results.equivalent_time}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

