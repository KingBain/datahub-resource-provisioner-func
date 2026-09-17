# Datahub User Provisioner

Python Azure Functions that synchronize workspace users in Databricks, Azure Key Vault, and Azure Storage. This standalone project was extracted from `ssc-sp/datahub-portal` at `develop` commit `469859be137c2b31c958265954b9370552c33e48`.

The Azure Functions project root is this repository root. `function_app.py`, `host.json`, `lib/`, the dependency files, and `Dockerfile` are all here; no .NET project or files from the original monorepo are required to import the application code or provide its Docker build context.

## Check changes

The GitHub workflow installs the locked dependencies on Python 3.12, runs syntax checks and offline unit tests, and confirms both Azure Functions register using the real SDK packages. Its Dockerfile job runs `docker buildx build --check .`, which checks the build definition without executing the build or producing an image. Image builds, publishing, and deployments belong to a separate flow.

Run the checks locally with Python 3.12:

```bash
poetry check --lock
poetry install --only main --no-root
poetry run python -m compileall -q function_app.py bug_report_message.py healthcheck_message.py lib tests
poetry run python -m unittest discover -s tests -p 'test_*.py' -v
poetry run python -c 'import function_app; print([fn.get_function_name() for fn in function_app.app.get_functions()])'
```

The offline tests stub Azure SDK calls. They check message normalization, template dispatch, and health/error handling; they do not exercise live Azure permissions or the resulting access policies. The older tests under the original monorepo's `ResourceProvisioner/test/ResourceProvisioner_PyFunctions_Tests` call live Azure services and have not been moved into this CI suite.

## Runtime contracts

- `SynchronizeWorkspaceUsersQueueTrigger` receives MassTransit JSON envelopes on the Service Bus queue `user-run-request`, using the `DatahubServiceBus` connection setting. It reads the envelope's `message` field as a workspace definition.
- `SynchronizeWorkspaceUsersHttpTrigger` exposes the `sync-workspace-users` route through Azure Functions.
- Synchronization errors are published to `bug-report`; health results go to `infrastructure-health-check-results`. The output envelopes use the existing MassTransit message types in `lib/queue_utils.py`.
- The synchronizer needs credentials and access to the target Azure subscription, the Service Bus namespace, and any Databricks workspaces in the definition. Keep queue names, the workspace definition shape, and output message types compatible with the portal and the downstream consumers when changing this repo.

For local use, install Python 3.12, Poetry, Azure Functions Core Tools 4, and a local Azure Storage emulator if you use `UseDevelopmentStorage=true`. Install dependencies with `poetry install`, then run `poetry run func start --python` from the repository root. Configure the Function host using `local.settings.json` (ignored by Git) or environment variables. Required settings for the full synchronization path are `FUNCTIONS_WORKER_RUNTIME=python`, `AzureWebJobsStorage`, `DatahubServiceBus`, `DataHub_ENVNAME`, `AzureSubscriptionId`, `AzureTenantId`, `AzureClientId`, and `AzureClientSecret`. Supply them through your existing environment's secret management; do not commit them.

`pyproject.toml` and `poetry.lock` are used by the Dockerfile. `requirements.txt` is retained for compatibility with the original Azure Functions project, but the image build does not install from it; keep the two declarations aligned until a single dependency format is chosen. The Dockerfile expects this repository root as its build context. The external image flow can use it directly without checking out the original monorepo.
