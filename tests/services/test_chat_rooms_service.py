from src.config import APP_CONFIG
from src.services import ChatRoomService
from tests.fixtures import (
    create_buy_order,
    create_chatroom,
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
    chat_room = create_chatroom(
        buyer_id=buyer["id"], seller_id=seller["id"], match_id=match["id"]
    )
    assert chat_room["buyer_id"] == buyer["id"]
    assert chat_room["seller_id"] == seller["id"]
    assert chat_room["match_id"] == match["id"]


def test_get_chat_rooms__seller():
    buyer = create_user("1", can_buy=False)
    seller = create_user("2", can_sell=False)
    buy_order = create_buy_order("1", user_id=str(buyer["id"]))
    sell_order = create_sell_order("2", user_id=str(seller["id"]))
    match = create_match(
        "1", buy_order_id=str(buy_order["id"]), sell_order_id=str(sell_order["id"])
    )
    create_chatroom(buyer_id=buyer["id"], seller_id=seller["id"], match_id=match["id"])

    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=seller["id"], user_type="seller", is_archived=False
    )
    assert len(chat_rooms) == 1


def test_get_chat_rooms__buyer():
    buyer = create_user("1", can_buy=False)
    seller = create_user("2", can_sell=False)
    buy_order = create_buy_order("1", user_id=str(buyer["id"]))
    sell_order = create_sell_order("2", user_id=str(seller["id"]))
    match = create_match(
        "1", buy_order_id=str(buy_order["id"]), sell_order_id=str(sell_order["id"])
    )
    create_chatroom(buyer_id=buyer["id"], seller_id=seller["id"], match_id=match["id"])

    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=buyer["id"], user_type="buyer", is_archived=False
    )
    assert len(chat_rooms) == 1


def test_get_archived_chat_rooms__buyer():
    buyer = create_user("1", can_buy=False)
    seller = create_user("2", can_sell=False)
    buy_order = create_buy_order("1", user_id=str(buyer["id"]))
    sell_order = create_sell_order("2", user_id=str(seller["id"]))
    match = create_match(
        "1", buy_order_id=str(buy_order["id"]), sell_order_id=str(sell_order["id"])
    )
    create_chatroom(buyer_id=buyer["id"], seller_id=seller["id"], match_id=match["id"])

    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=seller["id"], user_type="buyer", is_archived=True
    )
    assert len(chat_rooms) == 0


def test_get_archived_chat_rooms__seller():
    buyer = create_user("1", can_buy=False)
    seller = create_user("2", can_sell=False)
    buy_order = create_buy_order("1", user_id=str(buyer["id"]))
    sell_order = create_sell_order("2", user_id=str(seller["id"]))
    match = create_match(
        "1", buy_order_id=str(buy_order["id"]), sell_order_id=str(sell_order["id"])
    )
    create_chatroom(buyer_id=buyer["id"], seller_id=seller["id"], match_id=match["id"])

    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=seller["id"], user_type="seller", is_archived=True
    )
    assert len(chat_rooms) == 0


def test_get_chat_rooms__outsider():
    buyer = create_user("1", can_buy=False)
    seller = create_user("2", can_sell=False)
    outsider = create_user("3", can_sell=False)
    buy_order = create_buy_order("1", user_id=str(buyer["id"]))
    sell_order = create_sell_order("2", user_id=str(seller["id"]))
    match = create_match(
        "1", buy_order_id=str(buy_order["id"]), sell_order_id=str(sell_order["id"])
    )
    create_chatroom(buyer_id=buyer["id"], seller_id=seller["id"], match_id=match["id"])

    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=outsider["id"], user_type="seller", is_archived=False
    )
    assert len(chat_rooms) == 0


def test_get_chat_rooms__multiple_offers():
    buyer = create_user("1", can_buy=False)
    seller = create_user("2", can_sell=False)
    buy_order = create_buy_order("1", user_id=str(buyer["id"]))
    create_buy_order("2", user_id=str(buyer["id"]))
    sell_order = create_sell_order("3", user_id=str(seller["id"]))
    create_sell_order("4", user_id=str(seller["id"]))
    match = create_match(
        "1", buy_order_id=str(buy_order["id"]), sell_order_id=str(sell_order["id"])
    )
    create_chatroom(buyer_id=buyer["id"], seller_id=seller["id"], match_id=match["id"])

    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=seller["id"], user_type="seller", is_archived=False
    )
    assert len(chat_rooms) == 1


def test_get_chat_rooms__multiple_buyers():
    buyer = create_user("1", can_buy=False)
    create_user("2", can_buy=False)
    seller = create_user("3", can_sell=False)
    create_user("4", can_sell=False)
    buy_order = create_buy_order("1", user_id=str(buyer["id"]))
    sell_order = create_sell_order("2", user_id=str(seller["id"]))
    match = create_match(
        "1", buy_order_id=str(buy_order["id"]), sell_order_id=str(sell_order["id"])
    )
    create_chatroom(buyer_id=buyer["id"], seller_id=seller["id"], match_id=match["id"])

    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=seller["id"], user_type="seller", is_archived=False
    )
    assert len(chat_rooms) == 1
