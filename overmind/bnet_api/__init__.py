from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
from requests.adapters import HTTPAdapter
import os
import json
from itertools import dropwhile
from functools import partial
from operator import ne
from time import sleep
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

_oauth.mount(BASE_URL_FORMAT, HTTPAdapter(max_retries=10))

def _build_url(region, subregion, profile_id, endpoint=None):
    return BASE_URL_FORMAT.format(
        region, 
        subregion, 
        profile_id,
        endpoint if endpoint else '',
        _token['access_token'])

def _get(region, subregion, profile_id, endpoint, retries=10):
    assert retries > 0
    try:
        response = _oauth.get(_build_url(region, subregion, profile_id, endpoint))
        if not response.ok:
            if response.status_code == 429:
                sleep(5)
            _get(region, subregion, profile_id, endpoint, retries - 1)
        return response.json()
    except:
        sleep(1)
        _get(region, subregion, profile_id, endpoint, retries - 1)

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
    ladder = get_showcased_ladder(region, subregion, profile_id)
    ladder_id = ladder['currentLadderMembership']['ladderId'] \
        if ladder else None
    ladder_teams = enumerate(ladder['ladderTeams'], start=1) \
        if ladder else None
    def find_ladder_stats_from_teams():
        for rank, stats in ladder_teams:
            if stats['teamMembers'][0]['id'] == str(profile_id):
                return { 
                    'rank': rank,
                    'ladderId': ladder_id,
                    'id': profile_id,
                    **stats }
    ladder_stats = find_ladder_stats_from_teams() \
        if ladder_teams \
        else { 'teamMembers': [ {
            'id': str(profile_id),
            'realm': subregion,
            'region': region } ] }
    if flatten:
        ladder_stats.update(ladder_stats['teamMembers'][0])
        del ladder_stats['teamMembers']
    return ladder_stats

def get_mmr(region, subregion, profile_id, game_mode='1v1'):
    ladder_stats = get_showcased_ladder_stats(
        region, subregion, profile_id, game_mode)
    return ladder_stats['mmr'] if ladder_stats else None

