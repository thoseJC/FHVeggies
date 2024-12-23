"""Add total_price column to order_lines

Revision ID: 3e7360e6e511
Revises: 9f500070c26d
Create Date: 2024-11-04 20:43:24.514713

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3e7360e6e511'
down_revision = 'db0bd1ca9cd3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('order_lines', schema=None) as batch_op:
        batch_op.add_column(sa.Column('total_price', sa.Float(), nullable=False))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('order_lines', schema=None) as batch_op:
        batch_op.drop_column('total_price')

    # ### end Alembic commands ###
