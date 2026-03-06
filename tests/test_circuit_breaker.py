import pytest
from datetime import datetime, timedelta
import threading
import time

from ai_council.core.failure_handling import (
    CircuitBreaker, CircuitBreakerConfig, CircuitBreakerState, 
    CircuitBreakerOpenError, InMemoryCircuitBreakerStore
)

def test_circuit_breaker_success():
    store = InMemoryCircuitBreakerStore()
    cb = CircuitBreaker("test_success", CircuitBreakerConfig(failure_threshold=2), store=store)
    assert cb.state == CircuitBreakerState.CLOSED
    
    def success_func():
        return "ok"
        
    assert cb.call(success_func) == "ok"
    assert cb.state == CircuitBreakerState.CLOSED

def test_circuit_breaker_failure():
    store = InMemoryCircuitBreakerStore()
    cb = CircuitBreaker("test_fail", CircuitBreakerConfig(failure_threshold=2), store=store)
    
    def fail_func():
        raise ValueError("test error")
        
    with pytest.raises(ValueError):
        cb.call(fail_func)
        
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.store.get_failure_count("test_fail") == 1
    
    with pytest.raises(ValueError):
        cb.call(fail_func)
        
    assert cb.state == CircuitBreakerState.OPEN
    
    with pytest.raises(CircuitBreakerOpenError):
        cb.call(fail_func)

def test_circuit_breaker_recovery():
    store = InMemoryCircuitBreakerStore()
    config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1, success_threshold=1)
    cb = CircuitBreaker("test_recovery", config, store=store)
    
    def fail_func():
        raise ValueError("test error")
        
    with pytest.raises(ValueError):
        cb.call(fail_func)
        
    assert cb.state == CircuitBreakerState.OPEN
    
    # Wait for recovery timeout
    time.sleep(0.15)
    
    def success_func():
        return "ok"
        
    assert cb.call(success_func) == "ok"
    # Should move to closed if success_threshold is met
    assert cb.state == CircuitBreakerState.CLOSED

def test_distributed_circuit_breaker_simulation():
    store = InMemoryCircuitBreakerStore()
    config = CircuitBreakerConfig(failure_threshold=2)
    cb1 = CircuitBreaker("test", config, store=store)
    cb2 = CircuitBreaker("test", config, store=store)
    
    def fail_func():
        raise ValueError("error")
        
    with pytest.raises(ValueError):
        cb1.call(fail_func)
        
    assert cb1.state == CircuitBreakerState.CLOSED
    assert cb2.state == CircuitBreakerState.CLOSED
    
    with pytest.raises(ValueError):
        cb2.call(fail_func)
        
    # Circuit opens for both!
    assert cb1.state == CircuitBreakerState.OPEN
    assert cb2.state == CircuitBreakerState.OPEN
    
    with pytest.raises(CircuitBreakerOpenError):
        cb1.call(fail_func)

def test_circuit_breaker_store_import():
    try:
        from ai_council.core.redis_store import RedisCircuitBreakerStore
        assert True
    except Exception as e:
        pytest.fail(f"Could not import RedisCircuitBreakerStore: {e}")
