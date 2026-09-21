import pytest
from unittest.mock import MagicMock, patch


class TestEmitSettlementEvent:

    def _mock_sqs(self, queue_url="https://sqs.test/queue"):
        mock_client = MagicMock()
        mock_client.get_queue_url.return_value = {"QueueUrl": queue_url}
        mock_client.send_message.return_value  = {"MessageId": "msg-001"}
        return mock_client

    def test_sends_message_with_correct_body(self):
        from app import sqs
        import json
        mock_sqs = self._mock_sqs()
        with patch("app.sqs._client", return_value=mock_sqs):
            sqs.emit_settlement_event("txn-001", "SBI", 50000)

        call_kwargs = mock_sqs.send_message.call_args[1]
        body = json.loads(call_kwargs["MessageBody"])
        assert body["txn_id"]       == "txn-001"
        assert body["bank_code"]    == "SBI"
        assert body["amount_paise"] == 50000
        assert body["event"]        == "PAYMENT_SUCCESS"

    def test_does_not_raise_on_sqs_failure(self):
        """Fire-and-forget: SQS failure must never block payment response."""
        from app import sqs
        mock_sqs = self._mock_sqs()
        mock_sqs.send_message.side_effect = Exception("SQS unavailable")
        with patch("app.sqs._client", return_value=mock_sqs):
            sqs.emit_settlement_event("txn-001", "SBI", 50000)   # must not raise

    def test_does_not_raise_when_queue_url_fails(self):
        from app import sqs
        mock_sqs = self._mock_sqs()
        mock_sqs.get_queue_url.side_effect = Exception("SQS down")
        with patch("app.sqs._client", return_value=mock_sqs):
            sqs.emit_settlement_event("txn-001", "SBI", 50000)   # must not raise

    def test_correct_queue_url_used(self):
        from app import sqs
        mock_sqs = self._mock_sqs("https://sqs.ap-south-1.amazonaws.com/ibts-settlement-events")
        with patch("app.sqs._client", return_value=mock_sqs):
            sqs.emit_settlement_event("txn-001", "SBI", 50000)
        mock_sqs.send_message.assert_called_once()
        assert mock_sqs.send_message.call_args[1]["QueueUrl"] == \
               "https://sqs.ap-south-1.amazonaws.com/ibts-settlement-events"