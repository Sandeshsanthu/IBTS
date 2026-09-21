import sys
from unittest.mock import MagicMock, AsyncMock
import pytest

# ── mock shared + otel BEFORE any app import ──────────────────────────────
def _m():
    m = MagicMock()
    m.labels.return_value = m
    return m

_registry = MagicMock()
for _attr in [
    "AUTH_FAILURES_TOTAL", "RATE_LIMIT_HITS_TOTAL",
    "RATE_LIMIT_REMAINING", "REDIS_OP_LATENCY_SECONDS", "REDIS_ERRORS_TOTAL",
]:
    setattr(_registry, _attr, _m())

sys.modules["shared"]                        = MagicMock()
sys.modules["shared.telemetry"]              = MagicMock()
sys.modules["shared.metrics"]                = MagicMock()
sys.modules["shared.metrics.registry"]       = _registry
sys.modules["shared.metrics.middleware"]     = MagicMock()
sys.modules["shared.metrics.redis_tracker"]  = MagicMock()
sys.modules["opentelemetry"]                 = MagicMock()
sys.modules["opentelemetry.instrumentation"] = MagicMock()
sys.modules["opentelemetry.instrumentation.fastapi"] = MagicMock()
sys.modules["opentelemetry.instrumentation.httpx"]   = MagicMock()


def _make_pipe(count: int = 1):
    """
    RateLimiter calls pipeline() synchronously then awaits pipe.execute().
    So pipeline() must return a plain MagicMock (not a coroutine),
    with only execute() as an AsyncMock.
    """
    pipe = MagicMock()                                         # sync mock
    pipe.zremrangebyscore = MagicMock()
    pipe.zadd             = MagicMock()
    pipe.zcard            = MagicMock()
    pipe.expire           = MagicMock()
    pipe.execute          = AsyncMock(return_value=[0, 1, count, True])  # async
    return pipe


class FakeTrackedRedis:
    """
    Minimal stub for TrackedRedis used by RateLimiter.
    _r must be a plain MagicMock so that _r.pipeline() returns
    the pipe mock synchronously — NOT a coroutine.
    """
    def __init__(self, count: int = 1):
        self._r = MagicMock()                        # ← MagicMock, NOT AsyncMock
        self._r.pipeline.return_value = _make_pipe(count)

    def set_pipeline_count(self, count: int):
        self._r.pipeline.return_value = _make_pipe(count)


@pytest.fixture
def fake_redis():
    return FakeTrackedRedis()


@pytest.fixture
def valid_jwt_token():
    import jwt
    from app.config import settings
    return jwt.encode(
        {"sub": "user-001", "name": "Test User"},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


@pytest.fixture
def expired_jwt_token():
    import jwt, time
    from app.config import settings
    return jwt.encode(
        {"sub": "user-001", "exp": int(time.time()) - 3600},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )