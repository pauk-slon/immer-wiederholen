class AIGenerationError(Exception):
    """A model call of `authoring` failed: the API call itself, or a reply
    without the expected tool call or with a malformed one. Shadow
    exercises and lesson recalls both raise it, and the bot shows an error
    message for it, never a silent fallback (ADR 0006)."""
