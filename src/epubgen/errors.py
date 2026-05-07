class EpubgenError(Exception):
    pass


class ApiError(EpubgenError):
    def __init__(
        self, message: str, *, retryable: bool = False, hint: str | None = None
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.hint = hint


class OutlineError(EpubgenError):
    pass


class PandocError(EpubgenError):
    pass


class FsError(EpubgenError):
    pass


class CoverError(EpubgenError):
    pass


class ConfigError(EpubgenError):
    pass
