from collections import defaultdict
from datetime import datetime, timezone

import requests
from sqlalchemy import and_
from sqlalchemy.sql import func

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
from src.email_service import EmailService
from src.exceptions import (
    InvalidRequestException,
    InvisibleUnauthorizedException,
    ResourceNotFoundException,
    ResourceNotOwnedException,
    UnauthorizedException,
    UserProfileNotFoundException,
)
from src.match import match_buyers_and_sellers
from src.schemata import (
    AUTHENTICATE_SCHEMA,
    CREATE_BUY_ORDER_SCHEMA,
    CREATE_SELL_ORDER_SCHEMA,
    DELETE_ORDER_SCHEMA,
    EDIT_MARKET_PRICE_SCHEMA,
    EDIT_ORDER_SCHEMA,
    GET_AUTH_URL_SHCMEA,
    UUID_RULE,
    validate_input,
)


class UserService:
    def __init__(self, config):
        self.config = config
        self.email_service = EmailService(config)

    def create_if_not_exists(
        self, email, display_image_url, full_name, provider_user_id, is_buy, auth_token
    ):
        with session_scope() as session:
            user = (
                session.query(User)
                .filter_by(provider_user_id=provider_user_id)
                .one_or_none()
            )
            if user is None:
                user = User(
                    email=email,
                    full_name=full_name,
                    display_image_url=display_image_url,
                    provider="linkedin",
                    can_buy=False,
                    can_sell=False,
                    provider_user_id=provider_user_id,
                    auth_token=auth_token,
                )
                session.add(user)
                session.flush()

                buy_req = UserRequest(user_id=str(user.id), is_buy=True)
                session.add(buy_req)
                if not is_buy:
                    sell_req = UserRequest(user_id=str(user.id), is_buy=False)
                    session.add(sell_req)

                email_template = "register_buyer" if is_buy else "register_seller"
                self.email_service.send_email(emails=[email], template=email_template)

                committee_emails = [
                    u.email
                    for u in session.query(User).filter_by(is_committee=True).all()
                ]
                self.email_service.send_email(
                    emails=committee_emails, template="new_user_review"
                )
            else:
                user.email = email
                user.full_name = full_name
                user.display_image_url = display_image_url
                user.auth_token = auth_token

            session.commit()
            return user.asdict()

    def get_user_by_linkedin_id(self, provider_user_id):
        with session_scope() as session:
            user = (
                session.query(User)
                .filter_by(provider_user_id=provider_user_id)
                .one_or_none()
            )
            if user is None:
                raise ResourceNotFoundException()
            user_dict = user.asdict()
        return user_dict


class SellOrderService:
    def __init__(self, config):
        self.config = config
        self.email_service = EmailService(config)

    @validate_input(CREATE_SELL_ORDER_SCHEMA)
    def create_order(self, user_id, number_of_shares, price, security_id, scheduler):
        with session_scope() as session:
            user = session.query(User).get(user_id)
            if user is None:
                raise ResourceNotFoundException()
            if user.asdict()["can_sell"] == "NO":
                raise UnauthorizedException("User cannot place sell orders.")

            sell_order_count = (
                session.query(SellOrder).filter_by(user_id=user_id).count()
            )
            if sell_order_count >= self.config["ACQUITY_SELL_ORDER_PER_ROUND_LIMIT"]:
                raise UnauthorizedException("Limit of sell orders reached.")

            sell_order = SellOrder(
                user_id=user_id,
                number_of_shares=number_of_shares,
                price=price,
                security_id=security_id,
            )

            active_round = RoundService(self.config).get_active()
            if active_round is None:
                session.add(sell_order)
                session.commit()
                if RoundService(self.config).should_round_start():
                    RoundService(self.config).create_new_round_and_set_orders(scheduler)
            else:
                sell_order.round_id = active_round["id"]
                session.add(sell_order)

            session.commit()

            self.email_service.send_email(
                emails=[user.email], template="create_sell_order"
            )

            return sell_order.asdict()

    @validate_input({"user_id": UUID_RULE})
    def get_orders_by_user(self, user_id):
        with session_scope() as session:
            sell_orders = session.query(SellOrder).filter_by(user_id=user_id).all()
            return [sell_order.asdict() for sell_order in sell_orders]

    @validate_input({"id": UUID_RULE, "user_id": UUID_RULE})
    def get_order_by_id(self, id, user_id):
        with session_scope() as session:
            order = session.query(SellOrder).get(id)
            if order is None:
                raise ResourceNotFoundException()
            if order.user_id != user_id:
                raise ResourceNotOwnedException()
            return order.asdict()

    @validate_input(EDIT_ORDER_SCHEMA)
    def edit_order(self, id, subject_id, new_number_of_shares=None, new_price=None):
        with session_scope() as session:
            sell_order = session.query(SellOrder).get(id)
            if sell_order is None:
                raise ResourceNotFoundException()
            if sell_order.user_id != subject_id:
                raise ResourceNotOwnedException("You need to own this order.")

            if new_number_of_shares is not None:
                sell_order.number_of_shares = new_number_of_shares
            if new_price is not None:
                sell_order.price = new_price

            session.commit()

            user = session.query(User).get(sell_order.user_id)
            self.email_service.send_email(
                emails=[user.email], template="edit_sell_order"
            )

            return sell_order.asdict()

    @validate_input(DELETE_ORDER_SCHEMA)
    def delete_order(self, id, subject_id):
        with session_scope() as session:
            sell_order = session.query(SellOrder).get(id)
            if sell_order is None:
                raise ResourceNotFoundException()
            if sell_order.user_id != subject_id:
                raise ResourceNotOwnedException("You need to own this order.")

            session.delete(sell_order)
        return {}


