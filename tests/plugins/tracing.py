import os

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Tracer


def pytest_configure(config) -> None:
    # The test suite must never emit real telemetry, regardless of what
    # OTEL_EXPORTER_OTLP_* happens to be set to in the environment (e.g. real
    # Honeycomb credentials via compose.override.yaml, since `docker compose
    # run bot pytest` shares the same service config as the real bot).
    os.environ["OTEL_SDK_DISABLED"] = "true"


@pytest.fixture
def exporter() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
def tracer(
    exporter: InMemorySpanExporter,
    monkeypatch: pytest.MonkeyPatch,
) -> Tracer:
    # The test session forces OTEL_SDK_DISABLED=true (see pytest_configure
    # above) so nothing ever exports real telemetry — tests that need to
    # verify actual span content build a live, recording provider of their
    # own instead, so opt back in for just this provider's construction.
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test")
