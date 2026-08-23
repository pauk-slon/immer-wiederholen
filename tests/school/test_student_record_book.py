from unittest.mock import patch

import pytest

from wiederholen.school.student_record_book import StudentRecordBook


async def test_open_yields_an_empty_dict_for_an_unknown_student(
    student_record_book: StudentRecordBook,
) -> None:
    async with student_record_book.check_out("111") as student_record:
        assert student_record == {}


async def test_open_persists_mutations(student_record_book: StudentRecordBook) -> None:
    async with student_record_book.check_out("111") as student_record:
        student_record["marker"] = "a"

    async with student_record_book.check_out("111") as student_record:
        assert student_record == {"marker": "a"}


async def test_open_persists_mutations_even_if_the_body_raises(
    student_record_book: StudentRecordBook,
) -> None:
    with pytest.raises(ValueError, match="boom"):
        async with student_record_book.check_out("111") as student_record:
            student_record["marker"] = "a"
            raise ValueError("boom")

    async with student_record_book.check_out("111") as student_record:
        assert student_record == {"marker": "a"}


async def test_open_deletes_the_entry_once_emptied(
    student_record_book: StudentRecordBook,
) -> None:
    async with student_record_book.check_out("111") as student_record:
        student_record["marker"] = "a"

    async with student_record_book.check_out("111") as student_record:
        student_record.clear()

    assert [student_id async for student_id in student_record_book] == []


async def test_open_does_not_write_when_nothing_changed(
    student_record_book: StudentRecordBook,
) -> None:
    with patch.object(student_record_book, "_save", autospec=True) as mock_save:
        async with student_record_book.check_out("111"):
            pass

    mock_save.assert_not_awaited()


async def test_open_writes_when_something_changed(
    student_record_book: StudentRecordBook,
) -> None:
    with patch.object(student_record_book, "_save", autospec=True) as mock_save:
        async with student_record_book.check_out("111") as student_record:
            student_record["marker"] = "a"

    mock_save.assert_awaited_once_with("111", {"marker": "a"})


async def test_students_are_addressed_independently(
    student_record_book: StudentRecordBook,
) -> None:
    async with student_record_book.check_out("111") as student_record:
        student_record["marker"] = "a"
    async with student_record_book.check_out("222") as student_record:
        student_record["marker"] = "b"

    async with student_record_book.check_out("111") as student_record:
        assert student_record == {"marker": "a"}
    async with student_record_book.check_out("222") as student_record:
        assert student_record == {"marker": "b"}


async def test_iterating_yields_every_student_id(
    student_record_book: StudentRecordBook,
) -> None:
    async with student_record_book.check_out("111") as student_record:
        student_record["marker"] = "a"
    async with student_record_book.check_out("222") as student_record:
        student_record["marker"] = "b"

    student_ids = {student_id async for student_id in student_record_book}

    assert student_ids == {"111", "222"}
