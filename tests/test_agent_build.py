import pytest

from agent.agent import build_agent_executor
from simulator.clock import SimClock
from storage.memory_backend import InMemoryRepository
from datetime import datetime


def test_build_agent_executor_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 18, 0))

    with pytest.raises(ValueError, match="LLM_API_KEY"):
        build_agent_executor(repo, clock, "user-001")


def test_build_agent_executor_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "dummy")
    monkeypatch.setenv("LLM_PROVIDER", "unknown_provider")
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 18, 0))

    with pytest.raises(ValueError, match="unsupported LLM_PROVIDER"):
        build_agent_executor(repo, clock, "user-001")
