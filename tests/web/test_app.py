import os
from collections.abc import Callable

import pytest
from litestar import Litestar
from litestar.datastructures import State
from litestar.testing import AsyncTestClient

from tests.conftest import TmpYamlFile
from tests.plugins.curriculum import make_exercise, make_exercise_data
from wiederholen.school import Course, RedisStudentRecordBook, StudentRecordBook
from wiederholen.web.app import (
    check_answer,
    check_recall,
    client_error,
    create_app,
    next_exercise,
    request_recall,
)
from wiederholen.web.session import WebSessionStore

type WebAppFactory = Callable[[Course], Litestar]


@pytest.fixture
def web_app_factory(
    # Depended on purely to flush their DBs before the test, same as
    # elsewhere — student_record_book/web_session_store fixtures below are
    # deliberately *not* the objects handed to the app itself: AsyncTestClient
    # serves the app in its own event loop, and a Redis client whose
    # connection pool was already touched by the outer test's loop (the
    # fixtures' own flushdb()) can't be reused from a different one. Fresh
    # instances pointed at the same URL make first contact from whichever
    # loop actually serves the app.
    student_record_book: StudentRecordBook,
    web_session_store: WebSessionStore,
) -> WebAppFactory:
    def factory(course: Course) -> Litestar:
        return Litestar(
            route_handlers=[
                next_exercise,
                check_answer,
                request_recall,
                check_recall,
                client_error,
            ],
            state=State(
                {
                    "course": course,
                    "student_record_book": RedisStudentRecordBook.from_url(
                        os.environ["STUDENT_RECORD_STORAGE_URL"]
                    ),
                    "session_store": WebSessionStore.from_url(
                        os.environ["WEB_SESSION_STORAGE_URL"]
                    ),
                    "cookie_domain": "testserver.local",
                }
            ),
        )

    return factory