class BuyOrderService:
    def __init__(self, config):
        self.config = config
        self.email_service = EmailService(config)

    @validate_input(CREATE_BUY_ORDER_SCHEMA)
    def create_order(self, user_id, number_of_shares, price, security_id):
        with session_scope() as session:
            user = session.query(User).get(user_id)
            if user is None:
                raise ResourceNotFoundException()
            if user.asdict()["can_buy"] == "NO":
                raise UnauthorizedException("User cannot place buy orders.")

            buy_order_count = session.query(BuyOrder).filter_by(user_id=user_id).count()
            if buy_order_count >= self.config["ACQUITY_BUY_ORDER_PER_ROUND_LIMIT"]:
                raise UnauthorizedException("Limit of buy orders reached.")

            active_round = RoundService(self.config).get_active()

            buy_order = BuyOrder(
                user_id=user_id,
                number_of_shares=number_of_shares,
                price=price,
                security_id=security_id,
                round_id=(active_round and active_round["id"]),
            )

            session.add(buy_order)
            session.commit()

            self.email_service.send_email(
                emails=[user.email], template="create_buy_order"
            )

            return buy_order.asdict()

    @validate_input({"user_id": UUID_RULE})
    def get_orders_by_user(self, user_id):
        with session_scope() as session:
            buy_orders = session.query(BuyOrder).filter_by(user_id=user_id).all()
            return [buy_order.asdict() for buy_order in buy_orders]

    @validate_input({"id": UUID_RULE, "user_id": UUID_RULE})
    def get_order_by_id(self, id, user_id):
        with session_scope() as session:
            order = session.query(BuyOrder).get(id)
            if order is None:
                raise ResourceNotFoundException()
            if order.user_id != user_id:
                raise ResourceNotOwnedException()
            return order.asdict()

    @validate_input(EDIT_ORDER_SCHEMA)
    def edit_order(self, id, subject_id, new_number_of_shares=None, new_price=None):
        with session_scope() as session:
            buy_order = session.query(BuyOrder).get(id)
            if buy_order is None:
                raise ResourceNotFoundException()
            if buy_order.user_id != subject_id:
                raise ResourceNotOwnedException("You need to own this order.")

            if new_number_of_shares is not None:
                buy_order.number_of_shares = new_number_of_shares
            if new_price is not None:
                buy_order.price = new_price

            session.commit()

            user = session.query(User).get(buy_order.user_id)
            self.email_service.send_email(
                emails=[user.email], template="edit_buy_order"
            )

            return buy_order.asdict()

    @validate_input(DELETE_ORDER_SCHEMA)
    def delete_order(self, id, subject_id):
        with session_scope() as session:
            buy_order = session.query(BuyOrder).get(id)
            if buy_order is None:
                raise ResourceNotFoundException()
            if buy_order.user_id != subject_id:
                raise ResourceNotOwnedException("You need to own this order.")

            session.delete(buy_order)
        return {}


