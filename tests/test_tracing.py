import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from wiederholen import tracing


def test_otlp_endpoint_not_configured_when_no_endpoint_env_vars_are_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)

    assert tracing._otlp_endpoint_configured() is False


def test_otlp_endpoint_configured_via_the_generic_endpoint_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)

    assert tracing._otlp_endpoint_configured() is True


def test_otlp_endpoint_configured_via_the_traces_specific_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector:4318")

    assert tracing._otlp_endpoint_configured() is True


def test_configure_tracing_is_a_noop_without_an_otlp_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    provider_before = trace.get_tracer_provider()

    tracing.configure_tracing()

    assert trace.get_tracer_provider() is provider_before


def test_configure_tracing_installs_a_provider_when_an_otlp_endpoint_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # trace.set_tracer_provider() only ever succeeds once per process (see
    # wiederholen/tracing.py's own module docstring-equivalent notes on
    # this), so calling the real one here would make this test's outcome
    # depend on whether some earlier test in the same session already
    # claimed it — same reason tests/plugins/tracing.py's own `tracer`
    # fixture builds its own provider directly instead of going through the
    # global registration. Spying on the setter instead sidesteps that
    # entirely.
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    installed_providers: list[object] = []
    monkeypatch.setattr(trace, "set_tracer_provider", installed_providers.append)

    tracing.configure_tracing()

    assert len(installed_providers) == 1
    assert isinstance(installed_providers[0], TracerProvider)


def _configure_tracing_and_get_resource_attributes(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    # Spies on the setter for the same reason as the test above.
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    monkeypatch.delenv("OTEL_RESOURCE_ATTRIBUTES", raising=False)
    installed_providers: list[TracerProvider] = []
    monkeypatch.setattr(trace, "set_tracer_provider", installed_providers.append)

    tracing.configure_tracing()

    return dict(installed_providers[0].resource.attributes)


def test_configure_tracing_reports_app_version_as_service_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_VERSION", "2026.10.3")

    attributes = _configure_tracing_and_get_resource_attributes(monkeypatch)

    assert attributes["service.version"] == "2026.10.3"


def test_configure_tracing_reports_no_service_version_without_app_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_VERSION", raising=False)

    attributes = _configure_tracing_and_get_resource_attributes(monkeypatch)

    assert "service.version" not in attributes


def test_instrument_redis_is_idempotent() -> None:
    # RedisInstrumentor().instrument() just logs a warning and no-ops on a
    # repeat call rather than raising — calling it twice here (both
    # wiederholen.bot.__main__/reminder.py and wiederholen.web.__main__ call
    # it once per process, but the test session imports/exercises both) is
    # exactly that repeat-call case, so this just confirms it doesn't blow up.
    tracing.instrument_redis()
    tracing.instrument_redis()
