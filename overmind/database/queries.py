from .models import (
    Race, ReplayDataPath, Map, Replay,
    BattleNetInfo, Team, Player)
from . import Session, session
from functools import wraps


def query(query_func):
    @wraps(query_func)
    def _query(*args, **kwargs) -> (Session, object):
        return session, query_func(*args, **kwargs)
    return _query


def _exists(entity, **kwargs):
    return session.query(
        session.query(entity) \
            .filter_by(**kwargs) \
            .exists())

@query
def map_exists(file_hash):
    return _exists(Map, file_hash=file_hash)

@query
def replay_exists(file_hash):
    return _exists(Replay, file_hash=file_hash)

@query
def team_exists(clan_tag):
    return _exists(Team, clan_tag=clan_tag)

@query
def battle_net_info_exists(region, realm, profile_id):
    return _exists(BattleNetInfo,
        region=region, 
        realm=realm, 
        profile_id=profile_id)

@query
def player_exists(pro_name):
    return _exists(Player, pro_name=pro_name)


def _get(entity, **kwargs):
    return session.query(entity).filter_by(**kwargs).first()

@query
def get_player_by_pro_name(pro_name) -> Player:
    return _get(Player, pro_name=pro_name)

@query
def get_team_by_clan_tag(clan_tag):
    return _get(Team, clan_tag=clan_tag)

@query
def get_battle_net_info_by_locator(region, realm, profile_id):
    return _get(BattleNetInfo,
        region=region,
        realm=realm,
        profile_id=profile_id)

@query
def get_replay_by_file_hash(file_hash):
    return _get(Replay, file_hash=file_hash)

@query
def get_map_by_file_hash(file_hash):
    return _get(Map, file_hash=file_hash)

@query
def get_replay_data_path():
    return session.query(ReplayDataPath.replay_data_path).first()



