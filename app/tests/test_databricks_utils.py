"""Test Databricks synchronization through mock SDK clients."""

from unittest.mock import Mock, call

import pytest
from databricks.sdk.service.iam import ComplexValue, Group, User
from databricks.sdk.service.workspace import ScopeBackendType, SecretScope

from lib import databricks_utils as databricks


@pytest.mark.parametrize(
    ("role", "group_name"),
    [
        ("Guest", "project_users"),
        ("User", "project_users"),
        ("Admin", "admins"),
        ("Owner", "project_lead"),
    ],
)
def test_missing_user_is_created_in_expected_group(role, group_name):
    # Arrange
    client = Mock()
    client.users.list.return_value = iter([])
    client.groups.list.return_value = iter(
        [Group(id="group-id", display_name=group_name)]
    )
    definition = {
        "Workspace": {
            "Users": [
                {"ObjectId": "user-123", "Email": "user@example.test", "Role": role}
            ]
        }
    }

    # Act
    databricks.synchronize_workspace_users(definition, client)

    # Assert
    client.users.create.assert_called_once()
    arguments = client.users.create.call_args.kwargs
    assert arguments["external_id"] == "user-123"
    assert arguments["user_name"] == "user@example.test"
    assert arguments["emails"][0].value == "user@example.test"
    assert arguments["groups"] == [ComplexValue(value="group-id", display=group_name)]
    client.users.update.assert_not_called()


@pytest.mark.parametrize(
    "existing_groups", [None, [], [ComplexValue(display="project_users")]]
)
def test_existing_user_receives_missing_admin_group(existing_groups):
    # Arrange
    client = Mock()
    client.users.list.return_value = iter(
        [User(id="workspace-id", external_id="USER-123", groups=existing_groups)]
    )
    client.groups.list.return_value = iter(
        [Group(id="admins-id", display_name="admins")]
    )
    definition = {
        "Workspace": {
            "Users": [
                {"ObjectId": "user-123", "Email": "user@example.test", "Role": "Admin"}
            ]
        }
    }

    # Act
    databricks.synchronize_workspace_users(definition, client)

    # Assert
    client.users.update.assert_called_once_with(
        id="workspace-id",
        user_name="user@example.test",
        groups=[ComplexValue(value="admins-id", display="admins")],
    )
    client.users.create.assert_not_called()


def test_existing_user_in_correct_group_is_preserved():
    # Arrange
    client = Mock()
    client.users.list.return_value = iter(
        [
            User(
                id="workspace-id",
                external_id="user-123",
                groups=[ComplexValue(display="admins")],
            )
        ]
    )
    client.groups.list.return_value = iter(
        [Group(id="admins-id", display_name="admins")]
    )
    definition = {
        "Workspace": {
            "Users": [
                {"ObjectId": "user-123", "Email": "user@example.test", "Role": "Admin"}
            ]
        }
    }

    # Act
    databricks.synchronize_workspace_users(definition, client)

    # Assert
    client.users.create.assert_not_called()
    client.users.update.assert_not_called()
    client.users.delete.assert_not_called()


def test_removed_and_unlinked_users_are_deleted_but_active_user_is_preserved():
    # Arrange
    client = Mock()
    client.users.list.return_value = iter(
        [
            User(id="unlinked", external_id=None),
            User(id="removed", external_id="removed-object"),
            User(id="active", external_id="active-object"),
        ]
    )
    definition = {
        "Workspace": {
            "Users": [
                {"ObjectId": "removed-object", "Role": "Removed"},
                {"ObjectId": "active-object", "Role": "User"},
            ]
        }
    }

    # Act
    databricks.remove_deleted_users_in_workspace(definition, client)

    # Assert
    assert client.users.delete.call_args_list == [call("unlinked"), call("removed")]


@pytest.mark.parametrize("scope_exists", [False, True])
def test_keyvault_secret_scope_is_created_only_when_missing(scope_exists):
    # Arrange
    client = Mock()
    client.secrets.list_scopes.return_value = iter(
        [SecretScope(name="dh-workspace")] if scope_exists else []
    )
    definition = {"Workspace": {"Acronym": "demo"}}

    # Act
    databricks.synchronize_workspace_secret_scopes(
        "test", "subscription", definition, client
    )

    # Assert
    if scope_exists:
        client.secrets.create_scope.assert_not_called()
    else:
        client.secrets.create_scope.assert_called_once()
        arguments = client.secrets.create_scope.call_args.kwargs
        assert arguments["scope"] == "dh-workspace"
        assert arguments["scope_backend_type"] == ScopeBackendType.AZURE_KEYVAULT
        assert arguments["backend_azure_keyvault"].resource_id.startswith(
            "/subscriptions/subscription/"
        )
        assert arguments["backend_azure_keyvault"].dns_name.endswith(
            ".vault.azure.net/"
        )
