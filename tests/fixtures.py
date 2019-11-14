from datetime import datetime, timedelta

from src.database import (
    ArchivedChatRoom,
    BannedPair,
    BuyOrder,
    Chat,
    ChatRoom,
    Match,
    Offer,
    Round,
    Security,
    SellOrder,
    User,
    UserRequest,
    session_scope,
)


def combine_dicts(original, default_boxed):
    res = original.copy()
    for k, box_value in default_boxed.items():
        if k not in original:
            res[k] = box_value()

    return res


def attributes_for_user(id="", **kwargs):
    return {
        "email": f"a{id}@a",
        "provider_user_id": f"abcdef{id}",
        "full_name": f"a{id}",
        "display_image_url": "https://loremflickr.com/320/240",
        "can_buy": True,
        "can_sell": True,
        "is_committee": True,
        "provider": f"{id}",
        "auth_token": None,
        **kwargs,
    }


def attributes_for_security(id="", **kwargs):
    return {"name": f"a{id}", "market_price": 6.35, **kwargs}


def attributes_for_sell_order(id=0, **kwargs):
    return {"number_of_shares": 20 + int(id), "price": 30 + int(id), **kwargs}


def attributes_for_buy_order(id=0, **kwargs):
    return {"number_of_shares": 20 + int(id), "price": 30 + int(id), **kwargs}


def attributes_for_match(id=0, **kwargs):
    return {"number_of_shares": 20 + int(id), "price": 30 + int(id), **kwargs}


def attributes_for_round(id=0, **kwargs):
    return {
        "end_time": datetime.now() + timedelta(days=1 + int(id)),
        "is_concluded": False,
        **kwargs,
    }


def attributes_for_chat(id=0, **kwargs):
    return {"message": f"asdf{id}", **kwargs}


def attributes_for_offer(id=0, **kwargs):
    return {"number_of_shares": 20 + int(id), "price": 30 + int(id), **kwargs}


def create_user(id="", **kwargs):
    with session_scope() as session:
        user = User(**attributes_for_user(id, **kwargs))
        session.add(user)
        session.commit()
        return user.asdict()


def create_security(id="", **kwargs):
    with session_scope() as session:
        security = Security(**attributes_for_security(id, **kwargs))
        session.add(security)
        session.commit()
        return security.asdict()


def create_sell_order(id=0, **kwargs):
    with session_scope() as session:
        sell_order = SellOrder(
            **combine_dicts(
                attributes_for_sell_order(id, **kwargs),
                {
                    "user_id": lambda: create_user(id)["id"],
                    "security_id": lambda: create_security(id)["id"],
                    "round_id": lambda: create_round(id)["id"],
                },
            )
        )

        session.add(sell_order)
        session.commit()
        return sell_order.asdict()


def create_buy_order(id=0, **kwargs):
    with session_scope() as session:
        buy_order = BuyOrder(
            **combine_dicts(
                attributes_for_buy_order(id, **kwargs),
                {
                    "user_id": lambda: create_user(id)["id"],
                    "security_id": lambda: create_security(id)["id"],
                    "round_id": lambda: create_round(id)["id"],
                },
            )
        )

        session.add(buy_order)
        session.commit()
        return buy_order.asdict()


def create_match(id=0, **kwargs):
    with session_scope() as session:
        match = Match(
            **combine_dicts(
                attributes_for_match(id, **kwargs),
                {
                    "buy_order_id": lambda: create_buy_order(id + "0")["id"],
                    "sell_order_id": lambda: create_sell_order(id + "1")["id"],
                },
            )
        )
        session.add(match)
        session.commit()
        return match.asdict()


def create_round(id=0, **kwargs):
    with session_scope() as session:
        round = Round(**attributes_for_round(id, **kwargs))
        session.add(round)
        session.commit()
        return round.asdict()


def create_banned_pair(id=0, **kwargs):
    with session_scope() as session:
        banned_pair = BannedPair(
            **combine_dicts(
                kwargs,
                {
                    "buyer_id": lambda: create_user(str(id) + "0")["id"],
                    "seller_id": lambda: create_user(str(id) + "1")["id"],
                },
            )
        )
        session.add(banned_pair)
        session.commit()
        return banned_pair.asdict()


def create_chat_room(id=0, **kwargs):
    with session_scope() as session:
        chat_room = ChatRoom(
            **combine_dicts(
                kwargs,
                {
                    "buyer_id": lambda: create_user(str(id) + "0")["id"],
                    "seller_id": lambda: create_user(str(id) + "1")["id"],
                    "match_id": lambda: create_match(str(id) + "2")["id"],
                },
            )
        )
        session.add(chat_room)
        session.commit()
        return chat_room.asdict()


def create_archived_chat_room(id=0, **kwargs):
    with session_scope() as session:
        archived_chat_room = ArchivedChatRoom(
            **combine_dicts(
                kwargs,
                {
                    "user_id": lambda: create_user(str(id) + "0")["id"],
                    "chat_room_id": lambda: create_chat_room(str(id) + "1")["id"],
                },
            )
        )
        session.add(archived_chat_room)
        session.commit()
        return archived_chat_room.asdict()


def create_chat(id=0, **kwargs):
    with session_scope() as session:
        chat = Chat(
            **combine_dicts(
                attributes_for_chat(id, **kwargs),
                {
                    "chat_room_id": lambda: create_chat_room(str(id) + "0")["id"],
                    "author_id": lambda: create_user(str(id) + "1")["id"],
                },
            )
        )
        session.add(chat)
        session.commit()
        return chat.asdict()


def create_offer(id=0, **kwargs):
    with session_scope() as session:
        offer = Offer(
            **combine_dicts(
                attributes_for_offer(id, **kwargs),
                {
                    "chat_room_id": lambda: create_chat_room(str(id) + "0")["id"],
                    "author_id": lambda: create_user(str(id) + "1")["id"],
                },
            )
        )
        session.add(offer)
        session.commit()
        return offer.asdict()


def create_user_request(id=0, **kwargs):
    with session_scope() as session:
        user_request = UserRequest(
            **combine_dicts(
                kwargs,
                {
                    "user_id": lambda: create_user(str(id))["id"],
                    "is_buy": lambda: False,
                    "closed_by_user_id": lambda: None,
                },
            )
        )
        session.add(user_request)
        session.commit()
        return user_request.asdict()
