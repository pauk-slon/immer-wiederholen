from typing import Literal, get_args, Final

type Language = Literal["ru", "en"]


LANGUAGES: Final[frozenset[Language]] = frozenset(get_args(Language.__value__))
