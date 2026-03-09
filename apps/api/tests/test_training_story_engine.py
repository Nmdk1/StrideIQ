"""
Training Story Engine Tests

Enforces contracts on the training story synthesis layer,
especially the "silence over wrong narrative" campaign rule.
"""

from unittest.mock import MagicMock

from services.training_story_engine import synthesize_training_story


def test_campaign_narrative_is_none_without_campaign_data():
    """
    When no PerformanceEvent has campaign_data, synthesize_training_story
    must return campaign_narrative=None.  Silence is better than a wrong arc.
    """
    events_without_campaign = [
        MagicMock(campaign_data=None, event_date=None),
        MagicMock(campaign_data={}, event_date=None),
    ]
    story = synthesize_training_story(findings=[], events=events_without_campaign)
    assert story.campaign_narrative is None


def test_campaign_narrative_is_none_with_empty_events():
    """No events at all — campaign narrative must be None."""
    story = synthesize_training_story(findings=[], events=[])
    assert story.campaign_narrative is None
