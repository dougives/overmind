import re
from pathlib import Path
import string
import json
import difflib
from functools import partial, reduce
from itertools import (
    product, repeat, chain, combinations,
    starmap, dropwhile, count, islice)
from operator import xor, eq, ne, itemgetter, lt
import time
from overmind import bnet_api
from overmind.database import Session
from overmind.database.models import (
    BattleNetInfo, Player, Team, Race,
    Map, Replay)
from overmind.database.queries import (
    get_battle_net_info_by_locator,
    get_player_by_pro_name,
    get_team_by_clan_tag,
    get_map_by_file_hash,
    get_replay_by_file_hash,
    get_replay_data_path)
from datetime import datetime, timedelta
import shutil
from multiprocessing.pool import ThreadPool
import dotenv

dotenv.load_dotenv()

import sc2reader

SOURCE_PATH = '/media/bulk/sc2/ggtracker/'
SC2REPLAY_EXTENTION_GLOB = '*.[Ss][Cc]2[Rr][Ee][Pp][Ll][Aa][Yy]'
PLAYER_SET_PATH = 'player_set.txt'
BARCODE_REPORT_PATH = '_barcode_report.json'
PLAYER_ALIAS_MAP_PATH = 'player_alias_map.json'
NOT_LABELD_REPORT_PATH = 'not_labeled.txt'

_replay_data_path_session, _replay_data_path = \
    get_replay_data_path(None)
_replay_data_path_session.close()
_replay_data_path = Path(_replay_data_path)


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
        tuple(map(
            format_player_name,
            players.groups()))))

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
    if not players:
        return {
            (x.name, x.name.lower()): x
            for x in replay.players
        }
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
    # take highest value >= 0.6
    if all(map(partial(lt, 0.6), chain(*chain(*ratios)))):
        return None
    if all(starmap(eq, combinations(chain(*chain(*ratios)), 2))):
        return None
    return order_result(reduce(xor, reduce(
        lambda a, s: s if s[0] > a[0] else a, 
        ( (ratios[i][j][k], i, k) 
            for i, j, k in iter_ratios() ))[1:]))

def ladder_stats_to_locator(ladder_stats):
    return (
        ladder_stats['region'],
        ladder_stats['realm'],
        ladder_stats['id']) \
        if ladder_stats else None

def replay_to_map_info(replay, _session=None):
    #global _session
    _session, map_info = get_map_by_file_hash(_session, bytes.fromhex(replay.map_hash))
    if map_info:
        return _session, map_info
    replay.load_map()
    map_info = Map(
        file_hash=bytes.fromhex(replay.map.filehash),
        map_name=replay.map.name,
        width=replay.map.map_info.width,
        height=replay.map.map_info.height,
        tile_set=replay.map.map_info.tile_set,
        camera_top=replay.map.map_info.camera_top,
        camera_left=replay.map.map_info.camera_left,
        camera_bottom=replay.map.map_info.camera_bottom,
        camera_right=replay.map.map_info.camera_right)
    _session.add(map_info)
    return _session, map_info

def replay_to_replay_info(replay, map_info, bnet_infos, path, _session=None):
    #global _session
    _session, replay_info = get_replay_by_file_hash(_session, bytes.fromhex(replay.filehash))
    if replay_info:
        return _session, replay_info
    def select_winner():
        winner_data = replay.winner.players[0].detail_data['bnet']
        return next(dropwhile(
            lambda x: x[1] != (
                winner_data['region'],
                winner_data['subregion'],
                winner_data['uid']),
            ( (bnet_info, (bnet_info.region, bnet_info.realm, bnet_info.profile_id))
                for bnet_info in bnet_infos )))[0]
    replay = Replay(
        file_hash=bytes.fromhex(replay.filehash),
        original_path=bytes(path),
        versions=replay.versions,
        category=replay.category,
        map=map_info,
        start_time=replay.start_time + timedelta(hours=replay.time_zone),
        end_time=replay.end_time + timedelta(hours=replay.time_zone),
        real_length=timedelta(seconds=replay.real_length.seconds),
        expansion=replay.expansion,
        frames=replay.frames,
        game_fps=replay.game_fps,
        real_type=replay.real_type,
        is_ladder=replay.is_ladder,
        is_private=replay.is_private,
        speed=replay.speed,
        region=replay.region,
        winner=select_winner(),
        battle_net_infos=bnet_infos)
    _session.add(replay)
    return _session, replay