class SecurityService:
    def __init__(self, config):
        self.config = config

    def get_all(self):
        with session_scope() as session:
            return [sec.asdict() for sec in session.query(Security).all()]

    @validate_input(EDIT_MARKET_PRICE_SCHEMA)
    def edit_market_price(self, id, subject_id, market_price):
        with session_scope() as session:
            security = session.query(Security).get(id)
            if security is None:
                raise ResourceNotFoundException()

            subject = session.query(User).get(subject_id)
            if not subject.is_committee:
                raise UnauthorizedException(
                    "You need to be a committee of this security."
                )

            security.market_price = market_price
            session.commit()
            return security.asdict()


class RoundService:
    def __init__(self, config):
        self.config = config
        self.email_service = EmailService(config)

    def get_all(self):
        with session_scope() as session:
            return [r.asdict() for r in session.query(Round).all()]

    def get_active(self):
        with session_scope() as session:
            active_round = (
                session.query(Round)
                .filter(Round.end_time >= datetime.now(), Round.is_concluded == False)
                .one_or_none()
            )
            return active_round and active_round.asdict()

    def should_round_start(self):
        with session_scope() as session:
            unique_sellers = (
                session.query(SellOrder.user_id)
                .filter_by(round_id=None)
                .distinct()
                .count()
            )
            if (
                unique_sellers
                >= self.config["ACQUITY_ROUND_START_NUMBER_OF_SELLERS_CUTOFF"]
            ):
                return True

            total_shares = (
                session.query(func.sum(SellOrder.number_of_shares))
                .filter_by(round_id=None)
                .scalar()
                or 0
            )
            return (
                total_shares
                >= self.config["ACQUITY_ROUND_START_TOTAL_SELL_SHARES_CUTOFF"]
            )

    def create_new_round_and_set_orders(self, scheduler):
        with session_scope() as session:
            end_time = datetime.now(timezone.utc) + self.config["ACQUITY_ROUND_LENGTH"]
            new_round = Round(end_time=end_time, is_concluded=False)
            session.add(new_round)
            session.flush()

            for sell_order in session.query(SellOrder).filter_by(round_id=None):
                sell_order.round_id = str(new_round.id)
            for buy_order in session.query(BuyOrder).filter_by(round_id=None):
                buy_order.round_id = str(new_round.id)

            emails = [user.email for user in session.query(User).all()]
            self.email_service.send_email(emails, template="round_opened")

        if scheduler is not None:
            scheduler.add_job(
                MatchService(self.config).run_matches, "date", run_date=end_time
            )

    @validate_input({"security_id": UUID_RULE})
    def get_previous_round_statistics(self, security_id):
        return None


class MatchService:
    def __init__(self, config):
        self.config = config
        self.email_service = EmailService(config)

    def run_matches(self):
        round_id = RoundService(self.config).get_active()["id"]
        buy_orders, sell_orders, banned_pairs = self._get_matching_params(round_id)

        match_results = match_buyers_and_sellers(buy_orders, sell_orders, banned_pairs)

        buy_order_to_buyer_dict = {
            order["id"]: order["user_id"] for order in buy_orders
        }
        sell_order_to_seller_dict = {
            order["id"]: order["user_id"] for order in sell_orders
        }

        self._add_db_objects(
            round_id, match_results, sell_order_to_seller_dict, buy_order_to_buyer_dict
        )
        self._send_emails(buy_orders, sell_orders, match_results)

    def _get_matching_params(self, round_id):
        with session_scope() as session:
            buy_orders = [
                b.asdict()
                for b in session.query(BuyOrder)
                .join(User, User.id == BuyOrder.user_id)
                .filter(BuyOrder.round_id == round_id, User.can_buy)
                .all()
            ]
            sell_orders = [
                s.asdict()
                for s in session.query(SellOrder)
                .join(User, User.id == SellOrder.user_id)
                .filter(SellOrder.round_id == round_id, User.can_sell)
                .all()
            ]
            banned_pairs = [
                (bp.buyer_id, bp.seller_id) for bp in session.query(BannedPair).all()
            ]

        return buy_orders, self._double_sell_orders(sell_orders), banned_pairs

    def _double_sell_orders(self, sell_orders):
        seller_counts = defaultdict(lambda: 0)
        for sell_order in sell_orders:
            seller_counts[sell_order["user_id"]] += 1

        new_sell_orders = []
        for sell_order in sell_orders:
            new_sell_orders.append(sell_order)
            if seller_counts[sell_order["user_id"]] == 1:
                new_sell_orders.append(sell_order)

        return new_sell_orders

    def _add_db_objects(
        self,
        round_id,
        match_results,
        sell_order_to_seller_dict,
        buy_order_to_buyer_dict,
    ):
        with session_scope() as session:
            for buy_order_id, sell_order_id in match_results:
                match = Match(buy_order_id=buy_order_id, sell_order_id=sell_order_id)
                session.add(match)
                session.flush()
                chat_room = ChatRoom(
                    seller_id=sell_order_to_seller_dict[sell_order_id],
                    buyer_id=buy_order_to_buyer_dict[buy_order_id],
                    match_id=str(match.id),
                )
                session.add(chat_room)

            session.query(Round).get(round_id).is_concluded = True

    def _send_emails(self, buy_orders, sell_orders, match_results):
        matched_uuids = set()
        for buy_order_uuid, sell_order_uuid in match_results:
            matched_uuids.add(buy_order_uuid)
            matched_uuids.add(sell_order_uuid)

        all_user_ids = set()
        matched_user_ids = set()
        for buy_order in buy_orders:
            all_user_ids.add(buy_order["user_id"])
            if buy_order["id"] in matched_uuids:
                matched_user_ids.add(buy_order["user_id"])
        for sell_order in sell_orders:
            all_user_ids.add(sell_order["user_id"])
            if sell_order["id"] in matched_uuids:
                matched_user_ids.add(sell_order["user_id"])

        with session_scope() as session:
            matched_emails = [
                user.email
                for user in session.query(User)
                .filter(User.id.in_(matched_user_ids))
                .all()
            ]
            self.email_service.send_email(
                matched_emails, template="match_done_has_match"
            )

            unmatched_emails = [
                user.email
                for user in session.query(User)
                .filter(User.id.in_(all_user_ids - matched_user_ids))
                .all()
            ]
            self.email_service.send_email(
                unmatched_emails, template="match_done_no_match"
            )


