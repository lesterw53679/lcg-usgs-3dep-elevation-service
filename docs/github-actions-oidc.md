# GitHub Actions deployment with Azure OIDC

This chapter converts the working manual Azure deployment into continuous deployment. A push
containing application or deployment changes on the repository's `main` branch will test the
Python project, build a Docker image, push that image to Azure Container Registry, point Azure
App Service at the new immutable image tag, and confirm that the deployed `/health` endpoint
responds successfully. Documentation-only pushes continue to run CI but skip the container
deployment.

The workflow uses OpenID Connect (OIDC). No Azure client password, ACR password, or App Service
publish profile is stored in GitHub.

## The design pattern

There are two independent managed identities. Keeping them separate is important.

| Actor | Identity | Azure permission | Scope | Why it needs the permission |
| --- | --- | --- | --- | --- |
| GitHub Actions deployment job | User-assigned identity `id-github-lcg-elevation-dev` | `AcrPush` | Only `acrlcgelevation53679` | Push the newly built image |
| GitHub Actions deployment job | Same user-assigned identity | `Website Contributor` | Only `lcg-elevation-dev-53679` | Select the new image on the Web App |
| Running App Service | Existing system-assigned Web App identity | `AcrPull` | Only `acrlcgelevation53679` | Pull and start the selected image |

Authentication answers **who is this?** Authorization answers **what may it do?**

1. GitHub creates a signed OIDC token for one workflow job.
2. The token states the repository and branch that requested it.
3. Microsoft Entra ID compares those claims with the federated credential configured on the
   user-assigned identity.
4. When they match exactly, Azure issues a short-lived access token.
5. Azure RBAC limits that token to the two assigned roles and resource scopes.
6. The token expires after the job. There is no long-lived Azure password to rotate or leak.

The trust subject used by this project is:

```text
repo:lesterw53679@115024906/lcg-usgs-3dep-elevation-service@1328287130:ref:refs/heads/main
```

GitHub repositories created after July 15, 2026 use this immutable subject format. The numeric
owner and repository IDs remain stable if either display name changes. The complete subject
deliberately prevents a workflow from an untrusted branch, fork, renamed replacement, or
different repository from using the deployment identity.

## What is CI and what is CD?

The repository contains two workflows:

| File | Role | Trigger |
| --- | --- | --- |
| `.github/workflows/ci.yml` | Continuous integration: lint and test code | Pull requests and pushes to `main` |
| `.github/workflows/azure-deploy.yml` | Continuous deployment: test, build, push, deploy, and verify | Non-documentation pushes to `main` and manual dispatch |

The deployment workflow repeats linting and tests intentionally. A deployment should be able
to prove the revision it is about to release even if another workflow was skipped, cancelled,
or reconfigured.

Every deployment image is tagged with the full Git commit SHA, for example:

```text
acrlcgelevation53679.azurecr.io/lcg-usgs-3dep-elevation-service:abc123...
```

The SHA tag is immutable by convention and connects the running image to an exact source-code
revision. The workflow does not depend on a mutable `latest` tag.

## Prerequisites

Complete the [Azure installation and first deployment](azure-deployment.md) first. Confirm:

- `/health` succeeds on the existing Web App.
- The Web App has a system-assigned identity.
- That runtime identity has `AcrPull` on the registry.
- The `bootstrap` image is already running.
- The GitHub default branch is `main`.
- The Azure account can create user-assigned identities and role assignments.

Run the Azure commands below in Azure Cloud Shell using Bash.

## 1. Select Azure and restore the deployment variables

```bash
az account set --subscription "LogicCloudGeo_ss"

LCG_LOCATION="eastus2"
LCG_RG="rg-lcg-elevation-dev"
LCG_ACR="acrlcgelevation53679"
LCG_APP="lcg-elevation-dev-53679"
LCG_IMAGE="lcg-usgs-3dep-elevation-service"

LCG_GITHUB_OWNER="lesterw53679"
LCG_GITHUB_OWNER_ID="115024906"
LCG_GITHUB_REPO="lcg-usgs-3dep-elevation-service"
LCG_GITHUB_REPO_ID="1328287130"
LCG_GITHUB_BRANCH="main"
LCG_GITHUB_IDENTITY="id-github-lcg-elevation-dev"
LCG_GITHUB_FEDERATED_CREDENTIAL="github-main-lcg-elevation-dev"

LCG_GITHUB_IMMUTABLE_SUBJECT="repo:${LCG_GITHUB_OWNER}@${LCG_GITHUB_OWNER_ID}/${LCG_GITHUB_REPO}@${LCG_GITHUB_REPO_ID}:ref:refs/heads/${LCG_GITHUB_BRANCH}"

LCG_SUBSCRIPTION_ID=$(az account show --query id --output tsv)
LCG_TENANT_ID=$(az account show --query tenantId --output tsv)
```

