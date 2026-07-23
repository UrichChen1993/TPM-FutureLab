from botocore.exceptions import ClientError

from scripts.create_dynamodb_table import ensure_table


class FakeWaiter:
    def __init__(self):
        self.calls = []

    def wait(self, **kwargs):
        self.calls.append(kwargs)


class FakeDynamoClient:
    def __init__(self, exists: bool):
        self.exists = exists
        self.created_with = None
        self.waiter = FakeWaiter()

    def describe_table(self, **kwargs):
        if self.exists:
            return {"Table": {"TableStatus": "ACTIVE"}}
        raise ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "missing"}},
            "DescribeTable",
        )

    def create_table(self, **kwargs):
        self.created_with = kwargs

    def get_waiter(self, name: str):
        assert name == "table_exists"
        return self.waiter


def test_ensure_table_is_idempotent_when_table_exists():
    client = FakeDynamoClient(exists=True)
    assert ensure_table(client, "homewellness-test") is False
    assert client.created_with is None
    assert client.waiter.calls == [{"TableName": "homewellness-test"}]


def test_ensure_table_creates_on_demand_encrypted_table():
    client = FakeDynamoClient(exists=False)
    assert ensure_table(client, "homewellness-test") is True
    assert client.created_with["BillingMode"] == "PAY_PER_REQUEST"
    assert client.created_with["SSESpecification"] == {"Enabled": True}
    assert client.created_with["KeySchema"] == [
        {"AttributeName": "PK", "KeyType": "HASH"},
        {"AttributeName": "SK", "KeyType": "RANGE"},
    ]
    assert client.waiter.calls == [{"TableName": "homewellness-test"}]
