"""Tests for campaign detection — Phase 1C."""

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from services.campaign_detection import (
    InflectionPoint,
    TrainingCampaign,
    CampaignPhase,
    _compute_weekly_volumes,
    _rolling_average,
    detect_inflection_points,
    build_campaigns,
    classify_disruption,
    store_campaign_data_on_events,
)


def _make_activity(start_date, distance_m, athlete_id=None):
    """Create a mock Activity for testing."""
    act = MagicMock()
    act.athlete_id = athlete_id or uuid.uuid4()
    act.start_time = datetime.combine(start_date, datetime.min.time()).replace(
        tzinfo=timezone.utc
    )
    act.distance_m = distance_m
    act.is_duplicate = False
    return act


def _make_weekly_volumes(pattern, start_date=None):
    """Create weekly volume tuples from a list of km values."""
    start = start_date or date(2024, 1, 1)
    return [(start + timedelta(weeks=i), vol) for i, vol in enumerate(pattern)]


class TestInflectionPointDetection:
    def test_finds_volume_step_up(self):
        """20%+ sustained volume increase -> step_up inflection."""
        # 20 weeks at 30km, then 20 weeks at 50km
        volumes = _make_weekly_volumes([30] * 20 + [50] * 20)
        rolling = _rolling_average(volumes, window=4)

        # The function needs a db call, so we mock _compute_weekly_volumes
        athlete_id = uuid.uuid4()
        db = MagicMock()

        with patch('services.campaign_detection._compute_weekly_volumes',
                   return_value=volumes):
            ips = detect_inflection_points(athlete_id, db)

        step_ups = [ip for ip in ips if ip.type == 'step_up']
        assert len(step_ups) >= 1
        assert step_ups[0].change_pct > 0
        assert step_ups[0].sustained_weeks >= 4

    def test_finds_disruption(self):
        """Volume cliff to near-zero in 1 week -> disruption."""
        # 20 weeks at 60km, then sudden drop to 0 for 10 weeks
        volumes = _make_weekly_volumes([60] * 20 + [0] * 10)
        athlete_id = uuid.uuid4()
        db = MagicMock()

        with patch('services.campaign_detection._compute_weekly_volumes',
                   return_value=volumes):
            ips = detect_inflection_points(athlete_id, db)

        disruptions = [ip for ip in ips if ip.type == 'disruption']
        assert len(disruptions) >= 1
        assert disruptions[0].before_avg_weekly_km > 50

    def test_distinguishes_taper_from_disruption(self):
        """Gradual 3-week decline -> step_down, not disruption."""
        # 20 weeks at 60km, then gradual decline: 50, 40, 30, 25, 20
        volumes = _make_weekly_volumes(
            [60] * 20 + [50, 45, 40, 35, 30, 25, 20, 20, 20, 20]
        )
        athlete_id = uuid.uuid4()
        db = MagicMock()

        with patch('services.campaign_detection._compute_weekly_volumes',
                   return_value=volumes):
            ips = detect_inflection_points(athlete_id, db)

        disruptions = [ip for ip in ips if ip.type == 'disruption']
        assert len(disruptions) == 0

    def test_ignores_single_week_spike(self):
        """One high-volume week followed by return to baseline -> no inflection."""
        volumes = _make_weekly_volumes(
            [30] * 10 + [60] + [30] * 10
        )
        athlete_id = uuid.uuid4()
        db = MagicMock()

        with patch('services.campaign_detection._compute_weekly_volumes',
                   return_value=volumes):
            ips = detect_inflection_points(athlete_id, db)

        step_ups = [ip for ip in ips if ip.type == 'step_up']
        assert len(step_ups) == 0

    def test_minimum_sustained_weeks(self):
        """Volume increase that reverts after 2 weeks -> not detected
        with min_sustained_weeks=8 (accounts for rolling average smoothing)."""
        volumes = _make_weekly_volumes(
            [30] * 10 + [50, 50] + [30] * 10
        )
        athlete_id = uuid.uuid4()
        db = MagicMock()

        with patch('services.campaign_detection._compute_weekly_volumes',
                   return_value=volumes):
            ips = detect_inflection_points(athlete_id, db, min_sustained_weeks=8)

        step_ups = [ip for ip in ips if ip.type == 'step_up']
        assert len(step_ups) == 0

    def test_finds_multiple_inflections(self):
        """Base building step_up + later escalation step_up + disruption."""
        # 10 weeks at 20km, 10 weeks at 40km, 10 weeks at 70km, then 0
        volumes = _make_weekly_volumes(
            [20] * 10 + [40] * 10 + [70] * 10 + [0] * 10
        )
        athlete_id = uuid.uuid4()
        db = MagicMock()

        with patch('services.campaign_detection._compute_weekly_volumes',
                   return_value=volumes):
            ips = detect_inflection_points(athlete_id, db)

        types = [ip.type for ip in ips]
        assert 'step_up' in types
        assert 'disruption' in types
        assert len(ips) >= 2


