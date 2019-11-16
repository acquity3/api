from src.config import APP_CONFIG
from src.database import BannedPair, session_scope
from src.services import BannedPairService
from tests.fixtures import create_user

banned_pair_service = BannedPairService(config=APP_CONFIG)


def test_ban_user():
    user_id = create_user("1")["id"]
    user2_id = create_user("2")["id"]

    banned_pair_service._ban_user(my_user_id=user_id, other_user_id=user2_id)

    with session_scope() as session:
        banned_pairs = [bp.asdict() for bp in session.query(BannedPair).all()]

    assert len(banned_pairs) == 2

    first = (
        banned_pairs[0] if banned_pairs[0]["buyer_id"] == user_id else banned_pairs[1]
    )
    second = (
        banned_pairs[1] if banned_pairs[0]["buyer_id"] == user_id else banned_pairs[0]
    )

    assert first["seller_id"] == user2_id
    assert second["seller_id"] == user_id
