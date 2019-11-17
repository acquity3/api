from unittest.mock import MagicMock, patch

import pytest
from apscheduler.schedulers.base import BaseScheduler

from src.config import APP_CONFIG
from src.database import BuyOrder, Round, SellOrder, session_scope
from src.exceptions import ResourceNotOwnedException, UnauthorizedException
from src.services import SellOrderService
from tests.fixtures import (
    create_buy_order,
    create_security,
    create_sell_order,
    create_user,
    create_user_request,
)
from tests.utils import assert_dict_in

sell_order_service = SellOrderService(config=APP_CONFIG)


def test_get_orders_by_user():
    user_id = create_user()["id"]
    sell_order = create_sell_order("1", user_id=user_id)
    sell_order2 = create_sell_order("2", user_id=user_id)

    orders = sell_order_service.get_orders_by_user(user_id=user_id)
    assert len(orders) == 2

    assert (
        sell_order == orders[0]
        if orders[0]["number_of_shares"] == sell_order["number_of_shares"]
        else orders[1]
    )

    assert (
        sell_order2 == orders[1]
        if orders[0]["number_of_shares"] == sell_order["number_of_shares"]
        else orders[0]
    )


def test_get_order_by_id():
    sell_order = create_sell_order()

    order_retrieved = sell_order_service.get_order_by_id(
        id=sell_order["id"], user_id=sell_order["user_id"]
    )
    assert order_retrieved["id"] == sell_order["id"]


def test_get_order_by_id__unauthorized():
    sell_order = create_sell_order()
    user_id = sell_order["user_id"]
    false_user_id = ("1" if user_id[0] == "0" else "0") + user_id[1:]

    with pytest.raises(ResourceNotOwnedException):
        sell_order_service.get_order_by_id(id=sell_order["id"], user_id=false_user_id)


def test_create_order__authorized():
    user = create_user()
    user_id = user["id"]
    security_id = create_security()["id"]

    sell_order_params = {
        "user_id": user_id,
        "number_of_shares": 20,
        "price": 30,
        "security_id": security_id,
    }

    with patch("src.services.RoundService.get_active", return_value=None), patch(
        "src.services.RoundService.should_round_start", return_value=False
    ), patch("src.services.EmailService.send_email") as email_mock:
        sell_order_id = sell_order_service.create_order(
            **sell_order_params, scheduler=None
        )["id"]
        email_mock.assert_called_with(
            emails=[user["email"]], template="create_sell_order"
        )

    with session_scope() as session:
        sell_order = session.query(SellOrder).get(sell_order_id).asdict()

    assert_dict_in({**sell_order_params, "round_id": None}, sell_order)


def test_create_order__pending():
    user = create_user(can_sell=False)
    user_id = user["id"]
    security_id = create_security()["id"]
    create_user_request(user_id=user_id, is_buy=False)

    with pytest.raises(UnauthorizedException), patch(
        "src.services.EmailService.send_email"
    ) as email_mock:
        sell_order_service.create_order(
            user_id=user_id,
            number_of_shares=20,
            price=30,
            security_id=security_id,
            scheduler=None,
        )
        email_mock.assert_not_called()


def test_create_order__add_new_round():
    user = create_user(can_buy=True)
    security_id = create_security()["id"]

    user_id = user["id"]

    sell_order_params = {
        "user_id": user_id,
        "number_of_shares": 20,
        "price": 30,
        "security_id": security_id,
    }
    create_buy_order(round_id=None, user_id=user_id)

    with patch("src.services.RoundService.get_active", return_value=None), patch(
        "src.services.RoundService.should_round_start", return_value=False
    ), patch("src.services.EmailService.send_email") as email_mock:
        sell_order_id = sell_order_service.create_order(
            **sell_order_params, scheduler=None
        )["id"]

    with patch("src.services.RoundService.get_active", return_value=None), patch(
        "src.services.RoundService.should_round_start", return_value=True
    ), patch("src.services.EmailService.send_email") as email_mock:
        scheduler_mock = MagicMock()

        class SchedulerMock(BaseScheduler):
            shutdown = MagicMock()
            wakeup = MagicMock()
            add_job = scheduler_mock

        sell_order_id2 = sell_order_service.create_order(
            **sell_order_params, scheduler=SchedulerMock()
        )["id"]

        template_calls = [a[1].get("template") for a in email_mock.call_args_list]
        assert "round_opened_buyer" in template_calls
        assert "round_opened_seller" in template_calls

        email_mock.assert_any_call(emails=[user["email"]], template="create_sell_order")

    scheduler_args = scheduler_mock.call_args
    assert scheduler_args[0][1] == "date"

    with session_scope() as session:
        assert scheduler_args[1]["run_date"] == session.query(Round).one().end_time

        sell_order = session.query(SellOrder).get(sell_order_id).asdict()
        sell_order2 = session.query(SellOrder).get(sell_order_id2).asdict()
        buy_order = session.query(BuyOrder).one().asdict()

    assert_dict_in(sell_order_params, sell_order)
    assert sell_order["round_id"] is not None
    assert_dict_in(sell_order_params, sell_order2)
    assert sell_order2["round_id"] is not None
    assert buy_order["round_id"] is not None


def test_create_order__unauthorized():
    user_id = create_user(can_sell=False)["id"]
    security_id = create_security()["id"]

    with pytest.raises(UnauthorizedException), patch(
        "src.services.EmailService.send_email"
    ) as email_mock:
        sell_order_service.create_order(
            user_id=user_id,
            number_of_shares=20,
            price=30,
            security_id=security_id,
            scheduler=None,
        )
        email_mock.assert_not_called()


def test_create_order__limit_reached():
    user_id = create_user()["id"]
    security_id = create_security()["id"]

    sell_order_params = {
        "user_id": user_id,
        "number_of_shares": 20,
        "price": 30,
        "security_id": security_id,
    }

    with patch("src.services.EmailService.send_email"):
        for _ in range(APP_CONFIG["ACQUITY_SELL_ORDER_PER_ROUND_LIMIT"]):
            sell_order_service.create_order(**sell_order_params, scheduler=None)
    with pytest.raises(UnauthorizedException), patch(
        "src.services.EmailService.send_email"
    ) as email_mock:
        sell_order_service.create_order(**sell_order_params, scheduler=None)
        email_mock.assert_not_called()


def test_edit_order():
    user = create_user()
    user_id = user["id"]
    sell_order = create_sell_order(user_id=user_id)

    with patch("src.services.EmailService.send_email") as email_mock:
        sell_order_service.edit_order(
            id=sell_order["id"], subject_id=user_id, new_number_of_shares=50
        )
        email_mock.assert_called_with(
            emails=[user["email"]], template="edit_sell_order"
        )

    with session_scope() as session:
        new_sell_order = session.query(SellOrder).get(sell_order["id"]).asdict()

    test_dict = {**sell_order, "number_of_shares": 50}
    del test_dict["updated_at"]
    assert_dict_in(test_dict, new_sell_order)


def test_delete_order():
    user_id = create_user()["id"]
    sell_order_id = create_sell_order(user_id=user_id)["id"]

    sell_order_service.delete_order(id=sell_order_id, subject_id=user_id)

    with session_scope() as session:
        assert session.query(SellOrder).filter_by(id=sell_order_id).count() == 0