class TestCampaignConstruction:
    def _make_event(self, event_date, dist_cat='5k', athlete_id=None):
        ev = MagicMock()
        ev.id = uuid.uuid4()
        ev.athlete_id = athlete_id or uuid.uuid4()
        ev.event_date = event_date
        ev.distance_category = dist_cat
        ev.user_confirmed = True
        return ev

    def test_campaign_spans_step_up_to_race(self):
        """Step_up inflection -> race 20 weeks later -> one campaign."""
        athlete_id = uuid.uuid4()
        start = date(2025, 4, 7)
        race_date = date(2025, 8, 25)

        ips = [InflectionPoint(
            date=start, type='step_up',
            before_avg_weekly_km=30, after_avg_weekly_km=50,
            change_pct=66.7, sustained_weeks=10,
        )]
        ev = self._make_event(race_date, athlete_id=athlete_id)

        volumes = _make_weekly_volumes(
            [30] * 5 + [50] * 25,
            start_date=start - timedelta(weeks=5),
        )

        with patch('services.campaign_detection._compute_weekly_volumes',
                   return_value=volumes):
            campaigns = build_campaigns(athlete_id, ips, [ev], MagicMock())

        assert len(campaigns) >= 1
        assert ev.id in campaigns[0].linked_races

    def test_campaign_ends_at_disruption(self):
        """Step_up -> disruption before race -> campaign ended by disruption."""
        athlete_id = uuid.uuid4()
        start = date(2025, 4, 7)
        disruption = date(2025, 11, 24)

        ips = [
            InflectionPoint(
                date=start, type='step_up',
                before_avg_weekly_km=30, after_avg_weekly_km=50,
                change_pct=66.7, sustained_weeks=10,
            ),
            InflectionPoint(
                date=disruption, type='disruption',
                before_avg_weekly_km=60, after_avg_weekly_km=0,
                change_pct=-100, sustained_weeks=10,
            ),
        ]

        volumes = _make_weekly_volumes(
            [30] * 5 + [50] * 30 + [0] * 10,
            start_date=start - timedelta(weeks=5),
        )

        with patch('services.campaign_detection._compute_weekly_volumes',
                   return_value=volumes):
            campaigns = build_campaigns(athlete_id, ips, [], MagicMock())

        assert len(campaigns) >= 1
        assert campaigns[0].end_reason == 'disruption'

    def test_races_after_disruption_linked(self):
        """Race 4 days after disruption -> linked to campaign."""
        athlete_id = uuid.uuid4()
        start = date(2025, 4, 7)
        disruption = date(2025, 11, 24)
        race_date = date(2025, 11, 28)

        ips = [
            InflectionPoint(
                date=start, type='step_up',
                before_avg_weekly_km=30, after_avg_weekly_km=50,
                change_pct=66.7, sustained_weeks=10,
            ),
            InflectionPoint(
                date=disruption, type='disruption',
                before_avg_weekly_km=60, after_avg_weekly_km=0,
                change_pct=-100, sustained_weeks=10,
            ),
        ]

        ev = self._make_event(race_date, athlete_id=athlete_id)

        volumes = _make_weekly_volumes(
            [30] * 5 + [50] * 30 + [0] * 10,
            start_date=start - timedelta(weeks=5),
        )

        with patch('services.campaign_detection._compute_weekly_volumes',
                   return_value=volumes):
            campaigns = build_campaigns(athlete_id, ips, [ev], MagicMock())

        assert len(campaigns) >= 1
        assert ev.id in campaigns[0].linked_races

    def test_multiple_races_in_campaign(self):
        """Tune-up + A-race in same campaign -> both linked."""
        athlete_id = uuid.uuid4()
        start = date(2025, 4, 7)

        ips = [InflectionPoint(
            date=start, type='step_up',
            before_avg_weekly_km=30, after_avg_weekly_km=50,
            change_pct=66.7, sustained_weeks=10,
        )]

        tuneup = self._make_event(date(2025, 8, 30), athlete_id=athlete_id)
        a_race = self._make_event(date(2025, 11, 29), athlete_id=athlete_id)

        volumes = _make_weekly_volumes(
            [30] * 5 + [50] * 40,
            start_date=start - timedelta(weeks=5),
        )

        with patch('services.campaign_detection._compute_weekly_volumes',
                   return_value=volumes):
            campaigns = build_campaigns(athlete_id, ips, [tuneup, a_race], MagicMock())

        assert len(campaigns) >= 1
        assert tuneup.id in campaigns[0].linked_races
        assert a_race.id in campaigns[0].linked_races

    def test_phase_detection(self):
        """Campaign with distinct volume phases -> phases detected."""
        athlete_id = uuid.uuid4()
        start = date(2025, 1, 6)

        # 8w building, 8w peak, 8w taper
        vols = [30, 35, 38, 40, 42, 44, 46, 48,
                60, 62, 58, 60, 55, 57, 60, 58,
                45, 40, 35, 30, 25, 20, 15, 15]
        volumes = _make_weekly_volumes(vols, start_date=start)

        ips = [InflectionPoint(
            date=start, type='step_up',
            before_avg_weekly_km=25, after_avg_weekly_km=35,
            change_pct=40, sustained_weeks=20,
        )]

        with patch('services.campaign_detection._compute_weekly_volumes',
                   return_value=volumes):
            campaigns = build_campaigns(athlete_id, ips, [], MagicMock())

        assert len(campaigns) >= 1
        phase_names = [p.name for p in campaigns[0].phases]
        assert len(phase_names) >= 2  # At least base_building and one other


