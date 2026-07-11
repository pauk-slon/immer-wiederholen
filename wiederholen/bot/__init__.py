from .dispatcher import dp

# Each import below registers that command's handlers on `dp` as a side
# effect. Order matches handler registration order in the original
# single-file bot: start, language, then the wiederholen exercise flow.
from .commands import start, language, wiederholen  # noqa: F401

__all__ = ["dp"]
