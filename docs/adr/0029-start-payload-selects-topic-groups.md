# 0029. A /start payload can also select the topic groups of a new chat

**Status:** Accepted, 2026-11-15 ([#346](https://github.com/pauk-slon/immer-wiederholen/pull/346)). Amends [ADR 0019](0019-start-payload-sets-only-a-new-language.md). The feature is discussed in [#345](https://github.com/pauk-slon/immer-wiederholen/issues/345).

## Context

The landing site is a German grammar reference. A page explains a topic, shows a web widget with exercises on the topics of the page, and then links to the bot with "Continue in @ImmerWiederholenBot". The link carries a language as the payload, the text after `?start=` (see [ADR 0019](0019-start-payload-sets-only-a-new-language.md)).

A new learner then gets exercises from all topics. For example, a learner comes for the table of verbs with prepositions, practices them in the widget, and the bot asks for Partizip II and articles. The link says "continue", but the bot doesn't continue the topic.

## Decision

The payload is the language, then topic groups from `topics.yaml`, separated by `-`. For example, `?start=ru-verb_government` or `?start=ru-verb_government-prepositions`. The language is required and comes first. The payloads `ru` and `en` keep their meaning.

The bot applies the payload only to a new chat, by the same rule as the language in ADR 0019. It saves the groups as `topic_groups`, the same setting that `/topics` changes. The bot skips a group that the course doesn't have. A payload without a known language gives a usual start.

The greeting then shows the selected groups with the text of `/topics` ("✅ Topics: Verb government") and says how to choose other topics.

The selection stays until the learner changes it with `/topics`.

## Alternatives considered

- **Single topics instead of groups.** The link would select exactly the topics of the page. Not chosen, because `/topics` can't show or change single topics, so the learner couldn't see the selection or change it.
- **Apply the groups while the learner has no answers.** This is closer to "a learner without progress" than "a new chat". Not chosen, because it needs a second rule next to ADR 0019 and a look into the student record in `/start`. The gain is only for learners who sent `/start` and stopped.
- **Short link ids in `topics.yaml`.** Each group would get a short id for links. This would keep the links working after a group gets a new id. Not chosen, because the group ids already fit the limit of 64 characters for a payload, and the course authors would have to keep one more unique field.
- **Named fields in Base64URL,** such as `lang=ru&groups=verb_government`. Not chosen, because the encoding makes the text a third longer, so two long groups no longer fit in 64 characters, and an author can't read the link on the page.
- **Select the groups silently.** Not chosen, because the learner then doesn't know why the bot shows only some topics.
- **Ask the learner after the start.** Not chosen, because it adds a question before the first exercise, and the link on the page already shows the choice.
- **End the selection after some time,** for example after the first day. Not chosen, because the learner chose the page, and the greeting says how to change the topics.

## Consequences

- The group ids in `topics.yaml` are part of public links. A group with a new id doesn't break a link, but the link stops selecting the group. A group id must not contain `-`.
- The bot before this change doesn't understand a link with groups, and it loses the language of such a link too, because it compares the whole payload with a language. So the landing site changes its links only after this change is in production.
- The `telegram.message` span of `/start` records if the chat is new and which known groups the payload selected. So the share of new chats from a page that finish a lesson can be measured.
