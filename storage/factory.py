from config import load_settings
from storage.base import Repository
from storage.dynamodb_backend import DynamoDBRepository
from storage.memory_backend import InMemoryRepository


def get_repository() -> Repository:
    settings = load_settings()
    if settings.data_backend == "dynamodb":
        return DynamoDBRepository(table_name=settings.dynamodb_table, region=settings.aws_region)
    return InMemoryRepository()
