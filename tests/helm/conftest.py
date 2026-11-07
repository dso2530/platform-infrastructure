import subprocess
from pathlib import Path

import pytest
import yaml


ROOT_DIR = Path(__file__).resolve().parents[2]

CHART_DIR = ROOT_DIR / "helm" / "charts" / "spring-boot-microservice"
COMMON_VALUES = ROOT_DIR / "helm" / "environments" / "dev" / "common.yaml"

SERVICES = [
    {
        "id": "document-service",
        "release": "document-service",
        "namespace": "public-benefits",
        "values": (
            ROOT_DIR / "helm" / "environments" / "dev"
            / "ai-public-benefits" / "document-service.yaml"
        ),
        "fullname": "document-service",
        "container_port": 8085,
        "service_account": "document-service",
        "external_secret": True,
    },
    {
        "id": "repository-service",
        "release": "developer-content-creator-repository-service-dev",
        "namespace": "developer-content-creator",
        "values": (
            ROOT_DIR / "helm" / "environments" / "dev"
            / "developer-content-creator" / "repository-service.yaml"
        ),
        "fullname": "developer-content-creator-repository-service",
        "container_port": 8080,
        "service_account": "developer-content-creator",
        "external_secret": False,
    },
]


@pytest.fixture(scope="session")
def helm_binary():
    result = subprocess.run(
        ["helm", "version", "--short"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        pytest.fail("Helm n'est pas disponible sur cette machine.")

    return "helm"


@pytest.fixture(scope="session")
def chart_dir():
    assert CHART_DIR.is_dir(), f"Chart introuvable : {CHART_DIR}"
    return CHART_DIR


@pytest.fixture(scope="session")
def service_configs():
    assert COMMON_VALUES.is_file(), (
        f"Fichier commun introuvable : {COMMON_VALUES}"
    )

    for service in SERVICES:
        assert service["values"].is_file(), (
            f"Fichier de valeurs introuvable : {service['values']}"
        )

    return SERVICES


@pytest.fixture(params=SERVICES, ids=lambda service: service["id"])
def service_config(request):
    service = request.param

    assert COMMON_VALUES.is_file()
    assert service["values"].is_file(), (
        f"Fichier de valeurs introuvable : {service['values']}"
    )

    return service


def _build_render_command(
    helm_binary,
    chart_dir,
    service,
    overrides,
):
    return [
        helm_binary,
        "template",
        service["release"],
        str(chart_dir),
        "--namespace",
        service["namespace"],
        "-f",
        str(COMMON_VALUES),
        "-f",
        str(service["values"]),
        *overrides,
    ]


@pytest.fixture
def render_chart(helm_binary, chart_dir, service_config):
    def _render(*overrides):
        return subprocess.run(
            _build_render_command(
                helm_binary, chart_dir, service_config, overrides
            ),
            capture_output=True,
            text=True,
            check=False,
        )

    return _render


@pytest.fixture
def render_document_chart(helm_binary, chart_dir):
    service = SERVICES[0]

    def _render(*overrides):
        return subprocess.run(
            _build_render_command(
                helm_binary, chart_dir, service, overrides
            ),
            capture_output=True,
            text=True,
            check=False,
        )

    return _render


@pytest.fixture
def render_repository_chart(helm_binary, chart_dir):
    service = SERVICES[1]

    def _render(*overrides):
        return subprocess.run(
            _build_render_command(
                helm_binary, chart_dir, service, overrides
            ),
            capture_output=True,
            text=True,
            check=False,
        )

    return _render


@pytest.fixture
def parse_manifests():
    def _parse(content):
        return [
            document
            for document in yaml.safe_load_all(content)
            if document is not None
        ]

    return _parse
