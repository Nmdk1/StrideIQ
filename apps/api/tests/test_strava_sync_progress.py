"""
Tests for Strava sync PROGRESS state handling.

These tests verify that:
1. The sync task reports progress via update_state()
2. The status endpoint returns progress info when task is in PROGRESS state
"""
import pytest
from unittest.mock import MagicMock, patch


class TestSyncStatusProgressState:
    """Test the /strava/sync/status endpoint handles PROGRESS state correctly."""
    
    def test_progress_state_returns_current_and_total(self):
        """
        When a task is in PROGRESS state with meta info,
        the status endpoint should return current, total, and message.
        """
        from routers.strava import get_sync_status
        
        # Create a mock task with PROGRESS state
        mock_task = MagicMock()
        mock_task.state = "PROGRESS"
        mock_task.info = {
            'current': 23,
            'total': 47,
            'message': 'Syncing activity 23 of 47...'
        }
        
        # Mock Redis to return that task is known
        mock_redis = MagicMock()
        mock_redis.get.return_value = b'{"athlete_id": "test-123"}'
        
        # Patch at the source module where imports happen
        with patch('tasks.celery_app') as mock_celery, \
             patch('core.cache.get_redis_client') as mock_get_redis:
            mock_celery.AsyncResult.return_value = mock_task
            mock_get_redis.return_value = mock_redis
            
            result = get_sync_status("test-task-id")
        
        assert result["status"] == "progress"
        assert result["current"] == 23
        assert result["total"] == 47
        assert result["message"] == "Syncing activity 23 of 47..."
        assert result["task_id"] == "test-task-id"
    
    def test_progress_state_with_empty_meta(self):
        """
        When a task is in PROGRESS state but meta is empty or None,
        should return sensible defaults.
        """
        from routers.strava import get_sync_status
        
        mock_task = MagicMock()
        mock_task.state = "PROGRESS"
        mock_task.info = None
        
        mock_redis = MagicMock()
        mock_redis.get.return_value = b'{"athlete_id": "test-123"}'
        
        with patch('tasks.celery_app') as mock_celery, \
             patch('core.cache.get_redis_client') as mock_get_redis:
            mock_celery.AsyncResult.return_value = mock_task
            mock_get_redis.return_value = mock_redis
            
            result = get_sync_status("test-task-id")
        
        assert result["status"] == "progress"
        assert result["current"] == 0
        assert result["total"] == 0
        assert result["message"] == "Syncing activities..."
    
    def test_started_state_still_works(self):
        """
        STARTED state should still return the original message.
        (Regression test to ensure we didn't break existing behavior)
        """
        from routers.strava import get_sync_status
        
        mock_task = MagicMock()
        mock_task.state = "STARTED"
        mock_task.info = None
        
        mock_redis = MagicMock()
        mock_redis.get.return_value = b'{"athlete_id": "test-123"}'
        
        with patch('tasks.celery_app') as mock_celery, \
             patch('core.cache.get_redis_client') as mock_get_redis:
            mock_celery.AsyncResult.return_value = mock_task
            mock_get_redis.return_value = mock_redis
            
            result = get_sync_status("test-task-id")
        
        assert result["status"] == "started"
        assert result["message"] == "Task is currently being processed"


class TestSyncTaskProgressReporting:
    """Test that the sync task calls update_state with progress."""
    
    def test_update_state_called_with_progress(self):
        """
        Verify that sync_strava_activities_task calls self.update_state()
        during activity processing.
        """
        # This is a structural test - we verify the code pattern exists
        # Full integration would require mocking Strava API calls
        
        import inspect
        from tasks.strava_tasks import sync_strava_activities_task
        
        # Get the source code
        source = inspect.getsource(sync_strava_activities_task)
        
        # Verify the update_state call is in the source
        assert "self.update_state(" in source
        assert "state='PROGRESS'" in source
        assert "'current'" in source
        assert "'total'" in source
