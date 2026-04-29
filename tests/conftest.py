"""
Shared pytest fixtures for local-whisper tests.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    """
    Provides a TestClient wired to the FastAPI app.
    Loaded once per test session.
    """
    from app.main import app

    return TestClient(app)


@pytest.fixture(scope="session")
def anyio_backend():
    """
    Explicitly select the asyncio backend for pytest-asyncio.
    """
    return "asyncio"
