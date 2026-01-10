"""
Run Delivery Service

Ties together activity analysis, perception prompts, and delivery logic.
Provides the complete "run delivery" experience: objective insights + perception prompts.

Key principles:
- Only show insights if meaningful (no noise)
- Always prompt for perception (builds dataset)
- Tone: direct, sparse, irreverent when warranted
- Supportive but no coddling - data speaks
"""
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from datetime import datetime
from models import Activity, ActivityFeedback, Athlete
from services.activity_analysis import ActivityAnalysis
from services.perception_prompts import get_perception_prompts

# Tone templates for different scenarios
TONE_TEMPLATES = {
    "improvement_confirmed": {
        "tone": "irreverent",
        "messages": [
            "{improvement}% improvement. Cool. Keep doing what you're doing.",
            "{improvement}% better. The numbers don't lie.",
            "Efficiency up {improvement}%. Nice work."
        ]
    },
    "pr_improvement": {
        "tone": "irreverent",
        "messages": [
            "PR efficiency: {improvement}% better. What's your 10K time?",
            "{improvement}% improvement vs your best. Race results?",
            "Better than your PR. Show me the splits."
        ]
    },
    "no_meaningful_insight": {
        "tone": "sparse",
        "messages": [
            "Run complete. No significant changes detected.",
            "Nothing notable. Keep training.",
            "Baseline performance. Keep going."
        ]
    },
    "insufficient_data": {
        "tone": "sparse",
        "messages": [
            "Run logged. Need more data for insights.",
            "Activity recorded. Keep training to build baseline.",
            "Not enough data yet. More runs needed."
        ]
    }
}


def format_insight_message(insight: str, improvement_pct: float, baseline_type: str) -> str:
    """
    Format insight message with appropriate tone.
    
    Applies irreverent tone for meaningful improvements, sparse for everything else.
    """
    # Extract improvement percentage from insight if not provided
    if improvement_pct is None:
        # Try to extract from insight string
        try:
            improvement_pct = float(insight.split("%")[0].split()[-1])
        except:
            improvement_pct = 0
    
    # Determine tone based on baseline type and improvement
    if baseline_type == "pr" and improvement_pct >= 2.0:
        template = TONE_TEMPLATES["pr_improvement"]
        import random
        message = random.choice(template["messages"]).format(improvement=improvement_pct)
        return message
    
    if improvement_pct >= 2.5:
        template = TONE_TEMPLATES["improvement_confirmed"]
        import random
        message = random.choice(template["messages"]).format(improvement=improvement_pct)
        return message
    
    # Default: return original insight
    return insight


def deliver_run(activity: Activity, athlete: Athlete, db: Session) -> Dict:
    """
    Complete run delivery: analysis + perception prompts.
    
    Returns:
        {
            "activity_id": UUID,
            "has_meaningful_insight": bool,
            "insights": List[str],  # Only if meaningful
            "insight_tone": str,  # "irreverent", "sparse", "supportive"
            "metrics": {
                "pace_per_mile": float,
                "avg_heart_rate": int,
                "efficiency_score": float
            },
            "perception_prompt": {
                "should_prompt": bool,
                "prompt_text": str,
                "required_fields": List[str],
                "optional_fields": List[str],
                "has_feedback": bool,
                "run_type": str
            },
            "delivery_timestamp": datetime
        }
    """
    # Perform activity analysis
    analysis = ActivityAnalysis(activity, athlete, db)
    analysis_result = analysis.analyze()
    
    # Get perception prompts
    perception_prompt = get_perception_prompts(activity, db)
    
    # Check if feedback already exists
    existing_feedback = db.query(ActivityFeedback).filter(
        ActivityFeedback.activity_id == activity.id
    ).first()
    
    # Format insights with tone
    formatted_insights = []
    insight_tone = "sparse"
    
    if analysis_result.get("has_meaningful_insight"):
        insight_tone = "irreverent"
        raw_insights = analysis_result.get("insights", [])
        
        # Get improvement percentages from comparisons
        comparisons = analysis_result.get("comparisons", [])
        improvement_map = {
            comp.get("baseline_type"): comp.get("improvement_pct", 0)
            for comp in comparisons
            if comp.get("is_meaningful")
        }
        
        for insight in raw_insights:
            # Determine baseline type from insight
            baseline_type = "current_block"  # default
            if "PR efficiency" in insight:
                baseline_type = "pr"
            elif "Race efficiency" in insight:
                baseline_type = "last_race"
            elif "Block efficiency" in insight:
                baseline_type = "current_block"
            elif "Efficiency trend" in insight:
                baseline_type = "run_type_average"
            
            improvement_pct = improvement_map.get(baseline_type, 0)
            formatted_insight = format_insight_message(insight, improvement_pct, baseline_type)
            formatted_insights.append(formatted_insight)
    
    # If no meaningful insights, provide sparse message
    if not formatted_insights:
        if not analysis_result.get("metrics", {}).get("efficiency_score"):
            # Insufficient data
            template = TONE_TEMPLATES["insufficient_data"]
            import random
            formatted_insights = [random.choice(template["messages"])]
        else:
            # No meaningful change
            template = TONE_TEMPLATES["no_meaningful_insight"]
            import random
            formatted_insights = [random.choice(template["messages"])]
    
    return {
        "activity_id": str(activity.id),
        "has_meaningful_insight": analysis_result.get("has_meaningful_insight", False),
        "insights": formatted_insights if analysis_result.get("has_meaningful_insight") else formatted_insights,
        "insight_tone": insight_tone,
        "show_insights": analysis_result.get("has_meaningful_insight", False) or len(formatted_insights) > 0,
        "metrics": analysis_result.get("metrics", {}),
        "perception_prompt": {
            "should_prompt": perception_prompt["should_prompt"],
            "prompt_text": perception_prompt["prompt_text"],
            "required_fields": perception_prompt["required_fields"],
            "optional_fields": perception_prompt["optional_fields"],
            "has_feedback": existing_feedback is not None,
            "run_type": perception_prompt["run_type"]
        },
        "delivery_timestamp": datetime.utcnow().isoformat()
    }


def get_run_delivery(activity_id: str, athlete_id: str, db: Session) -> Dict:
    """
    Get run delivery for a specific activity.
    
    Main entry point for run delivery API.
    """
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise ValueError(f"Activity {activity_id} not found")
    
    if str(activity.athlete_id) != str(athlete_id):
        raise ValueError("Activity does not belong to athlete")
    
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise ValueError(f"Athlete {athlete_id} not found")
    
    return deliver_run(activity, athlete, db)


