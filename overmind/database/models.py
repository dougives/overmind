from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (
    Column, Enum, String, Integer,
    ForeignKey, Index, MetaData, DateTime,
    Interval, Float, Boolean)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import (
    BYTEA, ARRAY)
import inspect

class Base():
    def to_dict(self):
        return { k: v
            for k, v in inspect.getmembers(self)
            if not k.startswith('_')
            if not isinstance(v, MetaData)
            if not callable(v) }
    
    def __repr__(self, value=None):
        return f'<{type(self).__name__} {self.id if value is None else value}>'

Base = declarative_base(cls=Base)

@enum.unique
class Race(enum.Enum):
    PROTOSS = 'protoss'
    TERRAN = 'terran'
    ZERG = 'zerg'

class ReplayDataPath(Base):
    __tablename__ = 'replay_data_path'
    replay_data_path = Column(String)

class Map(Base):
    __tablename__ = 'maps'
    __table_args__ = {
        Index('idx_file_hash', 
            'file_hash', 
            unique=True, postgresql_using='hash')
    }
    id = Column(Integer, primary_key=True)
    file_hash = Column(BYTEA(32), nullable=False, unique=True)
    map_name = Column(String, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    tile_set = Column(String, nullable=False)
    camera_top = Column(Integer, nullable=False)
    camera_left = Column(Integer, nullable=False)
    camera_bottom = Column(Integer, nullable=False)
    camera_right = Column(Integer, nullable=False)

class Replay(Base):
    __tablename__ = 'replays'
    __table_args__ = {
        Index('idx_file_hash', 
            'file_hash', 
            unique=True, postgresql_using='hash')
    }
    id = Column(Integer, primary_key=True)
    file_hash = Column(BYTEA(32), unique=True)
    original_path = Column(BYTEA)
    versions = Column(ARRAY(Integer), nullable=False)
    category = Column(String(16), nullable=False)
    map_id = Column(Integer, ForeignKey('maps.id'))
    map = relationship('Map')
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    real_length = Column(Interval, nullable=False)
    expansion = Column(String(6), nullable=False)
    frames = Column(Integer, nullable=False)
    game_fps = Column(Float, nullable=False)
    real_type = Column(String(6), nullable=False)
    is_ladder = Column(Boolean, nullable=False)
    is_private = Column(Boolean, nullable=False)
    speed = Column(String(8), nullable=False)
    region = Column(String(2), nullable=False)
    winner_id = Column(Integer, ForeignKey('players.id'))
    winner = relationship('Player', foreign_keys=[ winner_id ])
    player_1_id = Column(Integer, ForeignKey('players.id'))
    player_1 = relationship('Player', foreign_keys=[ player_1_id ])
    player_2_id = Column(Integer, ForeignKey('players.id'))
    player_2 = relationship('Player', foreign_keys=[ player_2_id ])

class BattleNetInfo(Base):
    __tablename__ = 'battle_net_info'
    __table_args__ = {
        Index('idx_locator', 
            'profile_id', 'region', 'realm', 
            unique=True)
    }
    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, nullable=False)
    region = Column(Integer, nullable=False)
    realm = Column(Integer, nullable=False)
    ladder_id = Column(Integer)
    favorite_race = Column(Enum(Race))
    clan_tag = Column(String(6))
    clan_name = Column(String)
    display_name = Column(String(12))
    mmr = Column(Integer)
    rank = Column(Integer)
    points = Column(Integer)
    previous_rank = Column(Integer)
    wins = Column(Integer)
    losses = Column(Integer)
    join_timestamp = Column(DateTime)
    player_id = Column(Integer, ForeignKey('players.id'))
    player = relationship('Player', back_populates='battle_net_infos')

class Team(Base):
    __tablename__ = 'teams'
    id = Column(Integer, primary_key=True)
    clan_name = Column(String, nullable=False)
    clan_tag = Column(String(6), unique=True, index=True)
    players = relationship('Player', back_populates='team')

class Player(Base):
    __tablename__ = 'players'
    id = Column(Integer, primary_key=True)
    pro_name = Column(String(12), unique=True)
    #race = Column(Enum(Race), nullable=False)
    nationality = Column(String(2))
    team = relationship('Team', back_populates='players')
    team_id = Column(Integer, ForeignKey('teams.id'))
    battle_net_infos = relationship('BattleNetInfo')
    replays = relationship('Replay')

