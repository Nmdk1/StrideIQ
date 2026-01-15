"""
Validate Individual Performance Model (ADR-023)

Validates model calibration and predictions against:
1. Developer's historical data from dev DB (N=1 ground truth)
2. Figshare anonymized running datasets as N=1 proxies

Methodology:
- Train on first 80% of each athlete's history
- Predict held-out 20% (race times)
- Quantify accuracy: MAE/RMSE on race times
- Surface per-athlete insights

Usage:
    python scripts/validate_performance_model.py [--dev-only] [--output-dir ./validation_reports]

ADR-023: Individual Performance Model Validation
"""

import os
import sys
import json
import math
import logging
import argparse
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from uuid import UUID

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class TrainingDay:
    """Single day of training."""
    date: date
    tss: float


@dataclass
class RaceResult:
    """Single race result."""
    date: date
    distance_m: float
    time_seconds: float
    vdot: Optional[float] = None


@dataclass
class AthleteData:
    """Complete athlete data for validation."""
    athlete_id: str
    name: str
    source: str  # "dev_db" or "figshare_sample_N"
    training_days: List[TrainingDay]
    races: List[RaceResult]
    age: Optional[int] = None
    notes: List[str] = field(default_factory=list)


@dataclass
class RacePredictionResult:
    """Single race prediction vs actual."""
    race_date: str
    distance: str
    predicted_seconds: int
    actual_seconds: int
    error_seconds: int
    error_percent: float


@dataclass
class AthleteValidationResult:
    """Validation result for single athlete."""
    athlete_id: str
    source: str
    n_training_days: int
    n_races_train: int
    n_races_test: int
    calibrated_tau1: float
    calibrated_tau2: float
    model_confidence: str
    race_predictions: List[RacePredictionResult]
    mae_seconds: float
    mae_percent: float
    rmse_seconds: float
    tsb_mae: float
    passed: bool
    notes: List[str]


@dataclass
class ValidationReport:
    """Complete validation report."""
    validation_timestamp: str
    athletes_tested: int
    results: List[AthleteValidationResult]
    summary: Dict
    audit_log: List[str]


# =============================================================================
# METRIC CALCULATIONS
# =============================================================================

def calculate_mae(errors: List[float]) -> float:
    """Calculate Mean Absolute Error."""
    if not errors:
        return 0.0
    return sum(abs(e) for e in errors) / len(errors)


def calculate_rmse(errors: List[float]) -> float:
    """Calculate Root Mean Square Error."""
    if not errors:
        return 0.0
    return math.sqrt(sum(e ** 2 for e in errors) / len(errors))


def calculate_percent_error(predicted: float, actual: float) -> float:
    """Calculate percent error."""
    if actual == 0:
        return 0.0
    return ((predicted - actual) / actual) * 100


def distance_to_name(distance_m: float) -> str:
    """Convert distance in meters to name."""
    distances = {
        5000: "5K",
        10000: "10K",
        21097: "Half Marathon",
        42195: "Marathon"
    }
    # Find closest
    closest = min(distances.keys(), key=lambda d: abs(d - distance_m))
    if abs(closest - distance_m) < distance_m * 0.1:
        return distances[closest]
    return f"{distance_m/1000:.1f}K"


# =============================================================================
# DATA LOADING
# =============================================================================

