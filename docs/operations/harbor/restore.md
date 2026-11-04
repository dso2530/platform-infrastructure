# Harbor – Restore Procedure

## 1. Purpose and scope

This document describes the procedure for restoring Harbor after data loss, corruption or infrastructure failure.

It covers:

- PostgreSQL metadata restoration;
- MinIO registry object restoration;
- Harbor configuration and secrets recovery;
- Kubernetes application recovery;
- Functional validation.

Two scenarios are distinguished:

1. **Isolated recovery test:** validate backups without modifying the production environment.
2. **Production disaster recovery:** restore Harbor after a confirmed infrastructure or data failure.

The isolated recovery test must be completed before considering the disaster recovery procedure operational.

**Current recovery status:** PostgreSQL and MinIO have been restored and validated independently in isolated environments. A complete coordinated Harbor restoration, using a consistent PostgreSQL and MinIO recovery point, has not yet been validated.

## 2. Architecture and dependencies

Harbor relies on the following components:

| Component | Location | Recovery requirement |
|---|---|---|
| Harbor Core | Kubernetes / k0s | Helm configuration and deployment |
| Harbor Registry | Kubernetes / k0s | Registry configuration |
| Harbor Portal | Kubernetes / k0s | Application deployment |
| Harbor Jobservice | Kubernetes / k0s | Background jobs |
| PostgreSQL | External Podman service | Database dump |
| MinIO | External Podman service | Registry object backup |
| Redis | Kubernetes / k0s | Cache reconstruction |
| Trivy | Kubernetes / k0s | Vulnerability database reconstruction or refresh |
| Vault | External service | Secret recovery |
| External Secrets Operator | Kubernetes | Secret synchronization |

Current infrastructure:

- Harbor version: 2.15.4
- Helm chart: 1.19.4
- PostgreSQL: 17
- MinIO bucket: `harbor-registry`
- Kubernetes namespace: `harbor`
- Backup directory: `/home/mfo-dso/harbor-backups`
- Helm release: `harbor`
- Current Helm revision: 3

PostgreSQL and MinIO are external to the Kubernetes cluster.

Redis and Trivy are managed inside Kubernetes as StatefulSets.

The current Harbor Registry storage backend is S3-compatible storage backed by MinIO.

## 3. Preconditions

Before starting a restoration:

- Identify the backup date to restore.
- Verify the presence of the PostgreSQL dump.
- Verify the MinIO backup directory.
- Verify the SHA-256 manifest.
- Ensure sufficient disk space.
- Ensure PostgreSQL and MinIO are available.
- Ensure the required Harbor Helm configuration is available.
- Ensure the required secrets can be retrieved securely.
- Identify the exact PostgreSQL and MinIO recovery points.
- Confirm that the two backups are compatible with the same recovery point.

Never perform a production restoration without an approved maintenance window.

Never restore PostgreSQL and MinIO independently into a live Harbor installation.

A production restoration must be coordinated to avoid inconsistencies between database metadata and registry objects.

## 4. Backup selection and integrity verification

Set the backup directory:

```bash
BACKUP_DIR="/home/mfo-dso/harbor-backups/2026-11-04"
```

Check the backup structure:

```bash
find "$BACKUP_DIR" -maxdepth 4 -type f
```

Verify the SHA-256 manifest:

```bash
cd "$BACKUP_DIR"
sha256sum -c SHA256SUMS
```

Expected result:

- PostgreSQL dump: `OK`
- MinIO backup files: `OK`

If any checksum verification fails, stop the restoration.

A backup with failed integrity verification must not be used.

**Important:** the PostgreSQL and MinIO backups created on 2026-11-04 were not captured at exactly the same instant. Their independent integrity tests do not establish that they represent a fully coordinated recovery point.

## 5. PostgreSQL restoration

### 5.1 Restoration principles

PostgreSQL restoration must first be tested in an isolated database.

The production database `harbor` must never be overwritten during a recovery test.

The original dump uses PostgreSQL custom format (`pg_dump -Fc`).

### 5.2 Check the dump

