# Azure deployment preparation

The repository contains a Linux Dockerfile and two GitHub Actions workflows:

- `ci.yml` runs linting and mocked tests on pull requests and pushes to `main`.
- `azure-deploy.yml` is manual until the Azure resources and GitHub credentials are ready.

The target design uses an Azure Container Registry and an Azure App Service for Linux custom
container. Configure App Service to use container port `8000` and set its health-check path to
`/health`.

## GitHub configuration

Create these repository variables:

- `ACR_LOGIN_SERVER`, such as `example.azurecr.io`
- `AZURE_WEBAPP_NAME`

Create these repository secrets for an Azure federated identity:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

The federated identity needs permission to push to the registry and update the App Service.
Do not store an Azure password or publish profile in the repository.

## App settings

Copy the relevant values from `.env.example` into Azure App Service application settings.
At minimum, set:

```text
WEBSITES_PORT=8000
ELEVATION_PROVIDER=py3dep
ELEVATION_SOURCE=tep
MAX_BATCH_SIZE=500
MAX_REQUEST_BODY_BYTES=1000000
```

The deployment workflow is triggered manually from the GitHub Actions page. After the first
staging deployment is verified, a push-to-`main` trigger and an App Service staging slot can
be introduced.
