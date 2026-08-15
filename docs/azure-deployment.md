# Azure installation and first deployment

This chapter records the complete one-time installation of the LCG elevation service in
Azure. It includes the normal commands, the workarounds that were required during the
original deployment, verification after every important resource, and an explanation of
what each resource does.

The separate [GitHub Actions and Azure OIDC](github-actions-oidc.md) chapter starts from the
working Azure installation described here and adds automatic deployment from GitHub.

## Current development environment

The first working Azure deployment was confirmed healthy before the GitHub Actions setup
began. These names are intentionally repeated throughout the guide so that commands can be
compared with the resources in the Azure portal.

| Purpose | Azure resource or value |
| --- | --- |
| Subscription | `LogicCloudGeo_ss` |
| Azure region | East US 2 (`eastus2`) |
| Resource group | `rg-lcg-elevation-dev` |
| Container registry | `acrlcgelevation53679` |
| Registry login server | `acrlcgelevation53679.azurecr.io` |
| Container repository | `lcg-usgs-3dep-elevation-service` |
| Initial image tag | `bootstrap` |
| App Service plan | `asp-lcg-elevation-dev` |
| App Service web app | `lcg-elevation-dev-53679` |
| Container port | `8000` |
| Health endpoint | `/health` |
| GitHub repository | `lesterw53679/lcg-usgs-3dep-elevation-service` |

The names ending in `53679` satisfy Azure's global naming requirements. A future installation
for another Azure account must choose its own globally unique registry and web-app names.

## What the Azure resources do

| Resource | Responsibility | Persists when Cloud Shell closes? |
| --- | --- | --- |
| Resource group | Logical container for the development resources | Yes |
| Azure Container Registry (ACR) | Stores versioned Docker images | Yes |
| App Service plan | Supplies the Linux compute and B1 billing boundary | Yes |
| Web App | Runs the selected container image and exposes HTTPS | Yes |
| Web App system-assigned identity | Lets the running app pull an image from ACR without a registry password | Yes |
| Cloud Shell | Administrative terminal used to issue Azure CLI commands | Its Azure changes persist; its variables and ephemeral files do not |

Cloud Shell storage is not application storage. An ephemeral Bash session is sufficient for
this installation because the source is in GitHub and the built image is in ACR.

## Prerequisites

Before running the installation:

1. The GitHub repository must contain `Dockerfile`, `pyproject.toml`, `app/`, and the tests.
2. The Azure subscription must be enabled and able to create resources in East US 2.
3. The subscription must have at least one Linux B1 App Service worker of quota in East US 2.
4. Run the commands in Azure Cloud Shell using **Bash**, not PowerShell.
5. The signed-in account must be able to create resources and Azure role assignments.

The quota screen may describe the B1 limit as `B1 VMs`. A display of `Usage 0 of 1` means the
subscription has a limit of one and currently uses none; that is sufficient for this project.
The quota approval itself does not create or bill an App Service plan. Billing begins when the
plan is created.

## 1. Select the subscription and define variables

Cloud Shell variables are conveniences local to the current Bash process. They prevent typing
long names repeatedly, but they disappear when the session closes. Restoring a variable never
creates or changes an Azure resource.

```bash
az account set --subscription "LogicCloudGeo_ss"

LCG_LOCATION="eastus2"
LCG_RG="rg-lcg-elevation-dev"
LCG_ACR="acrlcgelevation53679"
LCG_PLAN="asp-lcg-elevation-dev"
LCG_APP="lcg-elevation-dev-53679"
LCG_IMAGE="lcg-usgs-3dep-elevation-service"
LCG_BOOTSTRAP_TAG="bootstrap"
LCG_REPOSITORY_URL="https://github.com/lesterw53679/lcg-usgs-3dep-elevation-service.git"

LCG_SUBSCRIPTION_ID=$(az account show --query id --output tsv)
LCG_TENANT_ID=$(az account show --query tenantId --output tsv)
```

Verify the active subscription and every human-readable value before continuing:

