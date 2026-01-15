#!/usr/bin/env python3
"""
Compare system-generated plan to Michael's actual hand-built plan.

Michael's actual 9-week block:
Week 3: 70mi, T-Emphasis (12 w/ 2x3@T, 20E)
Week 4: 42mi, Recovery 
Week 5: 68mi, MP-Emphasis (14 w/8@MP, 20 w/16@MP)
Week 6: 75mi, T-Emphasis (12 w/8@T straight, 22E)
Week 7: 72mi, MP-Emphasis (12 w/10@MP, 24E)
Week 8: 72mi, Peak MP (24 w/18@MP)
Week 9: 50mi, Taper 1
Week 10: 32mi, 10M Race Week
Week 11: 44.2mi, Marathon Week
"""

MICHAELS_PLAN = [
    {"week": 3, "miles": 70, "theme": "T-Emphasis", "key_sessions": ["12 w/ 2x3@T", "20E long"]},
    {"week": 4, "miles": 42, "theme": "Recovery", "key_sessions": ["All easy"]},
    {"week": 5, "miles": 68, "theme": "MP-Emphasis", "key_sessions": ["14 w/8@MP", "20 w/16@MP"]},
    {"week": 6, "miles": 75, "theme": "T-Emphasis", "key_sessions": ["12 w/8@T straight", "22E long"]},
    {"week": 7, "miles": 72, "theme": "MP-Emphasis", "key_sessions": ["12 w/10@MP", "2x3@T", "24E long"]},
    {"week": 8, "miles": 72, "theme": "Peak MP", "key_sessions": ["24 w/18@MP - THE BIG ONE"]},
    {"week": 9, "miles": 50, "theme": "Taper 1", "key_sessions": ["10 w/4@T", "14E fast finish"]},
    {"week": 10, "miles": 32, "theme": "10M Race", "key_sessions": ["8E+strides", "10-MILE RACE", "4R"]},
    {"week": 11, "miles": 44.2, "theme": "Marathon", "key_sessions": ["6E", "5E+strides", "MARATHON"]},
]

def main():
    print("=" * 80)
    print("MICHAEL'S ACTUAL PLAN (Self-Coached)")
    print("=" * 80)
    
    for week in MICHAELS_PLAN:
        print(f"\nWeek {week['week']}: {week['miles']:.0f}mi - {week['theme']}")
        for session in week['key_sessions']:
            print(f"  • {session}")
    
    print("\n" + "=" * 80)
    print("KEY FEATURES OF YOUR PLAN:")
    print("=" * 80)
    
    features = [
        "1. ALTERNATING EMPHASIS: T-week → Recovery → MP-week → T-week → MP-week",
        "2. TWO QUALITY SESSIONS/WEEK: Thursday threshold + Long run work",
        "3. SPECIFIC PRESCRIPTIONS: '2x3mi @ T', '8 @ T straight', not generic 'threshold'",
        "4. PEAK MP: 24mi with 18@MP - true race simulation for 55+ mpw runner",
        "5. PROPER RECOVERY: 42mi week to absorb, not just cutback",
        "6. VOLUME APPROPRIATE: 70-75 mpw peak, not 50 mpw",
        "7. PROGRESSIVE MP LONG RUNS: 8→16→10→18@MP over 4 weeks",
        "8. TAPER: 72→50→32→44.2 (proper step-down)",
        "9. STRIDES: Built into easy days for neuromuscular prep",
        "10. CROSS-TRAINING: Mountain legs, indoor bike for active recovery"
    ]
    
    for f in features:
        print(f)
    
    print("\n" + "=" * 80)
    print("WHAT THE SYSTEM NEEDS TO LEARN FROM THIS:")
    print("=" * 80)
    
    gaps = [
        "❌ Volume too low: System generated ~50 mpw for a 70+ mpw runner",
        "❌ No week themes: Should alternate T-emphasis and MP-emphasis",
        "❌ Single quality session: Should have 2 per week for experienced runners",
        "❌ Generic descriptions: Should specify '2x3mi @ T' not 'threshold work'",
        "❌ Peak MP too conservative: 18@MP in 24mi run, not 16@MP in 22mi",
        "❌ No true recovery week: Need 40% reduction, not just cutback",
        "❌ No cross-training integration: Mountain legs, bike options",
        "❌ Missing strides on easy days: Key for race prep",
        "❌ Taper too shallow: Should be 50→32→~18 before race",
    ]
    
    for g in gaps:
        print(g)
    
    print("\n" + "=" * 80)
    print("SYSTEM IMPROVEMENTS NEEDED:")
    print("=" * 80)
    
    improvements = [
        "1. Use athlete's PEAK weekly volume (70-75) not P90 (61)",
        "2. Add 'week_theme' concept: T-Emphasis, MP-Emphasis, Recovery, Peak",
        "3. Add second quality session for experienced runners",
        "4. Generate specific workout structures: 2x3mi, 8mi straight, etc.",
        "5. Scale peak MP to athlete's proven capability (18@MP in 24mi)",
        "6. Insert proper recovery week (40% reduction) every 3-4 weeks",
        "7. Add optional cross-training slots",
        "8. Add strides to easy day descriptions",
        "9. Make taper more aggressive for experienced marathoners",
    ]
    
    for i in improvements:
        print(i)


if __name__ == "__main__":
    main()
