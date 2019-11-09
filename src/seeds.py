from datetime import datetime

from src.database import (
    BuyOrder,
    ChatRoom,
    Match,
    Round,
    Security,
    SellOrder,
    User,
    session_scope,
)


def seed_db():
    with session_scope() as session:

        # add users
        user_seeds = [
            {
                "email": "nwjbrandon.ochemmaster@gmail.com",
                "provider": "linkedin",
                "full_name": "Brandon Ng",
                "display_image_url": None,
                "can_buy": True,
                "can_sell": True,
                "is_committee": True,
                "provider_user_id": "ynA5G0JDks",
            },
            {
                "email": "brandon.ng10@yahoo.com.sg",
                "provider": "linkedin",
                "full_name": "Brandon Ng",
                "display_image_url": None,
                "can_buy": True,
                "can_sell": True,
                "is_committee": True,
                "provider_user_id": "8tJpx5jWUx",
            },
        ]
        for user in user_seeds:
            if session.query(User).filter_by(email=user.get("email")).count() == 0:
                session.add(
                    User(
                        email=user.get("email"),
                        provider=user.get("provider"),
                        display_image_url=user.get("display_image_url"),
                        full_name=user.get("full_name"),
                        can_buy=user.get("can_buy"),
                        can_sell=user.get("can_sell"),
                        is_committee=user.get("is_committee"),
                        provider_user_id=user.get("provider_user_id"),
                    )
                )
        brandon_gmail_id = (
            session.query(User)
            .filter_by(email="nwjbrandon.ochemmaster@gmail.com")
            .first()
            .id
        )
        brandon_yahoo_id = (
            session.query(User).filter_by(email="brandon.ng10@yahoo.com.sg").first().id
        )

        # adds security
        if session.query(Security).filter_by(name="Grab").count() == 0:
            session.add(Security(name="Grab"))
        grab_security_id = session.query(Security).filter_by(name="Grab").first().id

        # creates round
        current_round_end_time = datetime.now()
        if session.query(Round).filter_by(end_time=current_round_end_time).count() == 0:
            session.add(Round(end_time=current_round_end_time, is_concluded=True))
        current_round_id = session.query(Round).first().id

        # create buy orders
        if (
            session.query(BuyOrder).filter_by(user_id=str(brandon_gmail_id)).count()
            == 0
        ):
            session.add(
                BuyOrder(
                    user_id=str(brandon_gmail_id),
                    security_id=str(grab_security_id),
                    number_of_shares=100,
                    price=10,
                    round_id=str(current_round_id),
                )
            )
        if (
            session.query(BuyOrder).filter_by(user_id=str(brandon_yahoo_id)).count()
            == 0
        ):
            session.add(
                BuyOrder(
                    user_id=str(brandon_yahoo_id),
                    security_id=str(grab_security_id),
                    number_of_shares=200,
                    price=10,
                    round_id=str(current_round_id),
                )
            )
        brandon_gmail_buy_order_id = (
            session.query(BuyOrder).filter_by(user_id=str(brandon_gmail_id)).first().id
        )
        brandon_yahoo_buy_order_id = (
            session.query(BuyOrder).filter_by(user_id=str(brandon_yahoo_id)).first().id
        )

        # create sell orders
        if (
            session.query(SellOrder).filter_by(user_id=str(brandon_gmail_id)).count()
            == 0
        ):
            session.add(
                SellOrder(
                    user_id=str(brandon_gmail_id),
                    security_id=str(grab_security_id),
                    number_of_shares=300,
                    price=10,
                    round_id=str(current_round_id),
                )
            )
        if (
            session.query(SellOrder).filter_by(user_id=str(brandon_yahoo_id)).count()
            == 0
        ):
            session.add(
                SellOrder(
                    user_id=str(brandon_yahoo_id),
                    security_id=str(grab_security_id),
                    number_of_shares=400,
                    price=10,
                    round_id=str(current_round_id),
                )
            )
        brandon_gmail_sell_order_id = (
            session.query(SellOrder).filter_by(user_id=str(brandon_gmail_id)).first().id
        )
        brandon_yahoo_sell_order_id = (
            session.query(SellOrder).filter_by(user_id=str(brandon_yahoo_id)).first().id
        )

        if session.query(Match).count() == 0:
            session.add(
                Match(
                    buy_order_id=str(brandon_gmail_buy_order_id),
                    sell_order_id=str(brandon_yahoo_sell_order_id),
                )
            )
            session.add(
                Match(
                    buy_order_id=str(brandon_yahoo_buy_order_id),
                    sell_order_id=str(brandon_gmail_sell_order_id),
                )
            )

        match_A = (
            session.query(Match)
            .filter_by(sell_order_id=str(brandon_gmail_sell_order_id))
            .first()
            .id
        )
        match_B = (
            session.query(Match)
            .filter_by(sell_order_id=str(brandon_yahoo_sell_order_id))
            .first()
            .id
        )
        # create chatrooms
        if (
            session.query(ChatRoom).filter_by(seller_id=str(brandon_gmail_id)).count()
            == 0
        ):
            session.add(
                ChatRoom(
                    buyer_id=str(brandon_yahoo_id),
                    seller_id=str(brandon_gmail_id),
                    match_id=str(match_A),
                )
            )
        if (
            session.query(ChatRoom).filter_by(seller_id=str(brandon_yahoo_id)).count()
            == 0
        ):
            session.add(
                ChatRoom(
                    buyer_id=str(brandon_gmail_id),
                    seller_id=str(brandon_yahoo_id),
                    match_id=str(match_B),
                )
            )


if __name__ == "__main__":
    seed_db()
