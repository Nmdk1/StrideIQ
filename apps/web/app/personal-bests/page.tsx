"use client";

import React, { useState, useEffect } from 'react';

interface PersonalBest {
  id: string;
  distance_category: string;
  distance_meters: number;
  time_seconds: number;
  pace_per_mile: number | null;
  achieved_at: string;
  is_race: boolean;
  age_at_achievement: number | null;
}

export default function PersonalBestsPage() {
  const [pbs, setPbs] = useState<PersonalBest[]>([]);
  const [loading, setLoading] = useState(true);
  const [athleteId, setAthleteId] = useState<string | null>(null);

  useEffect(() => {
    // Get all athletes and try each one until we find PBs
    fetch('http://localhost:8000/v1/athletes')
      .then(res => res.json())
      .then(athletes => {
        if (!athletes || athletes.length === 0) {
          setLoading(false);
          return;
        }
        
        // Try each athlete until we find one with PBs
        const tryAthlete = async (index: number) => {
          if (index >= athletes.length) {
            // No athlete with PBs found, use first athlete for recalculate
            if (athletes.length > 0) {
              setAthleteId(athletes[0].id);
            }
            setLoading(false);
            return;
          }
          
          const athlete = athletes[index];
          const id = athlete.id;
          
          try {
            const pbRes = await fetch(`http://localhost:8000/v1/athletes/${id}/personal-bests`);
            const pbs = await pbRes.json();
            if (pbs && Array.isArray(pbs) && pbs.length > 0) {
              // Found athlete with PBs - use this one
              setAthleteId(id);
              setPbs(pbs);
              setLoading(false);
            } else {
              // Try next athlete
              tryAthlete(index + 1);
            }
          } catch (err) {
            console.error(`Error fetching PBs for athlete ${id}:`, err);
            // Try next athlete
            tryAthlete(index + 1);
          }
        };
        
        tryAthlete(0);
      })
      .catch(err => {
        console.error("Error fetching athletes:", err);
        setLoading(false);
      });
  }, []);

  const formatDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDistanceCategory = (category: string): string => {
    const categoryMap: Record<string, string> = {
      '400m': '400m',
      '800m': '800m',
      'mile': 'Mile',
      '2mile': '2 Mile',
      '5k': '5K',
      '10k': '10K',
      '15k': '15K',
      '25k': '25K',
      '30k': '30K',
      '50k': '50K',
      '100k': '100K',
      'half_marathon': 'Half Marathon',
      'marathon': 'Marathon',
    };
    return categoryMap[category] || category;
  };

  const handleRecalculate = async () => {
    // If no athleteId set, try to get first athlete
    let idToUse = athleteId;
    if (!idToUse) {
      try {
        const athletesRes = await fetch('http://localhost:8000/v1/athletes');
        const athletes = await athletesRes.json();
        if (athletes && athletes.length > 0) {
          idToUse = athletes[0].id;
          setAthleteId(idToUse);
        } else {
          alert("No athlete found");
          return;
        }
      } catch (err) {
        console.error("Error fetching athletes:", err);
        alert("Error fetching athletes");
        return;
      }
    }
    
    try {
      const res = await fetch(`http://localhost:8000/v1/athletes/${idToUse}/recalculate-pbs`, {
        method: 'POST',
      });
      
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }
      
      const result = await res.json();
      console.log("Recalculate result:", result);
      
      // Refresh PBs after a short delay to ensure DB is updated
      await new Promise(resolve => setTimeout(resolve, 500));
      
      const pbsRes = await fetch(`http://localhost:8000/v1/athletes/${idToUse}/personal-bests`);
      const pbsData = await pbsRes.json();
      setPbs(Array.isArray(pbsData) ? pbsData : []);
      
      // Use total_pbs from result, or count from pbsData array
      const totalCount = result.total_pbs || (Array.isArray(pbsData) ? pbsData.length : 0);
      alert(`Recalculated! Found ${totalCount} personal bests.`);
    } catch (err) {
      console.error("Error recalculating PBs:", err);
      alert(`Error recalculating personal bests: ${err}`);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '2rem' }}>
        <div style={{ maxWidth: '896px', margin: '0 auto' }}>
          <h1 style={{ fontSize: '1.875rem', fontWeight: 'bold', marginBottom: '1.5rem' }}>Personal Bests</h1>
          <p>Loading your personal bests...</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '2rem' }}>
      <div style={{ maxWidth: '896px', margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h1 style={{ fontSize: '1.875rem', fontWeight: 'bold' }}>Personal Bests</h1>
          <button
            onClick={handleRecalculate}
            style={{
              padding: '0.5rem 1rem',
              backgroundColor: '#2563eb',
              color: 'white',
              borderRadius: '0.375rem',
              border: 'none',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#1d4ed8'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#2563eb'; }}
          >
            Recalculate PBs
          </button>
        </div>

        {pbs.length === 0 ? (
          <div style={{ backgroundColor: 'white', borderRadius: '0.5rem', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', padding: '2rem', textAlign: 'center' }}>
            <p style={{ color: '#4b5563', marginBottom: '1rem' }}>No personal bests found.</p>
            <p style={{ fontSize: '0.875rem', color: '#6b7280' }}>
              Personal bests are automatically calculated from your activities.
              Click &quot;Recalculate PBs&quot; to process your activity history.
            </p>
          </div>
        ) : (
          <div style={{ backgroundColor: 'white', borderRadius: '0.5rem', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead style={{ backgroundColor: '#f3f4f6' }}>
                <tr>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: '500' }}>Distance</th>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: '500' }}>Time</th>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: '500' }}>Pace</th>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: '500' }}>Date</th>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: '500' }}>Age</th>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: '500' }}>Race</th>
                </tr>
              </thead>
              <tbody>
                {pbs.map((pb) => (
                  <tr key={pb.id} style={{ borderTop: '1px solid #e5e7eb' }}>
                    <td style={{ padding: '0.75rem 1rem', fontWeight: '500' }}>
                      {formatDistanceCategory(pb.distance_category)}
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>{formatDuration(pb.time_seconds)}</td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      {pb.pace_per_mile
                        ? `${Math.floor(pb.pace_per_mile)}:${Math.round((pb.pace_per_mile % 1) * 60).toString().padStart(2, '0')}/mi`
                        : '--'}
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      {new Date(pb.achieved_at).toLocaleDateString()}
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      {pb.age_at_achievement ? `${pb.age_at_achievement} years` : '--'}
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      {pb.is_race ? (
                        <span style={{ color: '#16a34a', fontWeight: '600' }}>✓ Race</span>
                      ) : (
                        <span style={{ color: '#9ca3af' }}>--</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
