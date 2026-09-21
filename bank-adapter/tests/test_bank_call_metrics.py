import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
import pybreaker


class TestCallBankPrimary:
    """Tests for call_bank() primary/fallback/breaker flows."""

    @pytest.mark.asyncio
    async def test_primary_success_returns_response(self, sample_request):
        from app.bank_call_metrics import call_bank

        breaker = MagicMock(spec=pybreaker.CircuitBreaker)
        breaker.call.return_value = None

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "SUCCESS", "ref": "SBI-001"}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.bank_call_metrics.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_resp
            )
            result = await call_bank(
                bank_code="SBI",
                primary_url=sample_request["primaryEndpoint"],
                fallback_url=sample_request["fallbackEndpoint"],
                payload=sample_request,
                breaker=breaker,
            )
        assert result["status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_raises(self, sample_request):
        from app.bank_call_metrics import call_bank

        breaker = MagicMock(spec=pybreaker.CircuitBreaker)
        breaker.call.side_effect = pybreaker.CircuitBreakerError()

        with pytest.raises(pybreaker.CircuitBreakerError):
            await call_bank(
                bank_code="SBI",
                primary_url=sample_request["primaryEndpoint"],
                fallback_url=sample_request["fallbackEndpoint"],
                payload=sample_request,
                breaker=breaker,
            )

    @pytest.mark.asyncio
    async def test_primary_fails_fallback_succeeds(self, sample_request):
        from app.bank_call_metrics import call_bank

        breaker = MagicMock(spec=pybreaker.CircuitBreaker)
        breaker.call.return_value = None
        call_count = 0

        async def mock_post(url, json):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.TimeoutException("primary timeout")
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"status": "SUCCESS", "ref": "FB-001"}
            resp.raise_for_status = MagicMock()
            return resp

        with patch("app.bank_call_metrics.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = mock_post
            result = await call_bank(
                bank_code="SBI",
                primary_url=sample_request["primaryEndpoint"],
                fallback_url=sample_request["fallbackEndpoint"],
                payload=sample_request,
                breaker=breaker,
            )
        assert result["status"] == "SUCCESS"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_both_fail_raises_exception(self, sample_request):
        from app.bank_call_metrics import call_bank

        breaker = MagicMock(spec=pybreaker.CircuitBreaker)
        breaker.call.return_value = None

        with patch("app.bank_call_metrics.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )
            with pytest.raises(Exception):
                await call_bank(
                    bank_code="SBI",
                    primary_url=sample_request["primaryEndpoint"],
                    fallback_url=sample_request["fallbackEndpoint"],
                    payload=sample_request,
                    breaker=breaker,
                )

    @pytest.mark.asyncio
    async def test_primary_http_error_uses_fallback(self, sample_request):
        from app.bank_call_metrics import call_bank

        breaker = MagicMock(spec=pybreaker.CircuitBreaker)
        breaker.call.return_value = None
        call_count = 0

        async def mock_post(url, json):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                r = MagicMock()
                r.status_code = 503
                raise httpx.HTTPStatusError("503", request=MagicMock(), response=r)
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"status": "SUCCESS", "ref": "FB-002"}
            resp.raise_for_status = MagicMock()
            return resp

        with patch("app.bank_call_metrics.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = mock_post
            result = await call_bank(
                bank_code="SBI",
                primary_url=sample_request["primaryEndpoint"],
                fallback_url=sample_request["fallbackEndpoint"],
                payload=sample_request,
                breaker=breaker,
            )
        assert result["status"] == "SUCCESS"
        assert call_count == 2


class TestCallEndpointMetrics:
    """Tests that correct metric labels are recorded per outcome."""

    @pytest.mark.asyncio
    async def test_timeout_increments_timeout_failure_metric(self):
        from app.bank_call_metrics import _call_endpoint
        import app.bank_call_metrics as bm

        # reset mock call history before test
        bm.BANK_FAILURES_TOTAL.reset_mock()

        with patch("app.bank_call_metrics.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("timed out")
            )
            with pytest.raises(httpx.TimeoutException):
                await _call_endpoint("SBI", "primary",
                                     "https://api.sbi.com", {}, 3.0)

        bm.BANK_FAILURES_TOTAL.labels.assert_any_call(
            bank_code="SBI", failure_type="timeout"
        )

    @pytest.mark.asyncio
    async def test_http_error_increments_http_error_metric(self):
        from app.bank_call_metrics import _call_endpoint
        import app.bank_call_metrics as bm

        bm.BANK_FAILURES_TOTAL.reset_mock()

        async def failing_post(url, json):
            r = MagicMock()
            r.status_code = 500
            r.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500", request=MagicMock(), response=r
            )
            return r

        with patch("app.bank_call_metrics.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = failing_post
            with pytest.raises(httpx.HTTPStatusError):
                await _call_endpoint("HDFC", "primary",
                                     "https://api.hdfc.com", {}, 3.0)

        bm.BANK_FAILURES_TOTAL.labels.assert_any_call(
            bank_code="HDFC", failure_type="http_error"
        )

    @pytest.mark.asyncio
    async def test_latency_always_recorded_on_success(self):
        from app.bank_call_metrics import _call_endpoint
        import app.bank_call_metrics as bm

        bm.BANK_REQUEST_LATENCY_SECONDS.reset_mock()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "SUCCESS"}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.bank_call_metrics.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_resp
            )
            await _call_endpoint("SBI", "primary",
                                 "https://api.sbi.com", {}, 3.0)

        bm.BANK_REQUEST_LATENCY_SECONDS.labels.assert_any_call(
            bank_code="SBI", endpoint_type="primary"
        )