import pytest
from unittest.mock import MagicMock, patch, call
from botocore.exceptions import ClientError


def _client_error(code: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": code}},
        "operation"
    )


class TestInsertIfAbsent:

    def test_new_record_returns_true(self, dynamo_table):
        dynamo_table.put_item.return_value = {}
        from app import store
        record = {"idempotencyKey": "idem-001", "status": "PROCESSING"}
        result = store.insert_if_absent(record)
        assert result is True
        dynamo_table.put_item.assert_called_once()

    def test_duplicate_record_returns_false(self, dynamo_table):
        dynamo_table.put_item.side_effect = _client_error(
            "ConditionalCheckFailedException"
        )
        from app import store
        record = {"idempotencyKey": "idem-001", "status": "PROCESSING"}
        result = store.insert_if_absent(record)
        assert result is False

    def test_unexpected_error_raises(self, dynamo_table):
        dynamo_table.put_item.side_effect = _client_error(
            "ProvisionedThroughputExceededException"
        )
        from app import store
        record = {"idempotencyKey": "idem-001", "status": "PROCESSING"}
        with pytest.raises(ClientError):
            store.insert_if_absent(record)

    def test_ttl_field_added_to_record(self, dynamo_table):
        dynamo_table.put_item.return_value = {}
        from app import store
        record = {"idempotencyKey": "idem-001", "status": "PROCESSING"}
        store.insert_if_absent(record)
        assert "expiresAt" in record

    def test_put_item_called_with_condition(self, dynamo_table):
        dynamo_table.put_item.return_value = {}
        from app import store
        record = {"idempotencyKey": "idem-001", "status": "PROCESSING"}
        store.insert_if_absent(record)
        call_kwargs = dynamo_table.put_item.call_args[1]
        assert "ConditionExpression" in call_kwargs


class TestFindByKey:

    def test_returns_item_when_found(self, dynamo_table):
        dynamo_table.get_item.return_value = {
            "Item": {"idempotencyKey": "idem-001", "status": "SUCCESS"}
        }
        from app import store
        result = store.find_by_key("idem-001")
        assert result["idempotencyKey"] == "idem-001"
        assert result["status"]         == "SUCCESS"

    def test_returns_none_when_not_found(self, dynamo_table):
        dynamo_table.get_item.return_value = {}
        from app import store
        result = store.find_by_key("idem-not-found")
        assert result is None

    def test_uses_consistent_read(self, dynamo_table):
        dynamo_table.get_item.return_value = {}
        from app import store
        store.find_by_key("idem-001")
        call_kwargs = dynamo_table.get_item.call_args[1]
        assert call_kwargs.get("ConsistentRead") is True


class TestComplete:

    def test_updates_status_and_payload(self, dynamo_table):
        dynamo_table.update_item.return_value = {}
        from app import store
        store.complete("idem-001", "SUCCESS", '{"txn_id":"txn-001"}')
        dynamo_table.update_item.assert_called_once()
        call_kwargs = dynamo_table.update_item.call_args[1]
        vals = call_kwargs["ExpressionAttributeValues"]
        assert vals[":status"]  == "SUCCESS"
        assert vals[":payload"] == '{"txn_id":"txn-001"}'

    def test_none_payload_stored_as_empty_string(self, dynamo_table):
        dynamo_table.update_item.return_value = {}
        from app import store
        store.complete("idem-001", "SUCCESS", None)
        call_kwargs = dynamo_table.update_item.call_args[1]
        assert call_kwargs["ExpressionAttributeValues"][":payload"] == ""

    def test_conditional_check_failed_does_not_raise(self, dynamo_table):
        """complete() on non-PROCESSING record must silently skip."""
        dynamo_table.update_item.side_effect = _client_error(
            "ConditionalCheckFailedException"
        )
        from app import store
        store.complete("idem-001", "SUCCESS", None)   # must not raise

    def test_unexpected_error_raises(self, dynamo_table):
        dynamo_table.update_item.side_effect = _client_error(
            "ProvisionedThroughputExceededException"
        )
        from app import store
        with pytest.raises(ClientError):
            store.complete("idem-001", "SUCCESS", None)

    def test_correct_key_used(self, dynamo_table):
        dynamo_table.update_item.return_value = {}
        from app import store
        store.complete("idem-abc", "FAILED", None)
        call_kwargs = dynamo_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"idempotencyKey": "idem-abc"}


class TestScanAll:

    def test_returns_all_items(self, dynamo_table):
        dynamo_table.scan.return_value = {
            "Items": [
                {"idempotencyKey": "idem-001"},
                {"idempotencyKey": "idem-002"},
            ]
        }
        from app import store
        result = store.scan_all()
        assert len(result) == 2

    def test_returns_empty_list_when_no_items(self, dynamo_table):
        dynamo_table.scan.return_value = {"Items": []}
        from app import store
        result = store.scan_all()
        assert result == []