from src.config import APP_CONFIG
from src.services import ChatRoomService, ChatService
from tests.fixtures import (
    create_buy_order,
    create_chatroom,
    create_match,
    create_sell_order,
    create_user,
)

chat_room_service = ChatRoomService(config=APP_CONFIG)
chat_service = ChatService(config=APP_CONFIG)


def test_create_chat_conversation():
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

    chat_conversation = chat_service.get_conversation(
        user_id=seller["id"], chat_room_id=chat_room["id"], user_type="seller"
    )
    assert chat_conversation["conversation"] == []


def test_create_new_message__buyer_create():
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
    chat_service.create_new_message(
        chat_room_id=chat_room["id"],
        message="hello",
        author_id=buyer["id"],
        user_type="buyer",
    )

    chat_conversation = chat_service.get_conversation(
        user_id=seller["id"], chat_room_id=chat_room["id"], user_type="seller"
    )
    assert chat_conversation["conversation"][0]["message"] == "hello"
    assert chat_conversation["conversation"][0]["user_type"] == "buyer"

    chat_conversation = chat_service.get_conversation(
        user_id=buyer["id"], chat_room_id=chat_room["id"], user_type="buyer"
    )
    assert chat_conversation["conversation"][0]["message"] == "hello"
    assert chat_conversation["conversation"][0]["user_type"] == "buyer"


def test_create_new_message__seller_create():
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
    chat_service.create_new_message(
        chat_room_id=chat_room["id"],
        message="hello",
        author_id=seller["id"],
        user_type="seller",
    )

    chat_conversation = chat_service.get_conversation(
        user_id=seller["id"], chat_room_id=chat_room["id"], user_type="seller"
    )
    assert chat_conversation["conversation"][0]["message"] == "hello"
    assert chat_conversation["conversation"][0]["user_type"] == "seller"

    chat_conversation = chat_service.get_conversation(
        user_id=buyer["id"], chat_room_id=chat_room["id"], user_type="buyer"
    )
    assert chat_conversation["conversation"][0]["message"] == "hello"
    assert chat_conversation["conversation"][0]["user_type"] == "seller"


def test_create_new_conversation__multiple_offers():
    buyer = create_user("1", can_buy=False)
    seller = create_user("2", can_sell=False)
    buy_order = create_buy_order("1", user_id=str(buyer["id"]))
    create_buy_order("2", user_id=str(buyer["id"]))
    sell_order = create_sell_order("3", user_id=str(seller["id"]))
    create_sell_order("4", user_id=str(seller["id"]))
    match = create_match(
        "1", buy_order_id=str(buy_order["id"]), sell_order_id=str(sell_order["id"])
    )
    chat_room = create_chatroom(
        buyer_id=buyer["id"], seller_id=seller["id"], match_id=match["id"]
    )

    chat_conversation = chat_service.get_conversation(
        user_id=seller["id"], chat_room_id=chat_room["id"], user_type="seller"
    )
    assert chat_conversation["conversation"] == []


def test_create_new_conversation__multiple_users():
    buyer = create_user("1", can_buy=False)
    create_user("2", can_buy=False)
    seller = create_user("3", can_sell=False)
    create_user("4", can_sell=False)
    buy_order = create_buy_order("1", user_id=str(buyer["id"]))
    sell_order = create_sell_order("2", user_id=str(seller["id"]))
    match = create_match(
        "1", buy_order_id=str(buy_order["id"]), sell_order_id=str(sell_order["id"])
    )
    chat_room = create_chatroom(
        buyer_id=buyer["id"], seller_id=seller["id"], match_id=match["id"]
    )

    chat_conversation = chat_service.get_conversation(
        user_id=seller["id"], chat_room_id=chat_room["id"], user_type="seller"
    )
    assert chat_conversation["conversation"] == []
