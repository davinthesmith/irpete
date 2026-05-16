"""Pytest fixtures: test app, DB path, and auth headers."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

from irpete.app import create_app
from irpete.config import Settings


@pytest.fixture
def api_key() -> str:
    return "test-secret-key-for-pytest"


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def settings(api_key: str, db_path) -> Settings:
    return Settings(
        api_key=api_key,
        db_path=db_path,
        host="127.0.0.1",
        port=8000,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c
