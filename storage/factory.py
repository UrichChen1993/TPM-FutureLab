from config import load_settings
from storage.base import Repository
from storage.dynamodb_backend import DynamoDBRepository
from storage.memory_backend import InMemoryRepository


def get_repository() -> Repository:
    settings = load_settings()
    backend = settings.data_backend.strip().lower()
    if backend == "dynamodb":
        return DynamoDBRepository(table_name=settings.dynamodb_table, region=settings.aws_region)
    if backend == "memory":
        return InMemoryRepository()
    raise ValueError(
        f"Unsupported DATA_BACKEND={settings.data_backend!r}; expected 'memory' or 'dynamodb'"
    )
