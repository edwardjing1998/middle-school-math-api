# Configuration file inventory

| File | Purpose |
| --- | --- |
| `.github/workflows/deploy-openshift.yml` | GitHub Actions build and deployment workflow |
| `GITHUB-ACTIONS-OPENSHIFT.md` | Repository variables, secrets, and workflow setup |
| `OPENSHIFT-DEPLOYMENT.md` | Manual OpenShift deployment procedure |
| `Dockerfile` | CUDA Python production container image |
| `.dockerignore` | Excludes credentials and local artifacts from builds |
| `.env.example` | Local-development environment template |
| `openshift/imagestream.yaml` | Internal OpenShift image storage |
| `openshift/buildconfig.yaml` | Binary Docker build definition |
| `openshift/deployment.yaml` | Application pod and probe configuration |
| `openshift/service.yaml` | Internal port 8282 service |
| `openshift/route.yaml` | TLS external route |
| `openshift/configmap.yaml` | Non-sensitive runtime configuration |
| `openshift/secret.example.yaml` | Required secret-key template; never add real values |
| `openshift/pvc.yaml` | Persistent ChromaDB storage |
| `openshift/networkpolicy.yaml` | Application ingress policy |
| `openshift/gpu-patch.example.yaml` | Optional NVIDIA GPU request |
| `openshift/kustomization.yaml` | OpenShift resource collection |
| `common/db.py` | Snowflake environment-variable connection handling |

Real credentials belong in GitHub repository secrets and are created as an
OpenShift Secret by the workflow. They must not be committed to these files.
