"""Make buy order round ID nullable

Revision ID: 425adc3454b5
Revises: 6fb9fbed5f20
Create Date: 2019-10-20 17:36:19.967936

"""
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "425adc3454b5"
down_revision = "6fb9fbed5f20"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "buy_orders", "round_id", existing_type=postgresql.UUID(), nullable=True
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "buy_orders", "round_id", existing_type=postgresql.UUID(), nullable=False
    )
    # ### end Alembic commands ###
