'use client';

/**
 * Athlete Insights Page
 * 
 * Guided query interface for athletes to explore their own data.
 * Pre-built templates for common questions about performance,
 * training patterns, and trends.
 */

import React, { useState } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useInsightTemplates, useExecuteInsight } from '@/lib/hooks/queries/insights';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';

// Category colors
const CATEGORY_COLORS: Record<string, string> = {
  performance: '#f97316',
  training: '#3b82f6',
  conditions: '#22c55e',
  physiology: '#a855f7',
};

// Chart colors
const CHART_COLORS = ['#f97316', '#3b82f6', '#22c55e', '#a855f7', '#ec4899', '#eab308'];

// Category icons
const CATEGORY_ICONS: Record<string, string> = {
  performance: '🏃',
  training: '📊',
  conditions: '🌡️',
  physiology: '❤️',
};

function InsightCard({ 
  template, 
  onClick, 
  isSelected 
}: { 
  template: any; 
  onClick: () => void;
  isSelected: boolean;
}) {
  const color = CATEGORY_COLORS[template.category] || '#6b7280';
  
  return (
    <button
      onClick={onClick}
      disabled={!template.available}
      className={`p-4 rounded-lg border text-left transition-all w-full ${
        isSelected
          ? 'bg-orange-900/30 border-orange-600'
          : template.available
            ? 'bg-gray-800 border-gray-700 hover:border-gray-500'
            : 'bg-gray-800/50 border-gray-700/50 opacity-60 cursor-not-allowed'
      }`}
    >
      <div className="flex items-center gap-2 mb-2">
        <span>{CATEGORY_ICONS[template.category] || '📈'}</span>
        <span className="font-medium">{template.name}</span>
        {template.requires_premium && !template.available && (
          <span className="ml-auto px-2 py-0.5 bg-yellow-900/50 text-yellow-400 text-xs rounded">
            Premium
          </span>
        )}
      </div>
      <p className="text-sm text-gray-400">{template.description}</p>
    </button>
  );
}

