import uvicorn

from wiederholen.tracing import configure_tracing, instrument_redis
from wiederholen.web.app import create_app


def main() -> None:
    # Same setup as wiederholen.bot.__main__/wiederholen.bot.reminder — this
    # process talks to Redis via RedisStudentRecordBook/WebSessionStore too,
    # and both calls are safe no-ops without a configured OTEL endpoint (see
    # CLAUDE.md's "Tracing" section).
    configure_tracing()
    instrument_redis()
    uvicorn.run(create_app(), host="0.0.0.0", port=8000)


if __name__ == "__main__":  # pragma: no cover
    main()
