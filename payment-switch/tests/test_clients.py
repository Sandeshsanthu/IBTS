import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch


class TestAdapterClient:

    @pytest.mark.asyncio
    async def test_send_payment_success(self):
        from app.clients.adapter import send_payment

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "transactionId": "txn-001",
            "status": "SUCCESS",
            "bankReferenceId": "SBI-RRN-001",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("app.clients.adapter.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_resp
            )
            result = await send_payment(
                txn_id="txn-001", bank_code="SBI",
                primary_endpoint="https://api.sbi.com",
                fallback_endpoint="https://fallback.sbi.com",
                amount_paise=10000,
                payer_vpa="alice@oksbi",
                payee_vpa="bob@okhdfcbank",
                remarks="test",
            )
        assert result["status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_send_payment_raises_on_http_error(self):
        from app.clients.adapter import send_payment

        mock_resp = MagicMock(); mock_resp.status_code = 503
        with patch("app.clients.adapter.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "503", request=MagicMock(), response=mock_resp
                )
            )
            with pytest.raises(httpx.HTTPStatusError):
                await send_payment(
                    txn_id="txn-001", bank_code="SBI",
                    primary_endpoint="https://api.sbi.com",
                    fallback_endpoint="https://fallback.sbi.com",
                    amount_paise=10000,
                    payer_vpa="alice@oksbi",
                    payee_vpa="bob@okhdfcbank",
                    remarks=None,
                )

    @pytest.mark.asyncio
    async def test_amount_converted_from_paise_to_rupees(self):
        from app.clients.adapter import send_payment

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "SUCCESS"}
        mock_resp.raise_for_status = MagicMock()

        captured_payload = {}

        async def capture_post(url, json):
            captured_payload.update(json)
            return mock_resp

        with patch("app.clients.adapter.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = capture_post
            await send_payment(
                txn_id="txn-001", bank_code="SBI",
                primary_endpoint="https://api.sbi.com",
                fallback_endpoint="https://fallback.sbi.com",
                amount_paise=10000,   # 10000 paise = ₹100.00
                payer_vpa="alice@oksbi",
                payee_vpa="bob@okhdfcbank",
                remarks=None,
            )
        assert captured_payload["amount"] == 100.0


class TestIdempotencyClient:

    @pytest.mark.asyncio
    async def test_check_new_returns_response(self):
        from app.clients.idempotency import check

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"duplicate": False, "status": "NEW"}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.clients.idempotency.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_resp
            )
            result = await check("idem-key-001")
        assert result["duplicate"] is False

    @pytest.mark.asyncio
    async def test_check_409_returns_without_raising(self):
        from app.clients.idempotency import check

        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_resp.json.return_value = {
            "duplicate": True,
            "responsePayload": '{"txn_id":"txn-001","status":"SUCCESS"}'
        }

        with patch("app.clients.idempotency.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_resp
            )
            result = await check("idem-key-001")
        assert result["duplicate"] is True   # no exception raised

    @pytest.mark.asyncio
    async def test_complete_calls_correct_endpoint(self):
        from app.clients.idempotency import complete

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        captured = {}

        async def capture_post(url, json):
            captured["url"]  = url
            captured["json"] = json
            return mock_resp

        with patch("app.clients.idempotency.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = capture_post
            await complete("txn-001", "SUCCESS", '{"txn_id":"txn-001"}')

        assert "complete" in captured["url"]
        assert captured["json"]["transactionId"]  == "txn-001"
        assert captured["json"]["finalStatus"]    == "SUCCESS"


class TestRouterClient:

    @pytest.mark.asyncio
    async def test_resolve_vpa_returns_bank_info(self):
        from app.clients.router import resolve_vpa

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "bankCode":         "SBI",
            "primaryEndpoint":  "https://api.sbi.com",
            "fallbackEndpoint": "https://fallback.sbi.com",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("app.clients.router.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_resp
            )
            result = await resolve_vpa("bob@okhdfcbank")
        assert result["bankCode"] == "SBI"

    @pytest.mark.asyncio
    async def test_resolve_vpa_raises_on_404(self):
        from app.clients.router import resolve_vpa

        mock_resp = MagicMock(); mock_resp.status_code = 404
        with patch("app.clients.router.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "404", request=MagicMock(), response=mock_resp
                )
            )
            with pytest.raises(httpx.HTTPStatusError):
                await resolve_vpa("unknown@xyz")