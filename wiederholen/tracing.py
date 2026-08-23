import os
from typing import Final

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.environment_variables import (
    OTEL_EXPORTER_OTLP_ENDPOINT,
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

default_tracer: Final = trace.get_tracer(__name__)


def _otlp_endpoint_configured() -> bool:
    return bool(
        os.environ.get(OTEL_EXPORTER_OTLP_ENDPOINT)
        or os.environ.get(OTEL_EXPORTER_OTLP_TRACES_ENDPOINT)
    )


def configure_tracing() -> None:
    # OTLPSpanExporter() defaults to http://localhost:4318, a convention for a
    # local collector sidecar this project's deployment doesn't have — without
    # an explicit endpoint there's nowhere valid to export to, so skip wiring
    # up a real provider at all rather than let it retry into the void.
    if not _otlp_endpoint_configured():
        return
    provider = TracerProvider(resource=Resource.create())
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)


def instrument_redis() -> None:
    RedisInstrumentor().instrument()
