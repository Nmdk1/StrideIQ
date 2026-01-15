"use client";

/**
 * WMA Age-Grading Calculator
 * 
 * Enhanced version with comprehensive results display:
 * - Summary table with all calculation components
 * - Equivalent performances at other distances
 * - Close performances (nearby percentage levels)
 * - Classification interpretation
 * 
 * Feature flagged: AGE_GRADE_V2
 */

import React, { useState } from 'react';
import { API_CONFIG } from '@/lib/api/config';
import TimeInput from '@/components/ui/TimeInput';
import { isFeatureEnabled, FEATURE_FLAGS } from '@/lib/featureFlags';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Info, Trophy, Target, Clock, TrendingUp, Award, ExternalLink } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface AgeGradeResults {
  performance_percentage: number;
  equivalent_time: string;
  equivalent_time_seconds: number;
  age: number;
  sex: string;
  distance_meters: number;
  actual_time_seconds: number;
  // Enhanced fields
  athlete_time_formatted?: string;
  open_class_standard_seconds?: number;
  open_class_standard_formatted?: string;
  age_standard_seconds?: number;
  age_standard_formatted?: string;
  age_factor?: number;
  age_graded_time_seconds?: number;
  age_graded_time_formatted?: string;
  classification?: {
    level: string;
    label: string;
    color: string;
  };
  equivalent_performances?: Array<{
    distance: string;
    distance_meters: number;
    time_seconds: number;
    time_formatted: string;
  }>;
  close_performances?: Array<{
    percentage: number;
    time_seconds: number;
    time_formatted: string;
    is_current: boolean;
  }>;
}

// Classification standards table
const CLASSIFICATION_STANDARDS = [
  { percentage: "100%", standard: "World Record" },
  { percentage: "90%+", standard: "World Class" },
  { percentage: "80%+", standard: "National Class" },
  { percentage: "70%+", standard: "Regional Class" },
  { percentage: "60%+", standard: "Local Class" },
];

// Distance name mapping
const DISTANCE_NAMES: Record<string, string> = {
  "5000": "5K",
  "10000": "10K",
  "21097.5": "Half Marathon",
  "42195": "Marathon",
};

function getClassificationColor(level: string): string {
  switch (level) {
    case "world_record": return "bg-yellow-500 text-black";
    case "world_class": return "bg-purple-500 text-white";
    case "national_class": return "bg-blue-500 text-white";
    case "regional_class": return "bg-green-500 text-white";
    case "local_class": return "bg-teal-500 text-white";
    default: return "bg-slate-500 text-white";
  }
}