```bash
BACKUP_DIR="/home/mfo-dso/harbor-backups/2026-11-04"

DUMP="$BACKUP_DIR/postgres/harbor-115118.dump"

test -s "$DUMP"

podman exec -i postgres pg_restore -l < "$DUMP"
```

The dump must be readable by `pg_restore`.

### 5.3 Create an isolated recovery database

Use a dedicated database name:

```text
harbor_restore_test
```

First, verify that the database does not already exist:

```bash
podman exec postgres \
  psql -U postgres -d postgres -tAc \
  "SELECT datname FROM pg_database WHERE datname = 'harbor_restore_test';"
```

If it does not exist, create it:

```bash
podman exec postgres \
  createdb -U postgres -T template0 harbor_restore_test
```

The test database is intentionally separate from the production database.

### 5.4 Restore the dump

```bash
BACKUP_DIR="/home/mfo-dso/harbor-backups/2026-11-04"

podman exec -i postgres \
  pg_restore \
    -U postgres \
    -d harbor_restore_test \
    --no-owner \
    --no-privileges \
    --exit-on-error \
  < "$BACKUP_DIR/postgres/harbor-115118.dump"
```

The `--no-owner` and `--no-privileges` options avoid requiring the original object ownership and grants during this isolated test.

Consequently, this test does not validate the original ownership and privilege configuration.

### 5.5 Validate the restored database

Check that the database exists:

```bash
podman exec postgres \
  psql -U postgres -d postgres -c \
  "SELECT datname FROM pg_database WHERE datname = 'harbor_restore_test';"
```

Check the restored schema:

```bash
podman exec postgres \
  psql -U postgres -d harbor_restore_test -c "\dt"
```

Inspect the number of restored tables and sequences:

```bash
podman exec postgres \
  psql -U postgres -d harbor_restore_test -tAc \
  "SELECT count(*) FROM information_schema.tables
   WHERE table_schema NOT IN ('pg_catalog', 'information_schema');"

podman exec postgres \
  psql -U postgres -d harbor_restore_test -tAc \
  "SELECT count(*) FROM information_schema.sequences
   WHERE sequence_schema NOT IN ('pg_catalog', 'information_schema');"
```

**Recorded isolated restoration results:**

| Check | Result |
|---|---|
| PostgreSQL dump integrity | Valid |
| Isolated restoration | Successful |
| Restored tables | 49 |
| Restored sequences | 47 |
| Original ownership and grants | Not validated |

A successful `pg_restore` is necessary but does not alone prove that Harbor can operate correctly with the restored database.

## 6. MinIO restoration

### 6.1 Restoration principles

MinIO stores Harbor registry objects, including manifests, layers and metadata links.

The restoration test must use a dedicated bucket:

```text
harbor-registry-restore-test
```

Never overwrite the production bucket `harbor-registry` during an isolated recovery test.

The source backup is:

```text
/home/mfo-dso/harbor-backups/2026-11-04/minio/harbor-registry
```

### 6.2 Prepare the recovery bucket

Using an authenticated MinIO client:

1. Connect to the isolated MinIO recovery target.
2. Verify access to the target.
3. Create the dedicated recovery bucket if it does not exist.
4. Verify that the target bucket is empty.

Credentials must be supplied through a secure mechanism.

They must never be stored in Git, command-line arguments or logs.

### 6.3 Restore objects

The restoration direction is:

```text
Local backup directory
        |
        v
MinIO recovery bucket
```

Use `mc mirror` without `--remove`:

```bash
mc mirror \
  /backup/harbor-registry \
  harbor-restore/harbor-registry-restore-test
```

The alias `harbor-restore` represents the authenticated recovery target.

The source path `/backup/harbor-registry` must correspond to the actual path accessible to the MinIO client.

The source backup must remain unchanged.

### 6.4 Validate restored objects

Compare:

- Number of objects;
- Total data size;
- Registry repository structure;
- Presence of the reference image blobs;
- Presence of manifest revision links.

The reference image is:

```text
developer-content-creator/repository-service
```

