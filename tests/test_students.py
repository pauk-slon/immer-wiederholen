from wiederholen.students import StudentStore


async def test_get_is_empty_for_an_unknown_student(
    student_store: StudentStore,
) -> None:
    assert await student_store.get("111") == {}


async def test_set_roundtrips_through_get(student_store: StudentStore) -> None:
    await student_store.set("111", {"journal": {"marker": True}})

    assert await student_store.get("111") == {"journal": {"marker": True}}


async def test_set_with_an_empty_dict_deletes_the_key(
    student_store: StudentStore,
) -> None:
    await student_store.set("111", {"marker": True})

    await student_store.set("111", {})

    assert await student_store.get("111") == {}
    assert [item async for item in student_store.iter_items()] == []


async def test_students_are_addressed_independently(
    student_store: StudentStore,
) -> None:
    await student_store.set("111", {"marker": "a"})
    await student_store.set("222", {"marker": "b"})

    assert await student_store.get("111") == {"marker": "a"}
    assert await student_store.get("222") == {"marker": "b"}


async def test_iter_items_yields_every_student(student_store: StudentStore) -> None:
    await student_store.set("111", {"marker": "a"})
    await student_store.set("222", {"marker": "b"})

    items = {student_id: data async for student_id, data in student_store.iter_items()}

    assert items == {"111": {"marker": "a"}, "222": {"marker": "b"}}