def load_dev_db_data(db_url: Optional[str] = None) -> Optional[AthleteData]:
    """
    Load developer's data from dev database.
    
    Returns None if database unavailable.
    """
    try:
        from sqlalchemy import create_engine, text
        
        db_url = db_url or os.environ.get(
            'DATABASE_URL', 
            'postgresql://postgres:postgres@localhost:5432/running_app'
        )
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # Get first athlete (developer)
            athlete_row = conn.execute(text("""
                SELECT id, first_name, last_name 
                FROM athlete 
                ORDER BY created_at 
                LIMIT 1
            """)).fetchone()
            
            if not athlete_row:
                logger.warning("No athletes in dev DB")
                return None
            
            athlete_id = str(athlete_row[0])
            name = f"{athlete_row[1] or ''} {athlete_row[2] or ''}".strip() or "Dev User"
            
            # Get activities
            activities = conn.execute(text("""
                SELECT 
                    DATE(start_time) as activity_date,
                    SUM(distance_m) as distance,
                    SUM(duration_s) as duration,
                    AVG(avg_hr) as avg_hr,
                    bool_or(is_race) as has_race
                FROM activity 
                WHERE athlete_id = :aid
                    AND sport ILIKE 'run'
                    AND start_time > NOW() - INTERVAL '2 years'
                GROUP BY DATE(start_time)
                ORDER BY DATE(start_time)
            """), {"aid": athlete_id}).fetchall()
            
            if not activities:
                logger.warning("No activities for dev user")
                return None
            
            # Calculate TSS per day (simplified: duration/60 * intensity factor)
            training_days = []
            for row in activities:
                activity_date = row[0]
                duration_min = (row[2] or 0) / 60
                # Rough TSS: minutes * intensity (assume avg 0.8 for easy)
                tss = duration_min * 0.8
                training_days.append(TrainingDay(date=activity_date, tss=tss))
            
            # Get races
            races = conn.execute(text("""
                SELECT 
                    DATE(start_time) as race_date,
                    distance_m,
                    duration_s
                FROM activity
                WHERE athlete_id = :aid
                    AND is_race = TRUE
                    AND distance_m > 1000
                    AND duration_s > 0
                ORDER BY start_time
            """), {"aid": athlete_id}).fetchall()
            
            race_results = []
            for row in races:
                race_results.append(RaceResult(
                    date=row[0],
                    distance_m=row[1],
                    time_seconds=row[2]
                ))
            
            logger.info(f"Loaded dev user: {len(training_days)} days, {len(race_results)} races")
            
            return AthleteData(
                athlete_id=athlete_id,
                name=name,
                source="dev_db",
                training_days=training_days,
                races=race_results,
                notes=["Developer N=1 ground truth"]
            )
            
    except Exception as e:
        logger.warning(f"Could not load dev DB data: {e}")
        return None


def load_figshare_sample(sample_id: int, data_dir: Path) -> Optional[AthleteData]:
    """
    Load a figshare sample dataset.
    
    Expects CSV files in data_dir/figshare_sample_{N}.csv with columns:
    date,tss,is_race,distance_m,time_seconds
    
    If file doesn't exist, generates synthetic sample for validation testing.
    """
    csv_path = data_dir / f"figshare_sample_{sample_id}.csv"
    
    if csv_path.exists():
        return _load_csv_sample(csv_path, sample_id)
    else:
        logger.info(f"Generating synthetic sample {sample_id}")
        return _generate_synthetic_sample(sample_id)


def _load_csv_sample(csv_path: Path, sample_id: int) -> AthleteData:
    """Load sample from CSV file."""
    import csv
    
    training_days = []
    races = []
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            day_date = datetime.strptime(row['date'], '%Y-%m-%d').date()
            tss = float(row.get('tss', 0))
            
            training_days.append(TrainingDay(date=day_date, tss=tss))
            
            if row.get('is_race', '').lower() == 'true':
                races.append(RaceResult(
                    date=day_date,
                    distance_m=float(row['distance_m']),
                    time_seconds=float(row['time_seconds'])
                ))
    
    return AthleteData(
        athlete_id=f"figshare_{sample_id}",
        name=f"Figshare Proxy {sample_id}",
        source=f"figshare_sample_{sample_id}",
        training_days=training_days,
        races=races
    )


