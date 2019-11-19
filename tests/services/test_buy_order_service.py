from unittest.mock import patch

import pytest

from src.config import APP_CONFIG
from src.database import BuyOrder, session_scope
from src.exceptions import ResourceNotOwnedException, UnauthorizedException
from src.services import BuyOrderService
from tests.fixtures import (
    create_buy_order,
    create_round,
    create_security,
    create_user,
    create_user_request,
)
from tests.utils import assert_dict_in

buy_order_service = BuyOrderService(config=APP_CONFIG)


def test_get_orders_by_user_in_current_round():
    user_id = create_user()["id"]

    current_round = create_round()
    past_round = create_round(is_concluded=True)

    buy_order = create_buy_order("1", user_id=user_id, round_id=current_round["id"])
    buy_order2 = create_buy_order("2", user_id=user_id, round_id=current_round["id"])
    create_buy_order("3", user_id=user_id, round_id=past_round["id"])

    orders = buy_order_service.get_orders_by_user_in_current_round(user_id=user_id)
    assert len(orders) == 2

    assert (
        buy_order == orders[0]
        if orders[0]["number_of_shares"] == buy_order["number_of_shares"]
        else orders[1]
    )

    assert (
        buy_order2 == orders[1]
        if orders[0]["number_of_shares"] == buy_order["number_of_shares"]
        else orders[0]
    )


def test_get_order_by_id():
    buy_order = create_buy_order()

    order_retrieved = buy_order_service.get_order_by_id(
        id=buy_order["id"], user_id=buy_order["user_id"]
    )
    assert order_retrieved["id"] == buy_order["id"]


def test_get_order_by_id__unauthorized():
    buy_order = create_buy_order()
    user_id = buy_order["user_id"]
    false_user_id = ("1" if user_id[0] == "0" else "0") + user_id[1:]

    with pytest.raises(ResourceNotOwnedException):
        buy_order_service.get_order_by_id(id=buy_order["id"], user_id=false_user_id)


def test_create_order__authorized():
    user = create_user()
    user_id = user["id"]
    security_id = create_security()["id"]
    round = create_round()

    buy_order_params = {
        "user_id": user_id,
        "number_of_shares": 20,
        "price": 30,
        "security_id": security_id,
    }

    with patch("src.services.RoundService.get_active", return_value=round), patch(
        "src.services.RoundService.should_round_start", return_value=False
    ), patch("src.services.EmailService.send_email") as email_mock:
        buy_order_id = buy_order_service.create_order(**buy_order_params)["id"]
        email_mock.assert_called_with(
            emails=[user["email"]], template="create_buy_order"
        )

    with session_scope() as session:
        buy_order = session.query(BuyOrder).get(buy_order_id).asdict()

    assert_dict_in({**buy_order_params, "round_id": round["id"]}, buy_order)


def test_create_order__pending():
    user = create_user(can_buy=False)
    user_id = user["id"]
    security_id = create_security()["id"]
    create_user_request(user_id=user_id, is_buy=True)
    round = create_round()

    buy_order_params = {
        "user_id": user_id,
        "number_of_shares": 20,
        "price": 30,
        "security_id": security_id,
    }

    with patch("src.services.RoundService.get_active", return_value=round), patch(
        "src.services.RoundService.should_round_start", return_value=False
    ), patch("src.services.EmailService.send_email") as email_mock:
        buy_order_id = buy_order_service.create_order(**buy_order_params)["id"]
        email_mock.assert_called_with(
            emails=[user["email"]], template="create_buy_order"
        )

    with session_scope() as session:
        buy_order = session.query(BuyOrder).get(buy_order_id).asdict()

    assert_dict_in({**buy_order_params, "round_id": round["id"]}, buy_order)


def test_create_order__authorized_no_active_rounds():
    user = create_user()
    user_id = user["id"]
    security_id = create_security()["id"]

    buy_order_params = {
        "user_id": user_id,
        "number_of_shares": 20,
        "price": 30,
        "security_id": security_id,
    }

    with patch("src.services.RoundService.get_active", return_value=None), patch(
        "src.services.EmailService.send_email"
    ) as email_mock:
        buy_order_id = buy_order_service.create_order(**buy_order_params)["id"]
        email_mock.assert_called_with(
            emails=[user["email"]], template="create_buy_order"
        )

    with session_scope() as session:
        buy_order = session.query(BuyOrder).get(buy_order_id).asdict()

    assert_dict_in({**buy_order_params, "round_id": None}, buy_order)


def test_create_order__unauthorized():
    user_id = create_user(can_buy=False)["id"]
    security_id = create_security()["id"]

    with pytest.raises(UnauthorizedException), patch(
        "src.services.EmailService.send_email"
    ) as email_mock:
        buy_order_service.create_order(
            user_id=user_id, number_of_shares=20, price=30, security_id=security_id
        )
        email_mock.assert_not_called()


def test_create_order__limit_reached():
    user_id = create_user()["id"]
    security_id = create_security()["id"]
    create_round()

    buy_order_params = {
        "user_id": user_id,
        "number_of_shares": 20,
        "price": 30,
        "security_id": security_id,
    }

    with patch("src.services.EmailService.send_email"):
        for _ in range(APP_CONFIG["ACQUITY_BUY_ORDER_PER_ROUND_LIMIT"]):
            buy_order_service.create_order(**buy_order_params)
    with pytest.raises(UnauthorizedException), patch(
        "src.services.EmailService.send_email"
    ) as email_mock:
        buy_order_service.create_order(**buy_order_params)
        email_mock.assert_not_called()


def test_edit_order():
    user = create_user()
    user_id = user["id"]
    buy_order = create_buy_order(user_id=user_id)

    with patch("src.services.EmailService.send_email") as email_mock:
        buy_order_service.edit_order(
            id=buy_order["id"], subject_id=user_id, new_number_of_shares=50
        )
        email_mock.assert_called_with(emails=[user["email"]], template="edit_buy_order")

    with session_scope() as session:
        new_buy_order = session.query(BuyOrder).get(buy_order["id"]).asdict()

    test_dict = {**buy_order, "number_of_shares": 50}
    del test_dict["updated_at"]
    assert_dict_in(test_dict, new_buy_order)


def test_delete_order():
    user_id = create_user()["id"]
    buy_order_id = create_buy_order(user_id=user_id)["id"]

    buy_order_service.delete_order(id=buy_order_id, subject_id=user_id)

    with session_scope() as session:
        assert session.query(BuyOrder).filter_by(id=buy_order_id).count() == 0
