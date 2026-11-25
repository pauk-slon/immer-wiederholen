# 0037. A button style has a meaning

**Status:** Accepted, 2026-11-25

## Context

The summary of a lesson offers the practice and the next lesson with two buttons of the same look ([ADR 0036](0036-practice-after-a-lesson-is-a-choice.md)). The practice is the step that we recommend, but nothing shows it. In the first weeks, one learner other than the author saw the offer and chose the next lesson.

Bot API 10.4 gives an inline button a `style`: `primary`, `success` or `danger`. The style names the role of the button. How a role looks is the concern of the Telegram app and its theme. Without a style, the app uses its usual look. Older apps ignore the field.

## Decision

A style marks the role of a button. A button gets a style only if it has that role. Most buttons have no style. The rule is for the inline buttons of the Telegram bot. The web widget has its own buttons and styles.

- `primary` marks the recommended step, and only where the learner has a choice. A message has at most one `primary` button. A message with a single button gets no style. The button that ends a selection, such as "Done" in `/topics`, is a recommended step. The buttons that change the selection aren't. An optional step, which the learner takes only if they want more, is never `primary`. So "Drill", the optional recall, has no style.
- `danger` marks an action that can't be undone. In a confirmation, the button that cancels comes first and the `danger` button after it, so that a tap out of habit doesn't do the action.
- `success` marks an action that confirms a good result. No button of the bot has this role now.

The two styles are constants in `wiederholen/bot/button_styles.py`, `RECOMMENDED` and `DESTRUCTIVE`. Code uses the constants, not the strings.

When a message offers the practice, the practice is its `RECOMMENDED` button. A button for the current exercise, such as "Try again", then loses its style, so that the message keeps one recommended step.

## Alternatives considered

- **A style on every button.** Not chosen. If all buttons have a style, a style says nothing, and the practice doesn't stand out again.
- **A style only on the practice button.** It solves the problem of the summary. Not chosen, because the same need comes back in other places, such as "Try again" after a wrong recall and the confirmation of `/reset`. A rule for the whole bot keeps the styles consistent.
- **Remove the "next lesson" button, so that the practice is the only way on.** Not chosen. [ADR 0036](0036-practice-after-a-lesson-is-a-choice.md) rejected one button, because a learner who has no time can't decline the practice.

## Consequences

- A new inline button needs a decision about its role. Most buttons get no style.
- The share of learners who choose the practice can show if the style helps. Divide the number of `lesson_recall.generate` spans by the number of updates with `lesson_recall.offered`, before and after this change. With few learners, this takes a long time.
