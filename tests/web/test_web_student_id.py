import pytest

from wiederholen.web.web_student_id import NotAWebStudentIdError, WebStudentID


def test_generate_returns_a_web_prefixed_id() -> None:
    assert WebStudentID.generate().startswith("web:")


def test_generate_returns_a_fresh_id_each_time() -> None:
    assert WebStudentID.generate() != WebStudentID.generate()


def test_validate_accepts_a_web_prefixed_id() -> None:
    student_id = WebStudentID.generate()

    assert WebStudentID.validate(student_id) == student_id


def test_validate_rejects_an_id_from_a_different_frontend() -> None:
    with pytest.raises(NotAWebStudentIdError):
        WebStudentID.validate("telegram:123")