def ladder_stats_to_battle_net_info(
    display_name, clan_tag, locator, ladder_stats, 
    pro_name=None, _session=None):
    #global _session
    _session, bnet_info = get_battle_net_info_by_locator(_session, *locator)
    if bnet_info:
        return _session, bnet_info 
    player = None
    if pro_name:
        _session, player = get_player_by_pro_name(_session, pro_name)
    if not player:
        player = Player(pro_name=pro_name)
        _session.add(player)
    # team should be updated manually/from liquipedia
    bnet_info = tuple(filter(
        partial(eq, locator[2]), ( 
            bnetinfo.profile_id 
            for bnetinfo in player.battle_net_infos )))
    if bnet_info:
        return _session, bnet_info[0]
    bnet_info = BattleNetInfo(
        player=player, **{
            camel_to_snake(key) 
                if key != 'id' 
                else 'profile_id': Race[value.upper()]
                    if key == 'favoriteRace'
                    else datetime.fromtimestamp(value)
                    if key == 'joinTimestamp'
                    else int(value)
                    if key == 'id'
                    else value
            for key, value in ladder_stats.items() })
    if not bnet_info.display_name:
        bnet_info.display_name = display_name
    if not bnet_info.clan_tag:
        bnet_info.clan_tag = clan_tag
    _session.add(bnet_info)
    #session.commit()
    return _session, bnet_info
        

def player_to_locator(replay, player):
    return \
        player.detail_data['bnet']['region'], \
        player.detail_data['bnet']['subregion'], \
        player.detail_data['bnet']['uid']

def clan_tag_from_replay(display_name, replay):
    return next(dropwhile(
        partial(ne, display_name),
        ( player.name for player in replay.players ))) \
        .name

def import_with_path_label(path, assume_pro=False):
    _stopwatch = time.time_ns()
    _session = Session()
    not_labeled = list()
    replay = load_replay(path, load_level=2)
    if not replay:
        _session.close()
        mark = time.time_ns() - _stopwatch
        return mark / (10**9), None
    players = parse_players_from_path(path)
    #if not players:
    #    #not_labeled.append(path)
    #    _session.close()
    #    mark = time.time_ns() - _stopwatch
    #    return mark / (10**9), None
    match = match_replay_player_names(replay, players)
    if not match:
        _session.close()
        mark = time.time_ns() - _stopwatch
        return mark / (10**9), None
    bnet_infos = tuple(
        ladder_stats_to_battle_net_info(
            player.name,
            player.clan_tag,
            player_to_locator(replay, player),
            bnet_api.get_showcased_ladder_stats(
                *player_to_locator(replay, player)),
            pro_name,
            _session=_session)
        for (_, pro_name), player in match.items() )
    _session = bnet_infos[-1][0]
    _session, map_info = replay_to_map_info(replay, _session=_session)
    _session, replay_info = replay_to_replay_info(
        replay,
        map_info,
        tuple(map(itemgetter(1), bnet_infos)),
        path,
        _session=_session)

    copy_path = _replay_data_path / f'{replay.filehash}.SC2Replay'
    if not copy_path.exists():
        shutil.copy(path, copy_path)
    
    mark = time.time_ns() - _stopwatch
    _session.commit()
    _session.close()
    #print(f'{next(_counter)}    {mark / (10**9)}    {normalize_text(str(path))}')
    return mark / (10**9), copy_path

def _import_with_path_label_thread(counter_and_path):
    counter, path = counter_and_path
    try:
        result = (counter, None, path, import_with_path_label(path))
        return result
    except KeyboardInterrupt:
        return counter, KeyboardInterrupt, path, (None, None)
    #except AssertionError as e:
    except Exception as e:
        return counter, e, path, (None, None)


def main():
    load_player_alias_map(PLAYER_ALIAS_MAP_PATH)
    paths = list(map(tuple, enumerate(walk_paths(SOURCE_PATH))))
    with open('not_imported.txt', 'a') as file:
        results = ThreadPool(32).imap(
            _import_with_path_label_thread,
            paths)
        for counter, exception, path, (marktime, copy_path) in results:
            if isinstance(exception, KeyboardInterrupt):
                exit(-1)
            if copy_path:
                print(f'{counter}    {marktime}    {normalize_text(str(path))}')
                continue
            file.write(f'{normalize_text(str(path))}\n')
        #for path in paths[3060:3071]:
        #    try:
        #        copy_path = import_with_path_label(path)
        #        if not copy_path:
        #            file.write(f'{normalize_text(str(path))}\n')
        #    except KeyboardInterrupt:
        #        return -1
        #    except:
        #        file.write(f'{normalize_text(str(path))}\n')


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

