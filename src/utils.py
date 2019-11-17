import json
import random
from collections.abc import Mapping
from datetime import datetime
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


def handle_acquity_exceptions(f):
    async def decorated(self, sid, *args, **kwargs):
        try:
            return await f(self, sid, *args, **kwargs)
        except AcquityException as e:
            # on_req_* => req_*
            channel_name = f.__name__[3:]
            await self.emit(
                "error", {"name": channel_name, "message": e.message}, room=sid
            )

    return decorated


# Around 2.5 billion possibilities!
def generate_friendly_name():
    return (
        " ".join(coolname.generate(2)).capitalize()
        + " "
        + str(random.randint(1000, 9999))
    )


class AcquityEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return int(obj.timestamp())
        return json.JSONEncoder.default(self, obj)


class AcquityJson:
    @staticmethod
    def dumps(*args, **kwargs):
        return json.dumps(*args, **{**kwargs, "cls": AcquityEncoder})

    @staticmethod
    def loads(*args, **kwargs):
        return json.loads(*args, **kwargs)


EMAIL_STRFTIME_FORMAT = "%A, %B %d %Y, %I:%M %p %Z"
