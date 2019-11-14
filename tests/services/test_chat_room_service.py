from src.config import APP_CONFIG
from src.services import ChatRoomService
from tests.fixtures import (
    create_buy_order,
    create_chat_room,
    create_match,
    create_sell_order,
    create_user,
)

chat_room_service = ChatRoomService(config=APP_CONFIG)


def test_create_chat_room():
    buyer = create_user("1", can_buy=False)
    seller = create_user("2", can_sell=False)
    buy_order = create_buy_order("1", user_id=str(buyer["id"]))
    sell_order = create_sell_order("2", user_id=str(seller["id"]))
    match = create_match(
        "1", buy_order_id=str(buy_order["id"]), sell_order_id=str(sell_order["id"])
    )
    chat_room = create_chat_room(
        buyer_id=buyer["id"], seller_id=seller["id"], match_id=match["id"]
    )
    assert chat_room["buyer_id"] == buyer["id"]
    assert chat_room["seller_id"] == seller["id"]
    assert chat_room["match_id"] == match["id"]
