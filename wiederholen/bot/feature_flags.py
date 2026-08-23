"""Per-user feature flags via the FEATURE_FLAGS env var.

Format: "flag_name:chat_id1,chat_id2;other_flag:chat_id3" — parsed once at
startup (see wiederholen.bot.bootstrap.load_feature_flags()). No
persistence, no runtime toggling: enabling a flag for a chat means editing
the env var and restarting, same as BOT_TOKEN/OTEL_* already work.

Deliberately bot-layer-only: feature gating is config/infra, not part of
the learning-domain model, so a chat_id/flag never reaches
wiederholen.school.
"""


def parse_feature_flags(raw: str) -> dict[str, frozenset[int]]:
    flags: dict[str, frozenset[int]] = {}
    for entry in raw.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        flag_name, _, chat_ids = entry.partition(":")
        flags[flag_name.strip()] = frozenset(
            int(chat_id) for chat_id in chat_ids.split(",") if chat_id.strip()
        )
    return flags


def has_feature(flags: dict[str, frozenset[int]], flag: str, chat_id: int) -> bool:
    return chat_id in flags.get(flag, frozenset())