class BannedPairService:
    def __init__(self, config):
        self.config = config

    @validate_input({"my_user_id": UUID_RULE, "other_user_id": UUID_RULE})
    def ban_user(self, my_user_id, other_user_id):
        # Currently this bans the user two-way: both as buyer and as seller
        with session_scope() as session:
            session.add_all(
                [
                    BannedPair(buyer_id=my_user_id, seller_id=other_user_id),
                    BannedPair(buyer_id=other_user_id, seller_id=my_user_id),
                ]
            )


class OfferService:
    def __init__(self, config):
        self.config = config

    def create_new_offer(
        self, chat_room_id, author_id, price, number_of_shares, user_type
    ):
        with session_scope() as session:
            OfferService._check_deal_status(
                session=session,
                chat_room_id=chat_room_id,
                user_id=author_id,
                user_type=user_type,
            )
            chat_room = session.query(ChatRoom).get(chat_room_id)
            offer = Offer(
                chat_room_id=str(chat_room_id),
                price=price,
                number_of_shares=number_of_shares,
                author_id=str(author_id),
            )
            offer = OfferService._get_current_offer(session=session, offer=offer)
            OfferService._update_chatroom_datetime(
                session=session, chat_room=chat_room, offer=offer
            )
            return OfferService._serialize_chat_offer(
                chat_room_id=chat_room_id,
                offer=offer,
                is_deal_closed=chat_room.is_deal_closed,
                user_type=user_type,
                user_id=author_id,
            )

    def accept_offer(self, chat_room_id, offer_id, user_id, user_type):
        with session_scope() as session:
            OfferService._check_deal_status(
                session=session,
                chat_room_id=chat_room_id,
                user_id=user_id,
                user_type=user_type,
            )
            chat_room = session.query(ChatRoom).get(chat_room_id)
            offer = session.query(Offer).filter_by(id=offer_id).one()

            if offer.offer_status != "PENDING":
                raise InvalidRequestException("Offer is closed")
            if offer.author_id != user_id:
                OfferService._update_offer_status(
                    session=session,
                    chat_room=chat_room,
                    offer=offer,
                    offer_status="ACCEPTED",
                    is_deal_closed=True,
                )
            offer = OfferService._get_current_offer(session=session, offer=offer)
            return OfferService._serialize_chat_offer(
                chat_room_id=chat_room_id,
                offer=offer,
                is_deal_closed=chat_room.is_deal_closed,
                user_type=user_type,
                user_id=user_id,
            )

    def reject_offer(self, chat_room_id, offer_id, user_id, user_type):
        with session_scope() as session:
            OfferService._check_deal_status(
                session=session,
                chat_room_id=chat_room_id,
                user_id=user_id,
                user_type=user_type,
            )
            chat_room = session.query(ChatRoom).get(chat_room_id)
            offer = session.query(Offer).filter_by(id=offer_id).one()
            if offer.offer_status != "PENDING":
                raise InvalidRequestException("Offer is closed")
            OfferService._update_offer_status(
                session=session,
                chat_room=chat_room,
                offer=offer,
                offer_status="REJECTED",
                is_deal_closed=False,
            )
            offer = OfferService._get_current_offer(session=session, offer=offer)
            OfferService._update_chatroom_datetime(
                session=session, chat_room=chat_room, offer=offer
            )
            return OfferService._serialize_chat_offer(
                chat_room_id=chat_room_id,
                offer=offer,
                is_deal_closed=chat_room.is_deal_closed,
                user_type=user_type,
                user_id=user_id,
            )

    def get_chat_offers(self, user_id, user_type, chat_room_id):
        with session_scope() as session:
            results = session.query(Offer).filter_by(chat_room_id=chat_room_id).all()
            data = []
            for result in results:
                data.append(
                    OfferService._serialize_offer(
                        offer=result.asdict(), user_type=user_type, user_id=user_id
                    )
                )
            return data

    @staticmethod
    def _check_deal_status(session, chat_room_id, user_id, user_type):
        chat_room = session.query(ChatRoom).get(chat_room_id)
        if chat_room is None:
            raise ResourceNotFoundException("Chat room not found")
        if chat_room.is_deal_closed:
            raise InvalidRequestException("Deal is closed")
        OfferService._verify_user(
            chat_room=chat_room, user_id=user_id, user_type=user_type
        )

    @staticmethod
    def _serialize_offer(offer, user_type, user_id):
        other_user_type = "buyer" if user_type == "seller" else "seller"
        return {
            "id": offer.get("id"),
            "price": offer.get("price"),
            "number_of_shares": offer.get("number_of_shares"),
            "offer_status": offer.get("offer_status"),
            "created_at": datetime.timestamp(offer.get("created_at")) * 1000,
            "user_type": user_type
            if offer.get("author_id") == user_id
            else other_user_type,
            "type": "offer",
        }

    @staticmethod
    def _serialize_chat_offer(chat_room_id, offer, is_deal_closed, user_type, user_id):
        return {
            "chat_room_id": chat_room_id,
            "updated_at": datetime.timestamp(offer.get("created_at")) * 1000,
            "new_chat": OfferService._serialize_offer(
                offer=offer, user_type=user_type, user_id=user_id
            ),
            "is_deal_closed": is_deal_closed,
        }

    @staticmethod
    def _get_current_offer(session, offer):
        session.add(offer)
        session.flush()
        session.refresh(offer)
        return offer.asdict()

    @staticmethod
    def _update_chatroom_datetime(session, chat_room, offer):
        chat_room.updated_at = offer.get("created_at")
        session.commit()

    @staticmethod
    def _verify_user(chat_room, user_id, user_type):
        if (user_type == "buyer" and chat_room.buyer_id != user_id) or (
            user_type == "seller" and chat_room.seller_id != user_id
        ):
            raise ResourceNotOwnedException("Wrong user")

    @staticmethod
    def _update_offer_status(session, offer, chat_room, offer_status, is_deal_closed):
        chat_room.updated_at = offer.created_at
        chat_room.is_deal_closed = is_deal_closed
        offer.offer_status = offer_status
        session.commit()


