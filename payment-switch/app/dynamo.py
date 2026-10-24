"""DynamoDB persistence helpers for payment-switch transaction records.

Settings supply LocalStack connection details for local development and leave
credentials to boto3's default chain (including IRSA) when running on EKS.
The local table uses ``txn_id`` as its partition key, while the AWS table uses
``transaction_id``.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr

from app.config import settings
from app.models import TxnRecord, TxnState


dynamodb = boto3.resource("dynamodb", **settings.aws_client_kwargs)
table: Any = dynamodb.Table(settings.dynamodb_table_name)


def _partition_key_name() -> str:
    """Return the partition key used by the active DynamoDB table schema."""
    return "transaction_id" if settings.aws_mode else "txn_id"


def _utc_iso_timestamp() -> str:
    """Return a timezone-aware UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _normalize_item(item: Mapping[str, Any]) -> dict[str, Any]:
    """Convert the AWS storage alias into the application's transaction key."""
    normalized = dict(item)
    if "transaction_id" in normalized:
        normalized["txn_id"] = normalized.pop("transaction_id")
    return normalized


def write_txn(record: TxnRecord) -> dict[str, Any]:
    """Timestamp and persist a transaction record, returning its stored form."""
    now = _utc_iso_timestamp()
    if not record.created_at:
        record.created_at = now
    record.updated_at = now

    aws_mode = settings.aws_mode
    item = record.model_dump(by_alias=aws_mode, mode="json")
    table.put_item(Item=item)
    return item


def get_txn(txn_id: str) -> dict[str, Any] | None:
    """Fetch one transaction by its application-facing transaction ID."""
    response = table.get_item(Key={_partition_key_name(): txn_id})
    item = response.get("Item")
    if item is None:
        return None
    return _normalize_item(item)


def _scan_first(attribute_name: str, value: str) -> dict[str, Any] | None:
    """Scan all result pages until the first matching transaction is found."""
    scan_kwargs: dict[str, Any] = {
        "FilterExpression": Attr(attribute_name).eq(value),
    }

    while True:
        response = table.scan(**scan_kwargs)
        items = response.get("Items", [])
        if items:
            return _normalize_item(items[0])

        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            return None
        scan_kwargs["ExclusiveStartKey"] = last_evaluated_key


def get_txn_by_idempotency_key(idempotency_key: str) -> dict[str, Any] | None:
    """Return the first transaction matching an idempotency key."""
    return _scan_first("idempotency_key", idempotency_key)


def get_txn_by_bank_rrn(bank_rrn: str) -> dict[str, Any] | None:
    """Return the first transaction matching a bank retrieval reference number."""
    return _scan_first("bank_rrn", bank_rrn)


def update_state(
    txn_id: str,
    state: TxnState,
    bank_rrn: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Update a transaction's state and optional bank response information."""
    update_parts = ["#state = :state", "updated_at = :updated_at"]
    expression_values: dict[str, Any] = {
        ":state": getattr(state, "value", state),
        ":updated_at": _utc_iso_timestamp(),
    }

    if bank_rrn is not None:
        update_parts.append("bank_rrn = :r")
        expression_values[":r"] = bank_rrn

    if error is not None:
        update_parts.append("error = :err")
        expression_values[":err"] = error

    return table.update_item(
        Key={_partition_key_name(): txn_id},
        UpdateExpression="SET " + ", ".join(update_parts),
        ExpressionAttributeNames={"#state": "state"},
        ExpressionAttributeValues=expression_values,
        ReturnValues="ALL_NEW",
    )