```bash
az account show \
  --query "{Subscription:name,State:state,IsDefault:isDefault}" \
  --output table

printf 'Location: %s\n' "$LCG_LOCATION"
printf 'Resource group: %s\n' "$LCG_RG"
printf 'Registry: %s\n' "$LCG_ACR"
printf 'Plan: %s\n' "$LCG_PLAN"
printf 'Web App: %s\n' "$LCG_APP"
printf 'Image: %s\n' "$LCG_IMAGE"
```

Do not continue if any value after a label is blank. The original `:bootstrap` image-name
error occurred because `LCG_IMAGE` had disappeared from a restarted Cloud Shell session.

## 2. Register the Azure resource providers

An Azure subscription must register a resource provider before it can create that provider's
resource types. ACR belongs to `Microsoft.ContainerRegistry`; App Service belongs to
`Microsoft.Web`.

```bash
az provider register --namespace Microsoft.ContainerRegistry
az provider register --namespace Microsoft.Web
```

Registration can be asynchronous. Verify both states:

```bash
az provider show \
  --namespace Microsoft.ContainerRegistry \
  --query "{Namespace:namespace,State:registrationState}" \
  --output table

az provider show \
  --namespace Microsoft.Web \
  --query "{Namespace:namespace,State:registrationState}" \
  --output table
```

Both should report `Registered` before their resources are created.

## 3. Create the resource group

```bash
az group create \
  --name "$LCG_RG" \
  --location "$LCG_LOCATION"
```

Verify it:

```bash
az group show \
  --name "$LCG_RG" \
  --query "{Name:name,Location:location,State:properties.provisioningState}" \
  --output table
```

The resource-group location is where Azure stores its metadata. Each child resource also has
its own location; this project explicitly places the registry and plan in East US 2.

## 4. Create Azure Container Registry

The normal command is:

```bash
az acr create \
  --resource-group "$LCG_RG" \
  --name "$LCG_ACR" \
  --location "$LCG_LOCATION" \
  --sku Basic \
  --admin-enabled false
```

The admin account remains disabled because both the Web App and GitHub Actions use identities
rather than shared registry passwords.

Verify the registry:

```bash
az acr show \
  --resource-group "$LCG_RG" \
  --name "$LCG_ACR" \
  --query "{Name:name,State:provisioningState,Sku:sku.name,LoginServer:loginServer,AdminEnabled:adminUserEnabled}" \
  --output table
```

### ACR API-version workaround used during the original installation

During the first deployment, the Cloud Shell CLI selected the unsupported preview API version
`2026-01-01-preview`. The stable ARM REST call below created the same registry without creating
a duplicate. Use it only when the normal `az acr create` command fails with
`InvalidApiVersionParameter`.

```bash
LCG_ACR_RESOURCE_URL="https://management.azure.com/subscriptions/${LCG_SUBSCRIPTION_ID}/resourceGroups/${LCG_RG}/providers/Microsoft.ContainerRegistry/registries/${LCG_ACR}?api-version=2025-04-01"

printf '%s\n' "$LCG_ACR_RESOURCE_URL"
```

Before the `PUT`, confirm the printed URL contains both of these literal path segments:

```text
resourceGroups/rg-lcg-elevation-dev
registries/acrlcgelevation53679
```

Then create or converge the registry:

```bash
az rest \
  --method put \
  --url "$LCG_ACR_RESOURCE_URL" \
  --body "{\"location\":\"${LCG_LOCATION}\",\"sku\":{\"name\":\"Basic\"},\"properties\":{\"adminUserEnabled\":false,\"publicNetworkAccess\":\"Enabled\"}}"
```

Verify the stable-API result:

```bash
az rest \
  --method get \
  --url "$LCG_ACR_RESOURCE_URL" \
  --query "{Name:name,State:properties.provisioningState,Sku:sku.name,LoginServer:properties.loginServer}" \
  --output table
```

The expected provisioning state is `Succeeded`.

## 5. Build the initial Docker image in Azure

Clone the source into the current Cloud Shell session:

```bash
git clone \
  --config core.autocrlf=input \
  "$LCG_REPOSITORY_URL"

cd lcg-usgs-3dep-elevation-service
```

If the directory already exists in a persistent Cloud Shell, do not clone a second copy. Enter
the existing directory, run `git status`, and use `git pull --ff-only` only when it is clean.