async def test_next_exercise_sets_a_cookie_for_a_new_visitor(
    web_app_factory: WebAppFactory,
) -> None:
    exercise = make_exercise(word="warten")
    app = web_app_factory(Course([exercise]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        response = await client.post(
            "/api/exercise/next", json={"topics": ["government"]}
        )

    assert response.status_code == 200
    assert response.cookies.get("wiederholen_student_id") is not None
    body = response.json()
    assert body["word"] == "warten"
    assert body["topic"] == "government"
    assert sorted(body["choices"]) == sorted(["auf", "für", "an", "um"])


async def test_next_exercise_hides_the_answer_field(
    web_app_factory: WebAppFactory,
) -> None:
    exercise = make_exercise(word="warten")
    app = web_app_factory(Course([exercise]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        response = await client.post(
            "/api/exercise/next", json={"topics": ["government"]}
        )

    assert "answer" not in response.json()


async def test_next_exercise_omits_choices_for_a_typed_input_exercise(
    web_app_factory: WebAppFactory,
) -> None:
    exercise = make_exercise(word="warten", distractors=[])
    app = web_app_factory(Course([exercise]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        response = await client.post(
            "/api/exercise/next", json={"topics": ["government"]}
        )

    assert response.json()["choices"] is None


async def test_next_exercise_reuses_an_existing_session_without_resetting_the_cookie(
    web_app_factory: WebAppFactory,
) -> None:
    exercise = make_exercise(word="warten")
    app = web_app_factory(Course([exercise]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        first = await client.post("/api/exercise/next", json={"topics": ["government"]})
        second = await client.post(
            "/api/exercise/next", json={"topics": ["government"]}
        )

    assert first.cookies.get("wiederholen_student_id") is not None
    assert "set-cookie" not in second.headers


async def test_next_exercise_restricts_to_the_given_topics(
    web_app_factory: WebAppFactory,
) -> None:
    government = make_exercise(word="warten", topic="government")
    partizip = make_exercise(word="sprechen", topic="partizip_ii")
    app = web_app_factory(Course([government, partizip]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        response = await client.post(
            "/api/exercise/next", json={"topics": ["partizip_ii"]}
        )

    assert response.json()["topic"] == "partizip_ii"


async def test_next_exercise_with_empty_topics_draws_from_the_whole_course(
    web_app_factory: WebAppFactory,
) -> None:
    government = make_exercise(word="warten", topic="government")
    app = web_app_factory(Course([government]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        response = await client.post("/api/exercise/next", json={"topics": []})

    assert response.json()["topic"] == "government"


async def test_next_exercise_returns_null_when_nothing_matches_the_topics(
    web_app_factory: WebAppFactory,
) -> None:
    exercise = make_exercise(word="warten", topic="government")
    app = web_app_factory(Course([exercise]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        response = await client.post(
            "/api/exercise/next", json={"topics": ["partizip_ii"]}
        )

    assert response.status_code == 200
    assert response.json() is None


async def test_check_answer_without_a_shown_exercise_is_a_conflict(
    web_app_factory: WebAppFactory,
) -> None:
    app = web_app_factory(Course([make_exercise()]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        response = await client.post("/api/exercise/check", json={"answer": "auf"})

    assert response.status_code == 409


async def test_check_answer_reports_correctness_and_explanation(
    web_app_factory: WebAppFactory,
) -> None:
    exercise = make_exercise(word="warten", answer="auf")
    app = web_app_factory(Course([exercise]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        await client.post("/api/exercise/next", json={"topics": ["government"]})
        response = await client.post("/api/exercise/check", json={"answer": "auf"})

    assert response.status_code == 200
    body = response.json()
    assert body["correct"] is True
    assert body["answer"] == "auf"
    assert body["explanation"] == exercise.explanation["ru"]


async def test_check_answer_reports_wrong_answers_too(
    web_app_factory: WebAppFactory,
) -> None:
    exercise = make_exercise(word="warten", answer="auf")
    app = web_app_factory(Course([exercise]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        await client.post("/api/exercise/next", json={"topics": ["government"]})
        response = await client.post("/api/exercise/check", json={"answer": "für"})

    assert response.json()["correct"] is False


async def test_check_answer_respects_the_requested_language(
    web_app_factory: WebAppFactory,
) -> None:
    exercise = make_exercise(word="warten", answer="auf")
    app = web_app_factory(Course([exercise]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        await client.post("/api/exercise/next", json={"topics": ["government"]})
        response = await client.post(
            "/api/exercise/check", json={"answer": "auf", "language": "en"}
        )

    assert response.json()["explanation"] == exercise.explanation["en"]


async def test_request_recall_returns_a_recall_question(
    web_app_factory: WebAppFactory,
) -> None:
    exercise = make_exercise(word="warten", recalls=True)
    app = web_app_factory(Course([exercise]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        await client.post("/api/exercise/next", json={"topics": ["government"]})
        await client.post("/api/exercise/check", json={"answer": "auf"})
        response = await client.post("/api/exercise/recall", json={})

    assert response.status_code == 200
    assert response.json()["question"] == exercise.recalls[0].question


async def test_request_recall_respects_the_requested_language(
    web_app_factory: WebAppFactory,
) -> None:
    exercise = make_exercise(
        word="warten",
        recalls=[{"hint": {"ru": "подсказка", "en": "hint"}}],
    )
    app = web_app_factory(Course([exercise]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        await client.post("/api/exercise/next", json={"topics": ["government"]})
        await client.post("/api/exercise/check", json={"answer": "auf"})
        response = await client.post("/api/exercise/recall", json={"language": "en"})

    assert response.json()["hint"] == "hint"


async def test_request_recall_without_a_shown_exercise_is_a_conflict(
    web_app_factory: WebAppFactory,
) -> None:
    app = web_app_factory(Course([make_exercise(recalls=True)]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        response = await client.post("/api/exercise/recall", json={})

    assert response.status_code == 409


async def test_check_recall_reports_correctness(
    web_app_factory: WebAppFactory,
) -> None:
    exercise = make_exercise(
        word="warten", recalls=[{"answer": ["Ich warte auf den Bus."]}]
    )
    app = web_app_factory(Course([exercise]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        await client.post("/api/exercise/next", json={"topics": ["government"]})
        await client.post("/api/exercise/check", json={"answer": "auf"})
        await client.post("/api/exercise/recall", json={})
        response = await client.post(
            "/api/exercise/recall/check", json={"answer": "Ich warte auf den Bus."}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["correct"] is True
    assert body["answer"] == "Ich warte auf den Bus."


async def test_check_recall_reports_wrong_answers_too(
    web_app_factory: WebAppFactory,
) -> None:
    exercise = make_exercise(
        word="warten", recalls=[{"answer": ["Ich warte auf den Bus."]}]
    )
    app = web_app_factory(Course([exercise]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        await client.post("/api/exercise/next", json={"topics": ["government"]})
        await client.post("/api/exercise/check", json={"answer": "auf"})
        await client.post("/api/exercise/recall", json={})
        response = await client.post(
            "/api/exercise/recall/check", json={"answer": "wrong"}
        )

    assert response.json()["correct"] is False


async def test_check_recall_without_a_shown_recall_is_a_conflict(
    web_app_factory: WebAppFactory,
) -> None:
    exercise = make_exercise(word="warten", recalls=True)
    app = web_app_factory(Course([exercise]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        await client.post("/api/exercise/next", json={"topics": ["government"]})
        await client.post("/api/exercise/check", json={"answer": "auf"})
        response = await client.post(
            "/api/exercise/recall/check", json={"answer": "anything"}
        )

    assert response.status_code == 409


async def test_client_error_accepts_a_report_with_a_status(
    web_app_factory: WebAppFactory,
) -> None:
    app = web_app_factory(Course([make_exercise()]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        response = await client.post(
            "/api/client-error", json={"step": "submitAnswer", "status": 409}
        )

    assert response.status_code == 204


async def test_client_error_accepts_a_report_without_a_status(
    web_app_factory: WebAppFactory,
) -> None:
    app = web_app_factory(Course([make_exercise()]))

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        response = await client.post("/api/client-error", json={"step": "loadNext"})

    assert response.status_code == 204


async def test_two_visitors_get_distinct_student_ids(
    web_app_factory: WebAppFactory,
) -> None:
    exercise = make_exercise()
    # Two separate app instances, not one shared between two clients: each
    # AsyncTestClient serves its app in its own event loop (see
    # web_app_factory's own comment above), so sharing one app's Redis
    # clients across two clients would hit the same cross-loop issue.
    first_app = web_app_factory(Course([exercise]))
    second_app = web_app_factory(Course([exercise]))

    async with (
        AsyncTestClient(
            app=first_app, base_url="https://testserver.local"
        ) as first_client,
        AsyncTestClient(
            app=second_app, base_url="https://testserver.local"
        ) as second_client,
    ):
        first = await first_client.post(
            "/api/exercise/next", json={"topics": ["government"]}
        )
        second = await second_client.post(
            "/api/exercise/next", json={"topics": ["government"]}
        )

    first_id = first.cookies.get("wiederholen_student_id")
    second_id = second.cookies.get("wiederholen_student_id")
    assert first_id is not None
    assert second_id is not None
    assert first_id != second_id


async def test_next_exercise_treats_a_foreign_cookie_as_a_new_visitor(
    web_app_factory: WebAppFactory,
) -> None:
    exercise = make_exercise(word="warten")
    app = web_app_factory(Course([exercise]))

    async with AsyncTestClient(
        app=app,
        base_url="https://testserver.local",
        cookies={"wiederholen_student_id": "telegram:999"},
    ) as client:
        response = await client.post(
            "/api/exercise/next", json={"topics": ["government"]}
        )

    assert response.status_code == 200
    new_id = response.cookies.get("wiederholen_student_id")
    assert new_id is not None
    assert new_id != "telegram:999"


async def test_create_app_builds_a_working_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_yaml_file: TmpYamlFile,
    student_record_book: StudentRecordBook,
    web_session_store: WebSessionStore,
) -> None:
    exercise_data = make_exercise_data(word="warten")
    monkeypatch.setenv("WEB_ALLOWED_ORIGINS", "https://example.com")
    monkeypatch.setenv("WEB_COOKIE_DOMAIN", "example.com")
    with tmp_yaml_file([exercise_data], filename="exercises.yaml") as path:
        monkeypatch.setenv("COURSE_PATH", str(path.parent))
        app = create_app()

    assert isinstance(app, Litestar)

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        response = await client.post(
            "/api/exercise/next", json={"topics": ["government"]}
        )

    assert response.status_code == 200
    assert response.json()["word"] == "warten"


async def test_widget_js_is_served_as_a_static_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_yaml_file: TmpYamlFile,
    student_record_book: StudentRecordBook,
    web_session_store: WebSessionStore,
) -> None:
    monkeypatch.setenv("WEB_ALLOWED_ORIGINS", "https://example.com")
    monkeypatch.setenv("WEB_COOKIE_DOMAIN", "example.com")
    with tmp_yaml_file([], filename="exercises.yaml") as path:
        monkeypatch.setenv("COURSE_PATH", str(path.parent))
        app = create_app()

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        response = await client.get("/widget/widget.js")

    assert response.status_code == 200
    assert "customElements.define" in response.text


async def test_standalone_app_is_served_at_the_root_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_yaml_file: TmpYamlFile,
    student_record_book: StudentRecordBook,
    web_session_store: WebSessionStore,
) -> None:
    monkeypatch.setenv("WEB_ALLOWED_ORIGINS", "https://example.com")
    monkeypatch.setenv("WEB_COOKIE_DOMAIN", "example.com")
    with tmp_yaml_file([], filename="exercises.yaml") as path:
        monkeypatch.setenv("COURSE_PATH", str(path.parent))
        app = create_app()

    async with AsyncTestClient(app=app, base_url="https://testserver.local") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "german-exercise-widget" in response.text
