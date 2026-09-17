"""Keep unit tests isolated from external services."""

import socket

import pytest


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Fail immediately if a test accidentally attempts a network connection."""

    def reject_connection(*_args, **_kwargs):
        pytest.fail("Unit tests must not connect to external services")

    monkeypatch.setattr(socket.socket, "connect", reject_connection)
    monkeypatch.setattr(socket.socket, "connect_ex", reject_connection)
    monkeypatch.setattr(socket, "getaddrinfo", reject_connection)
