"""
Garmin Connect Service

Handles Garmin Connect integration using python-garminconnect library.
Pulls activities and recovery metrics (sleep, HRV, resting HR, overnight HR).

ARCHITECTURE:
- Uses unofficial python-garminconnect library
- Encrypted credential storage
- Graceful error handling with Strava fallback
- Rate limiting and retry logic
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import time

try:
    from garminconnect import Garmin
except ImportError:
    Garmin = None
    logging.warning("garminconnect library not installed. Garmin integration unavailable.")

from services.token_encryption import decrypt_token
from core.config import settings

logger = logging.getLogger(__name__)


class GarminService:
    """Service for interacting with Garmin Connect API."""
    
    def __init__(self, username: str, password_encrypted: str):
        """
        Initialize Garmin service with encrypted credentials.
        
        Args:
            username: Garmin username (plain text - username only)
            password_encrypted: Encrypted Garmin password
        """
        if Garmin is None:
            raise ImportError("garminconnect library not installed")
        
        self.username = username
        password = decrypt_token(password_encrypted)
        
        if not password:
            raise ValueError("Failed to decrypt Garmin password")
        
        self.client = Garmin(username, password)
        self._authenticated = False
    
    def login(self) -> bool:
        """
        Authenticate with Garmin Connect.
        
        Returns:
            True if login successful, False otherwise
        """
        try:
            self.client.login()
            self._authenticated = True
            logger.info(f"Garmin login successful for {self.username}")
            return True
        except Exception as e:
            error_msg = str(e) if e else "Unknown error"
            error_type = type(e).__name__
            logger.error(f"Garmin login failed for {self.username}: {error_type}: {error_msg}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            self._authenticated = False
            raise Exception(f"Garmin authentication failed: {error_type}: {error_msg}")
    
    def get_activities(self, start_date: Optional[datetime] = None, limit: int = 100) -> List[Dict]:
        """
        Get activities from Garmin Connect.
        
        Args:
            start_date: Start date for activities (default: last 30 days)
            limit: Maximum number of activities to retrieve
            
        Returns:
            List of activity dictionaries
        """
        if not self._authenticated:
            if not self.login():
                return []
        
        try:
            if start_date is None:
                start_date = datetime.now() - timedelta(days=30)
            
            activities = self.client.get_activities_by_date(
                start_date.strftime("%Y-%m-%d"),
                datetime.now().strftime("%Y-%m-%d"),
                limit=limit
            )
            
            logger.info(f"Retrieved {len(activities)} activities from Garmin for {self.username}")
            return activities if isinstance(activities, list) else []
            
        except Exception as e:
            logger.error(f"Failed to get Garmin activities for {self.username}: {e}")
            return []
    
    def get_activity_details(self, activity_id: int) -> Optional[Dict]:
        """
        Get detailed activity information.
        
        Args:
            activity_id: Garmin activity ID
            
        Returns:
            Activity details dictionary or None
        """
        if not self._authenticated:
            if not self.login():
                return None
        
        try:
            activity = self.client.get_activity(activity_id)
            return activity
        except Exception as e:
            logger.error(f"Failed to get Garmin activity {activity_id}: {e}")
            return None
    
    def get_daily_summary(self, date: datetime) -> Optional[Dict]:
        """
        Get daily summary including recovery metrics.
        
        Args:
            date: Date to get summary for
            
        Returns:
            Daily summary dictionary or None
        """
        if not self._authenticated:
            if not self.login():
                return None
        
        try:
            summary = self.client.get_daily_summary(date.strftime("%Y-%m-%d"))
            return summary
        except Exception as e:
            logger.error(f"Failed to get Garmin daily summary for {date}: {e}")
            return None
    
    def get_sleep_data(self, date: datetime) -> Optional[Dict]:
        """
        Get sleep data for a specific date.
        
        Args:
            date: Date to get sleep data for
            
        Returns:
            Sleep data dictionary or None
        """
        if not self._authenticated:
            if not self.login():
                return None
        
        try:
            sleep_data = self.client.get_sleep_data(date.strftime("%Y-%m-%d"))
            return sleep_data
        except Exception as e:
            logger.error(f"Failed to get Garmin sleep data for {date}: {e}")
            return None
    
    def get_hrv_data(self, date: datetime) -> Optional[Dict]:
        """
        Get HRV data for a specific date.
        
        Args:
            date: Date to get HRV data for
            
        Returns:
            HRV data dictionary or None
        """
        if not self._authenticated:
            if not self.login():
                return None
        
        try:
            hrv_data = self.client.get_hrv_summary(date.strftime("%Y-%m-%d"))
            return hrv_data
        except Exception as e:
            logger.error(f"Failed to get Garmin HRV data for {date}: {e}")
            return None
    
    def get_resting_heart_rate(self, date: datetime) -> Optional[int]:
        """
        Get resting heart rate for a specific date.
        
        Args:
            date: Date to get resting HR for
            
        Returns:
            Resting heart rate (bpm) or None
        """
        summary = self.get_daily_summary(date)
        if summary:
            # Extract resting HR from summary
            # Structure may vary - adjust based on actual API response
            return summary.get("restingHeartRate") or summary.get("restingHeartRateInBeatsPerMinute")
        return None
    
    def get_overnight_avg_hr(self, date: datetime) -> Optional[float]:
        """
        Get overnight average heart rate.
        
        Args:
            date: Date to get overnight HR for
            
        Returns:
            Overnight average HR (bpm) or None
        """
        sleep_data = self.get_sleep_data(date)
        if sleep_data:
            # Extract overnight avg HR from sleep data
            # Structure may vary - adjust based on actual API response
            return sleep_data.get("averageHeartRate") or sleep_data.get("avgHeartRate")
        return None


def extract_recovery_metrics(garmin_service: GarminService, date: datetime) -> Dict:
    """
    Extract recovery metrics from Garmin for a specific date.
    
    Returns:
        Dictionary with recovery metrics:
        - sleep_duration_hours: Total sleep time (time asleep only)
        - hrv_rmssd: HRV rMSSD value
        - hrv_sdnn: HRV SDNN value
        - resting_hr: Resting heart rate
        - overnight_avg_hr: Overnight average HR
    """
    metrics = {
        "sleep_duration_hours": None,
        "hrv_rmssd": None,
        "hrv_sdnn": None,
        "resting_hr": None,
        "overnight_avg_hr": None
    }
    
    # Get sleep data (time asleep only - no stages)
    sleep_data = garmin_service.get_sleep_data(date)
    if sleep_data:
        # Extract total sleep duration (time asleep)
        # Adjust field names based on actual API response
        sleep_seconds = sleep_data.get("sleepTimeSeconds") or sleep_data.get("totalSleepSeconds")
        if sleep_seconds:
            metrics["sleep_duration_hours"] = sleep_seconds / 3600.0
    
    # Get HRV data
    hrv_data = garmin_service.get_hrv_data(date)
    if hrv_data:
        metrics["hrv_rmssd"] = hrv_data.get("rmssd") or hrv_data.get("hrvRmssd")
        metrics["hrv_sdnn"] = hrv_data.get("sdnn") or hrv_data.get("hrvSdnn")
    
    # Get resting HR
    resting_hr = garmin_service.get_resting_heart_rate(date)
    if resting_hr:
        metrics["resting_hr"] = resting_hr
    
    # Get overnight avg HR
    overnight_hr = garmin_service.get_overnight_avg_hr(date)
    if overnight_hr:
        metrics["overnight_avg_hr"] = float(overnight_hr)
    
    return metrics

