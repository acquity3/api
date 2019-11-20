"""Add CANCELED to offer statuses

Revision ID: 3c017b2a1c6e
Revises: 9f8070535dd6
Create Date: 2019-11-20 13:46:43.733269

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "3c017b2a1c6e"
down_revision = "9f8070535dd6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE offers ALTER COLUMN offer_status TYPE VARCHAR")
    op.execute("ALTER TABLE offers ALTER COLUMN offer_status DROP DEFAULT")
    op.execute("DROP TYPE IF EXISTS offer_statuses")
    op.execute(
        "CREATE TYPE offer_statuses AS ENUM ('ACCEPTED', 'REJECTED', 'PENDING', 'CANCELED')"
    )
    op.execute(
        "ALTER TABLE offers ALTER COLUMN offer_status TYPE offer_statuses USING (offer_status::offer_statuses)"
    )
    op.execute("ALTER TABLE offers ALTER COLUMN offer_status SET DEFAULT 'PENDING'")


def downgrade():
    op.execute("ALTER TABLE offers ALTER COLUMN offer_status TYPE VARCHAR")
    op.execute("ALTER TABLE offers ALTER COLUMN offer_status DROP DEFAULT")
    op.execute("DROP TYPE IF EXISTS offer_statuses")
    op.execute("CREATE TYPE offer_statuses AS ENUM ('ACCEPTED', 'REJECTED', 'PENDING')")
    op.execute(
        "ALTER TABLE offers ALTER COLUMN offer_status TYPE offer_statuses USING (offer_status::offer_statuses)"
    )
    op.execute("ALTER TABLE offers ALTER COLUMN offer_status SET DEFAULT 'PENDING'")