function ResultsDisplay({ result }: { result: any }) {
  const data = result.data;
  
  if (!data) {
    return (
      <div className="text-center text-gray-400 py-8">
        No data available
      </div>
    );
  }

  // Render based on template type
  const templateId = result.template_id;

  // Efficiency Trend
  if (templateId === 'efficiency_trend') {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-gray-700/50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold">{data.count}</div>
            <div className="text-sm text-gray-400">Activities</div>
          </div>
          <div className="bg-gray-700/50 rounded-lg p-4 text-center">
            <div className={`text-2xl font-bold ${
              data.trend === 'improving' ? 'text-green-400' :
              data.trend === 'declining' ? 'text-red-400' : 'text-gray-400'
            }`}>
              {data.trend === 'improving' ? '↑' : data.trend === 'declining' ? '↓' : '→'}
              {data.change_pct}%
            </div>
            <div className="text-sm text-gray-400">Change</div>
          </div>
          <div className="bg-gray-700/50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold capitalize">{data.trend}</div>
            <div className="text-sm text-gray-400">Trend</div>
          </div>
        </div>
        
        {data.activities && data.activities.length > 0 && (
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={data.activities}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis 
                dataKey="start_time" 
                stroke="#9CA3AF"
                tickFormatter={(v) => new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              />
              <YAxis stroke="#9CA3AF" />
              <Tooltip
                contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                labelFormatter={(v) => new Date(v).toLocaleDateString()}
              />
              <Line 
                type="monotone" 
                dataKey="efficiency" 
                stroke="#f97316" 
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    );
  }

  // Workout Distribution
  if (templateId === 'workout_distribution') {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-gray-700/50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold">{data.total_distance_km} km</div>
            <div className="text-sm text-gray-400">Total Distance</div>
          </div>
          <div className="bg-gray-700/50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold">{data.total_time_hours} hrs</div>
            <div className="text-sm text-gray-400">Total Time</div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={data.distribution}
                dataKey="distance_km"
                nameKey="workout_type"
                cx="50%"
                cy="50%"
                outerRadius={80}
                label={({ name, value }) => `${String(name || '').replace(/_/g, ' ')}: ${value}km`}
              >
                {data.distribution?.map((entry: any, idx: number) => (
                  <Cell key={idx} fill={CHART_COLORS[idx % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>

          <div className="space-y-2">
            {data.distribution?.map((item: any, idx: number) => (
              <div key={idx} className="flex items-center justify-between p-2 bg-gray-700/30 rounded">
                <div className="flex items-center gap-2">
                  <div 
                    className="w-3 h-3 rounded-full" 
                    style={{ backgroundColor: CHART_COLORS[idx % CHART_COLORS.length] }}
                  />
                  <span className="capitalize">{item.workout_type?.replace(/_/g, ' ')}</span>
                </div>
                <div className="text-sm text-gray-400">
                  {item.count} runs • {item.distance_km} km
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Best Performances
  if (templateId === 'best_performances') {
    return (
      <div className="space-y-4">
        {data.performances?.map((perf: any, idx: number) => (
          <div 
            key={perf.id || idx} 
            className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg"
          >
            <div className="flex items-center gap-4">
              <div className={`text-2xl font-bold ${idx === 0 ? 'text-yellow-400' : 'text-gray-400'}`}>
                #{idx + 1}
              </div>
              <div>
                <div className="font-medium">{perf.name}</div>
                <div className="text-sm text-gray-400">
                  {new Date(perf.start_time).toLocaleDateString()} • {(perf.distance_m / 1000).toFixed(1)} km
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-lg font-semibold text-orange-400">
                {perf.efficiency?.toFixed(4)}
              </div>
              <div className="text-sm text-gray-400">efficiency</div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Weather Impact
  if (templateId === 'weather_impact') {
    return (
      <div className="space-y-6">
        {data.best_conditions && (
          <div className="bg-green-900/30 border border-green-700/50 rounded-lg p-4 text-center">
            <div className="text-lg font-semibold text-green-400">
              Best Performance Conditions: {data.best_conditions}
            </div>
          </div>
        )}
        
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={data.by_temperature}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="range" stroke="#9CA3AF" />
            <YAxis stroke="#9CA3AF" />
            <Tooltip contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }} />
            <Bar dataKey="avg_efficiency" fill="#f97316" name="Avg Efficiency" />
          </BarChart>
        </ResponsiveContainer>
        
        <div className="text-sm text-gray-400 text-center">
          Based on {data.total_activities} activities
        </div>
      </div>
    );
  }

  // Weekly Volume
  if (templateId === 'weekly_volume') {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-gray-700/50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold">{data.avg_weekly_distance_km} km</div>
            <div className="text-sm text-gray-400">Avg Weekly Distance</div>
          </div>
          <div className="bg-gray-700/50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold">{data.avg_weekly_time_hours} hrs</div>
            <div className="text-sm text-gray-400">Avg Weekly Time</div>
          </div>
        </div>

        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={data.weeks}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis 
              dataKey="week" 
              stroke="#9CA3AF" 
              tickFormatter={(v) => new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            />
            <YAxis stroke="#9CA3AF" />
            <Tooltip contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }} />
            <Bar dataKey="distance_km" fill="#3b82f6" name="Distance (km)" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // Heart Rate Analysis
  if (templateId === 'heart_rate_zones') {
    return (
      <div className="space-y-6">
        <div className="text-center text-sm text-gray-400">
          Estimated Max HR: {data.estimated_max_hr} bpm
        </div>
        
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={data.distribution} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis type="number" stroke="#9CA3AF" />
            <YAxis type="category" dataKey="zone" stroke="#9CA3AF" width={120} />
            <Tooltip contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }} />
            <Bar dataKey="time_hours" fill="#a855f7" name="Time (hours)" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // Personal Records
  if (templateId === 'personal_records') {
    return (
      <div className="space-y-4">
        {data.records?.length === 0 ? (
          <div className="text-center text-gray-400 py-8">
            No personal records found yet. Keep running!
          </div>
        ) : (
          data.records?.map((record: any, idx: number) => (
            <div 
              key={idx} 
              className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg"
            >
              <div className="flex items-center gap-4">
                <span className="text-2xl">🏆</span>
                <div>
                  <div className="font-medium">{record.distance}</div>
                  <div className="text-sm text-gray-400">
                    {record.date ? new Date(record.date).toLocaleDateString() : 'Unknown date'}
                  </div>
                </div>
              </div>
              <div className="text-xl font-bold text-orange-400">
                {record.time_formatted}
              </div>
            </div>
          ))
        )}
      </div>
    );
  }

  // Consistency Score
  if (templateId === 'consistency_score') {
    const scoreColor = 
      data.score >= 80 ? 'text-green-400' :
      data.score >= 60 ? 'text-blue-400' :
      data.score >= 40 ? 'text-yellow-400' : 'text-red-400';

    return (
      <div className="space-y-6">
        <div className="text-center">
          <div className={`text-6xl font-bold ${scoreColor}`}>{data.score}</div>
          <div className="text-xl font-semibold mt-2">{data.rating}</div>
          <div className="text-gray-400 mt-1">{data.message}</div>
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-gray-700/50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold">{data.avg_runs_per_week}</div>
            <div className="text-sm text-gray-400">Avg Runs/Week</div>
          </div>
          <div className="bg-gray-700/50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold">{data.avg_km_per_week} km</div>
            <div className="text-sm text-gray-400">Avg km/Week</div>
          </div>
        </div>
      </div>
    );
  }

  // Default: Show raw data
  return (
    <div className="bg-gray-700/30 rounded p-4">
      <pre className="text-xs overflow-x-auto max-h-96">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}

export default function InsightsPage() {
  const { data: templatesData, isLoading: templatesLoading } = useInsightTemplates();
  const executeInsight = useExecuteInsight();
  
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [days, setDays] = useState(90);
  const [weeks, setWeeks] = useState(12);
  const [limit, setLimit] = useState(10);
  const [result, setResult] = useState<any>(null);

  const handleExecute = async () => {
    if (!selectedTemplate) return;
    
    const template = templatesData?.templates.find(t => t.id === selectedTemplate);
    if (!template) return;

    const params: any = { templateId: selectedTemplate };
    if (template.params.includes('days')) params.days = days;
    if (template.params.includes('weeks')) params.weeks = weeks;
    if (template.params.includes('limit')) params.limit = limit;

    const res = await executeInsight.mutateAsync(params);
    setResult(res);
  };

  // Group templates by category
  const groupedTemplates = templatesData?.templates.reduce((acc, t) => {
    if (!acc[t.category]) acc[t.category] = [];
    acc[t.category].push(t);
    return acc;
  }, {} as Record<string, typeof templatesData.templates>);

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-900 text-gray-100 py-8">
        <div className="max-w-6xl mx-auto px-4">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold mb-2">📊 Insights</h1>
            <p className="text-gray-400">
              Explore your training data with guided queries
            </p>
            {templatesData && !templatesData.is_premium && (
              <div className="mt-2 inline-block px-3 py-1 bg-yellow-900/30 border border-yellow-700/50 rounded text-sm text-yellow-400">
                Upgrade to Premium for all insights
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Templates Sidebar */}
            <div className="lg:col-span-1 space-y-6">
              {templatesLoading ? (
                <div className="flex justify-center py-8">
                  <LoadingSpinner />
                </div>
              ) : groupedTemplates && Object.entries(groupedTemplates).map(([category, templates]) => (
                <div key={category} className="space-y-2">
                  <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide flex items-center gap-2">
                    {CATEGORY_ICONS[category]} {category}
                  </h3>
                  <div className="space-y-2">
                    {templates.map((t) => (
                      <InsightCard
                        key={t.id}
                        template={t}
                        isSelected={selectedTemplate === t.id}
                        onClick={() => setSelectedTemplate(t.id)}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Results Panel */}
            <div className="lg:col-span-2">
              {selectedTemplate ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                  {/* Parameters */}
                  <div className="flex flex-wrap gap-4 mb-6 pb-6 border-b border-gray-700">
                    {templatesData?.templates.find(t => t.id === selectedTemplate)?.params.includes('days') && (
                      <div>
                        <label className="block text-sm font-medium mb-1">Days</label>
                        <select
                          value={days}
                          onChange={(e) => setDays(parseInt(e.target.value))}
                          className="px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                        >
                          <option value={30}>30 days</option>
                          <option value={60}>60 days</option>
                          <option value={90}>90 days</option>
                          <option value={180}>180 days</option>
                          <option value={365}>1 year</option>
                        </select>
                      </div>
                    )}
                    {templatesData?.templates.find(t => t.id === selectedTemplate)?.params.includes('weeks') && (
                      <div>
                        <label className="block text-sm font-medium mb-1">Weeks</label>
                        <select
                          value={weeks}
                          onChange={(e) => setWeeks(parseInt(e.target.value))}
                          className="px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                        >
                          <option value={4}>4 weeks</option>
                          <option value={8}>8 weeks</option>
                          <option value={12}>12 weeks</option>
                          <option value={26}>26 weeks</option>
                          <option value={52}>52 weeks</option>
                        </select>
                      </div>
                    )}
                    {templatesData?.templates.find(t => t.id === selectedTemplate)?.params.includes('limit') && (
                      <div>
                        <label className="block text-sm font-medium mb-1">Show Top</label>
                        <select
                          value={limit}
                          onChange={(e) => setLimit(parseInt(e.target.value))}
                          className="px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                        >
                          <option value={5}>5</option>
                          <option value={10}>10</option>
                          <option value={20}>20</option>
                        </select>
                      </div>
                    )}
                    <div className="flex items-end">
                      <button
                        onClick={handleExecute}
                        disabled={executeInsight.isPending}
                        className="px-6 py-2 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-700 rounded font-medium"
                      >
                        {executeInsight.isPending ? 'Loading...' : 'Run Insight'}
                      </button>
                    </div>
                  </div>

                  {/* Results */}
                  {executeInsight.isPending && (
                    <div className="flex justify-center py-12">
                      <LoadingSpinner size="lg" />
                    </div>
                  )}

                  {executeInsight.isError && (
                    <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-red-400">
                      {executeInsight.error.message}
                    </div>
                  )}

                  {result && !executeInsight.isPending && (
                    <div>
                      <div className="flex justify-between items-center mb-4">
                        <h3 className="text-lg font-semibold">{result.template_name}</h3>
                        <span className="text-sm text-gray-400">
                          {result.execution_time_ms}ms
                        </span>
                      </div>
                      <ResultsDisplay result={result} />
                    </div>
                  )}

                  {!result && !executeInsight.isPending && (
                    <div className="text-center py-12 text-gray-400">
                      <p>Click &ldquo;Run Insight&rdquo; to see your data</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-12 text-center">
                  <div className="text-5xl mb-4">📊</div>
                  <h2 className="text-xl font-semibold mb-2">Select an Insight</h2>
                  <p className="text-gray-400">
                    Choose a query from the left to explore your training data
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
