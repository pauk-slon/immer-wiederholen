import os


def pytest_configure(config) -> None:
    # The test suite must never emit real telemetry, regardless of what
    # OTEL_EXPORTER_OTLP_* happens to be set to in the environment (e.g. real
    # Honeycomb credentials via compose.override.yaml, since `docker compose
    # run bot pytest` shares the same service config as the real bot).
    os.environ["OTEL_SDK_DISABLED"] = "true"
