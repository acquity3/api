from functools import wraps

from apscheduler.schedulers.base import BaseScheduler
from cerberus import TypeDefinition, Validator

from src.exceptions import InvalidRequestException

Validator.types_mapping["scheduler"] = TypeDefinition("scheduler", (BaseScheduler,), ())


def validate_input(schema, **validator_kwargs):
    def decorator(func):
        @wraps(func)
        def decorated_func(*args, **kwargs):
            validator = Validator(schema, require_all=True, **validator_kwargs)
            res = validator.validate(kwargs)
            if not res:
                raise InvalidRequestException(validator.errors)

            return func(*args, **kwargs)

        return decorated_func

    return decorator


UUID_REGEX = (
    "[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}"
)
EMAIL_REGEX = "^.+@.+$"

UUID_RULE = {"type": "string", "regex": UUID_REGEX}
EMAIL_RULE = {"type": "string", "regex": EMAIL_REGEX}
NONNEGATIVE_NUMBER_RULE = {"type": "number", "min": 0}
OPTIONAL_NONNEGATIVE_NUMBER_RULE = {"type": "number", "min": 0, "required": False}

CREATE_BUY_ORDER_SCHEMA = {
    "user_id": UUID_RULE,
    "number_of_shares": NONNEGATIVE_NUMBER_RULE,
    "price": NONNEGATIVE_NUMBER_RULE,
    "security_id": UUID_RULE,
}
CREATE_SELL_ORDER_SCHEMA = {
    "user_id": UUID_RULE,
    "number_of_shares": NONNEGATIVE_NUMBER_RULE,
    "price": NONNEGATIVE_NUMBER_RULE,
    "security_id": UUID_RULE,
    "scheduler": {"type": "scheduler", "nullable": True},
}
EDIT_ORDER_SCHEMA = {
    "id": UUID_RULE,
    "subject_id": UUID_RULE,
    "new_number_of_shares": OPTIONAL_NONNEGATIVE_NUMBER_RULE,
    "new_price": OPTIONAL_NONNEGATIVE_NUMBER_RULE,
}
DELETE_ORDER_SCHEMA = {"id": UUID_RULE, "subject_id": UUID_RULE}
EDIT_MARKET_PRICE_SCHEMA = {
    "id": UUID_RULE,
    "subject_id": UUID_RULE,
    "market_price": {"type": "number", "min": 0, "nullable": True},
}
GET_AUTH_URL_SHCMEA = {"redirect_uri": {"type": "list", "items": [{"type": "string"}]}}
AUTHENTICATE_SCHEMA = {
    "code": {"type": "string"},
    "redirect_uri": {"type": "string"},
    "user_type": {"type": "string", "allowed": ["buyer", "seller"]},
}
GET_CHATS_BY_USER_ID_SCHEMA = {
    "user_id": UUID_RULE,
    "as_buyer": {"type": "boolean"},
    "as_seller": {"type": "boolean"},
}
