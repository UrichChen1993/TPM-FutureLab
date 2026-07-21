from datetime import datetime

import storage.dynamodb_backend as dynamodb_backend
from storage.dynamodb_backend import DynamoDBRepository


def repository_with(table):
    repository = object.__new__(DynamoDBRepository)
    repository._table = table
    return repository


def test_repository_fails_fast_by_loading_table(monkeypatch):
    class FakeTable:
        def __init__(self):
            self.loaded = False

        def load(self):
            self.loaded = True

    table = FakeTable()

    class FakeResource:
        def Table(self, table_name: str):
            assert table_name == "homewellness-test"
            return table

    monkeypatch.setattr(
        dynamodb_backend.boto3,
        "resource",
        lambda service, region_name: FakeResource(),
    )

    DynamoDBRepository("homewellness-test", "ap-northeast-1")
    assert table.loaded is True


class PaginatedNotificationTable:
    def __init__(self):
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return {
                "Items": [{
                    "SK": "NOTIFICATION#2026-07-17T19:00:00#n1",
                    "notification_id": "n1",
                    "reason": "dose_overdue",
                    "severity": "medium",
                    "message": "first",
                }],
                "LastEvaluatedKey": {"PK": "USER#user-001", "SK": "cursor"},
            }
        return {
            "Items": [{
                "SK": "NOTIFICATION#2026-07-17T20:00:00#n2",
                "notification_id": "n2",
                "reason": "dose_missed",
                "severity": "high",
                "message": "second",
            }]
        }


def test_notification_query_reads_all_pages_consistently():
    table = PaginatedNotificationTable()
    notifications = repository_with(table).list_notifications("user-001")

    assert [notification.notification_id for notification in notifications] == ["n1", "n2"]
    assert notifications[1].occurred_at == datetime(2026, 7, 17, 20, 0)
    assert table.calls[0]["ConsistentRead"] is True
    assert table.calls[1]["ExclusiveStartKey"] == {
        "PK": "USER#user-001",
        "SK": "cursor",
    }


class DoseTable:
    def __init__(self):
        self.call = None

    def get_item(self, **kwargs):
        self.call = kwargs
        return {}


def test_dose_get_uses_consistent_read():
    table = DoseTable()
    result = repository_with(table).get_dose_record(
        "user-001", "2026-07-17", "med-001", "DINNER"
    )

    assert result is None
    assert table.call["ConsistentRead"] is True