class ChatService:
    def __init__(self, config):
        self.config = config

    def get_chat_by_users(self, user_id):
        pass

    def create_new_message(self, chat_room_id, message, author_id, user_type):
        with session_scope() as session:
            chat_room = session.query(ChatRoom).get(chat_room_id)
            if chat_room is None:
                raise ResourceNotFoundException("Chat room not found")
            ChatService._verify_user(
                chat_room=chat_room, user_id=author_id, user_type=user_type
            )
            message = Chat(
                chat_room_id=str(chat_room_id),
                message=message,
                author_id=str(author_id),
            )
            message = ChatService._get_current_message(session=session, message=message)
            ChatService._update_chatroom_datetime(
                session=session, chat_room=chat_room, message=message
            )

            return ChatService._serialize_chat_message(
                chat_room_id=chat_room_id,
                message=message,
                user_type=user_type,
                user_id=author_id,
            )

    def get_chat_messages(self, chat_room_id, user_type, user_id):
        with session_scope() as session:
            results = session.query(Chat).filter_by(chat_room_id=chat_room_id).all()
            data = []
            for result in results:
                data.append(
                    ChatService._serialize_message(
                        message=result.asdict(), user_type=user_type, user_id=user_id
                    )
                )
            return data

    def get_conversation(self, user_id, chat_room_id, user_type):
        with session_scope() as session:
            chat_room = session.query(ChatRoom).get(chat_room_id)
            if chat_room is None:
                raise ResourceNotFoundException("Chat room not found")
            ChatService._verify_user(
                chat_room=chat_room, user_id=user_id, user_type=user_type
            )
            results = (
                session.query(ChatRoom, Match, BuyOrder, SellOrder)
                .filter(ChatRoom.id == chat_room_id)
                .outerjoin(Match, ChatRoom.match_id == Match.id)
                .outerjoin(BuyOrder, Match.buy_order_id == BuyOrder.id)
                .outerjoin(SellOrder, Match.sell_order_id == SellOrder.id)
                .one()
            )

            chat_room = results[0].asdict()
            buy_order = results[2].asdict()
            sell_order = results[3].asdict()

            offers = OfferService(self.config).get_chat_offers(
                user_id=user_id, chat_room_id=chat_room_id, user_type=user_type
            )
            messages = self.get_chat_messages(
                chat_room_id=chat_room_id, user_type=user_type, user_id=user_id
            )

            return {
                "chat_room_id": chat_room_id,
                "seller_price": sell_order.get("price"),
                "seller_number_of_shares": sell_order.get("number_of_shares"),
                "buyer_price": buy_order.get("price"),
                "buyer_number_of_shares": buy_order.get("number_of_shares"),
                "updated_at": datetime.timestamp(chat_room.get("updated_at")) * 1000,
                "is_deal_closed": chat_room.get("is_deal_closed"),
                "conversation": sorted(
                    messages + offers, key=lambda item: item["created_at"]
                ),
            }

    @staticmethod
    def _serialize_message(message, user_type, user_id):
        other_user_type = "buyer" if user_type == "seller" else "seller"
        return {
            "id": message.get("id"),
            "message": message.get("message"),
            "created_at": datetime.timestamp(message.get("created_at")) * 1000,
            "user_type": user_type
            if message.get("author_id") == user_id
            else other_user_type,
            "type": "message",
        }

    @staticmethod
    def _serialize_chat_message(chat_room_id, message, user_type, user_id):
        return {
            "chat_room_id": chat_room_id,
            "updated_at": datetime.timestamp(message.get("created_at")) * 1000,
            "new_chat": ChatService._serialize_message(
                message=message, user_type=user_type, user_id=user_id
            ),
        }

    @staticmethod
    def _get_current_message(session, message):
        session.add(message)
        session.flush()
        session.refresh(message)
        return message.asdict()

    @staticmethod
    def _update_chatroom_datetime(session, chat_room, message):
        chat_room.updated_at = message.get("created_at")
        session.commit()

    @staticmethod
    def _verify_user(chat_room, user_id, user_type):
        if (user_type == "buyer" and chat_room.buyer_id != user_id) or (
            user_type == "seller" and chat_room.seller_id != user_id
        ):
            raise ResourceNotOwnedException("Wrong user")