Reference manifest digest:

```text
sha256:85fb9769566f4f3e031cf5fb9974f979d6602d1e70461de81add578104189324
```

**Recorded isolated restoration results:**

| Check | Result |
|---|---|
| Restored objects | 74 |
| Restored data size | Approximately 149 MiB |
| Cryptographically checked blobs | 37 |
| Object restoration errors | None reported |

The MinIO restoration test is successful only if the expected registry objects are present in the recovery bucket and their integrity checks pass.

## 7. Secrets and configuration recovery

### 7.1 Secret management

Vault is the intended source of truth for Harbor storage credentials.

External Secrets Operator is intended to synchronize credentials into Kubernetes.

The current Kubernetes Secret is:

```text
harbor-registry-s3
```

Namespace:

```text
harbor
```

Expected keys:

- `REGISTRY_STORAGE_S3_ACCESSKEY`
- `REGISTRY_STORAGE_S3_SECRETKEY`

**Current status:** the ExternalSecret integration for Harbor remains to be completed and validated. Do not assume that the Harbor credentials can already be recovered automatically through External Secrets Operator.

Before a production restoration:

1. Verify that Vault is available.
2. Verify that the required credentials can be retrieved securely.
3. Complete or validate the ExternalSecret configuration.
4. Verify that the Kubernetes Secret `harbor-registry-s3` exists.
5. Verify that the Registry can access the MinIO backend.

Never display secret values in terminal output, documentation or Git.

### 7.2 Helm configuration

The current Harbor configuration is stored in:

```text
infra/kubernetes/harbor/values/values-production.yaml
```

It represents the configuration exported from Helm revision 3.

The configuration includes:

- External PostgreSQL connection;
- S3-compatible Registry storage;
- MinIO endpoint and bucket reference;
- Kubernetes NodePort exposure;
- Harbor replica configuration;
- Kubernetes Secret references.

The file contains Secret references, not the actual credentials.

Before applying it during disaster recovery, verify that:

- The PostgreSQL service is available.
- The MinIO endpoint is reachable.
- The bucket `harbor-registry` exists and contains the restored objects.
- The Kubernetes Secret `harbor-db` exists.
- The Kubernetes Secret `harbor-registry-s3` exists.
- The configured endpoint and external URL match the recovered environment.

Do not replace the current S3 configuration with an older filesystem configuration.

## 8. Kubernetes application recovery

### 8.1 Check the namespace and release

```bash
kubectl get namespace harbor

helm -n harbor list

helm -n harbor history harbor
```

Confirm the expected Helm chart and application versions before proceeding.

### 8.2 Restore the Harbor deployment

Once PostgreSQL, MinIO, configuration and secrets are ready, restore the Harbor application using the approved Helm configuration.

The reference configuration is:

```text
infra/kubernetes/harbor/values/values-production.yaml
```

The Helm chart repository is:

```text
https://helm.goharbor.io
```

The chart version is:

```text
1.19.4
```

The exact Helm upgrade or installation command must be reviewed against the recovered cluster state before execution.

Do not blindly reinstall Harbor over an existing release.

Do not use Helm rollback to a revision configured with the filesystem Registry backend while the active data resides in MinIO.

### 8.3 Validate Kubernetes workloads

Check all Harbor pods:

```bash
kubectl -n harbor get pods -o wide
```

Check deployments:

```bash
kubectl -n harbor get deployments
```

Check StatefulSets:

```bash
kubectl -n harbor get statefulsets
```

Check Harbor deployments:

```bash
kubectl -n harbor rollout status deployment/harbor-core

kubectl -n harbor rollout status deployment/harbor-jobservice

kubectl -n harbor rollout status deployment/harbor-nginx

kubectl -n harbor rollout status deployment/harbor-portal

kubectl -n harbor rollout status deployment/harbor-registry
```

Check Redis and Trivy StatefulSets:

```bash
kubectl -n harbor rollout status statefulset/harbor-redis

kubectl -n harbor rollout status statefulset/harbor-trivy
```

Check services:

```bash
kubectl -n harbor get services
```

