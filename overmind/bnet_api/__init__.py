from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
import os
import json
import dotenv

dotenv.load_dotenv()

BASE_URL_FORMAT = 'https://us.api.blizzard.com/sc2/profile/{}/{}/{}{}?access_token={}'

_client = BackendApplicationClient(
    client_id=os.environ['BNET_API_CLIENT_ID'])
_oauth = OAuth2Session(client=_client)
_token = _oauth.fetch_token(
    token_url='https://us.battle.net/oauth/token',
    client_id=os.environ['BNET_API_CLIENT_ID'],
    client_secret=os.environ['BNET_API_CLIENT_SECRET'])

def _build_url(region, subregion, profile_id, endpoint=None):
    return BASE_URL_FORMAT.format(
        region, 
        subregion, 
        profile_id,
        endpoint if endpoint else '',
        _token['access_token'])

def _get(region, subregion, profile_id, endpoint):
    response = _oauth.get(_build_url(region, subregion, profile_id, endpoint))
    return response.json() if response.ok else None

def get_ladder_summary(region, subregion, profile_id):
    return _get(region, subregion, profile_id, '/ladder/summary')

def get_ladder(region, subregion, profile_id, ladder_id):
    return _get(region, subregion, profile_id, f'/ladder/{ladder_id}')

def get_ladder_showcase_entry(region, subregion, profile_id, game_mode='1v1'):
    ladder_summary = get_ladder_summary(region, subregion, profile_id)
    if not ladder_summary:
        return None
    showcase = tuple(filter(
        lambda x: x['team']['localizedGameMode'] == game_mode,
        ladder_summary['showCaseEntries']))
    return showcase[0] if showcase else None

def get_showcased_ladder(region, subregion, profile_id, game_mode='1v1'):
    showcase = get_ladder_showcase_entry(region, subregion, profile_id, game_mode)
    return get_ladder(region, subregion, profile_id, showcase['ladderId']) \
        if showcase else None

def get_showcased_ladder_teams(region, subregion, profile_id, game_mode='1v1'):
    ladder = get_showcased_ladder(region, subregion, profile_id, game_mode)
    return ladder['ladderTeams'] if ladder else None

def get_showcased_ladder_stats(
    region, subregion, profile_id,
    game_mode='1v1',
    flatten=True):
    ladder_teams = get_showcased_ladder_teams(
        region, subregion, profile_id, game_mode)
    if not ladder_teams:
        return None
    ladder_stats = tuple(filter(
        lambda x: any(map(
            lambda y: y['id'] == str(profile_id), 
            x['teamMembers'])),
        ladder_teams))
    if not ladder_stats:
        return None
    ladder_stats = ladder_stats[0]
    if flatten:
        ladder_stats.update(ladder_stats['teamMembers'][0])
        del ladder_stats['teamMembers']
    ladder_stats['id'] = int(ladder_stats['id'])
    return ladder_stats

def get_mmr(region, subregion, profile_id, game_mode='1v1'):
    ladder_stats = get_showcased_ladder_stats(
        region, subregion, profile_id, game_mode)
    return ladder_stats['mmr'] if ladder_stats else None

