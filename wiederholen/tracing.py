# Generic OpenTelemetry setup shared by every process that talks to Redis
# and/or wants a configured span exporter — wiederholen.bot.__main__,
# wiederholen.bot.reminder, and wiederholen.web.__main__ all call
# configure_tracing()/instrument_redis() from here. Deliberately a top-level
# module, a sibling of school/bot/web, not tucked inside wiederholen.bot: the
# bot package's own tracing.py (TracingMiddleware, aiogram-Update-specific)
# is bot-only by nature, but this generic setup is exactly the kind of thing
# wiederholen.web would otherwise have had to import from wiederholen.bot to
# get — which the "sibling of wiederholen.bot, not a dependency of it or vice
# versa" rule (see CLAUDE.md's "Web frontend" section) rules out. Living here
# instead means both bot and web depend on this shared module without either
# depending on the other.
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
