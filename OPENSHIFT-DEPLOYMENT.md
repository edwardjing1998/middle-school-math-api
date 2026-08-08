# OpenShift deployment

The application uses an OpenShift Binary BuildConfig and internal ImageStream.
No external image registry is required. For GitHub Actions automation, see
`GITHUB-ACTIONS-OPENSHIFT.md`.

The REST API listens on port `8282`. `GET /health` is used for startup,
readiness, and liveness probes.

## Architecture notes

- OpenShift builds the Dockerfile and stores the image internally.
- ChromaDB persists at `/app/data/chroma` on a 5 GiB PVC.
- The Deployment uses one replica and `Recreate` because embedded ChromaDB
  should have only one writer.
- CUDA/RAPIDS makes the build large; GPU runtime scheduling remains optional.
- Real credentials and `.env` files are excluded.

## 1. Select an OpenShift project

```bash
oc login https://api.your-cluster.example.com:6443
oc project your-project
```

## 2. Create the runtime Secret

```bash
oc create secret generic middle-school-math-api-secrets \
  --from-literal=SNOWFLAKE_ACCOUNT='your-account-identifier' \
  --from-literal=SNOWFLAKE_USER='your-service-user' \
  --from-literal=SNOWFLAKE_PASSWORD='your-password' \
  --from-literal=OPENAI_API_KEY='your-openai-api-key'
```

The OpenAI key is needed only for `/api/rag/ask`.

## 3. Review configuration

Edit `openshift/configmap.yaml` for your Snowflake warehouse, database, schema,
role, Cortex service, and completion model. If the cluster has no default
StorageClass, add `storageClassName` to `openshift/pvc.yaml`.

## 4. Apply resources

```bash
oc apply -k openshift/
```

The initial Deployment can remain pending until the first image is built.

## 5. Build from the local Git commit

```bash
git archive --format=tar.gz --output=/tmp/source.tar.gz HEAD

oc start-build middle-school-math-api \
  --from-archive=/tmp/source.tar.gz \
  --follow \
  --wait
```

The ImageStream trigger should update the Deployment. To deploy the exact image
reference explicitly:

```bash
IMAGE_REFERENCE="$(
  oc get imagestreamtag middle-school-math-api:latest \
    -o jsonpath='{.image.dockerImageReference}'
)"

oc set image deployment/middle-school-math-api \
  api="${IMAGE_REFERENCE}"

oc rollout status deployment/middle-school-math-api --timeout=20m
```

## 6. Verify

```bash
oc get builds
oc get imagestream middle-school-math-api
oc get pods
oc get pvc middle-school-math-api-chroma
oc get route middle-school-math-api
```

```bash
APP_ROUTE="$(oc get route middle-school-math-api -o jsonpath='{.spec.host}')"
curl "https://${APP_ROUTE}/health"
```

Internal callers in the namespace can use:

```text
http://middle-school-math-api:8282
```

## Optional NVIDIA GPU

Only apply the GPU patch if the cluster has NVIDIA GPU Operator support:

```bash
oc patch deployment middle-school-math-api \
  --type=strategic \
  --patch-file openshift/gpu-patch.example.yaml
```

## Build capacity

The BuildConfig currently requests up to 16 GiB memory and 40 GiB ephemeral
storage. Adjust `openshift/buildconfig.yaml` for cluster quotas and node
capacity. Build nodes require outbound access to the NVIDIA base image and
Python package sources.

## Scaling warning

Do not increase replicas while using embedded ChromaDB. For horizontal scaling,
move vector data to Snowflake Cortex Search, Qdrant, or a separate Chroma
service.
