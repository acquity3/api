from unittest.mock import patch

from src.config import APP_CONFIG
from src.database import User, UserRequest, session_scope
from src.services import UserService
from tests.fixtures import create_user
from tests.utils import assert_dict_in

user_service = UserService(config=APP_CONFIG)


def test_create__is_buy():
    user_params = {
        "email": "a@a.io",
        "full_name": "Ben",
        "provider_user_id": "testing",
        "display_image_url": "http://blah",
        "is_buy": True,
        "auth_token": None,
    }

    committee_email = create_user(is_committee=True)["email"]

    with patch("src.services.EmailService.send_email") as mock:
        user_service.create_if_not_exists(**user_params)
        mock.assert_any_call(emails=[user_params["email"]], template="register_buyer")
        mock.assert_any_call(emails=[committee_email], template="new_user_review")

    with session_scope() as session:
        user = session.query(User).filter_by(email="a@a.io").one().asdict()
        req = session.query(UserRequest).one().asdict()

    user_expected = user_params
    user_expected.pop("is_buy")
    user_expected.update({"can_buy": "UNAPPROVED", "can_sell": "NO"})
    assert_dict_in(user_expected, user)

    assert_dict_in({"user_id": user["id"], "is_buy": True}, req)


def test_create__is_sell():
    user_params = {
        "email": "a@a.io",
        "full_name": "Ben",
        "provider_user_id": "testing",
        "display_image_url": "http://blah",
        "is_buy": False,
        "auth_token": None,
    }

    committee_email = create_user(is_committee=True)["email"]

    with patch("src.services.EmailService.send_email") as mock:
        user_service.create_if_not_exists(**user_params)
        mock.assert_any_call(emails=[user_params["email"]], template="register_seller")
        mock.assert_any_call(emails=[committee_email], template="new_user_review")

    with session_scope() as session:
        user = session.query(User).filter_by(email="a@a.io").one().asdict()
        buy_req = session.query(UserRequest).filter_by(is_buy=True).one().asdict()
        sell_req = session.query(UserRequest).filter_by(is_buy=False).one().asdict()

    user_expected = user_params
    user_expected.pop("is_buy")
    user_expected.update({"can_buy": "UNAPPROVED", "can_sell": "UNAPPROVED"})
    assert_dict_in(user_expected, user)

    assert buy_req["user_id"] == user["id"]
    assert sell_req["user_id"] == user["id"]


def test_create__user_exists():
    user_params = {
        "email": "a@a.io",
        "full_name": "Ben",
        "provider_user_id": "testing",
        "display_image_url": "http://blah",
        "is_buy": True,
        "auth_token": None,
    }
    with patch("src.services.EmailService.send_email"):
        user_service.create_if_not_exists(
            **{
                **user_params,
                "email": "b@b.io",
                "full_name": "Boo",
                "display_image_url": "old",
            }
        )

    with patch("src.services.EmailService.send_email") as mock:
        user_service.create_if_not_exists(**user_params)
        mock.assert_not_called()

    with session_scope() as session:
        user = session.query(User).one().asdict()

    user_expected = user_params
    user_expected.pop("is_buy")
    user_expected.update({"can_buy": "UNAPPROVED", "can_sell": "NO"})
    assert_dict_in(user_expected, user)


def test_get_user_by_linkedin_id():
    user_params = create_user(provider_user_id="abcdef")

    user = user_service.get_user_by_linkedin_id(provider_user_id="abcdef")
    assert user_params == user
