import pytest

from src.config import APP_CONFIG
from src.database import User, UserRequest, session_scope
from src.exceptions import InvisibleUnauthorizedException
from src.services import UserRequestService
from tests.fixtures import create_user, create_user_request

user_request_service = UserRequestService(config=APP_CONFIG)


def test_get_requests():
    admin = create_user("1", is_committee=True)
    buyer = create_user("2", can_buy=False)
    seller = create_user("3", can_sell=False)

    buyer_request = create_user_request(
        user_id=buyer["id"], is_buy=True, closed_by_user_id=None
    )
    seller_request = create_user_request(
        user_id=seller["id"], is_buy=False, closed_by_user_id=None
    )

    reqs = user_request_service.get_requests(subject_id=admin["id"])

    assert [
        {
            **buyer_request,
            **{
                k: v
                for k, v in buyer.items()
                if k not in ["id", "created_at", "updated_at"]
            },
            "can_buy": "UNAPPROVED",
        }
    ] == reqs["buyers"]
    assert [
        {
            **seller_request,
            **{
                k: v
                for k, v in seller.items()
                if k not in ["id", "created_at", "updated_at"]
            },
            "can_sell": "UNAPPROVED",
        }
    ] == reqs["sellers"]


def test_get_requests__unauthorized():
    admin = create_user(is_committee=False)

    with pytest.raises(InvisibleUnauthorizedException):
        user_request_service.get_requests(subject_id=admin["id"])


def test_approve_request():
    admin = create_user("1", is_committee=True)

    buyer = create_user("2", can_buy=False, can_sell=False)
    buy_req = create_user_request(user_id=buyer["id"], is_buy=True)
    user_request_service.approve_request(
        request_id=buy_req["id"], subject_id=admin["id"]
    )
    with session_scope() as session:
        assert (
            session.query(UserRequest).get(buy_req["id"]).closed_by_user_id
            == admin["id"]
        )
        assert session.query(User).get(buy_req["user_id"]).can_buy

    seller = create_user("3", can_buy=False, can_sell=False)
    sell_req = create_user_request(user_id=seller["id"], is_buy=False)
    user_request_service.approve_request(
        request_id=sell_req["id"], subject_id=admin["id"]
    )
    with session_scope() as session:
        assert (
            session.query(UserRequest).get(sell_req["id"]).closed_by_user_id
            == admin["id"]
        )
        assert session.query(User).get(sell_req["user_id"]).can_sell


def test_approve_request__unauthorized():
    admin = create_user(is_committee=False)

    with pytest.raises(InvisibleUnauthorizedException):
        user_request_service.approve_request(
            request_id=create_user_request("1")["user_id"], subject_id=admin["id"]
        )


def test_reject_request():
    admin = create_user("1", is_committee=True)

    buyer = create_user("2", can_buy=False, can_sell=False)
    buy_req = create_user_request(user_id=buyer["id"], is_buy=True)
    user_request_service.reject_request(
        request_id=buy_req["id"], subject_id=admin["id"]
    )
    with session_scope() as session:
        assert (
            session.query(UserRequest).get(buy_req["id"]).closed_by_user_id
            == admin["id"]
        )
        assert not session.query(User).get(buy_req["user_id"]).can_buy

    seller = create_user("3", can_buy=False, can_sell=False)
    sell_req = create_user_request(user_id=seller["id"], is_buy=False)
    user_request_service.reject_request(
        request_id=sell_req["id"], subject_id=admin["id"]
    )
    with session_scope() as session:
        assert (
            session.query(UserRequest).get(sell_req["id"]).closed_by_user_id
            == admin["id"]
        )
        assert not session.query(User).get(sell_req["user_id"]).can_sell


def test_reject_request__unauthorized():
    admin = create_user(is_committee=False)

    with pytest.raises(InvisibleUnauthorizedException):
        user_request_service.reject_request(
            request_id=create_user_request("1")["user_id"], subject_id=admin["id"]
        )
