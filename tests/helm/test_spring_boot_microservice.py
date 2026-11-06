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
    assert "image.repository" in result.stderr


def test_pod_anti_affinity_disabled(
    render_chart,
    parse_manifests,
):
    result = render_chart()

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))

    pod_spec = resources["Deployment"]["spec"]["template"]["spec"]

    assert "affinity" not in pod_spec or (
        "podAntiAffinity" not in pod_spec["affinity"]
    )


def test_pod_anti_affinity_preferred(
    render_chart,
    parse_manifests,
):
    result = render_chart(
        "--set", "podAntiAffinity.enabled=true",
        "--set", "podAntiAffinity.type=preferred",
    )

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))

    pod_spec = resources["Deployment"]["spec"]["template"]["spec"]

    anti_affinity = pod_spec["affinity"]["podAntiAffinity"]

    terms = anti_affinity["preferredDuringSchedulingIgnoredDuringExecution"]

    assert len(terms) == 1
    assert terms[0]["weight"] == 100
    assert (
        terms[0]["podAffinityTerm"]["topologyKey"]
        == "kubernetes.io/hostname"
    )


def test_pod_anti_affinity_required(
    render_chart,
    parse_manifests,
):
    result = render_chart(
        "--set", "podAntiAffinity.enabled=true",
        "--set", "podAntiAffinity.type=required",
    )

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))

    pod_spec = resources["Deployment"]["spec"]["template"]["spec"]

    anti_affinity = pod_spec["affinity"]["podAntiAffinity"]

    terms = anti_affinity["requiredDuringSchedulingIgnoredDuringExecution"]

    assert len(terms) == 1
    assert (
        terms[0]["topologyKey"]
        == "kubernetes.io/hostname"
    )


def test_pod_anti_affinity_rejects_invalid_weight(
    render_chart,
):
    result = render_chart(
        "--set", "podAntiAffinity.enabled=true",
        "--set", "podAntiAffinity.type=preferred",
        "--set", "podAntiAffinity.weight=101",
    )

    assert result.returncode != 0
    assert "podAntiAffinity" in result.stderr

def test_hpa_renders_cpu_and_memory_metrics(
    render_chart,
    parse_manifests,
):
    result = render_chart(
        "--set", "autoscaling.enabled=true",
        "--set", "autoscaling.minReplicas=2",
        "--set", "autoscaling.maxReplicas=5",
    )

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))

    hpa = resources["HorizontalPodAutoscaler"]
    metrics = hpa["spec"]["metrics"]

    assert len(metrics) == 2
    assert metrics[0]["resource"]["name"] == "cpu"
    assert metrics[0]["resource"]["target"]["averageUtilization"] == 70

    assert metrics[1]["resource"]["name"] == "memory"
    assert metrics[1]["resource"]["target"]["averageUtilization"] == 80


def test_hpa_can_disable_memory_metric(
    render_chart,
    parse_manifests,
):
    result = render_chart(
        "--set", "autoscaling.enabled=true",
        "--set", "autoscaling.minReplicas=1",
        "--set", "autoscaling.maxReplicas=3",
        "--set", "autoscaling.targetMemoryUtilizationPercentage=null",
    )

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))

    hpa = resources["HorizontalPodAutoscaler"]
    metrics = hpa["spec"]["metrics"]

    assert len(metrics) == 1
    assert metrics[0]["resource"]["name"] == "cpu"


def test_hpa_rejects_min_replicas_greater_than_max(
    render_chart,
):
    result = render_chart(
        "--set", "autoscaling.enabled=true",
        "--set", "autoscaling.minReplicas=4",
        "--set", "autoscaling.maxReplicas=3",
    )

    assert result.returncode != 0

    assert (
        "autoscaling.minReplicas must be less than or equal to autoscaling.maxReplicas"
        in result.stderr
    )

def test_hpa_rejects_missing_cpu_request(render_chart):
    result = render_chart(
        "--set", "autoscaling.enabled=true",
        "--set", "autoscaling.minReplicas=2",
        "--set", "autoscaling.maxReplicas=5",
        "--set", "resources.requests.cpu=null",
    )

    assert result.returncode != 0
    assert "missing property 'cpu'" in result.stderr


def test_hpa_rejects_missing_memory_request_when_memory_metric_enabled(
    render_chart,
):
    result = render_chart(
        "--set", "autoscaling.enabled=true",
        "--set", "autoscaling.minReplicas=2",
        "--set", "autoscaling.maxReplicas=5",
        "--set", "resources.requests.memory=null",
    )

    assert result.returncode != 0
    assert "missing property 'memory'" in result.stderr


