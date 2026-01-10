"""
Lightweight Event System for Extensibility

Provides a simple event emitter pattern for hooks and extensibility.
Not a full plugin registry - just enough for clean extensibility.
"""
import logging
from typing import Callable, Dict, List, Any
from functools import wraps

logger = logging.getLogger(__name__)

# Event registry: event_name -> list of handlers
_event_handlers: Dict[str, List[Callable]] = {}


def subscribe(event_name: str, handler: Callable):
    """
    Subscribe a handler function to an event.
    
    Args:
        event_name: Name of the event (e.g., 'activity.created', 'nutrition.updated')
        handler: Function to call when event fires
    
    Example:
        @subscribe('activity.created')
        def on_activity_created(activity_id: str, athlete_id: str):
            # Do something
            pass
    """
    if event_name not in _event_handlers:
        _event_handlers[event_name] = []
    
    _event_handlers[event_name].append(handler)
    logger.debug(f"Subscribed handler to event: {event_name}")


def emit(event_name: str, **kwargs):
    """
    Emit an event, calling all subscribed handlers.
    
    Args:
        event_name: Name of the event
        **kwargs: Event data passed to handlers
    
    Example:
        emit('activity.created', activity_id=str(activity.id), athlete_id=str(athlete.id))
    """
    if event_name not in _event_handlers:
        return
    
    for handler in _event_handlers[event_name]:
        try:
            handler(**kwargs)
        except Exception as e:
            logger.error(f"Error in event handler for {event_name}: {e}", exc_info=True)


def event_hook(event_name: str):
    """
    Decorator to automatically emit an event after function execution.
    
    Args:
        event_name: Name of the event to emit
    
    Example:
        @event_hook('activity.created')
        def create_activity(...):
            # Function code
            return activity
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Extract common parameters from result or kwargs
            event_data = {}
            if hasattr(result, 'id'):
                event_data['id'] = str(result.id)
            if hasattr(result, 'athlete_id'):
                event_data['athlete_id'] = str(result.athlete_id)
            
            # Add any kwargs that might be relevant
            for key in ['athlete_id', 'activity_id', 'nutrition_id', 'body_comp_id']:
                if key in kwargs:
                    event_data[key] = str(kwargs[key])
            
            emit(event_name, **event_data)
            
            return result
        
        return wrapper
    return decorator


# Common event names
EVENT_ACTIVITY_CREATED = 'activity.created'
EVENT_ACTIVITY_UPDATED = 'activity.updated'
EVENT_NUTRITION_CREATED = 'nutrition.created'
EVENT_NUTRITION_UPDATED = 'nutrition.updated'
EVENT_BODY_COMP_CREATED = 'body_composition.created'
EVENT_BODY_COMP_UPDATED = 'body_composition.updated'
EVENT_ATHLETE_CREATED = 'athlete.created'
EVENT_ATHLETE_UPDATED = 'athlete.updated'


