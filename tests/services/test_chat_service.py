from datetime import datetime, timedelta

from src.config import APP_CONFIG
from src.services import ChatService
from tests.fixtures import (
    create_archived_chat_room,
    create_chat,
    create_chat_room,
    create_match,
    create_offer,
    create_user,
)
from tests.utils import assert_dict_in

chat_service = ChatService(config=APP_CONFIG)


# TODO refactor this mess
# - normal test for unarchived rooms (room, chats, buy_order, sell_order)
# - normal test for archived rooms
# - normal test for rooms the user is not in
# - test ordering by created_at
# - test the as_buyer, as_seller params
# - test is_revealed behavior
# - test latest_offer
def test_get_chats_by_user_id():
    me = create_user()

    match1 = create_match("345")
    match2 = create_match("456")
    chat_room1 = create_chat_room(
        "1", buyer_id=me["id"], is_buyer_revealed=False, match_id=match1["id"]
    )
    chat_room2 = create_chat_room(
        "2", seller_id=me["id"], is_seller_revealed=True, match_id=match2["id"]
    )
    create_chat_room("127")

    archived_match = create_match("789")
    archived_chat_room = create_chat_room(
        "3", seller_id=me["id"], is_seller_revealed=False, match_id=archived_match["id"]
    )
    create_archived_chat_room(chat_room_id=archived_chat_room["id"], user_id=me["id"])

    chat_room1["is_revealed"] = False
    chat_room2["is_revealed"] = True
    archived_chat_room["is_revealed"] = False
    for r in [chat_room1, chat_room2, archived_chat_room]:
        r.pop("is_buyer_revealed")
        r.pop("is_seller_revealed")

    chat_room1_chat1 = create_chat(
        "x",
        chat_room_id=chat_room1["id"],
        author_id=me["id"],
        created_at=datetime.now() + timedelta(hours=2),
    )
    chat_room1_chat2 = create_chat(
        "4",
        chat_room_id=chat_room1["id"],
        author_id=chat_room1["seller_id"],
        created_at=datetime.now() + timedelta(hours=3),
    )
    chat_room1_offer = create_offer(
        "5",
        chat_room_id=chat_room1["id"],
        author_id=me["id"],
        created_at=datetime.now() + timedelta(hours=1),
        offer_status="ACCEPTED",
    )
    chat_room2_chat1 = create_chat(
        "6",
        chat_room_id=chat_room2["id"],
        author_id=me["id"],
        created_at=datetime.now() + timedelta(hours=2),
    )
    chat_room2_chat2 = create_chat(
        "7",
        chat_room_id=chat_room2["id"],
        author_id=chat_room2["buyer_id"],
        created_at=datetime.now() + timedelta(hours=3),
    )
    chat_room2_offer = create_offer(
        "8",
        chat_room_id=chat_room2["id"],
        author_id=me["id"],
        created_at=datetime.now() + timedelta(hours=1),
        offer_status="REJECTED",
    )
    archived_chat_room_chat1 = create_chat(
        "9",
        chat_room_id=archived_chat_room["id"],
        author_id=me["id"],
        created_at=datetime.now() + timedelta(hours=2),
    )
    archived_chat_room_chat2 = create_chat(
        "315",
        chat_room_id=archived_chat_room["id"],
        author_id=archived_chat_room["buyer_id"],
        created_at=datetime.now() + timedelta(hours=3),
    )
    archived_chat_room_offer = create_offer(
        "203",
        chat_room_id=archived_chat_room["id"],
        author_id=me["id"],
        created_at=datetime.now() + timedelta(hours=1),
        offer_status="PENDING",
    )

    res = chat_service.get_chats_by_user_id(
        user_id=me["id"], as_buyer=True, as_seller=True
    )

    assert len(res["archived"]) == 1
    res_archived_chat_room = res["archived"][archived_chat_room["id"]]
    assert_dict_in(archived_chat_room, res_archived_chat_room)
    assert res_archived_chat_room["buy_order"]["id"] == archived_match["buy_order_id"]
    assert res_archived_chat_room["sell_order"]["id"] == archived_match["sell_order_id"]
    assert archived_chat_room_offer == res_archived_chat_room["latest_offer"]

    res_archived_chat_room_chats = res_archived_chat_room["chats"]
    assert_dict_in(archived_chat_room_offer, res_archived_chat_room_chats[0])
    assert_dict_in(archived_chat_room_chat1, res_archived_chat_room_chats[1])
    assert_dict_in(archived_chat_room_chat2, res_archived_chat_room_chats[2])

    assert len(res["unarchived"]) == 2
    unarchived_chat_rooms = res["unarchived"]

    assert_dict_in(chat_room1, unarchived_chat_rooms[chat_room1["id"]])
    assert (
        unarchived_chat_rooms[chat_room1["id"]]["buy_order"]["id"]
        == match1["buy_order_id"]
    )
    assert (
        unarchived_chat_rooms[chat_room1["id"]]["sell_order"]["id"]
        == match1["sell_order_id"]
    )
    assert unarchived_chat_rooms[chat_room1["id"]]["latest_offer"] == chat_room1_offer

    res_chat_room1_chats = unarchived_chat_rooms[chat_room1["id"]]["chats"]
    assert_dict_in(chat_room1_offer, res_chat_room1_chats[0])
    assert_dict_in(chat_room1_chat1, res_chat_room1_chats[1])
    assert_dict_in(chat_room1_chat2, res_chat_room1_chats[2])

    assert_dict_in(chat_room2, unarchived_chat_rooms[chat_room2["id"]])
    assert (
        unarchived_chat_rooms[chat_room2["id"]]["buy_order"]["id"]
        == match2["buy_order_id"]
    )
    assert (
        unarchived_chat_rooms[chat_room2["id"]]["sell_order"]["id"]
        == match2["sell_order_id"]
    )
    assert unarchived_chat_rooms[chat_room2["id"]]["latest_offer"] is None

    res_chat_room2_chats = unarchived_chat_rooms[chat_room2["id"]]["chats"]
    assert_dict_in(chat_room2_offer, res_chat_room2_chats[0])
    assert_dict_in(chat_room2_chat1, res_chat_room2_chats[1])
    assert_dict_in(chat_room2_chat2, res_chat_room2_chats[2])

    res_buyer = chat_service.get_chats_by_user_id(
        user_id=me["id"], as_buyer=True, as_seller=False
    )
    assert len(res_buyer["unarchived"]) == 1
    assert chat_room1["id"] in res_buyer["unarchived"]

    res_seller = chat_service.get_chats_by_user_id(
        user_id=me["id"], as_buyer=False, as_seller=True
    )
    assert len(res_seller["unarchived"]) == 1
    assert chat_room2["id"] in res_seller["unarchived"]
