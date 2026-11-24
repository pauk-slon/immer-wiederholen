# 0035. The result of an answer is one message

**Status:** Accepted, 2026-11-24 ([#393](https://github.com/pauk-slon/immer-wiederholen/pull/393)).

## Context

After an answer to an exercise, the bot sent two messages. The first said whether the answer was right. The second had the explanation and the inline buttons. [#46](https://github.com/pauk-slon/immer-wiederholen/pull/46) made this split the same for every exercise. Before it, the bot joined the two messages where it could, and the result looked different from one exercise to another.

The split has a reason in the Telegram Bot API. A multiple-choice exercise shows its options as a reply keyboard. Only a new message can remove a reply keyboard, with `ReplyKeyboardRemove`. A message has one `reply_markup`, so the message that removes the keyboard can't also have inline buttons.

For the learner, two messages for one answer are noise. Each message can make a notification. The verdict line also repeats what a mark at the start of the explanation can say.

## Decision

The bot sends the result of an answer as one message. The message starts with a mark for a right or a wrong answer. After a wrong answer, the correct answer follows. Then come the explanation and the buttons.

After an answer to a multiple-choice exercise, the bot first sends a short message with `ReplyKeyboardRemove` and no notification. Then it deletes this message at once. The keyboard stays removed after the deletion. If the deletion fails, the bot continues. The learner then sees the short message, and the result is still correct.

A test in a real chat confirmed this before the decision. On a phone and on a desktop client, the keyboard stayed removed, and the short message wasn't visible.

## Alternatives considered

- **Add the inline buttons to the message that removed the keyboard.** Send the result with `ReplyKeyboardRemove`, then add the buttons with `editMessageReplyMarkup`. Not chosen, because Telegram refuses it with "message can't be edited".
- **Don't remove the keyboard after an answer.** The keyboard has `one_time_keyboard`, so the client hides it after a tap, and the next question replaces or removes it. Not chosen, because of two gaps. If the learner types the answer, the keyboard stays open under the explanation. While the keyboard is hidden, the learner can open it again and tap an old option during an optional recall. The bot then takes the tap as an answer.
- **Show the options as inline buttons under the question.** Then there is no reply keyboard to remove. Not chosen now. The learner's answer would no longer be a message of their own in the chat, and the answer check would come from a callback instead of text. This is a larger change of the conversation, and it touches the open idea of a word bank widget ([#320](https://github.com/pauk-slon/immer-wiederholen/issues/320)).
- **Keep two messages.** Not chosen, for the reasons in the context.

## Consequences

- An answer to a multiple-choice exercise costs one more Bot API call, the deletion. The number of sent messages stays the same.
- The explanation is now part of an HTML message, so the bot escapes it with `html.escape()`.
- The marks for right and wrong differ in shape, not only in color, because no word says the verdict.
- The lesson summary is now a message of its own, right after the result of the last answer. Otherwise the summary would be lost at the end of a long explanation. The buttons move to the summary. If the last answer needs a recall, the summary has no buttons, and the recall result doesn't repeat it.
