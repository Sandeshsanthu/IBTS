# filename: bank-adapter/app/circuit_breaker/breaker_registry.py

import pybreaker

from app.config import settings


_breakers: dict[str, pybreaker.CircuitBreaker] = {}


def get_breaker(bank_code: str) -> pybreaker.CircuitBreaker:
    key = bank_code.upper()
    if key not in _breakers:
        _breakers[key] = pybreaker.CircuitBreaker(
            fail_max      = settings.breaker_fail_max,
            reset_timeout = settings.breaker_reset_timeout,
            name          = f"breaker-{key}",
        )
    return _breakers[key]


def reset_breaker(bank_code: str) -> bool:
    """Delete and recreate breaker - test teardown only."""
    key = bank_code.upper()
    if key in _breakers:
        del _breakers[key]
        get_breaker(key)
        return True
    return False


def all_breaker_states() -> dict:
    return {
        code: {
            "state":      b.current_state,
            "fail_count": b.fail_counter,
        }
        for code, b in _breakers.items()
    }