import importlib.util
from pathlib import Path
import sys
import tomllib
import types

from lights import (
    BUTTON_LED_PAIRS,
    COMMAND_COLORS,
    GAME_OVER_DIM,
    LOSS_COLOR,
    OFF,
    SPACE_ADDRESS,
    SPACE_REG_BLUE,
    SPACE_REG_CTRL,
    SPACE_REG_GREEN,
    SPACE_REG_PATTERN,
    SPACE_REG_RED,
    VICTORY_COLORS,
    QuestLights,
)
from quest import (
    ACTION_DURATION_MS,
    COMMANDS,
    STATE_CUE,
    STATE_ENEMY_ATTACK,
    STATE_GAME_OVER,
    STATE_INPUT,
    STATE_PLAYER_ATTACK,
    STATE_TITLE,
    STATE_VICTORY,
    VICTORY_DURATION_MS,
    QuestBattle,
)


ROOT = Path(__file__).parents[1]


class FakeContext:
    CENTER = "center"
    MIDDLE = "middle"

    def __init__(self):
        self.font_size = 0
        self.text_align = None
        self.text_baseline = None
        self.line_width = 1
        self.labels = []

    def save(self):
        return self

    def restore(self):
        return self

    def rgb(self, *_args):
        return self

    def rectangle(self, *_args):
        return self

    def arc(self, *_args):
        return self

    def begin_path(self):
        return self

    def move_to(self, *_args):
        return self

    def line_to(self, *_args):
        return self

    def text(self, value):
        self.labels.append(value)
        return self

    def fill(self):
        return self

    def stroke(self):
        return self


class FakeLeds:
    def __init__(self):
        self.values = {}
        self.writes = 0

    def __setitem__(self, index, color):
        self.values[index] = color

    def write(self):
        self.writes += 1


def load_game_runtime(monkeypatch):
    class FakeApp:
        def __init__(self):
            self.terminated = False

        def terminate(self):
            self.terminated = True

    class FakeButtons:
        def __init__(self, _app):
            self.down = set()

        def pressed(self, button):
            return button in self.down

        def clear(self):
            self.down.clear()

    app_module = types.ModuleType("app")
    app_module.App = FakeApp
    events_module = types.ModuleType("events")
    events_module.__path__ = []
    input_module = types.ModuleType("events.input")
    input_module.BUTTON_TYPES = {
        "UP": "up",
        "RIGHT": "right",
        "CONFIRM": "confirm",
        "DOWN": "down",
        "LEFT": "left",
        "CANCEL": "cancel",
    }
    input_module.Buttons = FakeButtons
    monkeypatch.setitem(sys.modules, "app", app_module)
    monkeypatch.setitem(sys.modules, "events", events_module)
    monkeypatch.setitem(sys.modules, "events.input", input_module)

    spec = importlib.util.spec_from_file_location(
        "ethans_quest_runtime", ROOT / "app.py"
    )
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    return runtime


def advance_to_input(battle):
    while battle.state == STATE_CUE:
        battle.update(battle.cue_interval_ms)
    assert battle.state == STATE_INPUT


def complete_sequence(battle):
    advance_to_input(battle)
    for command in battle.sequence:
        assert battle.press(command)


def test_difficulty_gets_faster_and_sequences_get_longer():
    battle = QuestBattle(seed=2)
    battle.start_game()
    first = (battle.sequence_length, battle.cue_interval_ms, battle.command_window_ms)

    assert first == (3, 1500, 3000)

    battle.level = 9
    later = (battle.sequence_length, battle.cue_interval_ms, battle.command_window_ms)

    assert later[0] > first[0]
    assert later[1] < first[1]
    assert later[2] < first[2]


def test_correct_sequence_damages_enemy_and_starts_another_round():
    battle = QuestBattle(seed=3)
    battle.start_game()
    enemy_hp = battle.enemy_hp

    complete_sequence(battle)

    assert battle.state == STATE_PLAYER_ATTACK
    assert battle.enemy_hp == enemy_hp - 1
    battle.update(ACTION_DURATION_MS)
    assert battle.state == STATE_CUE


def test_wrong_button_and_timeout_damage_player():
    battle = QuestBattle(seed=4)
    battle.start_game()
    advance_to_input(battle)
    wrong = next(command for command in COMMANDS if command != battle.expected_command)

    assert battle.press(wrong)
    assert battle.state == STATE_ENEMY_ATTACK
    assert battle.player_hp == battle.player_max_hp - battle.enemy_attack
    battle.update(ACTION_DURATION_MS)
    advance_to_input(battle)
    hp_before_timeout = battle.player_hp
    battle.update(battle.command_window_ms)
    assert battle.state == STATE_ENEMY_ATTACK
    assert battle.player_hp == hp_before_timeout - battle.enemy_attack


def test_victory_awards_xp_and_loads_next_enemy():
    battle = QuestBattle(seed=5)
    battle.start_game()
    first_enemy = battle.enemy_name
    battle.enemy_hp = 1

    complete_sequence(battle)
    battle.update(ACTION_DURATION_MS)

    assert battle.state == STATE_VICTORY
    assert battle.xp == 25
    battle.update(VICTORY_DURATION_MS)
    assert battle.level == 2
    assert battle.enemy_name != first_enemy
    assert battle.state == STATE_CUE


