from src.config import APP_CONFIG
from src.services import ChatRoomService
from tests.fixtures import (
    create_buy_order,
    create_chatroom,
    create_sell_order,
    create_user,
)

chat_room_service = ChatRoomService(config=APP_CONFIG)


def test_create_chat_room():
    buyer = create_user("2", can_buy=False)
    seller = create_user("3", can_sell=False)
    chat_room = create_chatroom(buyer_id=buyer["id"], seller_id=seller["id"])
    assert chat_room["buyer_id"] == buyer["id"]
    assert chat_room["seller_id"] == seller["id"]


def test_get_chat_rooms__seller():
    buyer = create_user("2", can_buy=True)
    seller = create_user("3", can_sell=True)
    create_buy_order("1", user_id=str(buyer["id"]))
    create_sell_order("2", user_id=str(seller["id"]))

    create_chatroom(buyer_id=buyer["id"], seller_id=seller["id"])
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=seller["id"], user_type="seller", is_archived=False
    )
    assert len(chat_rooms) == 1


def test_get_chat_rooms__buyer():
    buyer = create_user("2", can_buy=True)
    seller = create_user("3", can_sell=True)
    create_buy_order("1", user_id=str(buyer["id"]))
    create_sell_order("2", user_id=str(seller["id"]))

    create_chatroom(buyer_id=buyer["id"], seller_id=seller["id"])
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=buyer["id"], user_type="buyer", is_archived=False
    )
    assert len(chat_rooms) == 1


def test_get_archived_chat_rooms__buyer():
    buyer = create_user("2", can_buy=True)
    seller = create_user("3", can_sell=True)
    create_buy_order("1", user_id=str(buyer["id"]))
    create_sell_order("2", user_id=str(seller["id"]))

    create_chatroom(buyer_id=buyer["id"], seller_id=seller["id"])
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=buyer["id"], user_type="buyer", is_archived=True
    )
    assert len(chat_rooms) == 0


def test_get_archived_chat_rooms__seller():
    buyer = create_user("2", can_buy=True)
    seller = create_user("3", can_sell=True)
    create_buy_order("1", user_id=str(buyer["id"]))
    create_sell_order("2", user_id=str(seller["id"]))

    create_chatroom(buyer_id=buyer["id"], seller_id=seller["id"])
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=seller["id"], user_type="seller", is_archived=True
    )
    assert len(chat_rooms) == 0


def test_get_chat_rooms__outsider():
    buyer = create_user("2", can_buy=True)
    seller = create_user("3", can_sell=True)
    outsider = create_user("4", can_sell=True)
    create_buy_order("1", user_id=str(buyer["id"]))
    create_sell_order("2", user_id=str(seller["id"]))

    create_chatroom(buyer_id=buyer["id"], seller_id=seller["id"])
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=outsider["id"], user_type="seller", is_archived=False
    )
    assert len(chat_rooms) == 0
