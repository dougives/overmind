import sc2reader
from sc2reader.events import *

TEST_REPLAY = '/media/bulk/sc2/releases/HomeStory/2020/1/Stay at HSC Replay Pack/Day 2/Group C/Serral vs. Elazer/Zen.SC2Replay'

filtered_events = {
    PlayerSetupEvent,
    CameraEvent,
    GetControlGroupEvent,
    SetControlGroupEvent,
    ChatEvent,
}


def main():
    is_past_setup = False
    replay = sc2reader.load_replay(TEST_REPLAY, load_map=True)
    replay.load_map()
    with open('log.txt', 'w') as file:
        for event in replay.tracker_events:
            is_past_setup = is_past_setup or isinstance(event, PlayerStatsEvent)
            if not is_past_setup or type(event) in filtered_events:
                continue
            file.write(f'{event}\n')

    return 0