Verify the active subscription and the exact GitHub trust target:

```bash
az account show \
  --query "{Subscription:name,State:state,Tenant:tenantId}" \
  --output table

printf 'GitHub repository: %s/%s\n' "$LCG_GITHUB_OWNER" "$LCG_GITHUB_REPO"
printf 'Trusted branch: %s\n' "$LCG_GITHUB_BRANCH"
printf 'OIDC subject: %s\n' "$LCG_GITHUB_IMMUTABLE_SUBJECT"
```

OIDC claim matching is exact. Check the names, numeric IDs, and branch before creating the
credential. For this repository, the expected subject is:

```text
repo:lesterw53679@115024906/lcg-usgs-3dep-elevation-service@1328287130:ref:refs/heads/main
```

## 2. Create the GitHub deployment identity

Create one user-assigned managed identity in the development resource group:

```bash
az identity create \
  --resource-group "$LCG_RG" \
  --name "$LCG_GITHUB_IDENTITY" \
  --location "$LCG_LOCATION"
```

Capture its identifiers:

```bash
LCG_GITHUB_CLIENT_ID=$(az identity show \
  --resource-group "$LCG_RG" \
  --name "$LCG_GITHUB_IDENTITY" \
  --query clientId \
  --output tsv)

LCG_GITHUB_PRINCIPAL_ID=$(az identity show \
  --resource-group "$LCG_RG" \
  --name "$LCG_GITHUB_IDENTITY" \
  --query principalId \
  --output tsv)
```

These IDs have different jobs:

- `clientId` tells the GitHub login action which Azure identity to request.
- `principalId` identifies the corresponding service principal for Azure RBAC assignments.

Confirm both were retrieved:

```bash
test -n "$LCG_GITHUB_CLIENT_ID" && echo "GitHub identity client ID retrieved."
test -n "$LCG_GITHUB_PRINCIPAL_ID" && echo "GitHub identity principal ID retrieved."
```

Do not substitute one ID for the other in later commands.

## 3. Create the federated credential

The federated credential establishes trust; it does not grant resource permissions.

```bash
az identity federated-credential create \
  --resource-group "$LCG_RG" \
  --identity-name "$LCG_GITHUB_IDENTITY" \
  --name "$LCG_GITHUB_FEDERATED_CREDENTIAL" \
  --issuer "https://token.actions.githubusercontent.com" \
  --subject "$LCG_GITHUB_IMMUTABLE_SUBJECT" \
  --audiences "api://AzureADTokenExchange"
```

Verify the trust values:

```bash
az identity federated-credential show \
  --resource-group "$LCG_RG" \
  --identity-name "$LCG_GITHUB_IDENTITY" \
  --name "$LCG_GITHUB_FEDERATED_CREDENTIAL" \
  --query "{Name:name,Issuer:issuer,Subject:subject,Audiences:audiences}" \
  --output json
```

The subject must contain `lesterw53679@115024906`,
`lcg-usgs-3dep-elevation-service@1328287130`, and end in `ref:refs/heads/main`.

## 4. Resolve the two least-privilege scopes

Retrieve the resource IDs for the registry and Web App:

```bash
LCG_ACR_ID=$(az acr show \
  --resource-group "$LCG_RG" \
  --name "$LCG_ACR" \
  --query id \
  --output tsv)

LCG_WEBAPP_ID=$(az webapp show \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --query id \
  --output tsv)
```

Confirm both values exist:

```bash
test -n "$LCG_ACR_ID" && echo "Registry scope retrieved."
test -n "$LCG_WEBAPP_ID" && echo "Web App scope retrieved."
```

Scoping roles to these exact resources is safer than granting `Contributor` over the whole
subscription or resource group.

## 5. Grant permission to push images

