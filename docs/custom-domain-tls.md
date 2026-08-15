# GoDaddy custom domain and Azure-managed TLS

This chapter maps the public hostname `elevation.logiccloudgeo.com` to the existing Azure
App Service and secures it with a free App Service managed certificate. It records the exact
installation used for this project, including verification commands and the empty-thumbprint
problem encountered in Azure Cloud Shell.

Complete the [Azure installation](azure-deployment.md) and
[GitHub Actions/OIDC deployment](github-actions-oidc.md) chapters first. The Web App should be
healthy at its default Azure hostname before DNS is changed.

## Installed design

| Purpose | Installed value |
| --- | --- |
| DNS provider | GoDaddy |
| Base domain | `logiccloudgeo.com` |
| Public API hostname | `elevation.logiccloudgeo.com` |
| CNAME host in GoDaddy | `elevation` |
| CNAME target | `lcg-elevation-dev-53679.azurewebsites.net` |
| Ownership TXT host in GoDaddy | `asuid.elevation` |
| Web App | `lcg-elevation-dev-53679` |
| App Service plan | `asp-lcg-elevation-dev` (`B1`) |
| TLS certificate | App Service managed certificate |
| TLS binding | SNI |

The CNAME controls where requests are routed. The `asuid` TXT record proves that this Azure
subscription is authorized to attach the hostname to an App Service. The certificate proves
the server's identity to HTTPS clients and encrypts traffic between the client and Azure's
App Service front end.

The default `azurewebsites.net` hostname remains available. Adding a custom hostname creates
another valid route to the same Web App; it does not replace or rename the Azure resource.

## Prerequisites

Before starting:

1. The Web App must respond successfully at
   `https://lcg-elevation-dev-53679.azurewebsites.net/health`.
2. The signed-in user must be able to modify the Web App.
3. The GoDaddy account must be able to modify DNS for `logiccloudgeo.com`.
4. The App Service plan must support custom domains and managed certificates. The installed
   Basic B1 plan satisfies this requirement.
5. Run the Azure commands in Azure Cloud Shell using Bash.

DNS changes are external to Azure and can take time to propagate. Do not add the hostname to
App Service until both required DNS records resolve publicly.

## 1. Select Azure and restore Cloud Shell variables

Cloud Shell variables disappear when the Bash session restarts. Defining them again does not
recreate or change any Azure resource.

```bash
az account set --subscription "LogicCloudGeo_ss"

LCG_RG="rg-lcg-elevation-dev"
LCG_PLAN="asp-lcg-elevation-dev"
LCG_APP="lcg-elevation-dev-53679"
LCG_CUSTOM_HOSTNAME="elevation.logiccloudgeo.com"
```

Verify the selected subscription:

```bash
az account show \
  --query "{Subscription:name,State:state,Tenant:tenantId}" \
  --output table
```

Verify that the plan is B1 or higher:

```bash
az appservice plan show \
  --resource-group "$LCG_RG" \
  --name "$LCG_PLAN" \
  --query "{Plan:name,Sku:sku.name,Location:location}" \
  --output table
```

Expected SKU:

```text
B1
```

## 2. Retrieve the Azure DNS values

Retrieve the Web App's default hostname:

```bash
LCG_DEFAULT_HOSTNAME=$(az webapp show \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --query defaultHostName \
  --output tsv)
```

Retrieve the domain-verification value:

```bash
LCG_DOMAIN_VERIFICATION_ID=$(az webapp show \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --query customDomainVerificationId \
  --output tsv)
```

Print the values needed in GoDaddy:

```bash
printf 'Custom hostname: %s\n' "$LCG_CUSTOM_HOSTNAME"
printf 'CNAME name: elevation\n'
printf 'CNAME value: %s\n' "$LCG_DEFAULT_HOSTNAME"
printf 'TXT name: asuid.elevation\n'
printf 'TXT value: %s\n' "$LCG_DOMAIN_VERIFICATION_ID"
```

Do not continue if either retrieved value is blank. The domain-verification value is not an
application password, but it should be copied exactly.

## 3. Create the GoDaddy DNS records

Open the DNS-management page for `logiccloudgeo.com` and add these two records:

| Type | Name | Value | TTL |
| --- | --- | --- | --- |
| CNAME | `elevation` | `lcg-elevation-dev-53679.azurewebsites.net` | GoDaddy default |
| TXT | `asuid.elevation` | The retrieved `customDomainVerificationId` | GoDaddy default |

In GoDaddy, enter only the relative names `elevation` and `asuid.elevation`; GoDaddy appends
`.logiccloudgeo.com`. Do not put `https://`, a path, or a trailing `/` in the CNAME value.

Keep the `asuid.elevation` TXT record after setup. It helps prevent another Azure subscription
from validating and taking over the hostname if the App Service association changes.

## 4. Verify public DNS propagation

In Cloud Shell, check the CNAME:

