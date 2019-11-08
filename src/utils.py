import random
from collections.abc import Mapping
from functools import wraps

import coolname

from src.exceptions import InvalidRequestException


def expects_json_object(func):
    @wraps(func)
    async def decorated_func(request, *args, **kwargs):
        if not isinstance(request.json, Mapping):
            raise InvalidRequestException("Request body must be an object")

        return await func(request, *args, **kwargs)

    return decorated_func


# Around 2.5 billion possibilities!
def generate_friendly_name():
    return (
        " ".join(coolname.generate(2)).capitalize()
        + " "
        + str(random.randint(1000, 9999))
    )