def test_game_over_can_restart_with_confirm():
    battle = QuestBattle(seed=6)
    battle.start_game()
    battle.player_hp = 1
    advance_to_input(battle)
    wrong = next(command for command in COMMANDS if command != battle.expected_command)
    battle.press(wrong)
    battle.update(ACTION_DURATION_MS)

    assert battle.state == STATE_GAME_OVER
    assert battle.press("CONFIRM")
    assert battle.state == STATE_CUE
    assert battle.level == 1
    assert battle.player_hp == battle.player_max_hp


def test_sequences_use_only_combat_buttons_and_avoid_triple_repeats():
    battle = QuestBattle(seed=7)
    battle.start_game()
    battle.level = 20
    battle._begin_round()

    assert set(battle.sequence).issubset(COMMANDS)
    for index in range(2, len(battle.sequence)):
        assert not (
            battle.sequence[index]
            == battle.sequence[index - 1]
            == battle.sequence[index - 2]
        )


def test_each_cue_lights_the_led_pair_beside_its_button():
    battle = QuestBattle(seed=8)
    battle.start_game()
    leds = FakeLeds()
    lights = QuestLights(leds=leds)
    lights.acquire()

    for command in COMMANDS:
        battle.sequence = [command]
        battle.cue_index = 0
        battle.elapsed_ms = 0
        battle.state = STATE_CUE
        lights.update(battle)

        expected_pair = BUTTON_LED_PAIRS[command]
        expected_color = COMMAND_COLORS[command]
        assert {
            index for index, color in leds.values.items() if color != OFF
        } == set(expected_pair)
        assert all(leds.values[index] == expected_color for index in expected_pair)

    battle.elapsed_ms = battle.cue_interval_ms * 3 // 4
    lights.update(battle)
    assert all(leds.values[index] == OFF for index in range(1, 13))


def test_victory_and_loss_have_distinct_flashing_ring_effects():
    battle = QuestBattle(seed=9)
    battle.start_game()
    leds = FakeLeds()
    lights = QuestLights(leds=leds)
    lights.acquire()

    battle.state = STATE_VICTORY
    battle.elapsed_ms = 0
    lights.update(battle)
    assert set(leds.values.values()) == {VICTORY_COLORS[0]}
    battle.elapsed_ms = 180
    lights.update(battle)
    assert set(leds.values.values()) == {VICTORY_COLORS[1]}

    battle.state = STATE_ENEMY_ATTACK
    battle.elapsed_ms = 0
    lights.update(battle)
    assert set(leds.values.values()) == {LOSS_COLOR}
    battle.elapsed_ms = 130
    lights.update(battle)
    assert set(leds.values.values()) == {OFF}

    battle.state = STATE_GAME_OVER
    battle.elapsed_ms = 360
    lights.update(battle)
    assert set(leds.values.values()) == {GAME_OVER_DIM}


def test_space_unicorn_state_is_restored_when_game_releases_lights():
    initial = {
        SPACE_REG_CTRL: 8,
        SPACE_REG_PATTERN: 7,
        SPACE_REG_GREEN: 22,
        SPACE_REG_RED: 33,
        SPACE_REG_BLUE: 44,
    }
    buses = {}

    class FakeI2C:
        def __init__(self, port):
            self.port = port
            self.registers = dict(initial)
            self.writes = []

        def scan(self):
            return [SPACE_ADDRESS] if self.port == 4 else []

        def readfrom_mem(self, address, register, _length):
            assert address == SPACE_ADDRESS
            return bytes([self.registers[register]])

        def writeto_mem(self, address, register, value):
            assert address == SPACE_ADDRESS
            self.registers[register] = value[0]
            self.writes.append((register, value[0]))

    def make_i2c(port):
        bus = FakeI2C(port)
        buses[port] = bus
        return bus

    battle = QuestBattle(seed=10)
    battle.start_game()
    battle.state = STATE_VICTORY
    battle.elapsed_ms = 0
    lights = QuestLights(leds=FakeLeds(), i2c_factory=make_i2c)
    lights.acquire()
    lights.update(battle)

    assert lights.space_connected
    assert buses[4].registers != initial
    lights.release()
    assert buses[4].registers == initial
    assert not lights.space_connected


def test_badge_app_starts_exits_and_renders_every_state(monkeypatch):
    runtime = load_game_runtime(monkeypatch)
    game = runtime.EthansQuestApp()
    context = FakeContext()

    assert game.battle.state == STATE_TITLE
    game.draw(context)
    assert "ETHAN'S" in context.labels
    assert "QUEST" in context.labels

    game.buttons.down.add("confirm")
    game.update(20)
    assert game.battle.state == STATE_CUE

    for enemy_kind in ("slime", "goblin", "skeleton", "wraith", "dragon"):
        game.battle.enemy_kind = enemy_kind
        for state in (
            STATE_CUE,
            STATE_INPUT,
            STATE_PLAYER_ATTACK,
            STATE_ENEMY_ATTACK,
            STATE_VICTORY,
        ):
            game.battle.state = state
            game.battle.elapsed_ms = 100
            game.draw(context)

    game.battle.state = STATE_GAME_OVER
    game.draw(context)
    game.buttons.down.add("cancel")
    game.update(20)
    assert game.terminated
    assert not game.lights.owned


def test_manifests_use_ethans_quest_title_and_author():
    with (ROOT / "tildagon.toml").open("rb") as manifest_file:
        manifest = tomllib.load(manifest_file)

    assert manifest["app"]["name"] == "Ethan's Quest"
    assert manifest["app"]["category"] == "Games"
    assert manifest["entry"]["class"] == "EthansQuestApp"
    assert manifest["metadata"]["author"] == "Graham Hosking"
    assert manifest["metadata"]["version"] == "0.2.0"
    assert len(manifest["metadata"]["description"]) <= 140