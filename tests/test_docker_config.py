"""
Tests that validate docker-compose.yml structure.
No Docker daemon required — pure YAML validation.
"""
from pathlib import Path
import yaml
import pytest

COMPOSE_PATH = Path(__file__).resolve().parents[1] / "docker-compose.yml"


@pytest.fixture(scope="module")
def compose() -> dict:
    """Parse docker-compose.yml once for the whole module."""
    with open(COMPOSE_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_docker_compose_parses(compose: dict) -> None:
    """docker-compose.yml must parse successfully and return a dict."""
    assert isinstance(compose, dict), "docker-compose.yml did not parse to a dict"


def test_required_services_present(compose: dict) -> None:
    """api, frontend, and nginx services must all be defined."""
    services = compose.get("services", {})
    for name in ("api", "frontend", "nginx"):
        assert name in services, f"Required service '{name}' not found in docker-compose.yml"


def test_api_healthcheck_exists(compose: dict) -> None:
    """api service must declare a healthcheck block."""
    api = compose["services"]["api"]
    assert "healthcheck" in api, "api service is missing a 'healthcheck' key"


def test_api_healthcheck_start_period(compose: dict) -> None:
    """api healthcheck start_period must be '60s'."""
    start_period = compose["services"]["api"]["healthcheck"].get("start_period")
    assert start_period == "60s", f"Expected start_period '60s', got '{start_period}'"


def test_api_healthcheck_uses_curl(compose: dict) -> None:
    """api healthcheck test command must contain 'curl'."""
    test_cmd = compose["services"]["api"]["healthcheck"].get("test", [])
    # test can be a list like ["CMD", "curl", ...] or a shell string
    cmd_str = " ".join(test_cmd) if isinstance(test_cmd, list) else str(test_cmd)
    assert "curl" in cmd_str, f"Expected 'curl' in healthcheck test command, got: {cmd_str!r}"


def test_frontend_depends_on_api_healthy(compose: dict) -> None:
    """frontend must depend on api with condition: service_healthy."""
    depends = compose["services"]["frontend"].get("depends_on", {})
    # depends_on can be a dict (long form) or list (short form)
    if isinstance(depends, list):
        pytest.fail("frontend depends_on api must use long-form with condition, found list")
    api_dep = depends.get("api", {})
    condition = api_dep.get("condition")
    assert condition == "service_healthy", (
        f"Expected frontend depends_on api condition 'service_healthy', got '{condition}'"
    )


def test_nginx_port_80(compose: dict) -> None:
    """nginx service must expose port 80:80."""
    ports = compose["services"]["nginx"].get("ports", [])
    assert "80:80" in ports, f"Expected '80:80' in nginx ports, got: {ports}"


def test_network_defined(compose: dict) -> None:
    """bowtie-net network must be defined with driver: bridge."""
    networks = compose.get("networks", {})
    assert "bowtie-net" in networks, "Network 'bowtie-net' not defined in docker-compose.yml"
    driver = networks["bowtie-net"].get("driver")
    assert driver == "bridge", f"Expected 'bowtie-net' driver 'bridge', got '{driver}'"