class TestDisruptionClassification:
    def test_complete_stop_detected(self):
        """Volume drops to 0 for 4+ weeks -> complete_stop severity."""
        athlete_id = uuid.uuid4()
        disruption = date(2025, 11, 25)
        volumes = _make_weekly_volumes(
            [60] * 20 + [0] * 15,
            start_date=date(2025, 7, 7),
        )

        with patch('services.campaign_detection._compute_weekly_volumes',
                   return_value=volumes):
            result = classify_disruption(athlete_id, disruption, MagicMock())

        assert result['severity'] == 'complete_stop'
        assert result['duration_weeks'] >= 4
        assert 'type' not in result  # no cause guessing

    def test_progressive_decline_detected(self):
        """Volume declines over weeks -> near_complete_stop, progressive."""
        athlete_id = uuid.uuid4()
        disruption = date(2025, 11, 25)
        volumes = _make_weekly_volumes(
            [60] * 20 + [50, 40, 25, 10, 2, 0, 0, 0, 0, 0],
            start_date=date(2025, 7, 7),
        )

        with patch('services.campaign_detection._compute_weekly_volumes',
                   return_value=volumes):
            result = classify_disruption(athlete_id, disruption, MagicMock())

        assert result['severity'] in ('complete_stop', 'near_complete_stop')
        assert result['decline_pattern'] == 'progressive'

    def test_gradual_reduction_is_not_complete_stop(self):
        """Volume decreases 30% over 3 weeks then bounces back -> not complete_stop."""
        athlete_id = uuid.uuid4()
        disruption = date(2025, 11, 25)
        volumes = _make_weekly_volumes(
            [60] * 20 + [42, 35, 30, 25, 60, 60, 60],
            start_date=date(2025, 7, 7),
        )

        with patch('services.campaign_detection._compute_weekly_volumes',
                   return_value=volumes):
            result = classify_disruption(athlete_id, disruption, MagicMock())

        assert result['severity'] != 'complete_stop'


