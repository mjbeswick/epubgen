class EpubgenError(Exception):
    pass


class ApiError(EpubgenError):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


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
