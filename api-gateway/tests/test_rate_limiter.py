import pytest
from unittest.mock import MagicMock, AsyncMock


class TestRateLimiterCheckIp:

    @pytest.mark.asyncio
    async def test_under_limit_returns_allowed(self, fake_redis):
        from app.rate_limiter import RateLimiter
        fake_redis.set_pipeline_count(5)
        limiter = RateLimiter(fake_redis)
        allowed, remaining = await limiter.check_ip("127.0.0.1")
        assert allowed   is True
        assert remaining == 95

    @pytest.mark.asyncio
    async def test_at_limit_returns_allowed(self, fake_redis):
        from app.rate_limiter import RateLimiter
        fake_redis.set_pipeline_count(100)
        limiter = RateLimiter(fake_redis)
        allowed, _ = await limiter.check_ip("127.0.0.1")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_over_limit_returns_not_allowed(self, fake_redis):
        from app.rate_limiter import RateLimiter
        fake_redis.set_pipeline_count(101)
        limiter = RateLimiter(fake_redis)
        allowed, remaining = await limiter.check_ip("127.0.0.1")
        assert allowed   is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_uses_ip_prefixed_key(self, fake_redis):
        from app.rate_limiter import RateLimiter
        fake_redis.set_pipeline_count(1)
        limiter  = RateLimiter(fake_redis)
        await limiter.check_ip("10.0.0.1")
        pipe     = fake_redis._r.pipeline.return_value
        key_used = pipe.zadd.call_args[0][0]
        assert key_used == "rl:ip:10.0.0.1"

    @pytest.mark.asyncio
    async def test_remaining_clamped_to_zero(self, fake_redis):
        from app.rate_limiter import RateLimiter
        fake_redis.set_pipeline_count(999)
        limiter = RateLimiter(fake_redis)
        _, remaining = await limiter.check_ip("127.0.0.1")
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_pipeline_executed_on_every_call(self, fake_redis):
        from app.rate_limiter import RateLimiter
        fake_redis.set_pipeline_count(1)
        limiter = RateLimiter(fake_redis)
        await limiter.check_ip("127.0.0.1")
        fake_redis._r.pipeline.return_value.execute.assert_called_once()


class TestRateLimiterCheckVpa:

    @pytest.mark.asyncio
    async def test_under_vpa_limit_returns_allowed(self, fake_redis):
        from app.rate_limiter import RateLimiter
        fake_redis.set_pipeline_count(5)
        limiter = RateLimiter(fake_redis)
        allowed, remaining = await limiter.check_vpa("alice@sbi")
        assert allowed   is True
        assert remaining == 5

    @pytest.mark.asyncio
    async def test_over_vpa_limit_returns_not_allowed(self, fake_redis):
        from app.rate_limiter import RateLimiter
        fake_redis.set_pipeline_count(11)
        limiter = RateLimiter(fake_redis)
        allowed, remaining = await limiter.check_vpa("alice@sbi")
        assert allowed   is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_uses_vpa_prefixed_key(self, fake_redis):
        from app.rate_limiter import RateLimiter
        fake_redis.set_pipeline_count(1)
        limiter  = RateLimiter(fake_redis)
        await limiter.check_vpa("alice@sbi")
        pipe     = fake_redis._r.pipeline.return_value
        key_used = pipe.zadd.call_args[0][0]
        assert key_used == "rl:vpa:alice@sbi"

    @pytest.mark.asyncio
    async def test_remaining_clamped_to_zero(self, fake_redis):
        from app.rate_limiter import RateLimiter
        fake_redis.set_pipeline_count(999)
        limiter = RateLimiter(fake_redis)
        _, remaining = await limiter.check_vpa("alice@sbi")
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_at_vpa_limit_returns_allowed(self, fake_redis):
        from app.rate_limiter import RateLimiter
        fake_redis.set_pipeline_count(10)
        limiter = RateLimiter(fake_redis)
        allowed, _ = await limiter.check_vpa("alice@sbi")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_different_vpas_use_different_keys(self, fake_redis):
        from app.rate_limiter import RateLimiter
        fake_redis.set_pipeline_count(1)
        limiter = RateLimiter(fake_redis)

        await limiter.check_vpa("alice@sbi")
        key_alice = fake_redis._r.pipeline.return_value.zadd.call_args[0][0]

        await limiter.check_vpa("bob@hdfc")
        key_bob = fake_redis._r.pipeline.return_value.zadd.call_args[0][0]

        assert key_alice != key_bob