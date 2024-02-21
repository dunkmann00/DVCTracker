"""Add room_index to Room model

Revision ID: 30771795601d
Revises: 714e287b67c4
Create Date: 2022-07-21 15:32:16.291802

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '30771795601d'
down_revision = '714e287b67c4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('characteristics', sa.Column('room_index', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('characteristics', 'room_index')
    # ### end Alembic commands ###