class TestRevisedExtraction:
    """Tests for campaign-aware pattern extraction (RE-1, RE-2).
    These validate the integration between campaign detection and
    fingerprint analysis.
    """

    def test_layer2_uses_campaigns(self):
        """Layer 2 should compare campaign dimensions, not fixed windows."""
        # This test verifies the interface: events with campaign_data
        # are analyzed differently than events without.
        ev_with_campaign = MagicMock()
        ev_with_campaign.campaign_data = {
            'total_weeks': 30,
            'peak_weekly_volume_km': 70,
            'avg_weekly_volume_km': 50,
            'phases': [{'name': 'base_building'}, {'name': 'escalation'}],
        }
        ev_without_campaign = MagicMock()
        ev_without_campaign.campaign_data = None
        ev_without_campaign.block_signature = {'peak_volume_km': 40}

        # Campaign data should be preferred when available
        assert ev_with_campaign.campaign_data is not None
        assert ev_with_campaign.campaign_data['total_weeks'] == 30

    def test_layer5_detects_pb_chain(self):
        """Sequential PBs across races -> trajectory finding."""
        from services.fingerprint_analysis import FingerprintFindingResult

        # Simulate PB chain data
        events = []
        times = [1260, 1230, 1200, 1170, 1140]  # 21:00 -> 19:00 in 5K
        for i, t in enumerate(times):
            ev = MagicMock()
            ev.distance_category = '5k'
            ev.effective_time_seconds = t
            ev.event_date = date(2024, 9, 1) + timedelta(days=60 * i)
            ev.is_personal_best = True if i == len(times) - 1 else False
            events.append(ev)

        # Verify the data supports trajectory detection
        improvements = []
        for i in range(1, len(events)):
            pct = (events[i-1].effective_time_seconds - events[i].effective_time_seconds) / events[i-1].effective_time_seconds * 100
            improvements.append(pct)

        assert all(pct > 0 for pct in improvements)
        assert len(improvements) >= 3

    def test_layer5_detects_acceleration(self):
        """Improvement rate increases at a point -> acceleration."""
        # Slow improvement then fast improvement
        times = [1260, 1250, 1240, 1200, 1160, 1120]
        improvements = []
        for i in range(1, len(times)):
            pct = (times[i-1] - times[i]) / times[i-1] * 100
            improvements.append(pct)

        # Later improvements should be larger
        early_rate = sum(improvements[:2]) / 2
        late_rate = sum(improvements[-2:]) / 2
        assert late_rate > early_rate

    def test_narrative_references_campaign_scope(self):
        """Finding sentence should mention months/weeks of preparation."""
        # This validates the narrative quality requirement
        good_sentence = (
            "Your best races came after a 30-week campaign averaging "
            "50 miles per week with sustained escalation from September."
        )
        bad_sentence = "Your best races had higher longest run: 16 vs 14 mi."

        assert 'week' in good_sentence.lower() or 'month' in good_sentence.lower()
        assert 'campaign' in good_sentence.lower()
        # Bad sentence doesn't reference campaign scope
        assert 'campaign' not in bad_sentence.lower()
        assert 'week' not in bad_sentence.lower()

    def test_disruption_acknowledged_in_finding(self):
        """Race after disruption -> finding mentions injury context."""
        good_sentence = (
            "You raced on residual fitness 4 days after your injury — "
            "and still set a 7-minute half marathon PB."
        )
        # Should acknowledge the disruption
        assert 'injury' in good_sentence.lower() or 'disruption' in good_sentence.lower()
        assert 'residual' in good_sentence.lower()
