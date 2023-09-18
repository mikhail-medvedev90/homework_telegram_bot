class TokenNotFound(FileNotFoundError):
    pass


class ResponseKeyNotFound(KeyError):
    pass


class WrongResponseStatusCode(Exception):
    pass