Confirm the Docker build context:

```bash
pwd
test -f Dockerfile && echo "Dockerfile found."
test -f pyproject.toml && echo "pyproject.toml found."
test -d app && echo "Application package found."
```

Build the Linux AMD64 image in ACR and tag it `bootstrap`:

```bash
az acr build \
  --registry "$LCG_ACR" \
  --image "${LCG_IMAGE}:${LCG_BOOTSTRAP_TAG}" \
  --platform linux/amd64 \
  .
```

`az acr build` packages the current directory, uploads the build context to Azure, runs the
Docker build in ACR, and pushes the completed image into the registry. A local Docker Desktop
installation is not required for this step.

Verify the image tag:

```bash
az acr repository show-tags \
  --name "$LCG_ACR" \
  --repository "$LCG_IMAGE" \
  --output table
```

If Azure reports that `:bootstrap` is invalid, restore `LCG_IMAGE` and repeat the build. That
error means Bash expanded an empty repository name; it does not mean the registry is broken.

## 6. Create the App Service plan

```bash
az appservice plan create \
  --resource-group "$LCG_RG" \
  --name "$LCG_PLAN" \
  --location "$LCG_LOCATION" \
  --is-linux \
  --sku B1 \
  --number-of-workers 1
```

The plan supplies the Linux worker on which the Web App runs. The B1 plan is intentionally one
worker while request volume and upstream-service behavior are measured.

Verify it:

```bash
az appservice plan show \
  --resource-group "$LCG_RG" \
  --name "$LCG_PLAN" \
  --query "{Name:name,Location:location,State:status,Sku:sku.name,Workers:sku.capacity}" \
  --output table
```

### B1 quota troubleshooting used during the original installation

If plan creation reports `Current Limit (Total VMs): 0`, open Azure Portal **Quotas**, select:

- Subscription: `LogicCloudGeo_ss`
- Provider: **App Service (Public Preview)**
- Region: **East US 2**
- Quota: **B1 VMs**

`Usage 0 of 1` is sufficient. A request for a new limit of `2` is unnecessary for this
single-worker plan even if that larger request fails. Confirm Cloud Shell is using the same
subscription before retrying the plan command.

## 7. Create the Web App

The Azure CLI version used during the first installation required an initial runtime or image.
A temporary Python runtime was used to create the Web App; the custom container replaced it in
the later configuration step.

```bash
az webapp create \
  --resource-group "$LCG_RG" \
  --plan "$LCG_PLAN" \
  --name "$LCG_APP" \
  --runtime "PYTHON:3.12" \
  --https-only true
```

Verify creation:

```bash
az webapp show \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --query "{Name:name,State:state,Host:defaultHostName,HttpsOnly:httpsOnly}" \
  --output table
```

The expected default hostname is:

```text
lcg-elevation-dev-53679.azurewebsites.net
```

## 8. Give the Web App permission to pull from ACR

Enable a system-assigned managed identity on the Web App and capture its principal ID:

```bash
LCG_APP_PRINCIPAL_ID=$(az webapp identity assign \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --query principalId \
  --output tsv)
```

Capture the registry's Azure resource ID:

```bash
LCG_ACR_ID=$(az acr show \
  --resource-group "$LCG_RG" \
  --name "$LCG_ACR" \
  --query id \
  --output tsv)
```

Check that neither command returned an empty value without printing the full IDs:

```bash
test -n "$LCG_APP_PRINCIPAL_ID" && echo "Web App identity retrieved."
test -n "$LCG_ACR_ID" && echo "Registry resource ID retrieved."
```

Assign the built-in `AcrPull` role at registry scope:

```bash
az role assignment create \
  --assignee-object-id "$LCG_APP_PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --scope "$LCG_ACR_ID" \
  --role "AcrPull"
```

This is least privilege for the running application: it can download images from this
registry, but it cannot push images or modify the Web App.

Verify the role assignment:

```bash
az role assignment list \
  --assignee "$LCG_APP_PRINCIPAL_ID" \
  --scope "$LCG_ACR_ID" \
  --query "[?roleDefinitionName=='AcrPull'].{Role:roleDefinitionName,Scope:scope}" \
  --output table
```