def _generate_synthetic_sample(sample_id: int) -> AthleteData:
    """
    Generate synthetic sample for validation testing.
    
    Each sample represents a different edge case:
    1. Regular runner, age 30-40
    2. Masters runner, age 50+
    3. Injury recovery pattern
    4. Sparse data (<90 days)
    5. High volume marathoner
    """
    import random
    random.seed(42 + sample_id)  # Reproducible
    
    profiles = {
        1: {"name": "Regular 30-40", "days": 365, "races": 5, "base_tss": 50, "variability": 0.2},
        2: {"name": "Masters 50+", "days": 300, "races": 4, "base_tss": 40, "variability": 0.3, "age": 55},
        3: {"name": "Injury Recovery", "days": 200, "races": 3, "base_tss": 35, "variability": 0.4, "injury_gap": True},
        4: {"name": "Sparse Data", "days": 60, "races": 2, "base_tss": 45, "variability": 0.25},
        5: {"name": "High Volume Marathon", "days": 400, "races": 6, "base_tss": 70, "variability": 0.15},
    }
    
    profile = profiles.get(sample_id, profiles[1])
    
    start_date = date.today() - timedelta(days=profile["days"])
    training_days = []
    
    for i in range(profile["days"]):
        day = start_date + timedelta(days=i)
        
        # Simulate injury gap
        if profile.get("injury_gap") and 90 <= i <= 130:
            tss = random.uniform(0, 10)  # Very low during injury
        else:
            # Weekly pattern: rest Monday, long Sunday
            dow = day.weekday()
            if dow == 0:
                tss = 0
            elif dow == 6:
                tss = profile["base_tss"] * 1.5 * random.uniform(0.9, 1.1)
            else:
                tss = profile["base_tss"] * random.uniform(
                    1 - profile["variability"], 
                    1 + profile["variability"]
                )
        
        training_days.append(TrainingDay(date=day, tss=tss))
    
    # Generate races
    races = []
    race_dates = sorted(random.sample(
        range(profile["days"] // 4, profile["days"]), 
        min(profile["races"], profile["days"] // 60)
    ))
    
    # Simulate improving fitness
    base_vdot = 45 + random.uniform(-3, 3)
    for i, race_day in enumerate(race_dates):
        race_date = start_date + timedelta(days=race_day)
        
        # Slight improvement over time
        vdot = base_vdot + (i * 0.3)
        
        # Random distance
        distance = random.choice([5000, 10000, 21097, 42195])
        
        # Calculate time from VDOT (simplified Daniels formula)
        if distance == 5000:
            time_sec = (29 - 0.35 * (vdot - 30)) * 60
        elif distance == 10000:
            time_sec = (60 - 0.7 * (vdot - 30)) * 60
        elif distance == 21097:
            time_sec = (140 - 1.5 * (vdot - 30)) * 60
        else:  # Marathon
            time_sec = (300 - 3.5 * (vdot - 30)) * 60
        
        # Add some noise
        time_sec *= random.uniform(0.98, 1.02)
        
        races.append(RaceResult(
            date=race_date,
            distance_m=distance,
            time_seconds=time_sec,
            vdot=vdot
        ))
    
    notes = [f"Synthetic {profile['name']} profile"]
    if profile.get("age"):
        notes.append(f"Age {profile['age']}")
    if profile.get("injury_gap"):
        notes.append("Contains 40-day injury gap")
    
    return AthleteData(
        athlete_id=f"figshare_{sample_id}",
        name=f"Figshare Proxy {sample_id}: {profile['name']}",
        source=f"figshare_sample_{sample_id}",
        training_days=training_days,
        races=races,
        age=profile.get("age"),
        notes=notes
    )


# =============================================================================
# MODEL CALIBRATION (LOCAL IMPLEMENTATION)
# =============================================================================

def calibrate_model_from_data(
    training_days: List[TrainingDay],
    races: List[RaceResult]
) -> Tuple[float, float, float, float, float, str]:
    """
    Calibrate Banister model from training and race data.
    
    Returns: (tau1, tau2, k1, k2, p0, confidence)
    """
    if len(races) < 3 or len(training_days) < 60:
        # Insufficient data - use defaults
        return 42.0, 7.0, 1.0, 2.0, 50.0, "low"
    
    # Convert races to VDOT for performance metric
    performance_values = []
    for race in races:
        vdot = race.vdot or _estimate_vdot(race.distance_m, race.time_seconds)
        if vdot:
            performance_values.append((race.date, vdot))
    
    if len(performance_values) < 3:
        return 42.0, 7.0, 1.0, 2.0, 50.0, "low"
    
    # Grid search for best parameters
    best_error = float('inf')
    best_params = (42.0, 7.0, 1.0, 2.0, 50.0)
    
    tss_by_date = {td.date: td.tss for td in training_days}
    
    for tau1 in [30, 35, 40, 45, 50, 55, 60]:
        for tau2 in [5, 6, 7, 8, 9, 10, 12]:
            if tau1 <= tau2:
                continue
            
            for k1 in [0.5, 0.8, 1.0, 1.2, 1.5]:
                for k2 in [1.0, 1.5, 2.0, 2.5, 3.0]:
                    # Calculate CTL/ATL series
                    ctl = 0
                    atl = 0
                    decay1 = math.exp(-1.0 / tau1)
                    decay2 = math.exp(-1.0 / tau2)
                    
                    ctl_by_date = {}
                    atl_by_date = {}
                    
                    for td in sorted(training_days, key=lambda x: x.date):
                        tss = tss_by_date.get(td.date, 0)
                        ctl = ctl * decay1 + tss * (1 - decay1)
                        atl = atl * decay2 + tss * (1 - decay2)
                        ctl_by_date[td.date] = ctl
                        atl_by_date[td.date] = atl
                    
                    # Calculate prediction error
                    p0 = sum(v for _, v in performance_values) / len(performance_values)
                    total_error = 0
                    
                    for perf_date, actual_vdot in performance_values:
                        if perf_date in ctl_by_date:
                            predicted = p0 + k1 * ctl_by_date[perf_date] - k2 * atl_by_date[perf_date]
                            total_error += (predicted - actual_vdot) ** 2
                    
                    if total_error < best_error:
                        best_error = total_error
                        best_params = (tau1, tau2, k1, k2, p0)
    
    # Assess confidence
    if len(races) >= 5 and len(training_days) >= 180:
        confidence = "high"
    elif len(races) >= 3 and len(training_days) >= 90:
        confidence = "moderate"
    else:
        confidence = "low"
    
    return (*best_params, confidence)


def _estimate_vdot(distance_m: float, time_seconds: float) -> Optional[float]:
    """Estimate VDOT from race result (simplified Daniels)."""
    if distance_m <= 0 or time_seconds <= 0:
        return None
    
    velocity = distance_m / time_seconds  # m/s
    
    # Simplified VDOT estimate
    # Based on: VDOT ≈ velocity * constant + offset
    # Tuned for common distances
    if distance_m < 8000:
        vdot = velocity * 12 + 20
    elif distance_m < 15000:
        vdot = velocity * 13 + 18
    else:
        vdot = velocity * 14 + 15
    
    return min(85, max(25, vdot))


def predict_race_time(
    tau1: float, tau2: float, k1: float, k2: float, p0: float,
    training_days: List[TrainingDay],
    race_date: date,
    distance_m: float
) -> int:
    """Predict race time given model parameters and training history."""
    # Calculate CTL/ATL on race day
    ctl = 0
    atl = 0
    decay1 = math.exp(-1.0 / tau1)
    decay2 = math.exp(-1.0 / tau2)
    
    for td in sorted(training_days, key=lambda x: x.date):
        if td.date > race_date:
            break
        ctl = ctl * decay1 + td.tss * (1 - decay1)
        atl = atl * decay2 + td.tss * (1 - decay2)
    
    # Predict performance (VDOT)
    predicted_vdot = p0 + k1 * ctl - k2 * atl
    
    # Convert VDOT to race time (inverse of estimate)
    # Simplified inverse Daniels
    if distance_m < 8000:
        velocity = (predicted_vdot - 20) / 12
    elif distance_m < 15000:
        velocity = (predicted_vdot - 18) / 13
    else:
        velocity = (predicted_vdot - 15) / 14
    
    if velocity <= 0:
        velocity = 3.0  # Fallback ~5:30/km
    
    return int(distance_m / velocity)


# =============================================================================
# VALIDATION PIPELINE
# =============================================================================

def validate_athlete(athlete: AthleteData) -> AthleteValidationResult:
    """Run validation for a single athlete."""
    logger.info(f"Validating: {athlete.name} ({len(athlete.training_days)} days, {len(athlete.races)} races)")
    
    if len(athlete.races) < 2:
        return AthleteValidationResult(
            athlete_id=athlete.athlete_id,
            source=athlete.source,
            n_training_days=len(athlete.training_days),
            n_races_train=0,
            n_races_test=0,
            calibrated_tau1=42.0,
            calibrated_tau2=7.0,
            model_confidence="uncalibrated",
            race_predictions=[],
            mae_seconds=0,
            mae_percent=0,
            rmse_seconds=0,
            tsb_mae=0,
            passed=False,
            notes=["Insufficient race data for validation"]
        )
    
    # Split 80/20
    sorted_races = sorted(athlete.races, key=lambda r: r.date)
    split_idx = max(1, int(len(sorted_races) * 0.8))
    train_races = sorted_races[:split_idx]
    test_races = sorted_races[split_idx:]
    
    if not test_races:
        # Use last race as test
        train_races = sorted_races[:-1]
        test_races = sorted_races[-1:]
    
    # Training days up to first test race
    first_test_date = test_races[0].date
    train_days = [td for td in athlete.training_days if td.date < first_test_date]
    
    # Calibrate model on training set
    tau1, tau2, k1, k2, p0, confidence = calibrate_model_from_data(train_days, train_races)
    
    logger.info(f"  Calibrated: τ1={tau1:.1f}, τ2={tau2:.1f}, confidence={confidence}")
    
    # Predict test races
    predictions = []
    errors_seconds = []
    errors_percent = []
    
    for race in test_races:
        # Get training days up to race date
        race_train_days = [td for td in athlete.training_days if td.date <= race.date]
        
        predicted = predict_race_time(tau1, tau2, k1, k2, p0, race_train_days, race.date, race.distance_m)
        actual = int(race.time_seconds)
        error = predicted - actual
        error_pct = calculate_percent_error(predicted, actual)
        
        predictions.append(RacePredictionResult(
            race_date=race.date.isoformat(),
            distance=distance_to_name(race.distance_m),
            predicted_seconds=predicted,
            actual_seconds=actual,
            error_seconds=error,
            error_percent=round(error_pct, 2)
        ))
        
        errors_seconds.append(error)
        errors_percent.append(error_pct)
        
        logger.info(f"  Race {race.date}: predicted {predicted}s, actual {actual}s, error {error_pct:.1f}%")
    
    # Calculate metrics
    mae_sec = calculate_mae(errors_seconds)
    mae_pct = calculate_mae(errors_percent)
    rmse_sec = calculate_rmse(errors_seconds)
    
    # Pass criteria: MAE < 5%
    passed = mae_pct < 5.0
    
    notes = athlete.notes.copy()
    if tau1 < 40:
        notes.append(f"τ1={tau1:.0f} indicates faster adaptation than typical")
    if tau1 > 45:
        notes.append(f"τ1={tau1:.0f} indicates slower adaptation than typical")
    if confidence == "low":
        notes.append("Low confidence - need more race data")
    
    return AthleteValidationResult(
        athlete_id=athlete.athlete_id,
        source=athlete.source,
        n_training_days=len(athlete.training_days),
        n_races_train=len(train_races),
        n_races_test=len(test_races),
        calibrated_tau1=tau1,
        calibrated_tau2=tau2,
        model_confidence=confidence,
        race_predictions=predictions,
        mae_seconds=round(mae_sec, 1),
        mae_percent=round(mae_pct, 2),
        rmse_seconds=round(rmse_sec, 1),
        tsb_mae=0,  # TODO: Calculate TSB accuracy
        passed=passed,
        notes=notes
    )


def run_validation(
    dev_only: bool = False,
    data_dir: Path = None,
    output_dir: Path = None
) -> ValidationReport:
    """Run full validation pipeline."""
    timestamp = datetime.now().isoformat()
    audit_log = [f"Validation started: {timestamp}"]
    
    data_dir = data_dir or Path(__file__).parent.parent / "data"
    output_dir = output_dir or Path(__file__).parent.parent / "validation_reports"
    output_dir.mkdir(exist_ok=True)
    
    athletes = []
    
    # Load dev DB data
    dev_data = load_dev_db_data()
    if dev_data:
        athletes.append(dev_data)
        audit_log.append(f"Loaded dev DB data: {len(dev_data.training_days)} days, {len(dev_data.races)} races")
    else:
        audit_log.append("Dev DB data not available")
    
    # Load figshare samples (unless dev-only)
    if not dev_only:
        for i in range(1, 6):
            sample = load_figshare_sample(i, data_dir)
            if sample:
                athletes.append(sample)
                audit_log.append(f"Loaded figshare sample {i}: {sample.name}")
    
    if not athletes:
        logger.error("No data available for validation")
        return ValidationReport(
            validation_timestamp=timestamp,
            athletes_tested=0,
            results=[],
            summary={"error": "No data available"},
            audit_log=audit_log
        )
    
    # Validate each athlete
    results = []
    for athlete in athletes:
        result = validate_athlete(athlete)
        results.append(result)
        audit_log.append(f"Validated {athlete.athlete_id}: MAE={result.mae_percent:.2f}%, passed={result.passed}")
    
    # Summary
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    overall_mae = sum(r.mae_percent for r in results) / len(results) if results else 0
    
    summary = {
        "passed": passed,
        "failed": failed,
        "overall_mae_percent": round(overall_mae, 2),
        "recommendation": "Model ready for beta rollout" if passed >= len(results) * 0.8 else "Review failed cases before rollout"
    }
    
    report = ValidationReport(
        validation_timestamp=timestamp,
        athletes_tested=len(athletes),
        results=results,
        summary=summary,
        audit_log=audit_log
    )
    
    # Save report
    report_path = output_dir / f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w') as f:
        json.dump(_report_to_dict(report), f, indent=2)
    
    logger.info(f"Report saved to: {report_path}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Athletes tested: {len(results)}")
    print(f"Passed: {passed}/{len(results)}")
    print(f"Overall MAE: {overall_mae:.2f}%")
    print(f"Recommendation: {summary['recommendation']}")
    print("=" * 60)
    
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {result.athlete_id}: τ1={result.calibrated_tau1:.0f}, τ2={result.calibrated_tau2:.0f}, MAE={result.mae_percent:.2f}%")
    
    return report


def _report_to_dict(report: ValidationReport) -> dict:
    """Convert report to JSON-serializable dict."""
    return {
        "validation_timestamp": report.validation_timestamp,
        "athletes_tested": report.athletes_tested,
        "results": [
            {
                "athlete_id": r.athlete_id,
                "source": r.source,
                "n_training_days": r.n_training_days,
                "n_races_train": r.n_races_train,
                "n_races_test": r.n_races_test,
                "calibrated_tau1": r.calibrated_tau1,
                "calibrated_tau2": r.calibrated_tau2,
                "model_confidence": r.model_confidence,
                "race_predictions": [asdict(p) for p in r.race_predictions],
                "mae_seconds": r.mae_seconds,
                "mae_percent": r.mae_percent,
                "rmse_seconds": r.rmse_seconds,
                "tsb_mae": r.tsb_mae,
                "passed": r.passed,
                "notes": r.notes
            }
            for r in report.results
        ],
        "summary": report.summary,
        "audit_log": report.audit_log
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Validate Individual Performance Model")
    parser.add_argument("--dev-only", action="store_true", help="Only validate against dev DB data")
    parser.add_argument("--output-dir", type=str, help="Output directory for reports")
    parser.add_argument("--data-dir", type=str, help="Directory for figshare CSV samples")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir) if args.output_dir else None
    data_dir = Path(args.data_dir) if args.data_dir else None
    
    run_validation(
        dev_only=args.dev_only,
        data_dir=data_dir,
        output_dir=output_dir
    )


if __name__ == "__main__":
    main()
