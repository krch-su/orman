import os
from typing import Callable, Any

not_provided = object()


class ConfigurationOptionNotProvided(ValueError):
    message = 'Environment is not configured with {} variable ' \
              'and default value is not provided'

    def __init__(self, key: str, message=message):
        self.key = key
        self.message = message


def get(
    key: str,
    coerce: Callable[[str], Any] = str,
    default: Any = not_provided
) -> Any:
    value = os.getenv(key)
    if value is None and default is not_provided:
        raise ConfigurationOptionNotProvided(key)
    return coerce(value)
