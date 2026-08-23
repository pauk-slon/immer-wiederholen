from typing import Final, Literal, get_args

type Language = Literal["ru", "en"]


LANGUAGES: Final[frozenset[Language]] = frozenset(get_args(Language.__value__))