## 9. Connect the bootstrap image to the Web App

Tell App Service to use its managed identity when it contacts ACR:

```bash
az webapp config set \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --generic-configurations '{"acrUseManagedIdentityCreds": true}'
```

Enable ACR authentication through ARM tokens:

```bash
az acr config authentication-as-arm update \
  --registry "$LCG_ACR" \
  --status enabled
```

Print and inspect the complete image name before assigning it:

```bash
printf '%s\n' "${LCG_ACR}.azurecr.io/${LCG_IMAGE}:${LCG_BOOTSTRAP_TAG}"
```

Expected:

```text
acrlcgelevation53679.azurecr.io/lcg-usgs-3dep-elevation-service:bootstrap
```

Set the Web App's image:

```bash
az webapp config container set \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --container-image-name "${LCG_ACR}.azurecr.io/${LCG_IMAGE}:${LCG_BOOTSTRAP_TAG}" \
  --container-registry-url "https://${LCG_ACR}.azurecr.io"
```

Some CLI versions try to look up ACR admin credentials and print a warning when the admin
account is disabled. Do not enable the admin account. The important result is that the custom
image name is complete and `acrUseManagedIdentityCreds` is true.

## 10. Configure the port, application settings, and health check

The container listens on port 8000. `WEBSITES_PORT` tells App Service which internal port to
route to. The other values make the service limits explicit in Azure rather than relying only
on application defaults.

```bash
az webapp config appsettings set \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --settings \
    WEBSITES_PORT=8000 \
    WEBSITES_CONTAINER_START_TIME_LIMIT=1800 \
    ELEVATION_PROVIDER=py3dep \
    ELEVATION_SOURCE=tep \
    MAX_BATCH_SIZE=500 \
    MAX_REQUEST_BODY_BYTES=1000000 \
    UPSTREAM_TIMEOUT_SECONDS=60 \
    UPSTREAM_MAX_CONCURRENCY=2 \
    UPSTREAM_MAX_ATTEMPTS=3
```

Keep the B1 application warm and configure the health path:

```bash
az webapp config set \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --always-on true

az webapp config set \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --generic-configurations '{"healthCheckPath": "/health"}'
```

Restart once so all settings are applied together:

```bash
az webapp restart \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP"
```

## 11. Verify the first deployment

Retrieve the hostname rather than retyping it:

```bash
LCG_APP_HOST=$(az webapp show \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --query defaultHostName \
  --output tsv)

printf 'https://%s\n' "$LCG_APP_HOST"
```

Check the health endpoint. It does not call USGS and therefore separates application startup
health from upstream service availability:

```bash
curl --fail --show-error --silent \
  "https://${LCG_APP_HOST}/health"
```

Check a live Florida elevation:

```bash
curl --fail --show-error --silent \
  "https://${LCG_APP_HOST}/api/v1/elevation?latitude=30.4383&longitude=-84.2807&units=feet"
```

Finally, open the generated API documentation:

```text
https://lcg-elevation-dev-53679.azurewebsites.net/docs
```

## 12. Inspect or troubleshoot the running container

Show the selected image configuration:

```bash
az webapp config container show \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --output table
```

Enable container logs and stream them:

```bash
az webapp log config \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --docker-container-logging filesystem

az webapp log tail \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP"
```

Press `Ctrl+C` to stop following logs; that does not stop the Web App.

## Installation result

At this point Azure can run a manually selected image from ACR. The next chapter adds a second,
separate identity for GitHub Actions. That identity will be allowed to push a new image and
select it on the Web App. The Web App's existing system identity will remain responsible for
pulling and starting the selected image.

## Official references

- [Configure a custom container for Azure App Service](https://learn.microsoft.com/azure/app-service/configure-custom-container)
- [Use managed identity to pull an image from ACR](https://learn.microsoft.com/azure/app-service/configure-custom-container#use-managed-identity-to-pull-image-from-azure-container-registry)
- [Azure Container Registry roles and permissions](https://learn.microsoft.com/azure/container-registry/container-registry-rbac-built-in-roles-overview)
- [Azure CLI `az rest`](https://learn.microsoft.com/cli/azure/use-azure-cli-rest-command)