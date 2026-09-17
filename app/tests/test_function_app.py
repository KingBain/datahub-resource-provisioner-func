"""Unit tests for the workspace synchronization entry points."""

import json
from unittest.mock import Mock, call

import pytest

import function_app as app
from healthcheck_message import HealthcheckMessage


def test_new_project_template_syncs_keyvault_then_storage(monkeypatch):
    # Arrange
    definition = {"Workspace": {"Acronym": "demo"}}
    syncs = Mock()
    monkeypatch.setattr(app, "sync_keyvault_workspace_users_function", syncs.keyvault)
    monkeypatch.setattr(app, "sync_storage_workspace_users_function", syncs.storage)
    _, handler = app.get_sync_func_mappings()["new-project-template"]

    # Act
    handler(definition)

    # Assert
    assert syncs.mock_calls == [call.keyvault(definition), call.storage(definition)]


def test_queue_message_is_normalized_and_dispatched(monkeypatch):
    # Arrange
    envelope = {
        "message": {
            "workspace": {"acronym": "demo", "users": [{"objectId": "123"}]},
            "templates": [{"name": "azure-storage-blob"}],
        }
    }
    message = Mock()
    message.get_body.return_value = json.dumps(envelope).encode("utf-8")
    sync_workspace = Mock()
    monkeypatch.setattr(app, "new_sync_workspace", sync_workspace)

    # Act
    app.queue_sync_workspace_users_function.build().get_user_function()(message)

    # Assert
    sync_workspace.assert_called_once_with(
        {
            "Workspace": {"Acronym": "demo", "Users": [{"ObjectId": "123"}]},
            "Templates": [{"Name": "azure-storage-blob"}],
        }
    )


def test_template_sync_emits_healthy_result(monkeypatch):
    # Arrange
    storage_calls = []
    send_health = Mock()
    send_error = Mock()

    def sync_storage(definition):
        storage_calls.append(definition)

    monkeypatch.setattr(app, "sync_storage_workspace_users_function", sync_storage)
    monkeypatch.setattr(app, "send_healthcheck_to_service_bus", send_health)
    monkeypatch.setattr(app, "send_exception_to_service_bus", send_error)
    definition = {
        "Workspace": {"Acronym": "demo"},
        "Templates": [{"Name": "azure-storage-blob"}],
    }

    # Act
    app.new_sync_workspace(definition)

    # Assert
    assert storage_calls == [definition]
    send_error.assert_not_called()
    send_health.assert_called_once()
    result = send_health.call_args.args[0]
    assert isinstance(result, HealthcheckMessage)
    assert result.ResourceType == HealthcheckMessage.TYPE_WORKSPACE_SYNC
    assert result.Group == "workspaces"
    assert result.Name == "demo"
    assert result.Status == HealthcheckMessage.STATUS_HEALTHY
    assert result.Details == ""


def test_template_failure_reports_error_and_unhealthy_result(monkeypatch):
    # Arrange
    send_error = Mock()
    send_health = Mock()
    definition = {
        "Workspace": {"Acronym": "demo"},
        "Templates": [{"Name": "azure-storage-blob"}],
    }

    def sync_storage(_definition):
        raise ValueError("simulated failure")

    monkeypatch.setattr(app, "sync_storage_workspace_users_function", sync_storage)
    monkeypatch.setattr(app, "send_exception_to_service_bus", send_error)
    monkeypatch.setattr(app, "send_healthcheck_to_service_bus", send_health)

    # Act
    with pytest.raises(
        RuntimeError, match="Workspace demo had problems while synchronizing"
    ):
        app.new_sync_workspace(definition)

    # Assert
    send_error.assert_called_once_with(
        "Error synchronizing storage account policies for demo"
    )
    send_health.assert_called_once()
    result = send_health.call_args.args[0]
    assert isinstance(result, HealthcheckMessage)
    assert result.Status == HealthcheckMessage.STATUS_UNHEALTHY
    assert result.Details == "Error synchronizing storage account policies for demo"