```bash
az role assignment create \
  --assignee-object-id "$LCG_GITHUB_PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --scope "$LCG_ACR_ID" \
  --role "AcrPush"
```

`AcrPush` allows Docker image push and pull operations on this registry. It does not grant
permission to reconfigure the Web App or other Azure resources.

## 6. Grant permission to update only the Web App

```bash
az role assignment create \
  --assignee-object-id "$LCG_GITHUB_PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --scope "$LCG_WEBAPP_ID" \
  --role "Website Contributor"
```

`Website Contributor` lets the deployment job update the selected image on this Web App. The
scope is the individual app, not the complete resource group.

Azure RBAC changes can take several minutes to propagate. Creating both assignments before
configuring GitHub gives that propagation time naturally.

## 7. Verify the deployment identity's permissions

```bash
az role assignment list \
  --assignee "$LCG_GITHUB_PRINCIPAL_ID" \
  --all \
  --query "[].{Role:roleDefinitionName,Scope:scope}" \
  --output table
```

The result should contain exactly the intended deployment grants:

- `AcrPush` at the registry resource ID.
- `Website Contributor` at the Web App resource ID.

It may also show inherited permissions if the identity was previously assigned a broader role.
For this project, no broader role is required.

## 8. Create the GitHub Actions secrets

Open the repository:

```text
https://github.com/lesterw53679/lcg-usgs-3dep-elevation-service
```

In GitHub, go to **Settings → Secrets and variables → Actions → Secrets**. Create these three
repository secrets:

| Secret name | Value source |
| --- | --- |
| `AZURE_CLIENT_ID` | `$LCG_GITHUB_CLIENT_ID` |
| `AZURE_TENANT_ID` | `$LCG_TENANT_ID` |
| `AZURE_SUBSCRIPTION_ID` | `$LCG_SUBSCRIPTION_ID` |

To retrieve a value again in Cloud Shell:

```bash
printf 'AZURE_CLIENT_ID=%s\n' "$LCG_GITHUB_CLIENT_ID"
printf 'AZURE_TENANT_ID=%s\n' "$LCG_TENANT_ID"
printf 'AZURE_SUBSCRIPTION_ID=%s\n' "$LCG_SUBSCRIPTION_ID"
```

These three identifiers are not passwords, but GitHub's secret store hides them in logs and is
the convention used by the Azure login action. There is deliberately no `AZURE_CLIENT_SECRET`,
registry password, or publish-profile secret.

## 9. Create the GitHub Actions variables

On the same GitHub page, select the **Variables** tab and create:

| Variable name | Exact value |
| --- | --- |
| `ACR_LOGIN_SERVER` | `acrlcgelevation53679.azurecr.io` |
| `AZURE_WEBAPP_NAME` | `lcg-elevation-dev-53679` |

Variables are appropriate for non-sensitive deployment configuration. They remain visible to
repository administrators and can appear in workflow logs.

### Optional GitHub CLI method

If GitHub CLI is installed and authenticated on a trusted local computer, the same settings can
be created with these commands:

```bash
LCG_GITHUB_SLUG="lesterw53679/lcg-usgs-3dep-elevation-service"

gh secret set AZURE_CLIENT_ID \
  --repo "$LCG_GITHUB_SLUG" \
  --body "$LCG_GITHUB_CLIENT_ID"

gh secret set AZURE_TENANT_ID \
  --repo "$LCG_GITHUB_SLUG" \
  --body "$LCG_TENANT_ID"

gh secret set AZURE_SUBSCRIPTION_ID \
  --repo "$LCG_GITHUB_SLUG" \
  --body "$LCG_SUBSCRIPTION_ID"

gh variable set ACR_LOGIN_SERVER \
  --repo "$LCG_GITHUB_SLUG" \
  --body "acrlcgelevation53679.azurecr.io"

gh variable set AZURE_WEBAPP_NAME \
  --repo "$LCG_GITHUB_SLUG" \
  --body "lcg-elevation-dev-53679"
```

The GitHub web interface is equally valid and is easier to audit during the first setup.

## 10. Install the deployment workflow

The repository file is `.github/workflows/azure-deploy.yml`. Its important top-level controls
are:

```yaml
on:
  push:
    branches: [main]
    paths-ignore:
      - "docs/**"
      - "README.md"
      - "mkdocs.yml"
  workflow_dispatch:

permissions:
  contents: read
  id-token: write
```

