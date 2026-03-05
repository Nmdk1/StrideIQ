"""Run the training story synthesis against founder data and display results."""
import json
from core.database import SessionLocal
from models import Athlete, PerformanceEvent
from services.race_input_analysis import mine_race_inputs
from services.training_story_engine import synthesize_training_story

db = SessionLocal()
a = db.query(Athlete).filter(Athlete.email == 'mbshaf@gmail.com').first()

print(f"Running training story for {a.email} (RPI: {a.rpi})")
print("=" * 80)

findings, honest_gaps = mine_race_inputs(a.id, db)
print(f"{len(findings)} findings produced, {len(honest_gaps)} gaps")

events = db.query(PerformanceEvent).filter(
    PerformanceEvent.athlete_id == a.id,
    PerformanceEvent.user_confirmed == True,
).order_by(PerformanceEvent.event_date).all()

story = synthesize_training_story(findings, events)

print(f"\n{'=' * 80}")
print("RACE STORIES")
print(f"{'=' * 80}")
for rs in story.race_stories:
    pb = " (PB)" if rs.is_pb else ""
    print(f"\n--- {rs.distance} {rs.time_display}{pb} on {rs.race_date} ---")
    print(f"  Confidence: {rs.confidence}")
    if rs.peaking_adaptations:
        print(f"  Peaking adaptations ({len(rs.peaking_adaptations)}):")
        for a_item in rs.peaking_adaptations:
            print(f"    [{a_item['finding_type']}] {a_item['summary'][:120]}")
            if a_item.get('value_at_race'):
                print(f"      Value at race: {a_item['value_at_race']}")
    if rs.contributing_inputs:
        print(f"  Contributing inputs ({len(rs.contributing_inputs)}):")
        for inp in rs.contributing_inputs:
            print(f"    [{inp['finding_type']}] {inp['summary'][:120]}")
    if rs.confounds:
        print(f"  Confounds: {', '.join(rs.confounds)}")
    print(f"  Race evidence: CV={rs.race_evidence.get('pace_cv_pct')}%, "
          f"split ratio={rs.race_evidence.get('split_ratio_pct')}%")

print(f"\n{'=' * 80}")
print("PROGRESSIONS")
print(f"{'=' * 80}")
for p in story.progressions:
    print(f"\n--- {p.metric_name} ({p.duration_weeks} weeks, {p.trend}) ---")
    for dp in p.data_points:
        parts = [f"  {dp.get('date', '?')}: {dp.get('value', '?')}"]
        if dp.get('hr'):
            parts.append(f"HR {dp['hr']}")
        if dp.get('temp_f'):
            parts.append(f"{dp['temp_f']}°F")
        if dp.get('n'):
            parts.append(f"n={dp['n']}")
        print(" | ".join(parts))
    if p.biggest_jump:
        print(f"  Biggest jump: {p.biggest_jump}")

print(f"\n{'=' * 80}")
print("CONNECTIONS")
print(f"{'=' * 80}")
for c in story.connections:
    f_from = story.findings[c.from_index]
    f_to = story.findings[c.to_index]
    print(f"\n  [{c.connection_type}] {c.temporal}")
    print(f"    {f_from['type']} → {f_to['type']}")
    print(f"    {c.mechanism[:120]}")

print(f"\n{'=' * 80}")
print("CAMPAIGN")
print(f"{'=' * 80}")
if story.campaign_narrative:
    for k, v in story.campaign_narrative.items():
        print(f"  {k}: {v}")
else:
    print("  No campaign detected")

print(f"\n{'=' * 80}")
print("HONEST GAPS")
print(f"{'=' * 80}")
for g in story.honest_gaps:
    print(f"  - {g}")

print(f"\n{'=' * 80}")
print("COACH CONTEXT (what the LLM sees)")
print(f"{'=' * 80}")
print(story.to_coach_context())

db.close()
