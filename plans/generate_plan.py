#!/usr/bin/env python3
"""
Plan Generator - Converts archetype JSON to displayable HTML plans

Usage:
    python generate_plan.py marathon_mid_5d_18w
    python generate_plan.py marathon_mid_5d_18w --paces "1:30:00 half"
    
The generator reads from plans/archetypes/{name}.json and outputs to plans/generated/{name}.html
"""

import json
import argparse
from pathlib import Path
from datetime import datetime

# Workout type colors for display
WORKOUT_COLORS = {
    "easy": {"bg": "#00ba7c", "text": "#000"},
    "easy_strides": {"bg": "#00ba7c", "text": "#000"},
    "long": {"bg": "#1d9bf0", "text": "#fff"},
    "long_mp": {"bg": "#f91880", "text": "#fff"},
    "medium_long": {"bg": "#38bdf8", "text": "#000"},
    "threshold": {"bg": "#ff7a00", "text": "#000"},
    "threshold_light": {"bg": "#ff9a40", "text": "#000"},
    "threshold_short": {"bg": "#ff9a40", "text": "#000"},
    "recovery": {"bg": "#536471", "text": "#fff"},
    "rest": {"bg": "#2f3336", "text": "#8b98a5"},
    "gym": {"bg": "#4a5568", "text": "#fff"},
    "shakeout_strides": {"bg": "#00ba7c", "text": "#000"},
    "race": {"bg": "linear-gradient(135deg, #f91880, #ff7a00)", "text": "#fff"},
}

PHASE_COLORS = {
    "base": "#00ba7c",
    "build1": "#ff7a00",
    "build2": "#f91880",
    "peak": "#dc2626",
    "taper": "#7856ff",
    "cutback": "#ffd400",
    "race": "#f91880",
}


def load_archetype(name: str) -> dict:
    """Load archetype JSON file"""
    path = Path(__file__).parent / "archetypes" / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Archetype not found: {path}")
    
    with open(path, "r") as f:
        return json.load(f)