```bash
nslookup -type=CNAME elevation.logiccloudgeo.com
```

Expected relationship:

```text
elevation.logiccloudgeo.com canonical name = lcg-elevation-dev-53679.azurewebsites.net
```

Check the TXT record:

```bash
nslookup -type=TXT asuid.elevation.logiccloudgeo.com
```

The answer must contain the verification value retrieved from Azure. DNS responses may be
described as non-authoritative; that is normal for a recursive resolver.

Do not continue merely because the records are visible in the GoDaddy control panel. Azure
must be able to retrieve them through public DNS.

## 5. Add the custom hostname to the Web App

After both DNS queries succeed:

```bash
az webapp config hostname add \
  --resource-group "$LCG_RG" \
  --webapp-name "$LCG_APP" \
  --hostname "$LCG_CUSTOM_HOSTNAME"
```

Verify both hostnames:

```bash
az webapp config hostname list \
  --resource-group "$LCG_RG" \
  --webapp-name "$LCG_APP" \
  --query "[].{Hostname:name,Type:hostNameType,SSL:sslState}" \
  --output table
```

At this stage the custom hostname should be `Verified`, but its SSL column can still be blank.
That means DNS routing and domain ownership are configured, while TLS is not yet bound.

## 6. Create the App Service managed certificate

Run the certificate-creation command directly and inspect its complete output. Do not hide the
output in command substitution during the first attempt:

```bash
az webapp config ssl create \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --hostname "$LCG_CUSTOM_HOSTNAME" \
  --output json
```

The Azure CLI currently labels `ssl create` as a preview command. A preview warning is
informational; a JSON result containing the hostname and a nonblank `thumbprint` indicates
success.

Confirm that Azure can list the certificate:

```bash
az webapp config ssl list \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --query "[?subjectName=='elevation.logiccloudgeo.com'].{Name:name,Subject:subjectName,Thumbprint:thumbprint,State:provisioningState,Expires:expirationDate}" \
  --output table
```

Do not run the bind command if the result is empty or its thumbprint is blank. Wait a few
minutes and query again. Recreating the same certificate repeatedly is unnecessary once Azure
shows it.

## 7. Retrieve and validate the current thumbprint

Retrieve the certificate by its resource name:

```bash
LCG_CERT_THUMBPRINT=$(az webapp config ssl show \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --certificate-name "$LCG_CUSTOM_HOSTNAME" \
  --query thumbprint \
  --output tsv)
```

Inspect the value rather than relying only on a generic success message:

```bash
printf 'Certificate thumbprint: <%s>\n' "$LCG_CERT_THUMBPRINT"
printf 'Thumbprint length: %s\n' "${#LCG_CERT_THUMBPRINT}"
```

An Azure certificate thumbprint is normally a 40-character hexadecimal value. The angle
brackets make an empty value visible as `<>`.

## 8. Bind the certificate with SNI

Only run this variable-based command if the preceding output contains a real thumbprint:

```bash
az webapp config ssl bind \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --hostname "$LCG_CUSTOM_HOSTNAME" \
  --certificate-thumbprint "$LCG_CERT_THUMBPRINT" \
  --ssl-type SNI
```

SNI is appropriate for modern HTTPS clients and allows multiple TLS hostnames to share the
App Service front end.

### Recovery from `Certificate for thumbprint '' not found`

The empty quotation marks in this error are important:

```text
Certificate for thumbprint '' not found.
```

They mean the bind command received an empty shell value. They do not mean that Azure rejected
the certificate shown by the earlier create command. A Cloud Shell reconnection, a variable
defined in another shell, or a failed query can all leave the variable empty.

First inspect the certificate again:

```bash
az webapp config ssl show \
  --resource-group "rg-lcg-elevation-dev" \
  --name "lcg-elevation-dev-53679" \
  --certificate-name "elevation.logiccloudgeo.com" \
  --query "{Subject:subjectName,Thumbprint:thumbprint,Expires:expirationDate}" \
  --output table
```

Then copy the current 40-character thumbprint into an explicit bind command:

```bash
az webapp config ssl bind \
  --resource-group "rg-lcg-elevation-dev" \
  --name "lcg-elevation-dev-53679" \
  --hostname "elevation.logiccloudgeo.com" \
  --certificate-thumbprint "PASTE_CURRENT_40_CHARACTER_THUMBPRINT_HERE" \
  --ssl-type SNI \
  --output json
```

This explicit-value recovery succeeded during the original installation. Do not permanently
record a live thumbprint in automation because Azure can replace it when the managed
certificate renews.

## 9. Verify the SNI binding

```bash
az webapp config hostname list \
  --resource-group "$LCG_RG" \
  --webapp-name "$LCG_APP" \
  --query "[?name=='elevation.logiccloudgeo.com'].{Hostname:name,SSL:sslState,Thumbprint:thumbprint}" \
  --output table
```

