"""Ondelete cascade

Revision ID: 8e09e604c7a0
Revises: cf47d58bb9a4
Create Date: 2019-11-16 16:16:58.120414

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "8e09e604c7a0"
down_revision = "cf47d58bb9a4"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(
        "archived_chat_rooms_chat_room_id_fkey",
        "archived_chat_rooms",
        type_="foreignkey",
    )
    op.drop_constraint(
        "archived_chat_rooms_user_id_fkey", "archived_chat_rooms", type_="foreignkey"
    )
    op.create_foreign_key(
        None, "archived_chat_rooms", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None,
        "archived_chat_rooms",
        "chat_rooms",
        ["chat_room_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "banned_pairs_seller_id_fkey", "banned_pairs", type_="foreignkey"
    )
    op.drop_constraint("banned_pairs_buyer_id_fkey", "banned_pairs", type_="foreignkey")
    op.create_foreign_key(
        None, "banned_pairs", "users", ["buyer_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None, "banned_pairs", "users", ["seller_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_constraint("buy_orders_security_id_fkey", "buy_orders", type_="foreignkey")
    op.drop_constraint("buy_orders_user_id_fkey", "buy_orders", type_="foreignkey")
    op.drop_constraint("buy_orders_round_id_fkey", "buy_orders", type_="foreignkey")
    op.create_foreign_key(
        None, "buy_orders", "rounds", ["round_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None, "buy_orders", "securities", ["security_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None, "buy_orders", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_constraint("chat_rooms_buyer_id_fkey", "chat_rooms", type_="foreignkey")

    op.execute(
        'ALTER TABLE chat_rooms DROP CONSTRAINT IF EXISTS "chat_room_match_id-match_id"'
    )
    op.execute(
        'ALTER TABLE chat_rooms DROP CONSTRAINT IF EXISTS "chat_rooms_match_id_fkey"'
    )

    op.drop_constraint("chat_rooms_seller_id_fkey", "chat_rooms", type_="foreignkey")
    op.create_foreign_key(
        None, "chat_rooms", "users", ["seller_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None, "chat_rooms", "matches", ["match_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None, "chat_rooms", "users", ["buyer_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_constraint("chats_author_id_fkey", "chats", type_="foreignkey")
    op.drop_constraint("chats_chat_room_id_fkey", "chats", type_="foreignkey")
    op.create_foreign_key(
        None, "chats", "chat_rooms", ["chat_room_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None, "chats", "users", ["author_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_constraint("matches_buy_order_id_fkey", "matches", type_="foreignkey")
    op.drop_constraint("matches_sell_order_id_fkey", "matches", type_="foreignkey")
    op.create_foreign_key(
        None, "matches", "sell_orders", ["sell_order_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None, "matches", "buy_orders", ["buy_order_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_constraint("offers_chat_room_id_fkey", "offers", type_="foreignkey")
    op.drop_constraint("offers_author_id_fkey", "offers", type_="foreignkey")
    op.create_foreign_key(
        None, "offers", "users", ["author_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None, "offers", "chat_rooms", ["chat_room_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_constraint("sell_orders_round_id_fkey", "sell_orders", type_="foreignkey")
    op.drop_constraint("sell_orders_user_id_fkey", "sell_orders", type_="foreignkey")
    op.drop_constraint(
        "sell_orders_security_id_fkey", "sell_orders", type_="foreignkey"
    )
    op.create_foreign_key(
        None, "sell_orders", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None, "sell_orders", "securities", ["security_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None, "sell_orders", "rounds", ["round_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_constraint(
        "user_requests_user_id_fkey", "user_requests", type_="foreignkey"
    )
    op.drop_constraint(
        "user_requests_closed_by_user_id_fkey", "user_requests", type_="foreignkey"
    )
    op.create_foreign_key(
        None,
        "user_requests",
        "users",
        ["closed_by_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        None, "user_requests", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "user_requests", type_="foreignkey")
    op.drop_constraint(None, "user_requests", type_="foreignkey")
    op.create_foreign_key(
        "user_requests_closed_by_user_id_fkey",
        "user_requests",
        "users",
        ["closed_by_user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "user_requests_user_id_fkey", "user_requests", "users", ["user_id"], ["id"]
    )
    op.drop_constraint(None, "sell_orders", type_="foreignkey")
    op.drop_constraint(None, "sell_orders", type_="foreignkey")
    op.drop_constraint(None, "sell_orders", type_="foreignkey")
    op.create_foreign_key(
        "sell_orders_security_id_fkey",
        "sell_orders",
        "securities",
        ["security_id"],
        ["id"],
    )
    op.create_foreign_key(
        "sell_orders_user_id_fkey", "sell_orders", "users", ["user_id"], ["id"]
    )
    op.create_foreign_key(
        "sell_orders_round_id_fkey", "sell_orders", "rounds", ["round_id"], ["id"]
    )
    op.drop_constraint(None, "offers", type_="foreignkey")
    op.drop_constraint(None, "offers", type_="foreignkey")
    op.create_foreign_key(
        "offers_author_id_fkey", "offers", "users", ["author_id"], ["id"]
    )
    op.create_foreign_key(
        "offers_chat_room_id_fkey", "offers", "chat_rooms", ["chat_room_id"], ["id"]
    )
    op.drop_constraint(None, "matches", type_="foreignkey")
    op.drop_constraint(None, "matches", type_="foreignkey")
    op.create_foreign_key(
        "matches_sell_order_id_fkey",
        "matches",
        "sell_orders",
        ["sell_order_id"],
        ["id"],
    )
    op.create_foreign_key(
        "matches_buy_order_id_fkey", "matches", "buy_orders", ["buy_order_id"], ["id"]
    )
    op.drop_constraint(None, "chats", type_="foreignkey")
    op.drop_constraint(None, "chats", type_="foreignkey")
    op.create_foreign_key(
        "chats_chat_room_id_fkey", "chats", "chat_rooms", ["chat_room_id"], ["id"]
    )
    op.create_foreign_key(
        "chats_author_id_fkey", "chats", "users", ["author_id"], ["id"]
    )
    op.drop_constraint(None, "chat_rooms", type_="foreignkey")
    op.drop_constraint(None, "chat_rooms", type_="foreignkey")
    op.drop_constraint(None, "chat_rooms", type_="foreignkey")
    op.create_foreign_key(
        "chat_rooms_seller_id_fkey", "chat_rooms", "users", ["seller_id"], ["id"]
    )
    op.create_foreign_key(
        "chat_room_match_id-match_id", "chat_rooms", "matches", ["match_id"], ["id"]
    )
    op.create_foreign_key(
        "chat_rooms_buyer_id_fkey", "chat_rooms", "users", ["buyer_id"], ["id"]
    )
    op.drop_constraint(None, "buy_orders", type_="foreignkey")
    op.drop_constraint(None, "buy_orders", type_="foreignkey")
    op.drop_constraint(None, "buy_orders", type_="foreignkey")
    op.create_foreign_key(
        "buy_orders_round_id_fkey", "buy_orders", "rounds", ["round_id"], ["id"]
    )
    op.create_foreign_key(
        "buy_orders_user_id_fkey", "buy_orders", "users", ["user_id"], ["id"]
    )
    op.create_foreign_key(
        "buy_orders_security_id_fkey",
        "buy_orders",
        "securities",
        ["security_id"],
        ["id"],
    )
    op.drop_constraint(None, "banned_pairs", type_="foreignkey")
    op.drop_constraint(None, "banned_pairs", type_="foreignkey")
    op.create_foreign_key(
        "banned_pairs_buyer_id_fkey", "banned_pairs", "users", ["buyer_id"], ["id"]
    )
    op.create_foreign_key(
        "banned_pairs_seller_id_fkey", "banned_pairs", "users", ["seller_id"], ["id"]
    )
    op.drop_constraint(None, "archived_chat_rooms", type_="foreignkey")
    op.drop_constraint(None, "archived_chat_rooms", type_="foreignkey")
    op.create_foreign_key(
        "archived_chat_rooms_user_id_fkey",
        "archived_chat_rooms",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "archived_chat_rooms_chat_room_id_fkey",
        "archived_chat_rooms",
        "chat_rooms",
        ["chat_room_id"],
        ["id"],
    )
    # ### end Alembic commands ###
