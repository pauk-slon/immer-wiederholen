import os
from typing import Final

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.environment_variables import (
    OTEL_EXPORTER_OTLP_ENDPOINT,
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT,
)
from opentelemetry.sdk.resources import SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

default_tracer: Final = trace.get_tracer(__name__)


def _otlp_endpoint_configured() -> bool:
    return bool(
        os.environ.get(OTEL_EXPORTER_OTLP_ENDPOINT)
        or os.environ.get(OTEL_EXPORTER_OTLP_TRACES_ENDPOINT)
    )


def _resource_attributes() -> dict[str, str]:
    # The prod image sets APP_VERSION at build time (see Dockerfile)
    version = os.environ.get("APP_VERSION")
    return {SERVICE_VERSION: version} if version else {}


def configure_tracing() -> None:
    if not _otlp_endpoint_configured():
        return
    provider = TracerProvider(resource=Resource.create(_resource_attributes()))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)


def instrument_redis() -> None:
    RedisInstrumentor().instrument()