Expected SSL state:

```text
SniEnabled
```

The thumbprint in this table should match the certificate that was bound. Do not proceed to
client testing until Azure reports `SniEnabled`.

## 10. Require HTTPS

Check the current setting:

```bash
az webapp show \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --query "{WebApp:name,HttpsOnly:httpsOnly}" \
  --output table
```

If `HttpsOnly` is not `true`, enable it:

```bash
az webapp update \
  --resource-group "$LCG_RG" \
  --name "$LCG_APP" \
  --https-only true
```

App Service terminates public TLS before forwarding a request to the container. Application
code that must know the original protocol should inspect the trusted forwarding headers
provided by App Service rather than expecting the container connection itself to use TLS.

## 11. Test the public service

Test the health endpoint without contacting the upstream elevation provider:

```bash
curl --fail --show-error --silent \
  "https://elevation.logiccloudgeo.com/health"
```

Test a live Florida elevation:

```bash
curl --fail --show-error --silent \
  "https://elevation.logiccloudgeo.com/api/v1/elevation?latitude=30.4383&longitude=-84.2807&units=feet"
```

Open the interactive API documentation:

```text
https://elevation.logiccloudgeo.com/docs
```

Optionally confirm that plain HTTP redirects to HTTPS:

```bash
curl --head "http://elevation.logiccloudgeo.com/health"
```

Expect a `Location` header whose value begins with
`https://elevation.logiccloudgeo.com/`. The exact redirect status code can vary.

## 12. Certificate renewal and DNS maintenance

The App Service managed certificate is maintained by Azure while it remains configured for
the custom domain. Its visible expiration date is not a prompt to buy a GoDaddy certificate.

For reliable renewal and safe domain ownership:

- keep the custom hostname attached to the Web App;
- keep the CNAME pointed to the Web App's default Azure hostname;
- keep the `asuid.elevation` TXT record;
- do not hard-code the current certificate thumbprint in deployment automation;
- periodically confirm that the hostname remains `SniEnabled` and the HTTPS health check works.

GitHub Actions does not need certificate permissions for normal application deployments.
Deployments change the container image selected by the Web App; the custom hostname and TLS
binding remain App Service configuration.

## 13. Troubleshooting map

### Azure says the hostname is not verified

Re-run both `nslookup` commands. Check for a misspelled GoDaddy host, a CNAME containing
`https://`, an incorrect verification value, or DNS propagation that has not completed.

### The hostname is verified but HTTPS shows a certificate warning

The DNS/hostname step is complete, but a certificate is not bound. Confirm that the certificate
exists and that the hostname's SSL state is `SniEnabled`.

### Certificate creation returns no certificate

Confirm that the hostname is already attached to the Web App, public DNS still points to the
app, the plan is Basic B1 or higher, and the certificate query is using the correct resource
group and Web App.

### The bind error contains an empty thumbprint

Do not recreate DNS or change Azure roles. Retrieve the current certificate, copy its
thumbprint, and use the explicit bind command in the recovery section.

### DNS works from one computer but not another

This is usually DNS caching or propagation. Wait for the configured TTL and query a public
resolver. On Windows, `ipconfig /flushdns` clears the local DNS resolver cache.

### HTTPS works but a deployment later fails

Treat this as a deployment/runtime problem, not a custom-domain problem. The GitHub Actions
workflow deploys to the Web App resource, and the hostname continues to route to whichever
container image that Web App is running.

## Installation result

The public endpoint is now:

```text
https://elevation.logiccloudgeo.com
```

The completed request path is:

1. Public DNS resolves the custom hostname through the GoDaddy CNAME.
2. Azure App Service recognizes the verified hostname.
3. The SNI binding selects the managed certificate and terminates TLS.
4. App Service routes the request to the running FastAPI container.
5. The application handles `/health`, `/docs`, or the requested API route.

The next development phase can use the stable public hostname for notebooks, topographic
profiles, ArcGIS Pro integration, and the future browser interface.

## Official references

- [Map an existing custom DNS name to Azure App Service](https://learn.microsoft.com/azure/app-service/app-service-web-tutorial-custom-domain)
- [Secure a custom domain with an App Service managed certificate](https://learn.microsoft.com/azure/app-service/tutorial-secure-domain-certificate)
- [Enable HTTPS for a custom domain](https://learn.microsoft.com/azure/app-service/configure-ssl-bindings)
- [Azure CLI `az webapp config ssl`](https://learn.microsoft.com/cli/azure/webapp/config/ssl)
- [Prevent dangling DNS and subdomain takeover](https://learn.microsoft.com/azure/app-service/reference-dangling-subdomain-prevention)
- [GoDaddy: add a CNAME record](https://www.godaddy.com/help/add-a-cname-record-19236)
- [GoDaddy: add a TXT record](https://www.godaddy.com/help/add-a-txt-record-19232)