`contents: read` lets the job check out the repository. `id-token: write` does not grant write
access to source code; it allows the job to ask GitHub's OIDC provider for the signed identity
token that Azure validates.

The `paths-ignore` list prevents a documentation-only commit from rebuilding and redeploying an
unchanged container. `ci.yml` still installs the documentation dependencies and runs
`mkdocs build --strict`, so documentation changes remain validated. Manual dispatch remains
available even when the most recent commit contains only documentation.

The workflow image repository must remain exactly:

```yaml
IMAGE_NAME: lcg-usgs-3dep-elevation-service
```

The initial workflow draft used `usgs-elevation-service`, which did not match the existing ACR
repository. The corrected name prevents the pipeline from creating and deploying an accidental
second repository.

Configure the Azure secrets and GitHub variables **before** pushing the updated workflow to
`main`. That push becomes the first automatic deployment.

## 11. Understand one workflow run

The deployment job performs these steps in order:

1. `actions/checkout` checks out the exact Git commit that triggered the job.
2. `actions/setup-python` provides Python 3.12 and pip caching.
3. The job installs the Linux GDAL development package required by the geospatial stack.
4. It installs the project, runs Ruff, and runs all non-integration tests.
5. `azure/login` exchanges the GitHub OIDC token for a short-lived Azure token.
6. `az acr login` uses that Azure identity to authenticate Docker to ACR.
7. Docker builds and pushes `lcg-usgs-3dep-elevation-service:<full-git-sha>`.
8. `azure/webapps-deploy` changes the Web App's selected image to that SHA tag.
9. App Service uses its own system identity and `AcrPull` role to retrieve the image.
10. The workflow retries the public `/health` endpoint for up to five minutes.

If any step fails, the following steps do not run and GitHub marks the deployment unsuccessful.

## 12. Run and observe the first deployment

After the workflow update reaches `main`, open the repository's **Actions** tab and select
**Deploy custom container to Azure App Service**.

For an explicit manual rerun:

1. Select **Run workflow**.
2. Leave the branch as `main`.
3. Select the green **Run workflow** button.

The branch must be `main` because the Azure federated credential trusts only the main-branch
subject. Selecting another branch should fail at Azure login; that is the intended security
boundary.

## 13. Verify the deployed revision from Azure

Restore the common Cloud Shell variables if necessary:

```bash
LCG_RG="rg-lcg-elevation-dev"
LCG_ACR="acrlcgelevation53679"
LCG_APP="lcg-elevation-dev-53679"
LCG_IMAGE="lcg-usgs-3dep-elevation-service"
```

List recent image tags:

```bash
az acr repository show-tags \
  --name "$LCG_ACR" \
  --repository "$LCG_IMAGE" \
  --orderby time_desc \
  --top 10 \
  --output table
```

The latest tag should be the 40-character commit SHA shown in the GitHub workflow run.

Inspect the Web App image setting:

```bash
az webapp config container show \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --query "[?name=='DOCKER_CUSTOM_IMAGE_NAME'].value" \
  --output tsv
```

Then verify health and a real elevation:

```bash
curl --fail --show-error --silent \
  "https://${LCG_APP}.azurewebsites.net/health"

curl --fail --show-error --silent \
  "https://${LCG_APP}.azurewebsites.net/api/v1/elevation?latitude=30.4383&longitude=-84.2807&units=feet"
```

## 14. Routine development after OIDC is working

The deployed Web App can retain multiple hostnames. The GitHub workflow updates the Web App's
container image and does not need to recreate DNS or TLS settings. See
[GoDaddy custom domain and Azure-managed TLS](custom-domain-tls.md) for the one-time public
hostname configuration.

The normal change path is:

1. Create a short-lived feature branch locally.
2. Make and test the change.
3. Push the branch and open a pull request.
4. Let `ci.yml` lint and test the pull request.
5. Review and merge the pull request into `main`.
6. A merge containing application or deployment changes triggers `azure-deploy.yml`.
7. Confirm the deployment job and its health check succeed. For documentation-only merges,
   confirm CI succeeds; no deployment run is expected.

Direct non-documentation pushes to `main` also deploy, but pull requests provide a clearer
review and audit trail.

## 15. Roll back to an earlier image