def test_hpa_accepts_missing_memory_request_when_memory_metric_disabled(
    render_chart,
    parse_manifests,
):
    result = render_chart(
        "--set", "autoscaling.enabled=true",
        "--set", "autoscaling.minReplicas=2",
        "--set", "autoscaling.maxReplicas=5",
        "--set", "autoscaling.targetMemoryUtilizationPercentage=null",
        "--set", "resources.requests.memory=null",
    )

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))
    hpa = resources["HorizontalPodAutoscaler"]

    metrics = hpa["spec"]["metrics"]

    assert len(metrics) == 1
    assert metrics[0]["resource"]["name"] == "cpu"


def test_pdb_disabled_by_default(
    render_chart,
    parse_manifests,
):
    result = render_chart()

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))

    assert "PodDisruptionBudget" not in resources


def test_pdb_renders_min_available(
    render_chart,
    parse_manifests,
):
    result = render_chart(
        "--set", "podDisruptionBudget.enabled=true",
    )

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))
    pdb = resources["PodDisruptionBudget"]

    assert pdb["apiVersion"] == "policy/v1"
    assert pdb["spec"]["minAvailable"] == 1
    assert "maxUnavailable" not in pdb["spec"]


def test_pdb_renders_max_unavailable(
    render_chart,
    parse_manifests,
):
    result = render_chart(
        "--set", "podDisruptionBudget.enabled=true",
        "--set", "podDisruptionBudget.minAvailable=null",
        "--set", "podDisruptionBudget.maxUnavailable=1",
    )

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))
    pdb = resources["PodDisruptionBudget"]

    assert pdb["spec"]["maxUnavailable"] == 1
    assert "minAvailable" not in pdb["spec"]


def test_pdb_supports_percentage(
    render_chart,
    parse_manifests,
):
    result = render_chart(
        "--set", "podDisruptionBudget.enabled=true",
        "--set", "podDisruptionBudget.minAvailable=50%",
    )

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))
    pdb = resources["PodDisruptionBudget"]

    assert pdb["spec"]["minAvailable"] == "50%"


def test_pdb_rejects_both_strategies(
    render_chart,
):
    result = render_chart(
        "--set", "podDisruptionBudget.enabled=true",
        "--set", "podDisruptionBudget.minAvailable=1",
        "--set", "podDisruptionBudget.maxUnavailable=1",
    )

    assert result.returncode != 0


def test_pdb_rejects_missing_strategy(
    render_chart,
):
    result = render_chart(
        "--set", "podDisruptionBudget.enabled=true",
        "--set", "podDisruptionBudget.minAvailable=null",
        "--set", "podDisruptionBudget.maxUnavailable=null",
    )

    assert result.returncode != 0


def test_pdb_rejects_invalid_percentage(
    render_chart,
):
    result = render_chart(
        "--set", "podDisruptionBudget.enabled=true",
        "--set", "podDisruptionBudget.minAvailable=150%",
    )

    assert result.returncode != 0


def test_pdb_rejects_negative_value(
    render_chart,
):
    result = render_chart(
        "--set", "podDisruptionBudget.enabled=true",
        "--set", "podDisruptionBudget.minAvailable=-1",
    )

    assert result.returncode != 0


def test_pod_anti_affinity_rejects_conflicting_configuration(
    render_chart,
):
    result = render_chart(
        "--set", "podAntiAffinity.enabled=true",
        "--set", "affinity.podAntiAffinity.requiredDuringSchedulingIgnoredDuringExecution[0].topologyKey=kubernetes.io/hostname",
    )

    assert result.returncode != 0
    assert "Configure pod anti-affinity either through" in result.stderr

def test_network_policy_disabled_by_default(
    render_chart,
    parse_manifests,
):
    result = render_chart()

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))

    assert "NetworkPolicy" not in resources

def test_network_policy_enabled_without_rules_blocks_both_directions(
    render_chart,
    parse_manifests,
):
    result = render_chart(
        "--set", "networkPolicy.enabled=true",
    )

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))
    policy = resources["NetworkPolicy"]

    assert policy["spec"]["policyTypes"] == ["Ingress", "Egress"]
    assert "ingress" not in policy["spec"]
    assert "egress" not in policy["spec"]

def test_network_policy_renders_ingress_rule(
    render_chart,
    parse_manifests,
):
    result = render_chart(
        "--set", "networkPolicy.enabled=true",
        "--set", "networkPolicy.ingress[0].ports[0].protocol=TCP",
        "--set", "networkPolicy.ingress[0].ports[0].port=8080",
    )

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))
    policy = resources["NetworkPolicy"]

    assert policy["spec"]["ingress"][0]["ports"][0]["port"] == 8080


def test_network_policy_renders_egress_rule(
    render_chart,
    parse_manifests,
):
    result = render_chart(
        "--set", "networkPolicy.enabled=true",
        "--set", "networkPolicy.egress[0].ports[0].protocol=TCP",
        "--set", "networkPolicy.egress[0].ports[0].port=5432",
    )

    assert result.returncode == 0, result.stderr

    resources = resources_by_kind(parse_manifests(result.stdout))
    policy = resources["NetworkPolicy"]

    assert policy["spec"]["egress"][0]["ports"][0]["port"] == 5432