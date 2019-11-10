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


def test_create_archived_chat_room__buyer():
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

    chat_room_service.archive_room(user_id=buyer["id"], chat_room_id=chat_room["id"])
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=buyer["id"], user_type="buyer", is_archived=False
    )
    assert len(chat_rooms) == 0
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=buyer["id"], user_type="buyer", is_archived=True
    )
    assert len(chat_rooms) == 1


def test_unarchived_chat_room():
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

    chat_room_service.archive_room(user_id=buyer["id"], chat_room_id=chat_room["id"])
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=buyer["id"], user_type="buyer", is_archived=False
    )
    assert len(chat_rooms) == 0
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=buyer["id"], user_type="buyer", is_archived=True
    )
    assert len(chat_rooms) == 1
    chat_room_service.unarchive_room(user_id=buyer["id"], chat_room_id=chat_room["id"])
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=buyer["id"], user_type="buyer", is_archived=False
    )
    assert len(chat_rooms) == 1
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=buyer["id"], user_type="buyer", is_archived=True
    )
    assert len(chat_rooms) == 0


def test_create_archived_chat_room__seller():
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

    chat_room_service.archive_room(user_id=seller["id"], chat_room_id=chat_room["id"])
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=seller["id"], user_type="seller", is_archived=False
    )
    assert len(chat_rooms) == 0
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=seller["id"], user_type="seller", is_archived=True
    )
    assert len(chat_rooms) == 1


def test_archived_chat_room__multiple_rooms():
    buyer = create_user("1", can_buy=False)
    buyer2 = create_user("2", can_buy=False)
    seller = create_user("3", can_sell=False)

    buy_order = create_buy_order("1", user_id=str(buyer["id"]))
    buy_order2 = create_buy_order("2", user_id=str(buyer2["id"]))
    sell_order = create_sell_order("3", user_id=str(seller["id"]))

    match = create_match(
        "1", buy_order_id=str(buy_order["id"]), sell_order_id=str(sell_order["id"])
    )
    match2 = create_match(
        "2", buy_order_id=str(buy_order2["id"]), sell_order_id=str(sell_order["id"])
    )

    chat_room = create_chatroom(
        buyer_id=buyer["id"], seller_id=seller["id"], match_id=match["id"]
    )
    chat_room2 = create_chatroom(
        buyer_id=buyer2["id"], seller_id=seller["id"], match_id=match2["id"]
    )

    chat_room_service.archive_room(user_id=seller["id"], chat_room_id=chat_room["id"])
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=seller["id"], user_type="seller", is_archived=False
    )
    assert len(chat_rooms) == 1
    assert chat_rooms[0]["chat_room_id"] == chat_room2["id"]
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=seller["id"], user_type="seller", is_archived=True
    )
    assert len(chat_rooms) == 1
    assert chat_rooms[0]["chat_room_id"] == chat_room["id"]


def test_archived_chat_room__other_party_with_multiple_rooms():
    buyer = create_user("1", can_buy=False)
    buyer2 = create_user("2", can_buy=False)
    seller = create_user("3", can_sell=False)

    buy_order = create_buy_order("1", user_id=str(buyer["id"]))
    buy_order2 = create_buy_order("2", user_id=str(buyer2["id"]))
    sell_order = create_sell_order("3", user_id=str(seller["id"]))

    match = create_match(
        "1", buy_order_id=str(buy_order["id"]), sell_order_id=str(sell_order["id"])
    )
    match2 = create_match(
        "2", buy_order_id=str(buy_order2["id"]), sell_order_id=str(sell_order["id"])
    )

    chat_room = create_chatroom(
        buyer_id=buyer["id"], seller_id=seller["id"], match_id=match["id"]
    )
    create_chatroom(
        buyer_id=buyer2["id"], seller_id=seller["id"], match_id=match2["id"]
    )

    chat_room_service.archive_room(user_id=seller["id"], chat_room_id=chat_room["id"])
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=buyer["id"], user_type="buyer", is_archived=False
    )
    assert len(chat_rooms) == 1
    assert chat_rooms[0]["chat_room_id"] == chat_room["id"]
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=buyer["id"], user_type="buyer", is_archived=True
    )
    assert len(chat_rooms) == 0


def test_archived_chat_room__outsider():
    buyer = create_user("1", can_buy=False)
    seller = create_user("2", can_sell=False)
    outsider = create_user("3", can_buy=False)

    buy_order = create_buy_order("1", user_id=str(buyer["id"]))
    sell_order = create_sell_order("2", user_id=str(seller["id"]))
    create_buy_order("3", user_id=str(outsider["id"]))

    match = create_match(
        "1", buy_order_id=str(buy_order["id"]), sell_order_id=str(sell_order["id"])
    )

    chat_room = create_chatroom(
        buyer_id=buyer["id"], seller_id=seller["id"], match_id=match["id"]
    )

    chat_room_service.archive_room(user_id=seller["id"], chat_room_id=chat_room["id"])
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=outsider["id"], user_type="buyer", is_archived=False
    )
    assert len(chat_rooms) == 0
    chat_rooms = chat_room_service.get_chat_rooms(
        user_id=outsider["id"], user_type="buyer", is_archived=True
    )
    assert len(chat_rooms) == 0
