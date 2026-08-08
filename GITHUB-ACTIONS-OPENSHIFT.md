# GitHub Actions with repository-level configuration

The workflow is located at:

```text
.github/workflows/deploy-openshift.yml
```

It uses repository-level GitHub Actions variables and secrets. It does not use
a GitHub Environment and does not require Quay, GHCR, or another external
registry. GitHub uploads the exact commit to an OpenShift Binary BuildConfig,
and OpenShift stores the resulting image in its internal ImageStream.

## Required repository variables

Open the GitHub repository and navigate to:

```text
Settings > Secrets and variables > Actions > Variables
```

Add:

| Variable | Example |
| --- | --- |
| `OPENSHIFT_SERVER` | `https://api.cluster.example.com:6443` |
| `OPENSHIFT_NAMESPACE` | `education-production` |

Find these values with:

```bash
oc whoami --show-server
oc project -q
```

## Optional repository variables

Add these under the same **Variables** tab when their values differ from the
defaults:

| Variable | Default |
| --- | --- |
| `SNOWFLAKE_WAREHOUSE` | `GLOBAL_FINANCE_WAREHOUSE` |
| `SNOWFLAKE_DATABASE` | `EDU_AI_APP` |
| `SNOWFLAKE_SCHEMA` | `WEBAPP` |
| `SNOWFLAKE_ROLE` | Empty |
| `SNOWFLAKE_CORTEX_SEARCH_SERVICE` | `EDU_AI_APP.WEBAPP.STD_ITEM_SEARCH_SERVICE` |
| `SNOWFLAKE_CORTEX_COMPLETION_MODEL` | `llama3.3-70b` |
| `OPENAI_MODEL` | `gpt-4o-mini` |

## Required repository secrets

Navigate to:

```text
Settings > Secrets and variables > Actions > Secrets
```

Add:

| Secret | Purpose |
| --- | --- |
| `OPENSHIFT_TOKEN` | Authenticates GitHub Actions to OpenShift |
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier |
| `SNOWFLAKE_USER` | Snowflake service user |
| `SNOWFLAKE_PASSWORD` | Snowflake service-user password |

Optional:

| Secret | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Required only by the older Chroma/OpenAI `/api/rag/ask` endpoint |

The workflow does not require:

```text
IMAGE_REGISTRY
IMAGE_NAMESPACE
IMAGE_NAME
REGISTRY_USERNAME
REGISTRY_PASSWORD
```

## Create the OpenShift deployment identity

Run as an OpenShift administrator, replacing the namespace:

```bash
oc project education-production
oc create serviceaccount github-actions-deployer
oc adm policy add-role-to-user edit \
  -z github-actions-deployer \
  -n education-production
```

Generate a token:

```bash
oc create token github-actions-deployer --duration=8760h
```

Save the output as the repository secret `OPENSHIFT_TOKEN`. Use the shortest
practical lifetime. A custom least-privilege Role is preferable to `edit` for
long-term production use.

The service account needs access to:

- Builds and BuildConfigs
- ImageStreams and ImageStreamTags
- Deployments
- Services and Routes
- ConfigMaps and Secrets
- PersistentVolumeClaims
- NetworkPolicies

## Run the workflow

Push to `main`, or open:

```text
GitHub > Actions > Build and deploy with OpenShift internal registry
       > Run workflow
```

The workflow:

1. Logs into OpenShift.
2. Creates or updates the Secret and ConfigMap.
3. Applies the ImageStream, Binary BuildConfig, and runtime resources.
4. Archives the exact Git commit.
5. Uploads it using `oc start-build --from-archive`.
6. Waits for the internal image build.
7. Resolves and deploys the built image reference.
8. Waits for rollout and prints resource status.

## Cluster prerequisites

The cluster must support BuildConfig Docker builds, have its internal image
registry enabled, and allow build pods to access the NVIDIA base image and
Python package sources. The CUDA/RAPIDS build is large; the BuildConfig permits
up to 16 GiB memory and 40 GiB ephemeral storage.

If the cluster uses a private API certificate authority, add an
`OPENSHIFT_CA_DATA` repository secret and add this input to `oc-login`:

```yaml
certificate_authority_data: ${{ secrets.OPENSHIFT_CA_DATA }}
```

## Security recommendations

- Rotate OpenShift, Snowflake, and OpenAI credentials regularly.
- Do not enable shell tracing with `set -x`.
- Pin third-party actions to reviewed commit SHAs when required by policy.
- For protected production deployment approvals, migrate these values to a
  GitHub Environment later and restore `environment: production` in the job.