class ChatRoomService:
    def __init__(self, config):
        self.config = config

    def archive_room(self, user_id, chat_room_id):
        with session_scope() as session:
            archived_chat_room = ArchivedChatRoom(
                user_id=user_id, chat_room_id=chat_room_id
            )
            session.add(archived_chat_room)
        return {"chat_room_id": chat_room_id}

    def unarchive_room(self, user_id, chat_room_id):
        with session_scope() as session:
            session.query(ArchivedChatRoom).filter_by(
                user_id=user_id, chat_room_id=chat_room_id
            ).delete(synchronize_session=False)
        return {"chat_room_id": chat_room_id}

    def get_chat_rooms(self, user_id, user_type, is_archived):
        data = []
        with session_scope() as session:
            results = ChatRoomService._filter_chat_rooms_by_archive(
                user_id=user_id,
                user_type=user_type,
                session=session,
                is_archived=is_archived,
            )
            for result in results:
                data.append(
                    ChatRoomService._serialize_chat_room(
                        chat_room=result[0].asdict(),
                        buy_order=result[2].asdict(),
                        sell_order=result[3].asdict(),
                    )
                )
        return sorted(data, key=lambda item: item["updated_at"], reverse=True)

    def get_other_party_details(self, chat_room_id, user_id):
        with session_scope() as session:
            chat_room = session.query(ChatRoom).get(chat_room_id).asdict()

        if not (chat_room["is_buyer_revealed"] and chat_room["is_seller_revealed"]):
            raise ResourceNotOwnedException(
                "Both parties have not revealed their information."
            )

        if chat_room["seller_id"] == user_id:
            other_party_user_id = chat_room["buyer_id"]
        elif chat_room["buyer_id"] == user_id:
            other_party_user_id = chat_room["seller_id"]
        else:
            raise ResourceNotOwnedException("Wrong user.")

        with session_scope() as session:
            user = session.query(User).get(other_party_user_id).asdict()
            return {k: user[k] for k in ["email", "full_name"]}

    def reveal_identity(self, chat_room_id, user_id):
        with session_scope() as session:
            chat_room = session.query(ChatRoom).get(chat_room_id)

            if user_id not in (chat_room.seller_id, chat_room.buyer_id):
                raise ResourceNotOwnedException("Wrong user.")

            if not chat_room.is_deal_closed:
                raise UnauthorizedException("Need to have an accepted offer.")

            if chat_room.seller_id == user_id:
                chat_room.is_seller_revealed = True
            elif chat_room.buyer_id == user_id:
                chat_room.is_buyer_revealed = True

    @staticmethod
    def _filter_chat_rooms_by_archive(user_id, user_type, session, is_archived):
        user_type_queries = ChatRoomService._get_user_type_filter(
            user_type=user_type, user_id=user_id
        )
        archive_queries = ChatRoomService._get_archive_filter(is_archived=is_archived)
        results = (
            session.query(ChatRoom, Match, BuyOrder, SellOrder)
            .filter(user_type_queries)
            .outerjoin(
                ArchivedChatRoom,
                and_(
                    ChatRoom.id == ArchivedChatRoom.chat_room_id,
                    ArchivedChatRoom.user_id == user_id,
                ),
            )
            .filter(archive_queries)
            .outerjoin(Match, ChatRoom.match_id == Match.id)
            .outerjoin(BuyOrder, Match.buy_order_id == BuyOrder.id)
            .outerjoin(SellOrder, Match.sell_order_id == SellOrder.id)
            .all()
        )
        return results

    @staticmethod
    def _get_user_type_filter(user_type, user_id):
        if user_type == "buyer":
            return ChatRoom.buyer_id == user_id
        else:
            return ChatRoom.seller_id == user_id

    @staticmethod
    def _get_archive_filter(is_archived):
        if is_archived:
            return ArchivedChatRoom.user_id.isnot(None)
        else:
            return ArchivedChatRoom.user_id.is_(None)

    @staticmethod
    def _serialize_chat_room(chat_room, buy_order, sell_order):
        return {
            "chat_room_id": chat_room.get("id"),
            "friendly_name": chat_room.get("friendly_name"),
            "is_deal_closed": chat_room.get("is_deal_closed"),
            "seller_price": sell_order.get("price"),
            "seller_number_of_shares": sell_order.get("number_of_shares"),
            "buyer_price": buy_order.get("price"),
            "buyer_number_of_shares": buy_order.get("number_of_shares"),
            "updated_at": datetime.timestamp(chat_room.get("updated_at")) * 1000,
        }


