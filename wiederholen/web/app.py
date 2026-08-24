import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from litestar import Litestar, Request, post
from litestar.config.cors import CORSConfig
from litestar.datastructures import State
from litestar.exceptions import HTTPException
from litestar.plugins.opentelemetry import OpenTelemetryConfig, OpenTelemetryPlugin
from litestar.response import Response
from litestar.static_files import create_static_files_router

_STATIC_DIR: Final = Path(__file__).parent / "static"

from wiederholen.school import (
    Course,
    Exercise,
    Language,
    StudentID,
    StudentRecordBook,
    Tutor,
)
from wiederholen.web.bootstrap import load_web_course_and_storage
from wiederholen.web.session import WebSessionStore
from wiederholen.web.web_student_id import NotAWebStudentIdError, WebStudentID

_COOKIE_NAME: Final = "wiederholen_student_id"
_COOKIE_MAX_AGE_SECONDS: Final = 60 * 60 * 24 * 365  # a year — this is the whole point


@dataclass
class NextExerciseRequest:
    topics: list[str]
    language: Language = "ru"


@dataclass
class ExerciseDTO:
    word: str
    topic: str
    question: str
    # None for a typed-input exercise (no distractors) — the widget should
    # render a text field instead of multiple-choice buttons.
    choices: list[str] | None
    description: str | None
    instruction: str | None


@dataclass
class CheckAnswerRequest:
    answer: str
    language: Language = "ru"


@dataclass
class CheckAnswerResponse:
    correct: bool
    recall: str
    answer: str
    explanation: str


def _student_id_from_request(request: Request) -> tuple[StudentID, bool]:
    """Returns `(student_id, is_new)` — `is_new` tells the caller whether it
    still needs to set the cookie in its response.
    """
    raw = request.cookies.get(_COOKIE_NAME)
    if raw is not None:
        try:
            return WebStudentID.validate(raw), False
        except NotAWebStudentIdError:
            pass
    return WebStudentID.generate(), True


def _remember_student_id(
    response: Response, student_id: StudentID, *, cookie_domain: str
) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=student_id,
        domain=cookie_domain,
        max_age=_COOKIE_MAX_AGE_SECONDS,
        secure=True,
        httponly=True,
        samesite="lax",
    )


def _to_exercise_dto(
    exercise: Exercise, course: Course, language: Language
) -> ExerciseDTO:
    choices: list[str] | None = None
    if exercise.distractors:
        choices = [*exercise.distractors, exercise.answer]
        random.shuffle(choices)
    return ExerciseDTO(
        word=exercise.word,
        topic=exercise.topic,
        question=exercise.question,
        choices=choices,
        description=exercise.description[language] if exercise.description else None,
        instruction=course.topic_instructions.get(exercise.topic, {}).get(language),
    )


@post("/api/exercise/next", status_code=200)
async def next_exercise(
    data: NextExerciseRequest, request: Request, state: State
) -> Response[ExerciseDTO | None]:
    course: Course = state["course"]
    student_record_book: StudentRecordBook = state["student_record_book"]
    session_store: WebSessionStore = state["session_store"]
    student_id, is_new = _student_id_from_request(request)

    # An empty topics list means "no restriction" — the whole course — not
    # "restrict to nothing": Course.restricted_to([]) would otherwise filter
    # every exercise out, since an empty frozenset matches no topic. This is
    # what lets the standalone app practice across the whole course without
    # needing to know (or send) every topic name up front, unlike a landing
    # page's embedded widget, which always names its own specific topics.
    restricted_course = course.restricted_to(data.topics) if data.topics else course
    async with student_record_book.check_out(student_id) as student_record:
        exercise = Tutor(restricted_course, student_record).next_exercise()

    body: ExerciseDTO | None = None
    if exercise is not None:
        await session_store.set_shown_exercise(student_id, exercise)
        body = _to_exercise_dto(exercise, course, data.language)

    response = Response(body)
    if is_new:
        _remember_student_id(response, student_id, cookie_domain=state["cookie_domain"])
    return response


@post("/api/exercise/check", status_code=200)
async def check_answer(
    data: CheckAnswerRequest, request: Request, state: State
) -> Response[CheckAnswerResponse]:
    course: Course = state["course"]
    student_record_book: StudentRecordBook = state["student_record_book"]
    session_store: WebSessionStore = state["session_store"]
    # No is_new/cookie handling here, unlike next_exercise: a successful
    # check_answer() requires a shown exercise to already exist for this
    # exact student_id, which only next_exercise() ever creates — so by the
    # time this call succeeds, the caller has necessarily already been
    # handed (and sent back) a real cookie from an earlier request.
    student_id, _ = _student_id_from_request(request)

    shown_exercise = await session_store.get_shown_exercise(student_id)
    if shown_exercise is None:
        raise HTTPException(
            status_code=409,
            detail="no exercise currently shown for this student",
        )

    async with student_record_book.check_out(student_id) as student_record:
        mark = Tutor(course, student_record).check_answer(shown_exercise, data.answer)

    return Response(
        CheckAnswerResponse(
            correct=mark.is_correct,
            recall=mark.recall.value,
            answer=shown_exercise.answer,
            explanation=shown_exercise.explanation[data.language],
        )
    )


def create_app() -> Litestar:
    course, student_record_book, session_store = load_web_course_and_storage()
    widget_router = create_static_files_router(
        path="/widget", directories=[_STATIC_DIR]
    )
    # The standalone app (index.html/app.js — no fixed topics of its own,
    # see next_exercise()'s empty-topics handling above) at the root path.
    # html_mode serves index.html for "/", the same way a plain static host
    # would. A distinct name from widget_router's own default ("static") —
    # Litestar requires route handler names to be unique within one app.
    app_router = create_static_files_router(
        path="/",
        directories=[_STATIC_DIR / "app"],
        html_mode=True,
        name="app",
    )
    return Litestar(
        route_handlers=[next_exercise, check_answer, widget_router, app_router],
        state=State(
            {
                "course": course,
                "student_record_book": student_record_book,
                "session_store": session_store,
                "cookie_domain": os.environ["WEB_COOKIE_DOMAIN"],
            }
        ),
        cors_config=CORSConfig(
            allow_origins=os.environ["WEB_ALLOWED_ORIGINS"].split(","),
            allow_credentials=True,
        ),
        plugins=[OpenTelemetryPlugin(OpenTelemetryConfig())],
    )
