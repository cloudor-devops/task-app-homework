# System Architecture Diagram

```
                        +--------------------------+
                        |      Developer / Git     |
                        |  (Push to GitHub repo)   |
                        +------------+-------------+
                                     |
                                     | monitors repo (GitOps)
                                     v
+--------------------------------------------------------------------------+
|  Minikube Cluster (Docker driver)                                        |
|                                                                          |
|  +---------------------------+     +----------------------------------+  |
|  |  argocd namespace         |     |  production namespace            |  |
|  |                           |     |                                  |  |
|  |  +---------------------+  |     |  +----------------------------+  |  |
|  |  |   ArgoCD Server     |--+---->|  |  Deployment (task-app)     |  |  |
|  |  |  (auto-sync k8s/)   |  |     |  |  - 2 replicas (min)       |  |  |
|  |  +---------------------+  |     |  |  - RollingUpdate strategy  |  |  |
|  +---------------------------+     |  |  - Startup/liveness/       |  |  |
|                                    |  |    readiness probes        |  |  |
|  +---------------------------+     |  |  - CPU/memory limits       |  |  |
|  |  ingress-nginx namespace  |     |  |  - securityContext         |  |  |
|  |                           |     |  |    (nonRoot, readOnly,     |  |  |
|  |  +---------------------+  |     |  |     no privilege esc.)     |  |  |
|  |  | NGINX Ingress       |  |     |  |  - preStop hook (graceful) |  |  |
|  |  | Controller          |  |     |  |  - envFrom: ConfigMap      |  |  |
|  |  +---------------------+  |     |  |  - Prometheus annotations  |  |  |
|  +---------------------------+     |  |  - K8s recommended labels  |  |  |
|                                    |  +----------------------------+  |  |
|                                    |                                  |  |
|                                    |  +----------------------------+  |  |
|                                    |  |  ServiceAccount (task-app)  |  |  |
|                                    |  |  - automountToken: false    |  |  |
|                                    |  +----------------------------+  |  |
|                                    |                                  |  |
|                                    |  +----------------------------+  |  |
|                                    |  |  ConfigMap (task-app)       |  |  |
|                                    |  |  - APP_VERSION, ENVIRONMENT |  |  |
|                                    |  +----------------------------+  |  |
|                                    |                                  |  |
|                                    |  +----------------------------+  |  |
|                                    |  |  HPA                       |  |  |
|                                    |  |  - min: 2, max: 5 replicas |  |  |
|                                    |  |  - CPU 70% / Memory 80%    |  |  |
|                                    |  +----------------------------+  |  |
|                                    |                                  |  |
|                                    |  +----------------------------+  |  |
|                                    |  |  PodDisruptionBudget       |  |  |
|                                    |  |  - minAvailable: 1         |  |  |
|                                    |  +----------------------------+  |  |
|                                    |                                  |  |
|                                    |  +----------------------------+  |  |
|                                    |  |  NetworkPolicy             |  |  |
|                                    |  |  - ingress from nginx only |  |  |
|                                    |  +----------------------------+  |  |
|                                    |                                  |  |
|                                    |  +----------------------------+  |  |
|                                    |  |  LimitRange                |  |  |
|                                    |  |  - default CPU/mem limits  |  |  |
|                                    |  +----------------------------+  |  |
|                                    |                                  |  |
|                                    |  +----------------------------+  |  |
|                                    |  |  ResourceQuota             |  |  |
|                                    |  |  - max 2 CPU, 1Gi mem,    |  |  |
|                                    |  |    10 pods                 |  |  |
|                                    |  +----------------------------+  |  |
|                                    |                                  |  |
|                                    |  +------------+  +------------+  |  |
|                                    |  |  Service   |  | TLS Secret |  |  |
|                                    |  | :80 -> 8080|  | (self-sign)|  |  |
|                                    |  +------+-----+  +------+-----+  |  |
|                                    |         |               |        |  |
|                                    |  +------v---------------v------+ |  |
|                                    |  |  Ingress (nginx)            | |  |
|                                    |  |  - TLS termination          | |  |
|                                    |  |  - HTTP 80 -> HTTPS 443     | |  |
|                                    |  +-----------------------------+ |  |
|                                    +----------------------------------+  |
|                                              |                           |
+----------------------------------------------+---------------------------+
                                               |
                                     https://task-app.local
                                               |
                                          +----v----+
                                          |  User   |
                                          +---------+
```

## Flow

1. **Developer** pushes code/manifests to the GitHub repository.
2. **Terraform** provisions the cluster infrastructure: namespaces, TLS secret, ArgoCD (via Helm), and the ArgoCD Application CR.
3. **ArgoCD** watches the `k8s/` directory in the repo and auto-syncs all resources to the `production` namespace.
4. **Ingress** (NGINX) terminates TLS using the self-signed certificate and redirects HTTP to HTTPS.
5. **User** accesses the API at `https://task-app.local`.

## High Availability & Resilience

- **HPA** auto-scales pods (2-5) based on CPU/memory utilization, backed by metrics-server.
- **PodDisruptionBudget** guarantees at least 1 pod remains available during voluntary disruptions (node drains, upgrades).
- **Rolling update** strategy with `maxUnavailable: 0` ensures zero-downtime deployments.
- **Graceful shutdown** via `preStop` hook gives in-flight requests 5 seconds to complete before pod termination.
- **`terminationGracePeriodSeconds: 30`** gives the pod up to 30 seconds for graceful shutdown.

## Health Monitoring

- **Startup probe** prevents liveness probe from killing slow-starting pods during boot.
- **Liveness probe** on `/healthz` detects deadlocked or frozen pods and triggers restart.
- **Readiness probe** on `/healthz` removes unhealthy pods from Service traffic.
- **Prometheus annotations** expose metrics scraping endpoint for observability.

## Security

- **SecurityContext** enforces non-root, read-only filesystem, and no privilege escalation.
- **Dedicated ServiceAccount** with `automountServiceAccountToken: false` removes unnecessary K8s API access.
- **NetworkPolicy** restricts pod ingress to traffic from the NGINX ingress controller only.

## Resource Governance

- **Resource requests/limits** on each container prevent runaway CPU/memory consumption.
- **LimitRange** sets default resource limits for any container in the namespace without explicit limits.
- **ResourceQuota** caps total namespace resources (2 CPU, 1Gi memory, 10 pods max).

## Configuration Management

- **ConfigMap** externalizes application configuration (version, environment) from code.
- **Kubernetes recommended labels** (`app.kubernetes.io/*`) provide standardized metadata for tooling and operational visibility.