class LinkedInLogin:
    def __init__(self, config):
        self.config = config

    @validate_input(GET_AUTH_URL_SHCMEA)
    def get_auth_url(self, redirect_uri):
        client_id = self.config.get("CLIENT_ID")
        response_type = "code"

        scope = "r_liteprofile%20r_emailaddress"
        # TODO add state
        url = f"https://www.linkedin.com/oauth/v2/authorization?response_type={response_type}&client_id={client_id}&redirect_uri={redirect_uri[0]}&scope={scope}"

        return url

    @validate_input(AUTHENTICATE_SCHEMA)
    def authenticate(self, code, redirect_uri, user_type):
        is_buy = user_type == "buyer"
        token = self._get_token(code=code, redirect_uri=redirect_uri)
        user = self.get_linkedin_user(token["access_token"])
        UserService(self.config).create_if_not_exists(
            **user, is_buy=is_buy, auth_token=token["access_token"]
        )
        return token

    def get_linkedin_user(self, token):
        with session_scope() as session:
            users = [
                u.asdict()
                for u in session.query(User).filter_by(auth_token=token).all()
            ]

            if len(users) == 1:
                return users[0]

        user_profile = self.get_user_profile(token=token)
        email = self._get_user_email(token=token)
        return {**user_profile, "email": email}

    def _get_token(self, code, redirect_uri):
        res = requests.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            headers={"Content-Type": "x-www-form-urlencoded"},
            params={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": self.config.get("CLIENT_ID"),
                "client_secret": self.config.get("CLIENT_SECRET"),
            },
        )
        json_res = res.json()
        if json_res.get("access_token") is None:
            print(res, json_res)
            raise UserProfileNotFoundException("Token retrieval failed.")
        return json_res

    @staticmethod
    def get_user_profile(token):
        user_profile_request = requests.get(
            "https://api.linkedin.com/v2/me?projection=(id,firstName,lastName,profilePicture(displayImage~:playableStreams))",
            headers={"Authorization": f"Bearer {token}"},
        )
        if user_profile_request.status_code == 401:
            raise UserProfileNotFoundException("User profile not found.")
        user_profile_data = user_profile_request.json()
        provider_user_id = user_profile_data.get("id")
        first_name = user_profile_data.get("firstName").get("localized").get("en_US")
        last_name = user_profile_data.get("lastName").get("localized").get("en_US")
        try:
            display_image_url = (
                user_profile_data.get("profilePicture")
                .get("displayImage~")
                .get("elements")[-1]
                .get("identifiers")[0]
                .get("identifier")
            )
        except AttributeError:
            display_image_url = None

        return {
            "full_name": f"{first_name} {last_name}",
            "display_image_url": display_image_url,
            "provider_user_id": provider_user_id,
        }

    @staticmethod
    def _get_user_email(token):
        email_request = requests.get(
            "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))",
            headers={"Authorization": f"Bearer {token}"},
        )
        if email_request.status_code == 401:
            raise UserProfileNotFoundException("User email not found")
        email_data = email_request.json()
        return email_data.get("elements")[0].get("handle~").get("emailAddress")


