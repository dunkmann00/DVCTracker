"""Add relationships from Contacts to User

This also adds back User, changes Email, PhoneNumber, and PushToken from being
tables to being inherited models of the Contact model.

Revision ID: 22d42f460088
Revises: 2c63a547a651
Create Date: 2022-08-24 00:00:50.075013

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '22d42f460088'
down_revision = '2c63a547a651'
branch_labels = None
depends_on = None

contacttypes = sa.Enum('BASE', 'EMAIL', 'PHONE', 'APN', name='contacttypes')

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('users',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(), nullable=True),
    sa.Column('password_hash', sa.String(), nullable=True),
    sa.Column('important_criteria', sa.JSON(), nullable=True),
    sa.Column('last_accessed', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_users')),
    sa.UniqueConstraint('username', name=op.f('uq_users_username'))
    )
    op.create_table('contacts',
    sa.Column('contact_id', sa.Integer(), nullable=False),
    sa.Column('contact', sa.String(), nullable=True),
    sa.Column('get_errors', sa.Boolean(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('last_updated', sa.DateTime(), nullable=True),
    sa.Column('contact_type', contacttypes, nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], name=op.f('fk_contacts_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('contact_id', name=op.f('pk_contacts'))
    )
    op.drop_table('emails')
    op.drop_table('phone_numbers')
    op.drop_table('push_tokens')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('push_tokens',
    sa.Column('push_token', sa.String(), nullable=False),
    sa.Column('get_errors', sa.Boolean(), nullable=True),
    sa.Column('last_updated', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('push_token', name='push_tokens_pkey')
    )
    op.create_table('phone_numbers',
    sa.Column('phone_number', sa.String(length=11), nullable=False),
    sa.Column('get_errors', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('phone_number', name='phone_numbers_pkey')
    )
    op.create_table('emails',
    sa.Column('email', sa.String(length=80), nullable=False),
    sa.Column('get_errors', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('email', name='emails_pkey')
    )
    op.drop_table('contacts')
    op.drop_table('users')

    contacttypes.drop(op.get_bind())
    # ### end Alembic commands ###
