"""Add last_updated column to Status

Revision ID: 3a38ba5c6894
Revises: 22d42f460088
Create Date: 2022-09-14 17:00:04.971186

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3a38ba5c6894"
down_revision = "22d42f460088"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "status", sa.Column("last_updated", sa.DateTime(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("status", "last_updated")
    # ### end Alembic commands ###
