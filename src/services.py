from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy.sql import func

from src.database import (
    BannedPair,
    BuyOrder,
    Chat,
    ChatRoom,
    Match,
    Offer,
    OfferResponse,
    Round,
    Security,
    SellOrder,
    User,
    UserChatRoomAssociation,
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
    CREATE_NEW_MESSAGE_SCHEMA,
    CREATE_NEW_OFFER_SCHEMA,
    CREATE_SELL_ORDER_SCHEMA,
    DELETE_ORDER_SCHEMA,
    EDIT_MARKET_PRICE_SCHEMA,
    EDIT_OFFER_STATUS_SCHEMA,
    EDIT_ORDER_SCHEMA,
    GET_AUTH_URL_SHCMEA,
    GET_CHATS_BY_USER_ID_SCHEMA,
    UUID_RULE,
    validate_input,
)
from src.utils import EMAIL_STRFTIME_FORMAT


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

                if is_buy is not None:
                    buy_req = UserRequest(user_id=str(user.id), is_buy=True)
                    session.add(buy_req)
                    if not is_buy:
                        sell_req = UserRequest(user_id=str(user.id), is_buy=False)
                        session.add(sell_req)

                    email_template = "register_buyer" if is_buy else "register_seller"
                    self.email_service.send_email(
                        emails=[email], template=email_template
                    )

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

    def send_email_to_approved_users(self, template, to_buyers, to_sellers, **kwargs):
        with session_scope() as session:
            if to_sellers:
                seller_emails = [
                    user.email
                    for user in session.query(User).filter_by(can_sell=True).all()
                ]
                self.email_service.send_email(
                    seller_emails, template=template, **kwargs
                )

            if to_buyers:
                buyer_emails = [
                    user.email
                    for user in session.query(User).filter_by(can_buy=True).all()
                ]
                self.email_service.send_email(buyer_emails, template=template, **kwargs)

    def get_stats(self):
        with session_scope() as session:
            return {
                'sellers': session.query(User).filter_by(can_sell=True).count(), 
                'buyers': session.query(User).filter_by(can_buy=True).count()
            }


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
            if not user.can_sell:
                raise UnauthorizedException("User cannot place sell orders.")

            sell_order_count = len(
                self.get_orders_by_user_in_current_round(user_id=user_id)
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
    def get_orders_by_user_in_current_round(self, user_id):
        current_round = RoundService(self.config).get_active()
        with session_scope() as session:
            sell_orders = (
                session.query(SellOrder)
                .filter_by(user_id=user_id)
                .filter(
                    (SellOrder.round_id == (current_round and current_round["id"]))
                    | (SellOrder.round_id == None)
                )
                .all()
            )
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

            session.query(SellOrder).filter_by(id=id).delete()
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

            buy_order_count = len(
                self.get_orders_by_user_in_current_round(user_id=user_id)
            )
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
    def get_orders_by_user_in_current_round(self, user_id):
        current_round = RoundService(self.config).get_active()
        with session_scope() as session:
            buy_orders = (
                session.query(BuyOrder)
                .filter_by(user_id=user_id)
                .filter(
                    (BuyOrder.round_id == (current_round and current_round["id"]))
                    | (BuyOrder.round_id == None)
                )
                .all()
            )
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

            session.query(BuyOrder).filter_by(id=id).delete()
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

    def get_stats(self):
        with session_scope() as session:
            sell_orders = session.query(SellOrder.number_of_shares, SellOrder.price).join(Round).filter(Round.end_time >= datetime.now(), Round.is_concluded == False).all()
            total_sell_shares, min_sell_price, max_sell_price = 0, -1, 0 
            for o in sell_orders:
                total_sell_shares += o.number_of_shares
                if o.price < min_sell_price or min_sell_price < 0:
                    min_sell_price = o.price
                if o.price > max_sell_price:
                    max_sell_price = o.price

            buy_orders = session.query(BuyOrder.number_of_shares, BuyOrder.price).join(Round).filter(Round.end_time >= datetime.now(), Round.is_concluded == False).all()

            total_buy_shares, min_buy_price, max_buy_price = 0, -1, 0
            for o in buy_orders:
                total_buy_shares += o.number_of_shares
                if o.price < min_buy_price or min_buy_price < 0:
                    min_buy_price = o.price
                if o.price > max_buy_price:
                    max_buy_price = o.price


            return (total_sell_shares > 0 or total_buy_shares > 0) and {
                'sell': {
                    'total_shares': total_sell_shares,
                    'min_price': min_sell_price,
                    'max_price': max_sell_price

                } ,
                'buy': {
                    'total_shares': total_buy_shares,
                    'min_price': min_buy_price,
                    'max_price': max_buy_price
                } 
            }


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

            singapore_timezone = timezone(timedelta(hours=8))
            user_service = UserService(self.config)
            user_service.send_email_to_approved_users(
                template="round_opened_seller",
                to_buyers=False,
                to_sellers=True,
                start_date=datetime.now(singapore_timezone).strftime(
                    EMAIL_STRFTIME_FORMAT
                ),
                end_date=new_round.end_time.astimezone(tz=singapore_timezone).strftime(
                    EMAIL_STRFTIME_FORMAT
                ),
            )
            user_service.send_email_to_approved_users(
                template="round_opened_buyer",
                to_buyers=True,
                to_sellers=False,
                start_date=datetime.now(singapore_timezone).strftime(
                    EMAIL_STRFTIME_FORMAT
                ),
                end_date=new_round.end_time.astimezone(tz=singapore_timezone).strftime(
                    EMAIL_STRFTIME_FORMAT
                ),
            )

        if scheduler is not None:
            scheduler.add_job(
                self.send_round_closing_soon_emails,
                "date",
                run_date=end_time
                - self.config["ACQUITY_ROUND_CLOSING_REMINDER_BEFORE_END_TIME"],
            )
            scheduler.add_job(
                MatchService(self.config).run_matches, "date", run_date=end_time
            )

    def send_round_closing_soon_emails(self):
        singapore_timezone = timezone(timedelta(hours=8))
        round_end_time = (
            self.get_active()["end_time"]
            .astimezone(tz=singapore_timezone)
            .strftime(EMAIL_STRFTIME_FORMAT)
        )

        user_service = UserService(self.config)
        user_service.send_email_to_approved_users(
            template="round_closing_soon_buyer",
            to_buyers=True,
            to_sellers=False,
            end_date=round_end_time,
        )
        user_service.send_email_to_approved_users(
            template="round_closing_soon_seller",
            to_buyers=False,
            to_sellers=True,
            end_date=round_end_time,
        )

    @validate_input({"security_id": UUID_RULE})
    def get_previous_round_statistics(self, security_id):
        return None


class MatchService:
    def __init__(self, config):
        self.config = config
        self.email_service = EmailService(config)

    def run_matches(self):
        with session_scope() as session:
            round_id = str(
                session.query(Round).order_by(Round.created_at.desc()).first().id
            )
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

                chat_room = ChatRoom(match_id=str(match.id))
                session.add(chat_room)
                session.flush()

                buyer_assoc = UserChatRoomAssociation(
                    user_id=buy_order_to_buyer_dict[buy_order_id],
                    chat_room_id=str(chat_room.id),
                    role="BUYER",
                )
                seller_assoc = UserChatRoomAssociation(
                    user_id=sell_order_to_seller_dict[sell_order_id],
                    chat_room_id=str(chat_room.id),
                    role="SELLER",
                )
                session.add_all([buyer_assoc, seller_assoc])

            session.query(Round).get(round_id).is_concluded = True

    def _send_emails(self, buy_orders, sell_orders, match_results):
        matched_uuids = set()
        for buy_order_uuid, sell_order_uuid in match_results:
            matched_uuids.add(buy_order_uuid)
            matched_uuids.add(sell_order_uuid)

        all_user_ids = set()
        matched_buyer_user_ids = set()
        matched_seller_user_ids = set()
        for buy_order in buy_orders:
            all_user_ids.add(buy_order["user_id"])
            if buy_order["id"] in matched_uuids:
                matched_buyer_user_ids.add(buy_order["user_id"])
        for sell_order in sell_orders:
            all_user_ids.add(sell_order["user_id"])
            if sell_order["id"] in matched_uuids:
                matched_seller_user_ids.add(sell_order["user_id"])

        with session_scope() as session:
            matched_buyer_emails = [
                user.email
                for user in session.query(User)
                .filter(User.id.in_(matched_buyer_user_ids))
                .all()
            ]
            self.email_service.send_email(
                matched_buyer_emails, template="match_done_has_match_buyer"
            )
            matched_seller_emails = [
                user.email
                for user in session.query(User)
                .filter(User.id.in_(matched_seller_user_ids))
                .all()
            ]
            self.email_service.send_email(
                matched_seller_emails, template="match_done_has_match_seller"
            )
            unmatched_emails = [
                user.email
                for user in session.query(User)
                .filter(
                    User.id.in_(
                        all_user_ids - matched_buyer_user_ids - matched_seller_user_ids
                    )
                )
                .all()
            ]
            self.email_service.send_email(
                unmatched_emails, template="match_done_no_match"
            )


class BannedPairService:
    def __init__(self, config):
        self.config = config

    @validate_input({"my_user_id": UUID_RULE, "other_user_id": UUID_RULE})
    def _ban_user(self, my_user_id, other_user_id):
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

    @validate_input(CREATE_NEW_OFFER_SCHEMA)
    def create_new_offer(self, chat_room_id, author_id, price, number_of_shares):
        with session_scope() as session:
            OfferService._check_deal_status(
                session=session, chat_room_id=chat_room_id, user_id=author_id
            )

            offers = session.query(Offer).filter_by(
                chat_room_id=chat_room_id, offer_status="PENDING"
            )
            if offers.count() > 0:
                raise InvalidRequestException("There are still pending offers")

            chat_room = session.query(ChatRoom).get(chat_room_id)
            if ChatRoomService.is_disbanded(chat_room):
                raise ResourceNotFoundException("Chat room is disbanded")

            offer = Offer(
                chat_room_id=str(chat_room_id),
                price=price,
                number_of_shares=number_of_shares,
                author_id=str(author_id),
            )
            session.add(offer)
            session.flush()
            chat_room.updated_at = offer.created_at

            offer_dict = offer.asdict()
            return OfferService._serialize_chat_offer(
                offer=offer_dict, is_deal_closed=chat_room.is_deal_closed
            )

    @validate_input(EDIT_OFFER_STATUS_SCHEMA)
    def edit_offer_status(self, chat_room_id, offer_id, user_id, offer_status):
        with session_scope() as session:
            OfferService._check_deal_status(
                session=session, chat_room_id=chat_room_id, user_id=user_id
            )

            offer = session.query(Offer).get(offer_id)

            if offer.offer_status != "PENDING":
                raise InvalidRequestException("Offer is closed")
            if offer_status == "CANCELED" and offer.author_id != user_id:
                raise InvalidRequestException("You can only cancel your offer")
            if offer_status in ["ACCEPTED", "REJECTED"] and offer.author_id == user_id:
                raise InvalidRequestException(
                    "You can not accept/reject your own offer"
                )

            chat_room = session.query(ChatRoom).get(chat_room_id)
            chat_room.updated_at = offer.created_at
            chat_room.is_deal_closed = offer_status == "ACCEPTED"
            offer.offer_status = offer_status
            session.add(offer)
            session.flush()

            offer_response = OfferResponse(offer_id=str(offer.id))
            session.add(offer_response)
            session.flush()

            return OfferService._serialize_chat_offer(
                offer=offer.asdict(),
                is_deal_closed=chat_room.is_deal_closed,
                offer_response=offer_response.asdict(),
                author_id=user_id,
            )

    @staticmethod
    def _check_deal_status(session, chat_room_id, user_id):
        chat_room = session.query(ChatRoom).get(chat_room_id)
        if chat_room is None:
            raise ResourceNotFoundException("Chat room not found")
        if chat_room.is_deal_closed:
            raise InvalidRequestException("Deal is closed")

        if (
            session.query(UserChatRoomAssociation)
            .filter_by(user_id=user_id, chat_room_id=chat_room_id)
            .count()
            == 0
        ):
            raise ResourceNotOwnedException("User is not in this chat room")

    @staticmethod
    def _serialize_chat_offer(
        offer, is_deal_closed, offer_response=None, author_id=None
    ):
        if offer_response is None:
            return {"type": "offer", **offer}
        else:
            return {
                "type": "offer_response",
                "is_deal_closed": is_deal_closed,
                **offer,
                **offer_response,
                "author_id": author_id,
            }


class ChatService:
    def __init__(self, config):
        self.config = config
        self.email_service = EmailService(config=config)

    @validate_input(GET_CHATS_BY_USER_ID_SCHEMA)
    def get_chats_by_user_id(self, user_id, as_buyer, as_seller):
        roles = []
        if as_buyer:
            roles.append("BUYER")
        if as_seller:
            roles.append("SELLER")

        with session_scope() as session:
            user = session.query(User).get(user_id)
            if (as_buyer and (not user.can_buy)) or (as_seller and (not user.can_sell)):
                raise UnauthorizedException("Too much permissions requested.")

            chat_room_queries = (
                session.query(
                    ChatRoom, UserChatRoomAssociation, Match, BuyOrder, SellOrder
                )
                .join(Match, ChatRoom.match_id == Match.id)
                .join(
                    UserChatRoomAssociation,
                    UserChatRoomAssociation.chat_room_id == ChatRoom.id,
                )
                .join(BuyOrder, Match.buy_order_id == BuyOrder.id)
                .join(SellOrder, Match.sell_order_id == SellOrder.id)
                .filter(UserChatRoomAssociation.user_id == user_id)
                .filter(UserChatRoomAssociation.role.in_(roles))
                .all()
            )
            chats = session.query(Chat).all()
            offers = session.query(Offer).all()
            offer_responses = session.query(OfferResponse).all()

            whitelist_chat_rooms = None
            if not as_seller:
                whitelist_chat_rooms = set(
                    str(r[0].id)
                    for r in session.query(ChatRoom, Chat)
                    .join(Chat, ChatRoom.id == Chat.chat_room_id)
                    .all()
                ) | set(
                    str(r[0].id)
                    for r in session.query(ChatRoom, Offer)
                    .join(Offer, ChatRoom.id == Offer.chat_room_id)
                    .all()
                )

            res = {}

            for chat_room, assoc, match, buy_order, sell_order in chat_room_queries:
                chat_room_id = str(chat_room.id)
                if (chat_room_id in res) or (
                    (whitelist_chat_rooms is not None)
                    and (chat_room_id not in whitelist_chat_rooms)
                ):
                    continue

                chat_room_repr = ChatRoomService(self.config)._serialize_chat_room(
                    chat_room, user_id
                )
                res[chat_room_id] = chat_room_repr
                res[chat_room_id]["buy_order"] = buy_order.asdict()
                res[chat_room_id]["sell_order"] = (
                    sell_order.asdict() if as_seller else None
                )

                res[chat_room_id]["chats"] = []
                res[chat_room_id]["latest_offer"] = None

            for chat in chats:
                if chat.chat_room_id in res:
                    res[chat.chat_room_id]["chats"].append(
                        {"type": "chat", **chat.asdict()}
                    )

            offer_d = {}
            for offer in offers:
                if offer.chat_room_id in res:
                    offer_d[str(offer.id)] = offer

                    res[offer.chat_room_id]["chats"].append(
                        {"type": "offer", **offer.asdict()}
                    )

                    if offer.offer_status != "REJECTED":
                        res[offer.chat_room_id]["latest_offer"] = offer.asdict()

            for offer_resp in offer_responses:
                offer = offer_d.get(offer_resp.offer_id)
                if offer is None:
                    continue

                if offer.offer_status == "CANCELED":
                    author_id = offer.author_id
                else:
                    author_id = ChatRoomService._get_other_party_id(
                        chat_room_id=offer.chat_room_id, user_id=offer.author_id
                    )
                res[offer.chat_room_id]["chats"].append(
                    OfferService._serialize_chat_offer(
                        offer=offer.asdict(),
                        is_deal_closed=chat_room.is_deal_closed,
                        offer_response=offer_resp.asdict(),
                        author_id=author_id,
                    )
                )

            for v in res.values():
                v["chats"].sort(key=lambda x: x["created_at"])

            archived_room_ids = set(
                q[1].chat_room_id for q in chat_room_queries if q[1].is_archived
            )

        unarchived_res = {}
        archived_res = {}
        for chat_room_id, room in res.items():
            if chat_room_id in archived_room_ids:
                archived_res[chat_room_id] = room
            else:
                unarchived_res[chat_room_id] = room

        return {"archived": archived_res, "unarchived": unarchived_res}

    @validate_input(CREATE_NEW_MESSAGE_SCHEMA)
    def create_new_message(self, chat_room_id, message, author_id):
        with session_scope() as session:
            chat_room = session.query(ChatRoom).get(chat_room_id)
            if chat_room is None:
                raise ResourceNotFoundException("Chat room not found")
            if ChatRoomService.is_disbanded(chat_room):
                raise ResourceNotFoundException("Chat room is disbanded")

            if (
                session.query(UserChatRoomAssociation)
                .filter_by(user_id=author_id, chat_room_id=chat_room_id)
                .count()
                == 0
            ):
                raise ResourceNotOwnedException("User is not in this chat room")

            first_chat = (
                session.query(Chat).filter_by(chat_room_id=chat_room_id).count() == 0
            )

            message = Chat(
                chat_room_id=str(chat_room_id),
                message=message,
                author_id=str(author_id),
            )
            session.add(message)
            session.flush()
            chat_room.updated_at = message.created_at

            if first_chat:
                other_party_id = ChatRoomService._get_other_party_id(
                    chat_room_id=str(chat_room.id), user_id=author_id
                )
                other_party_email = session.query(User).get(other_party_id).email
                self.email_service.send_email(
                    emails=[other_party_email], template="new_chat_message"
                )

            return {"type": "chat", **message.asdict()}


class ChatRoomService:
    def __init__(self, config):
        self.config = config

    @validate_input({"user_id": UUID_RULE, "chat_room_id": UUID_RULE})
    def disband_chatroom(self, user_id, chat_room_id):
        with session_scope() as session:
            chat_room = session.query(ChatRoom).get(chat_room_id)
            assoc = [
                a.asdict()
                for a in session.query(UserChatRoomAssociation)
                .filter_by(chat_room_id=chat_room_id)
                .all()
            ]
            if user_id not in [a["user_id"] for a in assoc]:
                raise InvalidRequestException("Not in chat room")
            chat_room.disband_by_user_id = user_id
            chat_room.disband_time = datetime.now(timezone.utc)

        BannedPairService(self.config)._ban_user(
            my_user_id=assoc[0]["user_id"], other_user_id=assoc[1]["user_id"]
        )

        with session_scope() as session:
            chat_room = session.query(ChatRoom).get(chat_room_id)
            return ChatRoomService._chat_room_dict_with_disband_info(chat_room)

    @validate_input({"user_id": UUID_RULE, "chat_room_id": UUID_RULE})
    def archive_room(self, user_id, chat_room_id):
        with session_scope() as session:
            session.query(UserChatRoomAssociation).filter_by(
                user_id=user_id, chat_room_id=chat_room_id
            ).one().is_archived = True

        return {"chat_room_id": chat_room_id}

    @validate_input({"user_id": UUID_RULE})
    def get_chat_rooms_by_user_id(self, user_id):
        with session_scope() as session:
            chat_rooms = (
                session.query(UserChatRoomAssociation, ChatRoom)
                .join(ChatRoom, UserChatRoomAssociation.chat_room_id == ChatRoom.id)
                .filter(UserChatRoomAssociation.user_id == user_id)
                .all()
            )
            return [chat_room[1].asdict() for chat_room in chat_rooms]

    @validate_input({"user_id": UUID_RULE, "chat_room_id": UUID_RULE})
    def reveal_identity(self, chat_room_id, user_id):
        with session_scope() as session:
            assoc = (
                session.query(UserChatRoomAssociation)
                .filter_by(chat_room_id=chat_room_id, user_id=user_id)
                .one()
            )
            assoc.is_revealed = True

            everyone = (
                session.query(UserChatRoomAssociation, User)
                .join(User, UserChatRoomAssociation.user_id == User.id)
                .filter(UserChatRoomAssociation.chat_room_id == chat_room_id)
                .all()
            )
            is_all_revealed = all(a[0].is_revealed for a in everyone)
            if is_all_revealed:
                return {
                    **ChatRoomService(self.config)._serialize_chat_room(
                        session.query(ChatRoom).get(chat_room_id), user_id
                    ),
                    **{
                        str(a[1].id): {"email": a[1].email, "full_name": a[1].full_name}
                        for a in everyone
                    },
                }

    @validate_input(
        {"user_id": UUID_RULE, "chat_room_id": UUID_RULE, "last_read_id": UUID_RULE}
    )
    def update_last_read_id(self, user_id, chat_room_id, last_read_id):
        with session_scope() as session:
            session.query(UserChatRoomAssociation).filter_by(
                user_id=user_id, chat_room_id=chat_room_id
            ).one().last_read_id = last_read_id

    @staticmethod
    def is_disbanded(chat_room):
        return (chat_room.disband_by_user_id is not None) and (
            chat_room.disband_time is not None
        )

    @staticmethod
    def _chat_room_dict_with_disband_info(chat_room):
        res = chat_room.asdict()
        if ChatRoomService.is_disbanded(chat_room):
            res["disband_info"] = {
                "disband_by_user_id": res["disband_by_user_id"],
                "disband_time": res["disband_time"],
            }
        res.pop("disband_by_user_id")
        res.pop("disband_time")
        return res

    @staticmethod
    def _serialize_chat_room(chat_room, user_id):
        res = ChatRoomService._chat_room_dict_with_disband_info(chat_room)

        res["other_party_id"] = ChatRoomService._get_other_party_id(
            str(chat_room.id), user_id
        )
        with session_scope() as session:
            assoc = (
                session.query(UserChatRoomAssociation)
                .filter_by(chat_room_id=str(chat_room.id), user_id=user_id)
                .one()
            )

            res["is_revealed"] = assoc.is_revealed

            res["identities"] = None
            everyone = (
                session.query(UserChatRoomAssociation, User)
                .join(User, UserChatRoomAssociation.user_id == User.id)
                .filter(UserChatRoomAssociation.chat_room_id == str(chat_room.id))
                .all()
            )
            is_all_revealed = all(a[0].is_revealed for a in everyone)
            if is_all_revealed:
                res["identities"] = {
                    str(a[1].id): {"email": a[1].email, "full_name": a[1].full_name}
                    for a in everyone
                }

            last_read_id = assoc.last_read_id
            res["last_read_id"] = last_read_id

            unread_count_query = (
                session.query(Chat)
                .filter_by(chat_room_id=str(chat_room.id))
                .filter(Chat.author_id != user_id)
            )
            if last_read_id is not None:
                unread_count_query = unread_count_query.filter(
                    Chat.created_at > session.query(Chat).get(last_read_id).created_at
                )
            res["unread_count"] = unread_count_query.count()

        return res

    @staticmethod
    def _get_other_party_id(chat_room_id, user_id):
        with session_scope() as session:
            return (
                session.query(UserChatRoomAssociation)
                .filter_by(chat_room_id=chat_room_id)
                .filter(UserChatRoomAssociation.user_id != user_id)
                .one()
                .user_id
            )


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
        self.get_linkedin_user(token["access_token"], is_buy=is_buy)
        return token

    def get_linkedin_user(self, token, is_buy=None):
        with session_scope() as session:
            users = [
                u.asdict()
                for u in session.query(User).filter_by(auth_token=token).all()
            ]

            if len(users) == 1:
                return users[0]

        return self.get_user_profile(token=token, is_buy=is_buy)

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

    def get_user_profile(self, token, is_buy=None):
        email_request = requests.get(
            "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))",
            headers={"Authorization": f"Bearer {token}"},
        )
        if email_request.status_code == 401:
            raise UserProfileNotFoundException("User email not found.")
        email_data = email_request.json()
        email = email_data.get("elements")[0].get("handle~").get("emailAddress")

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

        return UserService(self.config).create_if_not_exists(
            email=email,
            full_name=f"{first_name} {last_name}",
            display_image_url=display_image_url,
            provider_user_id=provider_user_id,
            is_buy=is_buy,
            auth_token=token,
        )


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
