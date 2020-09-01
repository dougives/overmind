import re
from pathlib import Path
import string
import json
import difflib
from functools import partial, reduce
from itertools import product, repeat, chain
from operator import xor, eq
import time
from overmind import bnet_api
from overmind.database import session
from overmind.database.models import (
    BattleNetInfo, Player, Team)
from overmind.database.queries import (
    get_battle_net_info_by_locator,
    get_player_by_pro_name,
    get_team_by_clan_tag)
import dotenv

dotenv.load_dotenv()

import sc2reader

SOURCE_PATH = '/media/bulk/sc2/releases/'
SC2REPLAY_EXTENTION_GLOB = '*.[Ss][Cc]2[Rr][Ee][Pp][Ll][Aa][Yy]'
PLAYER_SET_PATH = 'player_set.txt'
BARCODE_REPORT_PATH = '_barcode_report.json'
PLAYER_ALIAS_MAP_PATH = 'player_alias_map.json'
NOT_LABELD_REPORT_PATH = 'not_labeled.txt'

_stopwatch = None
_session = session

_remove_re = re.compile(
    r'( \([PTZ]\)|_game_\d+)', re.I)

_barcode_re = re.compile(
    r'(?:\[(?P<clan_tag>\w+)\])?'
    r'(?P<barcode>[iIlI]{6,})')

_players_re = re.compile(
    r'(?:\([PTZ]\))?(?:\[(?:\w|\?)*\])?'
    r'(?P<player_1>[0-9A-Za-z\?]{2,}(?: \([PTZ]\))?)'
    r'(?:[ _]+vs?\.?|,)[ _]+'
    r'(?:\([PTZ]\))?(?:\[(?:\w|\?)*\])?'
    r'(?P<player_2>[0-9A-Za-z\?]{2,}(?: \([PTZ]\))?)',
    re.I)

_barcode_map = dict()
_player_alias_map = dict()
_player_alias_inverse_map = dict()

def camel_to_snake(s):
    return ''.join([
        '_'+c.lower() if c.isupper() else c
        for c in s ]).lstrip('_')

def normalize_text(text):
    return ''.join(filter(
        lambda c: c in string.printable,
        _remove_re.sub('', 
            text \
                .replace('&lt;', '[') \
                .replace('&gt;', ']') \
                .strip('?'))))

def format_player_name(text, resolve_alias=True):
    text = text.lstrip('?').lower()
    return _player_alias_inverse_map[text] \
        if resolve_alias and text in _player_alias_inverse_map \
        else text

def resolve_surrogates(text):
    return text \
        .encode('utf-8','surrogatepass') \
        .decode('utf-8')

def replace_barcode(text):
    for match in _barcode_re.finditer(text):
        clan_tag = format_player_name(
            match['clan_tag'] \
                .rstrip('1234567890') \
                .lower()) \
            if match['clan_tag'] \
            else ''
        _barcode_map[match['barcode']] = clan_tag
        if match['clan_tag']:    
            text = text.replace(match[0], clan_tag)
    return text

def transform_path_name(text):
    return replace_barcode(normalize_text(text))

def parse_players_from_path(path):
    players = _players_re.search(
        transform_path_name(path.name))
    if not players:
        players = _players_re.search(
            transform_path_name(path.parent.name))
    if not players:
        return None
    return tuple(zip(
        players.groups(), 
        tuple(filter(None, map(
            format_player_name,
            players.groups())))))

def process_path(path):
    return parse_players_from_path(path)

def walk_paths(path):
    return Path(path).rglob(SC2REPLAY_EXTENTION_GLOB)

def load_player_alias_map(path):
    global _player_alias_map
    global _player_alias_inverse_map
    with open(path, 'r') as file:
        _player_alias_map = json.load(file)
        _player_alias_inverse_map = {
            alias: player
            for player, values in _player_alias_map.items()
            for alias in values
        }
    return _player_alias_map

def load_replay(path, load_level=4, only_1v1=True):
    replay = sc2reader.load_replay(
        str(path), 
        load_level=load_level)
    return replay \
        if not only_1v1 or replay.type == '1v1' \
        else None

def string_simularity(left, right):
    return difflib.SequenceMatcher(None, left, right).ratio()

def match_replay_player_names(replay, players):
    order = players, tuple( x.name for x in replay.players )
    ratios = tuple(
        tuple( tuple(map(partial(string_simularity, h), s))
                for h, s in m )
        for m in (
            zip((n, format_player_name(n)), zip(*players))
            for n in order[1] ) )
    def order_result(swap):
        return dict(zip(order[0], replay.players[::1-(int(swap)*2)]))
    def iter_ratios():
        return product((0, 1), repeat=3)
    # take highest value
    return order_result(reduce(xor, reduce(
        lambda a, s: s if s[0] > a[0] else a, 
        ( (ratios[i][j][k], i, k) 
            for i, j, k in iter_ratios() ))[1:]))

def ladder_stats_to_locator(ladder_stats):
    return (
        ladder_stats['region'],
        ladder_stats['realm'],
        ladder_stats['id'])

def ladder_stats_to_battle_net_info(ladder_stats, pro_name=None):
    global session
    locator = ladder_stats_to_locator(ladder_stats)
    session, bnet_info = get_battle_net_info_by_locator(locator)
    if bnet_info:
        return bnet_info
    player = None
    if pro_name:
        session, player = get_player_by_pro_name(pro_name)
    if not Player:
        player = Player(pro_name=pro_name)
    # team should be updated manually/from liquipedia
    bnet_info = filter(
        partial(eq, locator[3]), ( 
            bnetinfo.profile_id 
            for bnetinfo in player.battle_net_infos ))
    if bnet_info:
        return bnet_info
    bnet_info = BattleNetInfo(
        player=player,
        **{ camel_to_snake(key) if key != 'id' else 'profile_id': value
            for key, value in ladder_stats.items() })
    return bnet_info
        

def player_to_battle_net_locator(replay, player):
    return \
        player.detail_data['bnet']['region'], \
        player.detail_data['bnet']['subregion'], \
        player.detail_data['bnet']['uid']

def import_with_path_label(path, assume_pro=False):
    global _stopwatch
    _stopwatch = time.time_ns()
    not_labeled = list()
    replay = load_replay(path, load_level=2)
    replay.load_map()
    players = parse_players_from_path(path)
    if not players:
        not_labeled.append(path)
        return None
    match = match_replay_player_names(replay, players)
    mark = time.time_ns() - _stopwatch
    print(mark / (10**9))
    ladder_stats = tuple(
        bnet_api.get_showcased_ladder_stats(
            *player_to_battle_net_locator(replay, player))
        for player in match.values() )
    pass


def main():
    load_player_alias_map(PLAYER_ALIAS_MAP_PATH)
    for path in walk_paths(SOURCE_PATH):
        import_with_path_label(path)

    #player_set = set()
    #not_labeled = list()
    #for path in walk_paths():
    #    replay = load_replay(path)
    #    players = process_path(path)
    #    if not players:
    #        not_labeled.append(path)
    #        continue
    #    players = tuple(filter(None, map(
    #        format_player_name,
    #        players)))
    #    player_set.update(players)
    #with open(PLAYER_SET_PATH, 'w') as file:
    #    for player in player_set:
    #        file.write(f'{player}\n')
    #with open(BARCODE_REPORT_PATH, 'w') as file:
    #    json.dump(_barcode_map, file, indent=4)
    #with open(NOT_LABELD_REPORT_PATH, 'w') as file:
    #    for path in not_labeled:
    #        file.write(f'{path}\n')
    return 0

