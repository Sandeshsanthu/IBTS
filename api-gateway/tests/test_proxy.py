import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException
import httpx


def _mock_request(
    method: str = "POST",
    path: str = "/api/v1/payments/initiate",
    body: bytes = b'{"amount":100}',
    headers: dict = None,
    client_host: str = "127.0.0.1",
):
    req              = MagicMock()
    req.method       = method
    req.url.path     = path
    req.query_params = {}
    req.client       = MagicMock()
    req.client.host  = client_host
    req.body         = AsyncMock(return_value=body)
    req.headers      = {
        "content-type": "application/json",
        "x-request-id": "req-001",
        **(headers or {}),
    }
    req.state        = MagicMock()
    req.state.request_id = "req-001"
    return req


def _mock_upstream_resp(status: int = 200, body: bytes = b'{"status":"SUCCESS"}'):
    resp             = MagicMock()
    resp.status_code = status
    resp.content     = body
    resp.headers     = {"content-type": "application/json"}
    return resp


class TestProxyRequest:

    @pytest.mark.asyncio
    async def test_success_returns_upstream_response(self):
        from app.proxy import proxy_request
        client = AsyncMock()
        client.request = AsyncMock(return_value=_mock_upstream_resp(200))

        resp = await proxy_request(client, _mock_request(), "/api/v1/payments/initiate")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_forwards_upstream_status_code(self):
        from app.proxy import proxy_request
        client = AsyncMock()
        client.request = AsyncMock(return_value=_mock_upstream_resp(404))

        resp = await proxy_request(client, _mock_request(), "/api/v1/payments/initiate")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_timeout_raises_504(self):
        from app.proxy import proxy_request
        client = AsyncMock()
        client.request = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with pytest.raises(HTTPException) as exc:
            await proxy_request(client, _mock_request(), "/api/v1/payments/initiate")

        assert exc.value.status_code == 504

    @pytest.mark.asyncio
    async def test_connect_error_raises_502(self):
        from app.proxy import proxy_request
        client = AsyncMock()
        client.request = AsyncMock(side_effect=httpx.ConnectError("unreachable"))

        with pytest.raises(HTTPException) as exc:
            await proxy_request(client, _mock_request(), "/api/v1/payments/initiate")

        assert exc.value.status_code == 502

    @pytest.mark.asyncio
    async def test_hop_by_hop_headers_stripped_from_request(self):
        from app.proxy import proxy_request
        client = AsyncMock()
        client.request = AsyncMock(return_value=_mock_upstream_resp(200))

        req = _mock_request(headers={
            "connection":        "keep-alive",
            "transfer-encoding": "chunked",
            "content-type":      "application/json",
        })
        await proxy_request(client, req, "/api/v1/payments/initiate")

        call_kwargs = client.request.call_args[1]
        forwarded   = call_kwargs["headers"]
        assert "connection"        not in forwarded
        assert "transfer-encoding" not in forwarded
        assert "content-type"      in forwarded

    @pytest.mark.asyncio
    async def test_x_forwarded_for_header_added(self):
        from app.proxy import proxy_request
        client = AsyncMock()
        client.request = AsyncMock(return_value=_mock_upstream_resp(200))

        await proxy_request(client, _mock_request(client_host="10.0.0.1"),
                            "/api/v1/payments/initiate")

        call_kwargs = client.request.call_args[1]
        assert call_kwargs["headers"]["X-Forwarded-For"] == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_hop_by_hop_stripped_from_response(self):
        from app.proxy import proxy_request
        client  = AsyncMock()
        up_resp = MagicMock()
        up_resp.status_code = 200
        up_resp.content     = b"{}"
        up_resp.headers     = {
            "content-type": "application/json",
            "connection":   "keep-alive",   # must be stripped
        }
        client.request = AsyncMock(return_value=up_resp)

        resp = await proxy_request(client, _mock_request(), "/api/v1/payments/initiate")

        assert "connection" not in dict(resp.headers)

    @pytest.mark.asyncio
    async def test_upstream_body_forwarded(self):
        from app.proxy import proxy_request
        client = AsyncMock()
        client.request = AsyncMock(return_value=_mock_upstream_resp(200))

        body = b'{"payer_vpa":"alice@sbi","amount_paise":10000}'
        await proxy_request(client, _mock_request(body=body), "/api/v1/payments/initiate")

        call_kwargs = client.request.call_args[1]
        assert call_kwargs["content"] == body


class TestForwardHeaders:

    def test_strips_host_header(self):
        from app.proxy import _forward_headers
        req = MagicMock()
        req.headers = {"host": "api-gateway:8084", "content-type": "application/json"}
        result = _forward_headers(req)
        assert "host"         not in result
        assert "content-type" in result

    def test_preserves_custom_headers(self):
        from app.proxy import _forward_headers
        req = MagicMock()
        req.headers = {
            "x-idempotency-key": "idem-001",
            "x-caller-service":  "payment-switch",
            "authorization":     "Bearer token",
        }
        result = _forward_headers(req)
        assert result["x-idempotency-key"] == "idem-001"
        assert result["authorization"]     == "Bearer token"