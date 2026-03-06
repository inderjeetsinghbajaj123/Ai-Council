"""Redis-backed store for distributed circuit breaker pattern."""

import json
from datetime import datetime
from typing import Dict, List, Optional, ContextManager

try:
    import redis
except ImportError:
    redis = None

from .failure_handling import CircuitBreakerStore, CircuitBreakerState


class RedisCircuitBreakerStore(CircuitBreakerStore):
    """Redis-backed store for distributed circuit breaker state."""
    
    def __init__(self, redis_client: 'redis.Redis', key_prefix: str = "ai_council:cb:"):
        if redis is None:
            raise ImportError("redis package is required for RedisCircuitBreakerStore")
        self.redis = redis_client
        self.key_prefix = key_prefix
        
    def _key(self, name: str, field: str) -> str:
        return f"{self.key_prefix}{name}:{field}"
        
    def get_state(self, name: str) -> CircuitBreakerState:
        val = self.redis.get(self._key(name, "state"))
        if val:
            return CircuitBreakerState(val.decode('utf-8'))
        return CircuitBreakerState.CLOSED
        
    def set_state(self, name: str, state: CircuitBreakerState):
        self.redis.set(self._key(name, "state"), state.value)
        
    def get_failure_count(self, name: str) -> int:
        val = self.redis.get(self._key(name, "failures"))
        return int(val) if val else 0
        
    def increment_failure_count(self, name: str) -> int:
        return self.redis.incr(self._key(name, "failures"))
        
    def reset_failure_count(self, name: str):
        self.redis.set(self._key(name, "failures"), 0)
        
    def get_success_count(self, name: str) -> int:
        val = self.redis.get(self._key(name, "successes"))
        return int(val) if val else 0
        
    def increment_success_count(self, name: str) -> int:
        return self.redis.incr(self._key(name, "successes"))
        
    def reset_success_count(self, name: str):
        self.redis.set(self._key(name, "successes"), 0)
        
    def get_last_failure_time(self, name: str) -> Optional[datetime]:
        val = self.redis.get(self._key(name, "last_failure"))
        if val:
            return datetime.fromisoformat(val.decode('utf-8'))
        return None
        
    def set_last_failure_time(self, name: str, dt: datetime):
        self.redis.set(self._key(name, "last_failure"), dt.isoformat())
        
    def add_failure_time(self, name: str, dt: datetime):
        self.redis.rpush(self._key(name, "failure_times"), dt.isoformat())
        
    def clear_failure_times(self, name: str):
        self.redis.delete(self._key(name, "failure_times"))
        
    def clean_old_failure_times(self, name: str, cutoff_time: datetime) -> List[datetime]:
        key = self._key(name, "failure_times")
        times_str = self.redis.lrange(key, 0, -1)
        valid_times = []
        for t_bytes in times_str:
            t = datetime.fromisoformat(t_bytes.decode('utf-8'))
            if t > cutoff_time:
                valid_times.append(t)
        
        # Rewrite the list (under lock this is safe)
        if valid_times:
            pipe = self.redis.pipeline()
            pipe.delete(key)
            pipe.rpush(key, *[t.isoformat() for t in valid_times])
            pipe.execute()
        else:
            self.redis.delete(key)
            
        return valid_times

    def lock(self, name: str) -> ContextManager:
        return self.redis.lock(self._key(name, "lock"), timeout=10, blocking_timeout=5)
