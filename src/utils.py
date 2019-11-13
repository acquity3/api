import random
from collections.abc import Mapping
from functools import wraps

import coolname

from src.exceptions import AcquityException, InvalidRequestException


def expects_json_object(func):
    @wraps(func)
    async def decorated_func(request, *args, **kwargs):
        if not isinstance(request.json, Mapping):
            raise InvalidRequestException("Request body must be an object")

        return await func(request, *args, **kwargs)

    return decorated_func


def handle_acquity_exceptions(emit_message):
    def decorator(f):
        async def decorated(self, sid, *args, **kwargs):
            try:
                return await f(self, sid, *args, **kwargs)
            except AcquityException as e:
                await self.emit(
                    emit_message,
                    {"status_code": e.status_code, "message": e.message},
                    room=sid,
                )

        return decorated

    return decorator


# Around 2.5 billion possibilities!
def generate_friendly_name():
    return (
        " ".join(coolname.generate(2)).capitalize()
        + " "
        + str(random.randint(1000, 9999))
    )