All required workloads must be healthy before functional validation.

## 9. Functional validation

A successful infrastructure restoration must be followed by application-level checks.

### 9.1 Harbor API and interface

Verify that:

- The Harbor interface is accessible.
- Harbor Core responds correctly.
- Authentication works.
- Projects and repositories are visible.
- No critical errors are reported by Harbor components.

### 9.2 Registry validation

Validate the reference image:

```text
developer-content-creator/repository-service
```

Check the expected manifest digest:

```text
sha256:85fb9769566f4f3e031cf5fb9974f979d6602d1e70461de81add578104189324
```

Perform an authenticated image pull from Harbor.

The image digest must match the expected value.

### 9.3 Registry restart validation

The following test has already been performed independently:

- Registry restart;
- Image pull after restart;
- Digest verification.

The test succeeded.

This validates Registry persistence across a restart, but it does not replace a complete coordinated disaster recovery test.

### 9.4 Logs and events

Check Harbor events:

```bash
kubectl -n harbor get events --sort-by=.lastTimestamp
```

Inspect the logs of the main components if errors are reported:

```bash
kubectl -n harbor logs deployment/harbor-core --tail=100

kubectl -n harbor logs deployment/harbor-registry --tail=100

kubectl -n harbor logs deployment/harbor-jobservice --tail=100
```

Do not consider the restoration complete while critical errors remain unresolved.

## 10. Production disaster recovery procedure

Production disaster recovery must be performed as a coordinated operation.

The following sequence defines the required order. It is a controlled procedure, not an instruction to execute blindly.

1. Declare the incident and obtain approval for the maintenance window.
2. Identify the PostgreSQL and MinIO recovery points to use.
3. Verify the integrity of both backups.
4. Confirm that the selected backups represent a compatible recovery point.
5. Stop or isolate Harbor write operations to prevent new metadata or registry changes during recovery.
6. Restore PostgreSQL using the approved production recovery procedure.
7. Restore MinIO objects using the corresponding recovery point.
8. Recover Vault credentials and validate Kubernetes Secret synchronization.
9. Verify the Helm configuration and external dependencies.
10. Restore or reconcile Harbor workloads in Kubernetes.
11. Validate application health, repositories and image pulls.
12. Record the recovery results and obtain operational approval before reopening Harbor to users.

The production database and production bucket must not be overwritten during isolated recovery testing.

Any destructive production operation requires a separately reviewed procedure and an approved execution plan.

## 11. Recovery test results and limitations

### 11.1 Completed tests

| Test | Result |
|---|---|
| PostgreSQL dump integrity | Successful |
| Isolated PostgreSQL restoration | Successful |
| PostgreSQL tables restored | 49 |
| PostgreSQL sequences restored | 47 |
| MinIO isolated restoration | Successful |
| MinIO objects restored | 74 |
| MinIO blobs cryptographically checked | 37 |
| Registry restart | Successful |
| Image pull after Registry restart | Successful |
| Reference image digest verification | Successful |

### 11.2 Remaining work

The following activities remain necessary:

- Validate a coordinated PostgreSQL and MinIO recovery point.
- Validate a complete Harbor restoration from that coordinated recovery point.
- Validate original PostgreSQL ownership and grants.
- Complete and test the Harbor ExternalSecret integration.
- Validate a complete functional recovery, including authenticated image push and pull.
- Automate backup scheduling and retention.
- Document and measure the recovery time objective (RTO) and recovery point objective (RPO).

### 11.3 Recovery status

**Status: Partial recovery validation completed.**

The independent PostgreSQL and MinIO restoration tests are successful.

The complete coordinated Harbor disaster recovery procedure is not yet validated.

## 12. References

- `docs/operations/harbor/README.md`
- `docs/operations/harbor/architecture.md`
- `docs/operations/harbor/backup.md`
- `docs/operations/harbor/minio-migration.md`
- `docs/operations/harbor/rollback.md`
- `docs/operations/harbor/troubleshooting.md`
- `infra/kubernetes/harbor/values/values-production.yaml`