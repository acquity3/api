import uuid
from contextlib import contextmanager

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from src.config import APP_CONFIG
from src.utils import generate_friendly_name

_base = declarative_base()


class Base(_base):
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def additional_things_to_dict(self):
        return {}

    def asdict(self):
        d = {}
        columns = self.__table__.columns.keys()

        for col in columns:
            item = getattr(self, col)

            if isinstance(item, uuid.UUID):
                d[col] = str(item)
            else:
                d[col] = item

        for key, value in self.additional_things_to_dict.items():
            d[key] = value

        return d


class User(Base):
    __tablename__ = "users"

    email = Column(String, nullable=False, unique=True)
    provider = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    display_image_url = Column(String)
    can_buy = Column(Boolean, nullable=False, server_default="f")
    can_sell = Column(Boolean, nullable=False, server_default="f")
    is_committee = Column(Boolean, nullable=False, server_default="f")
    provider_user_id = Column(String, nullable=False, unique=True)
    auth_token = Column(String)

    sell_orders = relationship("SellOrder", back_populates="user")
    buy_orders = relationship("BuyOrder", back_populates="user")
    bans_as_buyer = relationship(
        "BannedPair", back_populates="buyer", foreign_keys="[BannedPair.buyer_id]"
    )
    bans_as_seller = relationship(
        "BannedPair", back_populates="seller", foreign_keys="[BannedPair.seller_id]"
    )

    @property
    def additional_things_to_dict(self):
        d = {"auth_token": None}

        with session_scope() as session:
            req = session.query(UserRequest).filter_by(
                user_id=str(self.id), closed_by_user_id=None
            )

            for col in ["can_buy", "can_sell"]:
                if getattr(self, col):
                    item = "YES"
                elif req.filter_by(is_buy=col == "can_buy").count() > 0:
                    item = "UNAPPROVED"
                else:
                    item = "NO"
                d[col] = item

        return d


class Security(Base):
    __tablename__ = "securities"

    name = Column(String, nullable=False, unique=True)
    market_price = Column(Float)

    sell_orders = relationship("SellOrder", back_populates="security")
    buy_orders = relationship("BuyOrder", back_populates="security")


class SellOrder(Base):
    __tablename__ = "sell_orders"

    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    security_id = Column(
        UUID, ForeignKey("securities.id", ondelete="CASCADE"), nullable=False
    )
    number_of_shares = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    round_id = Column(UUID, ForeignKey("rounds.id", ondelete="CASCADE"))

    @property
    def additional_things_to_dict(self):
        return {"security_name": self.security.name}

    user = relationship("User", back_populates="sell_orders")
    matches = relationship("Match", back_populates="sell_order")
    security = relationship("Security", back_populates="sell_orders", lazy="joined")
    round = relationship("Round", back_populates="sell_orders")


class BuyOrder(Base):
    __tablename__ = "buy_orders"

    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    security_id = Column(
        UUID, ForeignKey("securities.id", ondelete="CASCADE"), nullable=False
    )
    number_of_shares = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    round_id = Column(UUID, ForeignKey("rounds.id", ondelete="CASCADE"))

    @property
    def additional_things_to_dict(self):
        return {"security_name": self.security.name}

    user = relationship("User", back_populates="buy_orders")
    matches = relationship("Match", back_populates="buy_order")
    security = relationship("Security", back_populates="buy_orders", lazy="joined")
    round = relationship("Round", back_populates="buy_orders")


class Match(Base):
    __tablename__ = "matches"

    buy_order_id = Column(
        UUID, ForeignKey("buy_orders.id", ondelete="CASCADE"), nullable=False
    )
    sell_order_id = Column(
        UUID, ForeignKey("sell_orders.id", ondelete="CASCADE"), nullable=False
    )
    number_of_shares = Column(Float)
    price = Column(Float)

    buy_order = relationship("BuyOrder", back_populates="matches")
    sell_order = relationship("SellOrder", back_populates="matches")


class Round(Base):
    __tablename__ = "rounds"

    end_time = Column(DateTime(timezone=True), nullable=False)
    is_concluded = Column(Boolean, nullable=False)

    buy_orders = relationship("BuyOrder", back_populates="round")
    sell_orders = relationship("SellOrder", back_populates="round")


class BannedPair(Base):
    __tablename__ = "banned_pairs"

    buyer_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    seller_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    buyer = relationship(
        "User", back_populates="bans_as_buyer", foreign_keys=[buyer_id]
    )
    seller = relationship(
        "User", back_populates="bans_as_seller", foreign_keys=[seller_id]
    )

    __table_args__ = (UniqueConstraint("buyer_id", "seller_id"),)


class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    is_deal_closed = Column(Boolean, nullable=False, server_default="f")
    friendly_name = Column(String, nullable=False, default=generate_friendly_name)
    match_id = Column(
        UUID, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    disband_by_user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"))
    disband_time = Column(DateTime)


class UserChatRoomAssociation(Base):
    __tablename__ = "user_chat_room_association"
    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    chat_room_id = Column(
        UUID, ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False
    )
    role = Column(Enum("BUYER", "SELLER", name="user_type"), nullable=False)
    is_revealed = Column(Boolean, nullable=False, server_default="f")
    is_archived = Column(Boolean, nullable=False, server_default="f")
    last_read_id = Column(UUID, ForeignKey("chats.id", ondelete="CASCADE"))

    __table_args__ = (UniqueConstraint("user_id", "chat_room_id"),)


class Chat(Base):
    __tablename__ = "chats"

    chat_room_id = Column(
        UUID, ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False
    )
    message = Column(Text, nullable=False)
    author_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


class Offer(Base):
    __tablename__ = "offers"

    chat_room_id = Column(
        UUID, ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False
    )
    price = Column(Float, nullable=False)
    number_of_shares = Column(Float, nullable=False)
    author_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    offer_status = Column(
        Enum("ACCEPTED", "REJECTED", "PENDING", "CANCELED", name="offer_statuses"),
        nullable=False,
        server_default="PENDING",
    )


class OfferResponse(Base):
    __tablename__ = "offer_responses"

    offer_id = Column(UUID, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False)
    # TODO migrate Offer.offer_status to an "is_accepted" column here


class UserRequest(Base):
    __tablename__ = "user_requests"

    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_buy = Column(Boolean, nullable=False)
    closed_by_user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"))


engine = create_engine(APP_CONFIG["DATABASE_URL"])


Session = sessionmaker(bind=engine)


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
