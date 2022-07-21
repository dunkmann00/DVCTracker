"""Separate room and view in special

Revision ID: 5335069d04aa
Revises: 28031748b406
Create Date: 2022-06-09 23:36:56.297680

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5335069d04aa'
down_revision = '28031748b406'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('stored_specials', sa.Column('view', sa.String(length=100), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('stored_specials', 'view')
    # ### end Alembic commands ###