Because each successful build is tagged with its Git SHA, rollback means selecting a known-good
earlier tag. First list tags as shown above. Then set a specific tag:

```bash
LCG_ROLLBACK_TAG="replace-with-known-good-40-character-git-sha"

az webapp config container set \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --container-image-name "${LCG_ACR}.azurecr.io/${LCG_IMAGE}:${LCG_ROLLBACK_TAG}" \
  --container-registry-url "https://${LCG_ACR}.azurecr.io"

az webapp restart \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP"
```

Verify `/health` after rollback. The rollback changes Azure immediately but does not rewrite
Git history. Follow it with a source fix or a documented revert so the next deployment does not
reintroduce the bad revision.

## 16. Troubleshooting map

### `AADSTS700213: No matching federated identity record found`

Azure received a GitHub token, but the issuer, subject, or audience did not match. Check:

- The workflow ran from `main`.
- The owner is `lesterw53679`.
- The immutable owner ID is `115024906`.
- The repository is `lcg-usgs-3dep-elevation-service`.
- The immutable repository ID is `1328287130`.
- The federated subject ends with `ref:refs/heads/main`.
- The workflow has `id-token: write`.

The GitHub Actions login step prints the subject claim that Azure received. Compare that entire
value with the Azure credential; the comparison is exact. A name-only subject such as
`repo:lesterw53679/lcg-usgs-3dep-elevation-service:ref:refs/heads/main` does not match this
repository's immutable subject.

### Azure login says a secret is missing

Check the exact GitHub secret names. They are case-sensitive:

```text
AZURE_CLIENT_ID
AZURE_TENANT_ID
AZURE_SUBSCRIPTION_ID
```

OIDC does not use `AZURE_CLIENT_SECRET`.

### ACR login or Docker push is unauthorized

Verify `AcrPush` is assigned to the **GitHub user-assigned identity's principal ID** at the ACR
resource scope. Do not confuse it with the Web App system identity, which has `AcrPull`.

Allow several minutes after creating a role assignment before retrying.

### Web App deployment is forbidden

Verify `Website Contributor` is assigned to the GitHub identity at the Web App resource scope.
The deployment workflow does not need subscription-wide `Contributor`.

### Deployment succeeds but the container cannot be pulled

This is normally a runtime-identity problem rather than a GitHub problem. Recheck:

- The Web App system identity is enabled.
- That system identity has `AcrPull` on ACR.
- `acrUseManagedIdentityCreds` is true.
- ACR `authentication-as-arm` is enabled.
- The image name contains the full repository and SHA tag.

### The health-check step times out

Open the App Service log stream and look for Python import, package, port, or upstream startup
errors. Confirm `WEBSITES_PORT=8000`. The `/health` route does not call USGS, so an upstream USGS
outage alone should not make this check fail.

### Manual workflow works only from `main`

That is expected. A `workflow_dispatch` run presents the selected branch in its OIDC subject.
This installation trusts only `main`.

## 17. Extending the pattern to staging and production

Do not widen the development identity to every future app. Create a separate App Service,
user-assigned deployment identity, federated credential, and narrowly scoped role assignments
for each environment. Production can later use a protected GitHub Environment and an
environment-specific OIDC subject.

This gives each environment its own:

- deployment approval policy;
- Azure permissions;
- Web App and health endpoint;
- rollback history;
- failure boundary.

## Official references

- [Azure App Service custom-container deployment with GitHub Actions](https://learn.microsoft.com/azure/app-service/deploy-container-github-action)
- [Use Azure Login with OpenID Connect](https://learn.microsoft.com/azure/developer/github/connect-from-azure-openid-connect)
- [GitHub OIDC concepts](https://docs.github.com/actions/concepts/security/openid-connect)
- [GitHub OIDC subject reference](https://docs.github.com/actions/reference/openid-connect-reference)
- [Migrate GitHub credentials to immutable subjects](https://learn.microsoft.com/entra/workload-id/workload-identities-github-immutable-subjects)
- [Azure Login action](https://github.com/Azure/login)
- [Azure Web Apps Deploy action](https://github.com/Azure/webapps-deploy)
- [User-assigned identity federated-credential CLI](https://learn.microsoft.com/cli/azure/identity/federated-credential)
- [Azure built-in roles for Web and Mobile](https://learn.microsoft.com/azure/role-based-access-control/built-in-roles/web-and-mobile)