export default function WMACalculator() {
  const [age, setAge] = useState('');
  const [gender, setGender] = useState('M');
  const [distance, setDistance] = useState('5000');
  const [time, setTime] = useState('');
  const [results, setResults] = useState<AgeGradeResults | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCalculate = async (e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    
    if (!age || !time) {
      setError('Please enter age and time');
      return;
    }
    
    setLoading(true);
    setError(null);
    setResults(null);
    
    try {
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

      const response = await fetch(`${API_CONFIG.baseURL}/v1/public/age-grade`, {
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
      setResults(data);
    } catch (error: any) {
      console.error('Error calculating age-grade:', error);
      setError(error.message || 'Failed to connect to server. Please check your connection.');
    } finally {
      setLoading(false);
    }
  };

  const showEnhancedResults = isFeatureEnabled(FEATURE_FLAGS.AGE_GRADE_V2);
  const distanceLabel = DISTANCE_NAMES[distance] || `${parseFloat(distance) / 1000}km`;

  return (
    <div className="space-y-4">
      {/* Age-Grading Explanation */}
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3 text-xs text-slate-300">
        <div className="flex items-start gap-2">
          <Info className="w-4 h-4 text-orange-500 mt-0.5 flex-shrink-0" />
          <div>
            <span className="font-semibold text-orange-400">Age-Grading:</span> Calculates your performance as a percentage of the World Record standard for your specific age and gender. This creates a unified &apos;Level Playing Field&apos; across all demographics. An 80% score at age 60 represents the exact same relative competitiveness as an 80% score at age 25, even though the absolute race times differ.
          </div>
        </div>
      </div>

      {/* Input Form */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-2">Age</label>
          <input
            type="number"
            value={age}
            onChange={(e) => setAge(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700/50 rounded px-3 py-2 text-white focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500/50"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-2">Gender</label>
          <select
            value={gender}
            onChange={(e) => setGender(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700/50 rounded px-3 py-2 text-white focus:border-orange-500 focus:outline-none"
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
          className="w-full bg-slate-800 border border-slate-700/50 rounded px-3 py-2 text-white focus:border-orange-500 focus:outline-none"
        >
          <option value="5000">5K</option>
          <option value="10000">10K</option>
          <option value="21097.5">Half Marathon</option>
          <option value="42195">Marathon</option>
        </select>
      </div>

      {/* Time Input */}
      {isFeatureEnabled(FEATURE_FLAGS.TIME_INPUT_V2) ? (
        <TimeInput
          value={time}
          onChange={(formatted) => setTime(formatted)}
          placeholder=""
          label="Time"
          className="w-full"
          maxLength="hhmmss"
        />
      ) : (
        <div>
          <label className="block text-sm font-medium mb-2">Time (MM:SS or HH:MM:SS)</label>
          <input
            type="text"
            value={time}
            onChange={(e) => setTime(e.target.value)}
            placeholder="00:00:00"
            className="w-full bg-slate-800 border border-slate-700/50 rounded px-3 py-2 text-white focus:border-orange-500 focus:outline-none"
          />
        </div>
      )}

      <button
        type="button"
        onClick={handleCalculate}
        disabled={loading}
        className="w-full bg-orange-600 hover:bg-orange-500 text-white py-2.5 rounded-lg font-medium transition-colors disabled:opacity-50 shadow-lg shadow-orange-500/20"
      >
        {loading ? 'Calculating...' : 'Calculate Age-Grade'}
      </button>

      {error && (
        <div className="p-3 bg-red-900/50 border border-red-700 rounded-lg text-red-200 text-sm">
          {error}
        </div>
      )}

      {/* Results Section */}
      {results && (
        <div className="space-y-6 pt-4">
          {/* Hero Result */}
          <div className="text-center py-4">
            <div className="text-5xl font-bold text-orange-500 mb-2">
              {results.performance_percentage?.toFixed(2)}%
            </div>
            <div className="text-slate-400 text-sm mb-3">Age-Graded Performance</div>
            {results.classification && (
              <Badge className={`${getClassificationColor(results.classification.level)} text-sm px-3 py-1`}>
                <Award className="w-3.5 h-3.5 mr-1.5" />
                {results.classification.label}
              </Badge>
            )}
          </div>

          {/* Summary Sentence */}
          <div className="text-center text-slate-300 text-sm px-4">
            Your time of <span className="font-semibold text-white">{results.athlete_time_formatted || results.equivalent_time}</span> for {distanceLabel} as a <span className="font-semibold text-white">{results.age} year old {results.sex === 'M' ? 'male' : 'female'}</span> yields an age-grading percentage of <span className="font-semibold text-orange-400">{results.performance_percentage?.toFixed(2)}%</span>
          </div>

          {showEnhancedResults && results.open_class_standard_formatted && (
            <>
              {/* Summary Table */}
              <Card className="bg-slate-800 border-slate-700">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base font-semibold flex items-center gap-2">
                    <Target className="w-4 h-4 text-orange-400" />
                    Summary
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <table className="w-full text-sm">
                    <tbody>
                      <tr className="border-b border-slate-700/50">
                        <td className="px-4 py-2.5 text-slate-400">Age-grading percentage</td>
                        <td className="px-4 py-2.5 text-right font-semibold text-orange-400">{results.performance_percentage?.toFixed(2)}%</td>
                      </tr>
                      <tr className="border-b border-slate-700/50 bg-slate-700/20">
                        <td className="px-4 py-2.5 text-slate-400">Open-class standard</td>
                        <td className="px-4 py-2.5 text-right font-mono text-white">{results.open_class_standard_formatted}</td>
                      </tr>
                      <tr className="border-b border-slate-700/50">
                        <td className="px-4 py-2.5 text-slate-400">Age-standard</td>
                        <td className="px-4 py-2.5 text-right font-mono text-white">{results.age_standard_formatted}</td>
                      </tr>
                      <tr className="border-b border-slate-700/50 bg-slate-700/20">
                        <td className="px-4 py-2.5 text-slate-400">Age-factor</td>
                        <td className="px-4 py-2.5 text-right font-mono text-white">{results.age_factor?.toFixed(4)}</td>
                      </tr>
                      <tr className="border-b border-slate-700/50">
                        <td className="px-4 py-2.5 text-slate-400">Athlete time</td>
                        <td className="px-4 py-2.5 text-right font-mono text-white">{results.athlete_time_formatted}</td>
                      </tr>
                      <tr className="bg-orange-500/10">
                        <td className="px-4 py-2.5 text-slate-300 font-medium">Age-graded time</td>
                        <td className="px-4 py-2.5 text-right font-mono font-semibold text-orange-400">{results.age_graded_time_formatted}</td>
                      </tr>
                    </tbody>
                  </table>
                </CardContent>
              </Card>

              {/* Equivalent Performances */}
              {results.equivalent_performances && results.equivalent_performances.length > 0 && (
                <Card className="bg-slate-800 border-slate-700">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base font-semibold flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-blue-400" />
                      Equivalent Performances
                    </CardTitle>
                    <p className="text-xs text-slate-500 mt-1">
                      Times to achieve {results.performance_percentage?.toFixed(2)}% at other distances
                    </p>
                  </CardHeader>
                  <CardContent className="p-0">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-700/50 bg-slate-700/30">
                          <th className="px-4 py-2 text-left text-slate-400 font-medium">Distance</th>
                          <th className="px-4 py-2 text-right text-slate-400 font-medium">Time</th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.equivalent_performances.map((perf, idx) => (
                          <tr key={perf.distance} className={idx % 2 === 0 ? '' : 'bg-slate-700/20'}>
                            <td className="px-4 py-2 text-white">{perf.distance}</td>
                            <td className="px-4 py-2 text-right font-mono text-white">{perf.time_formatted}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </CardContent>
                </Card>
              )}

              {/* Close Performances */}
              {results.close_performances && results.close_performances.length > 0 && (
                <Card className="bg-slate-800 border-slate-700">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base font-semibold flex items-center gap-2">
                      <Clock className="w-4 h-4 text-green-400" />
                      Close Performances
                    </CardTitle>
                    <p className="text-xs text-slate-500 mt-1">
                      Times for different percentages at {distanceLabel}
                    </p>
                  </CardHeader>
                  <CardContent className="p-0">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-700/50 bg-slate-700/30">
                          <th className="px-4 py-2 text-left text-slate-400 font-medium">Time</th>
                          <th className="px-4 py-2 text-right text-slate-400 font-medium">Age-Grade %</th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.close_performances.map((perf, idx) => (
                          <tr 
                            key={perf.percentage} 
                            className={`${perf.is_current ? 'bg-orange-500/20 border-l-2 border-orange-500' : idx % 2 === 0 ? '' : 'bg-slate-700/20'}`}
                          >
                            <td className={`px-4 py-2 font-mono ${perf.is_current ? 'text-orange-400 font-semibold' : 'text-white'}`}>
                              {perf.time_formatted}
                            </td>
                            <td className={`px-4 py-2 text-right ${perf.is_current ? 'text-orange-400 font-semibold' : 'text-white'}`}>
                              {perf.percentage}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </CardContent>
                </Card>
              )}

              {/* Classification Guide */}
              <Card className="bg-slate-800 border-slate-700">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base font-semibold flex items-center gap-2">
                    <Trophy className="w-4 h-4 text-yellow-400" />
                    Interpreting Results
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-700/50 bg-slate-700/30">
                        <th className="px-4 py-2 text-left text-slate-400 font-medium">Percentage</th>
                        <th className="px-4 py-2 text-right text-slate-400 font-medium">Standard</th>
                      </tr>
                    </thead>
                    <tbody>
                      {CLASSIFICATION_STANDARDS.map((std, idx) => {
                        const isCurrentLevel = 
                          (std.percentage === "100%" && results.performance_percentage >= 100) ||
                          (std.percentage === "90%+" && results.performance_percentage >= 90 && results.performance_percentage < 100) ||
                          (std.percentage === "80%+" && results.performance_percentage >= 80 && results.performance_percentage < 90) ||
                          (std.percentage === "70%+" && results.performance_percentage >= 70 && results.performance_percentage < 80) ||
                          (std.percentage === "60%+" && results.performance_percentage >= 60 && results.performance_percentage < 70);
                        
                        return (
                          <tr 
                            key={std.percentage} 
                            className={`${isCurrentLevel ? 'bg-orange-500/20 border-l-2 border-orange-500' : idx % 2 === 0 ? '' : 'bg-slate-700/20'}`}
                          >
                            <td className={`px-4 py-2 ${isCurrentLevel ? 'text-orange-400 font-semibold' : 'text-white'}`}>
                              {std.percentage}
                            </td>
                            <td className={`px-4 py-2 text-right ${isCurrentLevel ? 'text-orange-400 font-semibold' : 'text-white'}`}>
                              {std.standard}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  {results.classification && (
                    <div className="px-4 py-3 border-t border-slate-700/50 text-sm text-slate-300">
                      Your age-grading percentage of <span className="text-orange-400 font-semibold">{results.performance_percentage?.toFixed(2)}%</span> places you in the <span className="text-orange-400 font-semibold">{results.classification.label}</span> category.
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}

          {/* Fallback for non-enhanced display */}
          {!showEnhancedResults && (
            <div className="text-sm text-slate-300">
              Equivalent open performance: <span className="font-mono text-white">{results.equivalent_time}</span>
            </div>
          )}
        </div>
      )}

      {/* Data Source Attribution */}
      <div className="pt-4 border-t border-slate-700/30 mt-4">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <button className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-400 transition-colors">
                <Info className="w-3.5 h-3.5" />
                <span>Data source</span>
              </button>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-xs bg-slate-800 border-slate-700 text-slate-200">
              <p className="text-xs leading-relaxed">
                Age-grading factors from the{' '}
                <a 
                  href="https://github.com/AlanLyttonJones/Age-Grade-Tables" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-orange-400 hover:text-orange-300 underline inline-flex items-center gap-0.5"
                >
                  Alan Jones 2025 Road Age-Grading Tables
                  <ExternalLink className="w-2.5 h-2.5" />
                </a>
                , approved by USATF Masters Long Distance Running Council (Jan 2025).
              </p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>
  );
}
