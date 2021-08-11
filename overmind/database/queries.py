from .models import (
    Race, ReplayDataPath, Map, Replay,
    BattleNetInfo, Team, Player)
from functools import wraps
from . import Session

def query(query_func):
    @wraps(query_func)
    def _query(session, *args, **kwargs) -> (Session, object):
        if not session:
            session = Session()
        return session, query_func(session, *args, **kwargs)
    return _query


def _exists(session, entity, **kwargs):
    return session.query(
        session.query(entity) \
            .filter_by(**kwargs) \
            .exists())

@query
def map_exists(session, file_hash):
    return _exists(session, Map, file_hash=file_hash)

@query
def replay_exists(session, file_hash):
    return _exists(session, Replay, file_hash=file_hash)

@query
def team_exists(session, clan_tag):
    return _exists(session, Team, clan_tag=clan_tag)

@query
def battle_net_info_exists(session, region, realm, profile_id):
    return _exists(session, BattleNetInfo,
        region=region, 
        realm=realm, 
        profile_id=profile_id)

@query
def player_exists(session, pro_name):
    return _exists(session, Player, pro_name=pro_name)


def _get(session, entity, **kwargs):
    return session.query(entity).filter_by(**kwargs).first()

@query
def get_player_by_pro_name(session, pro_name) -> Player:
    return _get(session, Player, pro_name=pro_name)

@query
def get_team_by_clan_tag(session, clan_tag):
    return _get(session, Team, clan_tag=clan_tag)

@query
def get_battle_net_info_by_locator(session, region, realm, profile_id):
    return _get(session, BattleNetInfo,
        region=region,
        realm=realm,
        profile_id=profile_id)

@query
def get_replay_by_file_hash(session, file_hash):
    return _get(session, Replay, file_hash=file_hash)

@query
def get_map_by_file_hash(session, file_hash):
    return _get(session, Map, file_hash=file_hash)

@query
def get_replay_data_path(session):
    return session.query(
        ReplayDataPath.replay_data_path).first()[0]





