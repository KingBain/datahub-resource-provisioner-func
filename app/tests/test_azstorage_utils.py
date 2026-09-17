"""Exercise storage policy decisions without connecting to Azure."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from azure.core.exceptions import HttpResponseError

from lib import azstorage_utils as storage


@pytest.mark.parametrize(
    ("role", "expected_role"),
    [
        ("Guest", storage.READER),
        ("User", storage.CONTRIBUTOR),
        ("Admin", storage.CONTRIBUTOR),
        ("Owner", storage.CONTRIBUTOR),
    ],
)
def test_user_without_access_receives_expected_role(role, expected_role):
    # Arrange
    client = Mock()
    client.role_assignments.list_for_scope.return_value = []
    definition = {
        "Workspace": {
            "Acronym": "demo",
            "Users": [{"ObjectId": "user-123", "Role": role}],
        }
    }

    # Act
    storage.synchronize_access_policies(
        client, "subscription", "test", definition, ["shared", "users"]
    )

    # Assert
    assert client.role_assignments.create.call_count == 2
    for invocation, container in zip(
        client.role_assignments.create.call_args_list, ["shared", "users"]
    ):
        arguments = invocation.kwargs
        assert arguments["scope"].endswith(
            f"/blobServices/default/containers/{container}"
        )
        assert arguments["parameters"].principal_id == "user-123"
        assert arguments["parameters"].role_definition_id == (
            f"/subscriptions/subscription/providers/Microsoft.Authorization/roleDefinitions/{expected_role}"
        )
    client.role_assignments.delete_at_scope.assert_not_called()


@pytest.mark.parametrize(
    ("role", "existing_role", "expected_role"),
    [
        ("Guest", storage.CONTRIBUTOR, storage.READER),
        ("User", storage.READER, storage.CONTRIBUTOR),
    ],
)
def test_changed_role_replaces_existing_assignment(role, existing_role, expected_role):
    # Arrange
    client = Mock()
    client.role_assignments.list_for_scope.return_value = [
        SimpleNamespace(
            principal_id="user-123", role_definition_id=existing_role, name="assignment"
        )
    ]
    definition = {
        "Workspace": {
            "Acronym": "demo",
            "Users": [{"ObjectId": "user-123", "Role": role}],
        }
    }

    # Act
    storage.synchronize_access_policies(
        client, "subscription", "test", definition, ["shared"]
    )

    # Assert
    client.role_assignments.create.assert_called_once()
    arguments = client.role_assignments.create.call_args.kwargs
    client.role_assignments.delete_at_scope.assert_called_once_with(
        arguments["scope"], "assignment"
    )
    assert arguments["parameters"].role_definition_id.endswith(expected_role)


@pytest.mark.parametrize(
    ("role", "existing_role"),
    [("Guest", storage.READER), ("User", storage.CONTRIBUTOR)],
)
def test_correct_access_is_preserved(role, existing_role):
    # Arrange
    client = Mock()
    client.role_assignments.list_for_scope.return_value = [
        SimpleNamespace(principal_id="user-123", role_definition_id=existing_role)
    ]
    definition = {
        "Workspace": {
            "Acronym": "demo",
            "Users": [{"ObjectId": "user-123", "Role": role}],
        }
    }

    # Act
    storage.synchronize_access_policies(
        client, "subscription", "test", definition, ["shared"]
    )

    # Assert
    client.role_assignments.create.assert_not_called()
    client.role_assignments.delete_at_scope.assert_not_called()


def test_removed_user_loses_only_their_managed_roles():
    # Arrange
    client = Mock()
    client.role_assignments.list_for_scope.return_value = [
        SimpleNamespace(
            principal_id="removed", role_definition_id=storage.READER, name="managed"
        ),
        SimpleNamespace(
            principal_id="removed",
            role_definition_id="unrelated-role",
            name="unrelated",
        ),
        SimpleNamespace(
            principal_id="other-user", role_definition_id=storage.READER, name="other"
        ),
    ]
    definition = {
        "Workspace": {
            "Acronym": "demo",
            "Users": [{"ObjectId": "removed", "Role": "Removed"}],
        }
    }

    # Act
    storage.synchronize_access_policies(
        client, "subscription", "test", definition, ["shared"]
    )

    # Assert
    scope = client.role_assignments.list_for_scope.call_args.args[0]
    client.role_assignments.delete_at_scope.assert_called_once_with(scope, "managed")
    client.role_assignments.create.assert_not_called()


def test_storage_api_failure_is_currently_logged_and_suppressed(caplog):
    # Arrange
    client = Mock()
    client.role_assignments.list_for_scope.side_effect = HttpResponseError(
        "Access denied"
    )
    definition = {
        "Workspace": {
            "Acronym": "demo",
            "Users": [{"ObjectId": "user-123", "Role": "Guest"}],
        }
    }

    # Act
    storage.synchronize_access_policies(
        client, "subscription", "test", definition, ["shared"]
    )

    # Assert
    # Characterizes existing behavior; this is not a guarantee that synchronization succeeded.
    assert "Error processing user user-123 access policies" in caplog.text
    client.role_assignments.create.assert_not_called()
