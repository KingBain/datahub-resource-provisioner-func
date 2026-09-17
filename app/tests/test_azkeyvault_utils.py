"""Exercise Key Vault permissions with an in-memory vault and mock client."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from azure.mgmt.keyvault.models import AccessPolicyEntry, Permissions

from lib import azkeyvault_utils as keyvault


@pytest.mark.parametrize(
    ("role", "permissions"),
    [
        ("Guest", ["list", "get"]),
        ("User", ["list", "get"]),
        ("Admin", ["list", "get", "delete", "set"]),
        ("Owner", ["list", "get", "delete", "set"]),
    ],
)
def test_new_user_receives_role_permissions(role, permissions):
    # Arrange
    client = Mock()
    vault = SimpleNamespace(properties=SimpleNamespace(access_policies=[]))
    client.vaults.get.return_value = vault
    definition = {
        "Workspace": {
            "Acronym": "demo",
            "Users": [{"ObjectId": "user-123", "Role": role}],
        }
    }

    # Act
    result = keyvault.synchronize_access_policies(client, "test", definition, "tenant")

    # Assert
    (policy,) = vault.properties.access_policies
    assert policy.object_id == "user-123"
    assert policy.tenant_id == "tenant"
    assert policy.permissions["secrets"] == permissions
    client.vaults.begin_create_or_update.assert_called_once_with(
        *client.vaults.get.call_args.args, vault
    )
    assert (
        result is client.vaults.begin_create_or_update.return_value.result.return_value
    )


def test_changed_permissions_replace_policy_and_preserve_other_users():
    # Arrange
    client = Mock()
    old = AccessPolicyEntry(
        tenant_id="tenant",
        object_id="user-123",
        permissions=Permissions(secrets=["get"]),
    )
    other = AccessPolicyEntry(
        tenant_id="tenant", object_id="other", permissions=Permissions(secrets=["get"])
    )
    vault = SimpleNamespace(properties=SimpleNamespace(access_policies=[old, other]))
    client.vaults.get.return_value = vault
    definition = {
        "Workspace": {
            "Acronym": "demo",
            "Users": [{"ObjectId": "user-123", "Role": "Admin"}],
        }
    }

    # Act
    keyvault.synchronize_access_policies(client, "test", definition, "tenant")

    # Assert
    assert len(vault.properties.access_policies) == 2
    assert vault.properties.access_policies[0] is other
    replacement = vault.properties.access_policies[1]
    assert replacement.object_id == "user-123"
    assert replacement.permissions["secrets"] == ["list", "get", "delete", "set"]


def test_correct_permissions_preserve_existing_policy():
    # Arrange
    client = Mock()
    policy = AccessPolicyEntry(
        tenant_id="tenant",
        object_id="user-123",
        permissions=Permissions(secrets=["get", "list"]),
    )
    vault = SimpleNamespace(properties=SimpleNamespace(access_policies=[policy]))
    client.vaults.get.return_value = vault
    definition = {
        "Workspace": {
            "Acronym": "demo",
            "Users": [{"ObjectId": "user-123", "Role": "Guest"}],
        }
    }

    # Act
    keyvault.synchronize_access_policies(client, "test", definition, "tenant")

    # Assert
    assert len(vault.properties.access_policies) == 1
    assert vault.properties.access_policies[0] is policy


def test_removed_user_policy_is_deleted():
    # Arrange
    client = Mock()
    removed = AccessPolicyEntry(
        tenant_id="tenant",
        object_id="removed",
        permissions=Permissions(secrets=["get"]),
    )
    other = AccessPolicyEntry(
        tenant_id="tenant", object_id="other", permissions=Permissions(secrets=["get"])
    )
    vault = SimpleNamespace(
        properties=SimpleNamespace(access_policies=[removed, other])
    )
    client.vaults.get.return_value = vault
    definition = {
        "Workspace": {
            "Acronym": "demo",
            "Users": [{"ObjectId": "removed", "Role": "Removed"}],
        }
    }

    # Act
    keyvault.synchronize_access_policies(client, "test", definition, "tenant")

    # Assert
    assert vault.properties.access_policies == [other]
