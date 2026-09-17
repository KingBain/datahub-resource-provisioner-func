"""Verify outgoing report payloads without a Service Bus connection."""

import json
from unittest.mock import MagicMock

import pytest

import function_app as app
from healthcheck_message import HealthcheckMessage


@pytest.mark.parametrize("report_kind", ["health", "error"])
def test_report_is_sent_in_mass_transit_envelope(monkeypatch, report_kind):
    # Arrange
    factory = MagicMock()
    client = factory.return_value.__enter__.return_value
    client.fully_qualified_namespace = "test.servicebus.windows.net"
    sender = client.get_queue_sender.return_value.__enter__.return_value
    monkeypatch.setattr(
        app.servicebus.ServiceBusClient, "from_connection_string", factory
    )
    monkeypatch.setattr(
        app, "get_config", lambda: ("fake-connection", "bugs", "health")
    )
    health = HealthcheckMessage(
        HealthcheckMessage.TYPE_WORKSPACE_SYNC,
        "workspaces",
        "demo",
        "",
        HealthcheckMessage.STATUS_HEALTHY,
    )

    # Act
    if report_kind == "health":
        app.send_healthcheck_to_service_bus(health)
    else:
        app.send_exception_to_service_bus("Sync failed")

    # Assert
    queue = "health" if report_kind == "health" else "bugs"
    client.get_queue_sender.assert_called_once_with(queue)
    sender.send_messages.assert_called_once()
    message = sender.send_messages.call_args.args[0]
    envelope = json.loads(b"".join(message.body))
    assert envelope["destinationAddress"] == f"sb://test.servicebus.windows.net/{queue}"
    if report_kind == "health":
        assert envelope["message"]["Name"] == "demo"
        assert envelope["message"]["Status"] == HealthcheckMessage.STATUS_HEALTHY
        assert message.message_id == envelope["messageId"]
    else:
        assert envelope["message"]["Description"] == "Sync failed"
        assert (
            envelope["message"]["BugReportType"] == app.PYTHON_WORKSPACE_SYNC_ERROR_CODE
        )
