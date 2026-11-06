def resources_by_kind(manifests):
    return {
        manifest["kind"]: manifest
        for manifest in manifests
    }


def test_document_service_renders_expected_resources(
    render_chart,
    parse_manifests,
):
    result = render_chart()

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))

    assert "ServiceAccount" in resources
    assert "Service" in resources
    assert "Deployment" in resources
    assert "ExternalSecret" in resources


def test_document_service_uses_configured_image(
    render_chart,
    parse_manifests,
):
    result = render_chart()

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))

    containers = resources["Deployment"]["spec"]["template"]["spec"]["containers"]

    assert containers[0]["image"] == (
        "demo.goharbor.io/ai-public-benefits/"
        "document-service:sha-d68e470"
    )


def test_deployment_has_configured_probes(
    render_chart,
    parse_manifests,
):
    result = render_chart()

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))

    containers = resources["Deployment"]["spec"]["template"]["spec"]["containers"]
    container = containers[0]

    assert "startupProbe" in container
    assert "livenessProbe" in container
    assert "readinessProbe" in container


def test_hpa_disabled_keeps_replica_count(
    render_chart,
    parse_manifests,
):
    result = render_chart()

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))

    deployment = resources["Deployment"]

    assert deployment["spec"]["replicas"] == 1
    assert "HorizontalPodAutoscaler" not in resources


def test_hpa_enabled_removes_fixed_replica_count(
    render_chart,
    parse_manifests,
):
    result = render_chart("--set", "autoscaling.enabled=true")

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))

    deployment = resources["Deployment"]

    assert "replicas" not in deployment["spec"]
    assert "HorizontalPodAutoscaler" in resources

    hpa = resources["HorizontalPodAutoscaler"]

    assert hpa["spec"]["scaleTargetRef"]["name"] == "document-service"


def test_external_secrets_disabled(
    render_chart,
    parse_manifests,
):
    result = render_chart("--set", "externalSecrets.enabled=false")

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))

    assert "ExternalSecret" not in resources


def test_external_secrets_reference_vault(
    render_chart,
    parse_manifests,
):
    result = render_chart()

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))

    external_secret = resources["ExternalSecret"]

    assert external_secret["spec"]["secretStoreRef"]["name"] == "vault"
    assert external_secret["spec"]["secretStoreRef"]["kind"] == (
        "ClusterSecretStore"
    )

    assert external_secret["spec"]["target"]["name"] == (
        "document-service-secrets"
    )

    secret_keys = {
        item["secretKey"]
        for item in external_secret["spec"]["data"]
    }

    assert "STORAGE_ACCESS_KEY" in secret_keys
    assert "STORAGE_SECRET_KEY" in secret_keys
    assert "JWT_SECRET" in secret_keys


def test_service_can_be_disabled(
    render_chart,
    parse_manifests,
):
    result = render_chart("--set", "service.enabled=false")

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))

    assert "Service" not in resources
    assert "Deployment" in resources


def test_empty_image_repository_is_rejected(
    render_chart,
):
    result = render_chart(
        "--set-string",
        "image.repository=",
    )

    assert result.returncode != 0
    assert "image/repository" in result.stderr