class UserRequestService:
    def __init__(self, config):
        self.config = config
        self.email_service = EmailService(config)

    @validate_input({"subject_id": UUID_RULE})
    def get_requests(self, subject_id):
        with session_scope() as session:
            if not session.query(User).get(subject_id).is_committee:
                raise InvisibleUnauthorizedException("Not committee")

            buy_requests = (
                session.query(UserRequest, User)
                .join(User, User.id == UserRequest.user_id)
                .filter(
                    UserRequest.is_buy == True, UserRequest.closed_by_user_id == None
                )
                .all()
            )
            sell_requests = (
                session.query(UserRequest, User)
                .join(User, User.id == UserRequest.user_id)
                .filter(
                    UserRequest.is_buy == False, UserRequest.closed_by_user_id == None
                )
                .all()
            )
            return {
                "buyers": [
                    {
                        **r[0].asdict(),
                        **{
                            k: v
                            for k, v in r[1].asdict().items()
                            if k not in ["id", "created_at", "updated_at"]
                        },
                    }
                    for r in buy_requests
                ],
                "sellers": [
                    {
                        **r[0].asdict(),
                        **{
                            k: v
                            for k, v in r[1].asdict().items()
                            if k not in ["id", "created_at", "updated_at"]
                        },
                    }
                    for r in sell_requests
                ],
            }

    @validate_input({"request_id": UUID_RULE, "subject_id": UUID_RULE})
    def approve_request(self, request_id, subject_id):
        with session_scope() as session:
            if not session.query(User).get(subject_id).is_committee:
                raise InvisibleUnauthorizedException("Not committee")

            request = session.query(UserRequest).get(request_id)
            request.closed_by_user_id = subject_id

            user = session.query(User).get(request.user_id)
            if request.is_buy:
                user.can_buy = True
                self.email_service.send_email(
                    emails=[user.email], template="approved_buyer"
                )
            else:
                user.can_sell = True
                self.email_service.send_email(
                    emails=[user.email], template="approved_seller"
                )

    @validate_input({"request_id": UUID_RULE, "subject_id": UUID_RULE})
    def reject_request(self, request_id, subject_id):
        with session_scope() as session:
            if not session.query(User).get(subject_id).is_committee:
                raise InvisibleUnauthorizedException("Not committee")

            request = session.query(UserRequest).get(request_id)
            request.closed_by_user_id = subject_id

            user = session.query(User).get(request.user_id)
            email_template = "rejected_buyer" if request.is_buy else "rejected_seller"
            self.email_service.send_email(emails=[user.email], template=email_template)
