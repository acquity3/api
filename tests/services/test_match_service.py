from unittest.mock import call, patch

from src.config import APP_CONFIG
from src.database import Match, Round, UserChatRoomAssociation, session_scope
from src.services import MatchService
from tests.fixtures import (
    create_banned_pair,
    create_buy_order,
    create_round,
    create_sell_order,
    create_user,
)

match_service = MatchService(config=APP_CONFIG)


def test_run_matches():
    round = create_round()

    buy_user = create_user("1")
    buy_user2 = create_user("2")
    sell_user = create_user("3")
    sell_user2 = create_user("4")

    buy_order = create_buy_order("1", round_id=round["id"], user_id=buy_user["id"])
    buy_order_id = buy_order["id"]
    create_buy_order("2", round_id=round["id"], user_id=buy_user2["id"])
    sell_order = create_sell_order("3", round_id=round["id"], user_id=sell_user["id"])
    sell_order_id = sell_order["id"]
    create_sell_order("4", round_id=round["id"], user_id=sell_user2["id"])

    with patch(
        "src.services.match_buyers_and_sellers",
        return_value=[(buy_order_id, sell_order_id)],
    ) as mock_match, patch(
        "src.services.RoundService.get_active", return_value=round
    ), patch(
        "src.services.EmailService.send_email"
    ) as mock_email:
        match_service.run_matches()
        mock_email.assert_has_calls(
            [
                call([buy_user["email"]], template="match_done_has_match_buyer"),
                call([sell_user["email"]], template="match_done_has_match_seller"),
                call(
                    [buy_user2["email"], sell_user2["email"]],
                    template="match_done_no_match",
                ),
            ]
        )

        assert set(u["user_id"] for u in mock_match.call_args[0][0]) == set(
            [buy_user["id"], buy_user2["id"]]
        )
        assert set(u["user_id"] for u in mock_match.call_args[0][1]) == set(
            [sell_user["id"], sell_user2["id"]]
        )
        assert mock_match.call_args[0][2] == []

    with session_scope() as session:
        match = session.query(Match).one()
        assert match.buy_order_id == buy_order_id
        assert match.sell_order_id == sell_order_id

        assert (
            session.query(UserChatRoomAssociation)
            .filter_by(user_id=buy_order["user_id"])
            .one()
            .chat_room_id
            == session.query(UserChatRoomAssociation)
            .filter_by(user_id=sell_order["user_id"])
            .one()
            .chat_room_id
        )

        assert session.query(Round).get(round["id"]).is_concluded


def test_run_matches__cannot_buy_or_sell():
    round = create_round()

    buy_user = create_user("1", can_buy=True)
    buy_user2 = create_user("2", can_buy=False)
    sell_user = create_user("3", can_sell=True)
    sell_user2 = create_user("4", can_sell=False)

    create_buy_order("1", round_id=round["id"], user_id=buy_user["id"])
    create_buy_order("2", round_id=round["id"], user_id=buy_user2["id"])
    create_sell_order("3", round_id=round["id"], user_id=sell_user["id"])
    create_sell_order("4", round_id=round["id"], user_id=sell_user2["id"])

    with patch("src.services.match_buyers_and_sellers") as mock_match, patch(
        "src.services.RoundService.get_active", return_value=round
    ), patch("src.services.EmailService.send_email"):
        match_service.run_matches()

        assert set(u["user_id"] for u in mock_match.call_args[0][0]) == set(
            [buy_user["id"]]
        )
        assert set(u["user_id"] for u in mock_match.call_args[0][1]) == set(
            [sell_user["id"]]
        )
        assert mock_match.call_args[0][2] == []


def test_run_matches__banned_pairs():
    round = create_round()

    buy_user = create_user("1")
    buy_user2 = create_user("2")
    sell_user = create_user("3")
    sell_user2 = create_user("4")

    buy_user_id = buy_user["id"]
    sell_user_id = sell_user["id"]

    create_buy_order("1", round_id=round["id"], user_id=buy_user["id"])
    create_buy_order("2", round_id=round["id"], user_id=buy_user2["id"])
    create_sell_order("3", round_id=round["id"], user_id=sell_user["id"])
    create_sell_order("4", round_id=round["id"], user_id=sell_user2["id"])

    create_banned_pair(buyer_id=buy_user_id, seller_id=sell_user_id)

    with patch("src.services.match_buyers_and_sellers") as mock_match, patch(
        "src.services.RoundService.get_active", return_value=round
    ), patch("src.services.EmailService.send_email"):
        match_service.run_matches()

        assert set(u["user_id"] for u in mock_match.call_args[0][0]) == set(
            [buy_user_id, buy_user2["id"]]
        )
        assert set(u["user_id"] for u in mock_match.call_args[0][1]) == set(
            [sell_user_id, sell_user2["id"]]
        )
        assert mock_match.call_args[0][2] == [(buy_user_id, sell_user_id)]


def test_run_matches__double_sell_orders():
    round = create_round()

    sell_user = create_user("3")
    sell_user2 = create_user("4")

    sell_order1 = create_sell_order("3", round_id=round["id"], user_id=sell_user["id"])
    sell_order21 = create_sell_order(
        "4", round_id=round["id"], user_id=sell_user2["id"]
    )
    sell_order22 = create_sell_order(
        "5", round_id=round["id"], user_id=sell_user2["id"]
    )

    with patch("src.services.match_buyers_and_sellers") as mock_match, patch(
        "src.services.RoundService.get_active", return_value=round
    ), patch("src.services.EmailService.send_email"):
        match_service.run_matches()

        assert (
            len([o for o in mock_match.call_args[0][1] if o["id"] == sell_order1["id"]])
            == 2
        )
        assert (
            len(
                [o for o in mock_match.call_args[0][1] if o["id"] == sell_order21["id"]]
            )
            == 1
        )
        assert (
            len(
                [o for o in mock_match.call_args[0][1] if o["id"] == sell_order22["id"]]
            )
            == 1
        )
