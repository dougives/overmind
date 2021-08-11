"""empty message

Revision ID: 39c639763aa8
Revises: 80c63f706d1b
Create Date: 2020-09-02 18:26:00.422402

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '39c639763aa8'
down_revision = '80c63f706d1b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('battle_net_info_replay_association',
    sa.Column('player_id', sa.Integer(), nullable=False),
    sa.Column('replay_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['player_id'], ['battle_net_info.id'], ),
    sa.ForeignKeyConstraint(['replay_id'], ['replays.id'], ),
    sa.PrimaryKeyConstraint('player_id', 'replay_id')
    )
    op.drop_table('player_replay_association')
    op.drop_constraint('replays_winner_id_fkey', 'replays', type_='foreignkey')
    op.create_foreign_key(None, 'replays', 'battle_net_info', ['winner_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'replays', type_='foreignkey')
    op.create_foreign_key('replays_winner_id_fkey', 'replays', 'players', ['winner_id'], ['id'])
    op.create_table('player_replay_association',
    sa.Column('player_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('replay_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['player_id'], ['players.id'], name='player_replay_association_player_id_fkey'),
    sa.ForeignKeyConstraint(['replay_id'], ['replays.id'], name='player_replay_association_replay_id_fkey'),
    sa.PrimaryKeyConstraint('player_id', 'replay_id', name='player_replay_association_pkey')
    )
    op.drop_table('battle_net_info_replay_association')
    # ### end Alembic commands ###