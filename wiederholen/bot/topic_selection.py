from typing import Any

from wiederholen.school import Course


def get_selected_groups(state: dict[str, Any], course: Course) -> list[str]:
    # Drops ids the course no longer defines (a group renamed or removed in
    # topics.yaml since the learner picked it) rather than failing on them.
    return [
        group_id
        for group_id in state.get("topic_groups", [])
        if group_id in course.topic_groups
    ]


def restrict_to_selected_groups(course: Course, state: dict[str, Any]) -> Course:
    # No selection means every topic, the same as before /topics existed —
    # an empty selection never narrows the course down to nothing.
    selected = get_selected_groups(state, course)
    if not selected:
        return course
    return course.restricted_to(
        topic for group_id in selected for topic in course.topic_groups[group_id].topics
    )
