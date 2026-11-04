# Platform Infrastructure

Infrastructure as Code, GitOps and operational tooling for the shared platform infrastructure.

## 1. Overview

`platform-infrastructure` centralizes the provisioning, configuration, deployment and operation of shared infrastructure services.

It provides a common foundation for application projects, including:

- `ai-public-benefits-platform`
- `developer-content-creator`
- `platform-engineering-idp`

The repository follows Infrastructure as Code, GitOps, security-by-design and automation principles.

## 2. Architecture principles

- **Single source of truth:** infrastructure configuration is version-controlled.
- **Infrastructure as Code:** cloud resources are managed through OpenTofu and Terragrunt.
- **GitOps:** Kubernetes applications and platform services are reconciled through ArgoCD.
- **Secrets management:** credentials are stored in Vault and exposed through controlled integrations.
- **Reproducibility:** environments are defined declaratively.
- **Isolation:** application workloads are separated from shared infrastructure services.
- **Observability:** platform services expose metrics, logs and traces.

## 3. Technology stack

| Domain | Technologies |
|---|---|
| Local infrastructure | Podman, Podman Compose |
| Cloud infrastructure | OpenTofu, Terragrunt |
| Container orchestration | Kubernetes, k0s, GKE |
| Container registry | Harbor |
| Object storage | MinIO |
| GitOps | ArgoCD, Helm, Kustomize |
| Secrets management | HashiCorp Vault, External Secrets Operator |
| Policy enforcement | Kyverno, OPA |
| Observability | Prometheus, Grafana, Loki, Jaeger |
| CI/CD | GitHub Actions |

## 4. Repository structure

```text
platform-infrastructure/
├── docs/
│   ├── architecture/
│   ├── operations/
│   │   ├── harbor/
│   │   ├── minio/
│   │   ├── kubernetes/
│   │   └── disaster-recovery/
│   └── security/
├── infra/
│   ├── podman/
│   ├── kubernetes/
│   ├── opentofu/
│   │   ├── modules/
│   │   └── environments/
│   └── terragrunt/
├── gitops/
│   ├── bootstrap/
│   ├── applications/
│   └── projects/
├── policies/
│   ├── kyverno/
│   └── opa/
├── scripts/
│   ├── backup/
│   ├── restore/
│   └── validation/
└── .github/
    └── workflows/
```

## 5. Infrastructure scope

### Shared platform services

- Harbor: container image registry.
- MinIO: S3-compatible object storage.
- Vault: centralized secrets management.
- PostgreSQL and Redis: shared infrastructure dependencies where applicable.
- Kafka: event streaming infrastructure.
- Observability stack: monitoring, logging and distributed tracing.

### Kubernetes platform

- Local k0s cluster.
- GKE environments.
- ArgoCD deployment and application management.
- Helm and Kustomize configuration.
- External Secrets Operator integration.

### Cloud provisioning

OpenTofu modules and environment configurations manage cloud resources.

Terragrunt may be used to organize environment-specific deployments and reusable configuration.

## 6. Relationship with other repositories

| Repository | Responsibility |
|---|---|
| `platform-infrastructure` | Shared infrastructure and platform services |
| `platform-engineering-idp` | Backstage developer portal and self-service workflows |
| `ai-public-benefits-platform` | Public benefits business platform |
| `developer-content-creator` | AI-powered technical content generation |

Application repositories consume infrastructure services through documented interfaces and deployment contracts.

## 7. Security

- Never commit credentials, tokens or private keys.
- Store secrets in Vault.
- Use External Secrets Operator where appropriate.
- Apply least-privilege access policies.
- Keep environment-specific configuration isolated.
- Protect Terraform/OpenTofu state files.
- Review infrastructure changes before deployment.

## 8. Operational documentation

Operational procedures are maintained under `docs/operations/`.

Each critical platform service should have:

- Architecture and dependencies.
- Deployment procedure.
- Configuration reference.
- Backup procedure.
- Restoration procedure.
- Health checks.
- Troubleshooting guide.

## 9. Contribution workflow

1. Create a feature branch.
2. Implement infrastructure changes.
3. Run formatting and validation checks.
4. Review the proposed changes.
5. Open a pull request.
6. Deploy through the approved GitOps or CI/CD workflow.

Infrastructure changes must not be applied directly to production without review.

## 10. Roadmap

- [ ] Centralize Harbor and MinIO configuration.
- [ ] Document Harbor backup and recovery.
- [ ] Automate MinIO backups.
- [ ] Formalize PostgreSQL backup and restoration.
- [ ] Integrate Vault and External Secrets Operator.
- [ ] Centralize Kubernetes and ArgoCD configuration.
- [ ] Migrate reusable OpenTofu modules.
- [ ] Introduce infrastructure validation pipelines.
- [ ] Implement disaster recovery testing.
- [ ] Integrate platform services into Backstage.

---

**Status:** Initial repository foundation.