def generate_html(archetype: dict, paces: dict = None) -> str:
    """Generate HTML plan from archetype"""
    
    meta = archetype["meta"]
    weeks = archetype["weeks"]
    
    # Determine if we're showing paces or effort descriptions
    show_paces = paces is not None
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{meta['distance'].title()} Training Plan - {meta['mileage_tier'].title()} Mileage | {meta['days_per_week']} Days/Week | {meta['duration_weeks']} Weeks</title>
    <style>
        :root {{
            --bg-dark: #0f1419;
            --bg-card: #1a1f26;
            --bg-week: #232a33;
            --text-primary: #e7e9ea;
            --text-secondary: #8b98a5;
            --text-muted: #536471;
            --accent-blue: #1d9bf0;
            --border: #2f3336;
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            line-height: 1.5;
            padding: 20px;
        }}
        
        .container {{ max-width: 1400px; margin: 0 auto; }}
        
        header {{
            text-align: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }}
        
        h1 {{ font-size: 1.8rem; font-weight: 700; margin-bottom: 6px; }}
        .subtitle {{ color: var(--text-secondary); font-size: 1rem; }}
        
        .info-banner {{
            background: linear-gradient(135deg, #1d9bf022, #7856ff22);
            border: 1px solid var(--accent-blue);
            border-radius: 10px;
            padding: 14px 18px;
            margin-bottom: 20px;
        }}
        
        .info-banner h3 {{ color: var(--accent-blue); margin-bottom: 6px; font-size: 0.95rem; }}
        .info-banner p {{ color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 4px; }}
        
        .legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 16px;
            padding: 10px 14px;
            background: var(--bg-card);
            border-radius: 8px;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 0.75rem;
        }}
        
        .legend-color {{
            width: 12px;
            height: 12px;
            border-radius: 3px;
        }}
        
        .calendar {{ display: grid; gap: 5px; }}
        
        .week-row {{
            display: grid;
            grid-template-columns: 80px 60px repeat(7, 1fr);
            gap: 4px;
            padding: 6px;
            background: var(--bg-week);
            border-radius: 6px;
            border-left: 4px solid transparent;
        }}
        
        .week-header {{
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        
        .week-num {{ font-weight: 700; font-size: 0.85rem; }}
        .week-phase {{ font-size: 0.6rem; color: var(--text-muted); text-transform: uppercase; }}
        
        .week-mileage {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            background: var(--bg-card);
            border-radius: 5px;
            padding: 3px;
        }}
        
        .mileage-value {{ font-weight: 700; font-size: 0.95rem; color: var(--accent-blue); }}
        .mileage-label {{ font-size: 0.55rem; color: var(--text-muted); text-transform: uppercase; }}
        
        .day-cell {{
            background: var(--bg-card);
            border-radius: 4px;
            padding: 5px;
            min-height: 55px;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }}
        
        .day-label {{ font-size: 0.55rem; color: var(--text-muted); text-transform: uppercase; }}
        
        .workout-type {{
            font-weight: 600;
            font-size: 0.65rem;
            padding: 2px 4px;
            border-radius: 3px;
            display: inline-block;
            width: fit-content;
        }}
        
        .workout-detail {{ font-size: 0.65rem; color: var(--text-secondary); line-height: 1.2; }}
        
        .day-cell.rest-day {{
            background: var(--bg-dark);
            border: 1px dashed var(--border);
        }}
        
        .summary {{
            margin-top: 20px;
            padding: 14px;
            background: var(--bg-card);
            border-radius: 10px;
        }}
        
        .summary h2 {{ margin-bottom: 10px; color: var(--accent-blue); font-size: 1.1rem; }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 10px;
        }}
        
        .summary-item {{
            background: var(--bg-week);
            padding: 10px;
            border-radius: 6px;
        }}
        
        .summary-item .label {{ font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase; }}
        .summary-item .value {{ font-size: 1.1rem; font-weight: 700; }}
        
        footer {{
            text-align: center;
            margin-top: 20px;
            color: var(--text-muted);
            font-size: 0.75rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🏃 {meta['distance'].title()} Training Plan</h1>
            <p class="subtitle">{meta['mileage_tier'].title()} Mileage ({meta['starting_volume_mi']}-{meta['peak_volume_mi']} mi/wk) • {meta['days_per_week']} Days/Week • {meta['duration_weeks']} Weeks</p>
        </header>
        
        <div class="info-banner">
            <h3>📐 Plan Structure</h3>
            <p><strong>Volume:</strong> {meta['starting_volume_mi']} mi → {meta['peak_volume_mi']} mi peak (hold 3 weeks) → Taper</p>
            <p><strong>Cut-back:</strong> Every {meta['cutback_frequency']}th week ({int(meta['cutback_reduction']*100)}% reduction)</p>
            <p><strong>Long Run:</strong> {meta['long_run_start_mi']} mi start → {meta['long_run_peak_mi']} mi peak</p>
            {"<p><strong>Paces:</strong> Use Training Pace Calculator to get your specific paces</p>" if not show_paces else ""}
        </div>
        
        <div class="legend">
            <div class="legend-item"><div class="legend-color" style="background: #00ba7c;"></div><span>Easy/Strides</span></div>
            <div class="legend-item"><div class="legend-color" style="background: #38bdf8;"></div><span>Med-Long</span></div>
            <div class="legend-item"><div class="legend-color" style="background: #1d9bf0;"></div><span>Long Run</span></div>
            <div class="legend-item"><div class="legend-color" style="background: #ff7a00;"></div><span>Threshold</span></div>
            <div class="legend-item"><div class="legend-color" style="background: #f91880;"></div><span>Long+MP</span></div>
            <div class="legend-item"><div class="legend-color" style="background: #4a5568;"></div><span>Gym</span></div>
            <div class="legend-item"><div class="legend-color" style="background: #2f3336;"></div><span>Rest</span></div>
        </div>
        
        <div class="calendar">
"""
    
    # Generate each week
    for week in weeks:
        phase = week["phase"]
        phase_color = PHASE_COLORS.get(phase, "#536471")
        is_cutback = phase == "cutback"
        
        html += f"""
            <div class="week-row" style="border-left-color: {phase_color};{' background: linear-gradient(90deg, #ffd40011, transparent);' if is_cutback else ''}">
                <div class="week-header">
                    <span class="week-num">Week {week['week']}</span>
                    <span class="week-phase">{phase.replace('build', 'Build ').title()}</span>
                </div>
                <div class="week-mileage">
                    <span class="mileage-value">{week['total_miles'] if week['phase'] != 'race' else '26.2+'}</span>
                    <span class="mileage-label">{'race!' if week['phase'] == 'race' else 'miles'}</span>
                </div>
"""
        
        # Generate each day
        for day in ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]:
            workout = week["workouts"][day]
            w_type = workout["type"]
            colors = WORKOUT_COLORS.get(w_type, WORKOUT_COLORS["easy"])
            is_rest = w_type in ["rest", "gym"]
            
            day_class = "day-cell rest-day" if is_rest else "day-cell"
            
            # Format miles display
            miles_display = f"{workout['miles']} mi" if workout['miles'] > 0 else ""
            if w_type == "race":
                miles_display = ""
            
            # Combine description
            if miles_display and workout['description']:
                full_desc = f"{miles_display} {workout['description']}"
            elif workout['description']:
                full_desc = workout['description']
            else:
                full_desc = miles_display
            
            bg_style = f"background: {colors['bg']};" if "gradient" not in colors['bg'] else f"background: {colors['bg']};"
            
            html += f"""
                <div class="{day_class}">
                    <span class="day-label">{day[:3].title()}</span>
                    <span class="workout-type" style="{bg_style} color: {colors['text']};">{w_type.replace('_', ' ').title()}</span>
                    <span class="workout-detail">{full_desc}</span>
                </div>
"""
        
        html += "            </div>\n"
    
    # Summary section
    total_volume = sum(w['total_miles'] for w in weeks if w['phase'] != 'race')
    
    html += f"""
        </div>
        
        <div class="summary">
            <h2>📊 Plan Summary</h2>
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="label">Starting Volume</div>
                    <div class="value">{meta['starting_volume_mi']} mi</div>
                </div>
                <div class="summary-item">
                    <div class="label">Peak Volume</div>
                    <div class="value">{meta['peak_volume_mi']} mi</div>
                </div>
                <div class="summary-item">
                    <div class="label">Longest Run</div>
                    <div class="value">{meta['long_run_peak_mi']} mi</div>
                </div>
                <div class="summary-item">
                    <div class="label">Cut-backs</div>
                    <div class="value">Every {meta['cutback_frequency']}th wk</div>
                </div>
                <div class="summary-item">
                    <div class="label">Taper</div>
                    <div class="value">{meta['taper_weeks']} weeks</div>
                </div>
                <div class="summary-item">
                    <div class="label">Total Volume</div>
                    <div class="value">~{total_volume} mi</div>
                </div>
            </div>
        </div>
        
        <footer>
            <p>StrideIQ Training Plan | Generated {datetime.now().strftime('%Y-%m-%d')}</p>
            <p>Version {meta['version']}</p>
        </footer>
    </div>
</body>
</html>
"""
    
    return html


def save_html(html: str, name: str) -> Path:
    """Save generated HTML to file"""
    output_dir = Path(__file__).parent / "generated"
    output_dir.mkdir(exist_ok=True)
    
    output_path = output_dir / f"{name}.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Generate training plan from archetype")
    parser.add_argument("archetype", help="Name of archetype (without .json)")
    parser.add_argument("--paces", help="Race time for pace calculation (e.g., '1:30:00 half')")
    parser.add_argument("--open", action="store_true", help="Open in browser after generation")
    
    args = parser.parse_args()
    
    # Load archetype
    print(f"Loading archetype: {args.archetype}")
    archetype = load_archetype(args.archetype)
    
    # Parse paces if provided
    paces = None
    if args.paces:
        # TODO: Integrate with Training Pace Calculator
        print(f"Pace calculation from '{args.paces}' not yet implemented")
    
    # Generate HTML
    print("Generating HTML...")
    html = generate_html(archetype, paces)
    
    # Save
    output_path = save_html(html, args.archetype)
    print(f"Saved to: {output_path}")
    
    # Open in browser if requested
    if args.open:
        import webbrowser
        webbrowser.open(str(output_path))


if __name__ == "__main__":
    main()
