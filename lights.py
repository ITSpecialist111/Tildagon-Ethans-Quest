OFF = (0, 0, 0)

BUTTON_LED_PAIRS = {
    "UP": (1, 12),
    "RIGHT": (2, 3),
    "CONFIRM": (4, 5),
    "DOWN": (6, 7),
    "LEFT": (8, 9),
}

COMMAND_COLORS = {
    "UP": (20, 75, 110),
    "RIGHT": (105, 48, 8),
    "CONFIRM": (100, 88, 15),
    "DOWN": (18, 95, 40),
    "LEFT": (80, 28, 100),
}

VICTORY_COLORS = ((18, 100, 38), (105, 82, 10))
STRIKE_COLOR = (95, 50, 8)
LOSS_COLOR = (110, 6, 2)
GAME_OVER_DIM = (28, 0, 0)

SPACE_ADDRESS = 0x40
SPACE_REG_CTRL = 0x00
SPACE_REG_PATTERN = 0x01
SPACE_REG_GREEN = 0x10
SPACE_REG_RED = 0x11
SPACE_REG_BLUE = 0x12
SPACE_CTRL_PATTERN = 0x04
SPACE_PATTERN_OFF = 0
SPACE_PATTERN_SOLID = 1
SPACE_SNAPSHOT_REGISTERS = (
    SPACE_REG_CTRL,
    SPACE_REG_PATTERN,
    SPACE_REG_GREEN,
    SPACE_REG_RED,
    SPACE_REG_BLUE,
)

try:
    from machine import I2C as _I2C
except ImportError:
    _I2C = None

try:
    from tildagonos import tildagonos as _tildagonos
except ImportError:
    _tildagonos = None

try:
    from system.eventbus import eventbus as _eventbus
    from system.patterndisplay.events import PatternDisable, PatternEnable
except ImportError:
    _eventbus = None
    PatternDisable = None
    PatternEnable = None


def _solid_frame(color):
    return (color,) * 12


def _command_frame(command, color):
    frame = [OFF] * 12
    for led in BUTTON_LED_PAIRS.get(command, ()):
        frame[led - 1] = color
    return tuple(frame)


class QuestLights:
    def __init__(self, leds=None, i2c_factory=None):
        self.leds = leds
        if self.leds is None and _tildagonos is not None:
            self.leds = _tildagonos.leds
        self.i2c_factory = i2c_factory if i2c_factory is not None else _I2C
        self.owned = False
        self.last_ring_frame = None
        self.space_i2c = None
        self.space_snapshot = None
        self.last_space_color = object()

    @property
    def space_connected(self):
        return self.space_i2c is not None

    def acquire(self):
        if not self.owned:
            if _eventbus is not None and PatternDisable is not None:
                _eventbus.emit(PatternDisable())
            self.owned = True
        self.last_ring_frame = None
        if self.space_i2c is None:
            self._find_space_unicorn()

    def release(self):
        self._write_ring(_solid_frame(OFF))
        self._restore_space_unicorn()
        if self.owned and _eventbus is not None and PatternEnable is not None:
            _eventbus.emit(PatternEnable())
        self.owned = False

    def _find_space_unicorn(self):
        if self.i2c_factory is None:
            return
        for port in range(1, 7):
            try:
                candidate = self.i2c_factory(port)
                if SPACE_ADDRESS not in candidate.scan():
                    continue
                snapshot = {}
                for register in SPACE_SNAPSHOT_REGISTERS:
                    snapshot[register] = candidate.readfrom_mem(
                        SPACE_ADDRESS, register, 1
                    )[0]
                self.space_i2c = candidate
                self.space_snapshot = snapshot
                self.last_space_color = object()
                return
            except Exception:
                continue

    def _write_ring(self, frame):
        if frame == self.last_ring_frame:
            return
        self.last_ring_frame = frame
        if self.leds is None:
            return
        try:
            for index, color in enumerate(frame, 1):
                self.leds[index] = color
            self.leds.write()
        except Exception:
            self.leds = None

    def _write_space(self, color):
        if self.space_i2c is None or color == self.last_space_color:
            return
        try:
            if color == OFF:
                self.space_i2c.writeto_mem(
                    SPACE_ADDRESS, SPACE_REG_PATTERN, bytes([SPACE_PATTERN_OFF])
                )
            else:
                red, green, blue = color
                for register, value in (
                    (SPACE_REG_GREEN, green),
                    (SPACE_REG_RED, red),
                    (SPACE_REG_BLUE, blue),
                    (SPACE_REG_PATTERN, SPACE_PATTERN_SOLID),
                ):
                    self.space_i2c.writeto_mem(
                        SPACE_ADDRESS, register, bytes([value])
                    )
            self.space_i2c.writeto_mem(
                SPACE_ADDRESS, SPACE_REG_CTRL, bytes([SPACE_CTRL_PATTERN])
            )
            self.last_space_color = color
        except Exception:
            self.space_i2c = None

    def _restore_space_unicorn(self):
        if self.space_i2c is None or self.space_snapshot is None:
            return
        try:
            for register in (
                SPACE_REG_GREEN,
                SPACE_REG_RED,
                SPACE_REG_BLUE,
                SPACE_REG_PATTERN,
                SPACE_REG_CTRL,
            ):
                self.space_i2c.writeto_mem(
                    SPACE_ADDRESS,
                    register,
                    bytes([self.space_snapshot[register]]),
                )
        except Exception:
            pass
        self.space_i2c = None
        self.space_snapshot = None
        self.last_space_color = object()

    def update(self, battle):
        frame = _solid_frame(OFF)
        space_color = OFF

        if battle.state == "cue":
            cue_on_ms = battle.cue_interval_ms * 3 // 4
            if battle.elapsed_ms < cue_on_ms:
                command = battle.shown_command
                color = COMMAND_COLORS.get(command, OFF)
                frame = _command_frame(command, color)
                space_color = color
        elif battle.state == "player_attack":
            frame = _solid_frame(STRIKE_COLOR)
            space_color = STRIKE_COLOR
        elif battle.state == "enemy_attack":
            if (battle.elapsed_ms // 130) % 2 == 0:
                frame = _solid_frame(LOSS_COLOR)
                space_color = LOSS_COLOR
        elif battle.state == "victory":
            color = VICTORY_COLORS[(battle.elapsed_ms // 180) % 2]
            frame = _solid_frame(color)
            space_color = color
        elif battle.state == "game_over":
            color = LOSS_COLOR if (battle.elapsed_ms // 360) % 2 == 0 else GAME_OVER_DIM
            frame = _solid_frame(color)
            space_color = color

        self._write_ring(frame)
        self._write_space(space_color)
