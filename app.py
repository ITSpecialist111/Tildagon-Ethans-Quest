import math
import time

import app
from events.input import BUTTON_TYPES, Buttons

try:
    from .lights import QuestLights
    from .quest import (
        ACTION_DURATION_MS,
        COMMANDS,
        STATE_CUE,
        STATE_ENEMY_ATTACK,
        STATE_GAME_OVER,
        STATE_INPUT,
        STATE_PLAYER_ATTACK,
        STATE_TITLE,
        STATE_VICTORY,
        QuestBattle,
    )
except ImportError:
    from lights import QuestLights
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
        QuestBattle,
    )


BUTTON_COMMANDS = (
    (BUTTON_TYPES["UP"], "UP"),
    (BUTTON_TYPES["RIGHT"], "RIGHT"),
    (BUTTON_TYPES["CONFIRM"], "CONFIRM"),
    (BUTTON_TYPES["DOWN"], "DOWN"),
    (BUTTON_TYPES["LEFT"], "LEFT"),
)

COMMAND_LABELS = {
    "UP": "A",
    "RIGHT": "B",
    "CONFIRM": "C",
    "DOWN": "D",
    "LEFT": "E",
}

TAU = 2 * math.pi


def _ticks_ms():
    try:
        return time.ticks_ms()
    except AttributeError:
        return int(time.time() * 1000)


def _line(ctx, x1, y1, x2, y2):
    ctx.begin_path()
    ctx.move_to(x1, y1)
    ctx.line_to(x2, y2)
    ctx.stroke()


def _polygon(ctx, points, fill=True):
    ctx.begin_path()
    ctx.move_to(points[0][0], points[0][1])
    for x, y in points[1:]:
        ctx.line_to(x, y)
    ctx.line_to(points[0][0], points[0][1])
    if fill:
        ctx.fill()
    else:
        ctx.stroke()


class EthansQuestApp(app.App):
    def __init__(self):
        super().__init__()
        self.buttons = Buttons(self)
        self.battle = QuestBattle(seed=_ticks_ms())
        self.clock_ms = 0
        self.lights = QuestLights()
        self.lights.acquire()

    def update(self, delta):
        self.clock_ms += delta

        if self.buttons.pressed(BUTTON_TYPES["CANCEL"]):
            self.buttons.clear()
            self.lights.release()
            self.terminate()
            return True

        for button, command in BUTTON_COMMANDS:
            if self.buttons.pressed(button):
                self.buttons.clear()
                self.battle.press(command)
                break

        self.battle.update(delta)
        self.lights.update(self.battle)
        return True

    def on_resume(self):
        self.lights.acquire()

    def on_pause(self):
        self.lights.release()

    def _draw_bar(self, ctx, x, y, width, value, maximum, color):
        ratio = 0 if maximum <= 0 else max(0, min(1, value / maximum))
        ctx.rgb(0.12, 0.14, 0.17).rectangle(x, y, width, 6).fill()
        if ratio:
            ctx.rgb(*color).rectangle(x + 1, y + 1, (width - 2) * ratio, 4).fill()

    def _draw_stars(self, ctx):
        ctx.rgb(0.16, 0.2, 0.28)
        for x, y in ((-91, -50), (-72, 18), (-30, -72), (5, -57), (34, 8), (75, -66), (92, 22)):
            pulse = 1 if ((self.clock_ms // 350 + x) % 3) else 2
            ctx.rectangle(x, y, pulse, pulse).fill()

    def _action_positions(self):
        player_x = -55
        enemy_x = 55
        if self.battle.state in (STATE_PLAYER_ATTACK, STATE_ENEMY_ATTACK):
            progress = min(1, self.battle.elapsed_ms / ACTION_DURATION_MS)
            lunge = math.sin(progress * math.pi)
            if self.battle.state == STATE_PLAYER_ATTACK:
                player_x += lunge * 25
                enemy_x += max(0, math.sin((progress - 0.35) * math.pi)) * 8
            else:
                enemy_x -= lunge * 24
                player_x -= max(0, math.sin((progress - 0.35) * math.pi)) * 8
        return player_x, enemy_x

    def _draw_player(self, ctx, x, y):
        bob = math.sin(self.clock_ms / 180) * 1.5
        y += bob
        attacking = self.battle.state == STATE_PLAYER_ATTACK
        blocking = (
            self.battle.state == STATE_INPUT
            and self.battle.expected_command == "DOWN"
        )

        ctx.line_width = 3
        ctx.rgb(0.82, 0.9, 0.98)
        ctx.arc(x, y - 27, 7, 0, TAU, True).stroke()
        _line(ctx, x, y - 20, x + (5 if attacking else 0), y + 7)
        _line(ctx, x + 2, y - 13, x - 13, y - 2)
        _line(ctx, x + 3, y - 12, x + 13, y - 4)
        _line(ctx, x + 4, y + 6, x - 7, y + 23)
        _line(ctx, x + 4, y + 6, x + 14, y + 22)

        sword_reach = 27 if attacking else 18
        ctx.rgb(0.92, 0.72, 0.27)
        _line(ctx, x - 13, y - 2, x - 17, y - sword_reach)
        _line(ctx, x - 21, y - sword_reach + 3, x - 13, y - sword_reach - 1)

        shield_x = x + (16 if blocking else 14)
        shield_scale = 1.18 if blocking else 1
        ctx.rgb(0.14, 0.55, 0.78)
        _polygon(
            ctx,
            (
                (shield_x - 8 * shield_scale, y - 13),
                (shield_x + 8 * shield_scale, y - 11),
                (shield_x + 7 * shield_scale, y + 5),
                (shield_x, y + 13 * shield_scale),
                (shield_x - 7 * shield_scale, y + 5),
            ),
        )
        ctx.rgb(0.55, 0.9, 1)
        _line(ctx, shield_x, y - 8, shield_x, y + 7)
        _line(ctx, shield_x - 5, y - 1, shield_x + 5, y - 1)

    def _draw_slime(self, ctx, x, y, phase):
        squash = 2 * math.sin(phase)
        ctx.rgb(0.3, 0.78, 0.35)
        ctx.arc(x, y - 2 + squash, 19, math.pi, TAU, False).fill()
        ctx.rectangle(x - 19, y - 2 + squash, 38, 13 - squash).fill()
        ctx.arc(x - 11, y + 10, 8, 0, math.pi, False).fill()
        ctx.arc(x + 11, y + 10, 8, 0, math.pi, False).fill()
        ctx.rgb(0.04, 0.1, 0.05)
        ctx.arc(x - 7, y - 5 + squash, 2.5, 0, TAU, True).fill()
        ctx.arc(x + 7, y - 5 + squash, 2.5, 0, TAU, True).fill()

    def _draw_goblin(self, ctx, x, y, phase):
        swing = math.sin(phase) * 7
        ctx.rgb(0.42, 0.72, 0.28)
        ctx.arc(x, y - 15, 13, 0, TAU, True).fill()
        _polygon(ctx, ((x - 10, y - 18), (x - 24, y - 24), (x - 13, y - 8)))
        _polygon(ctx, ((x + 10, y - 18), (x + 24, y - 24), (x + 13, y - 8)))
        ctx.rgb(0.35, 0.24, 0.14).rectangle(x - 9, y - 2, 18, 22).fill()
        ctx.line_width = 4
        _line(ctx, x + 9, y + 2, x + 24, y - 11 + swing)
        ctx.rgb(0.55, 0.38, 0.17)
        ctx.arc(x + 25, y - 13 + swing, 6, 0, TAU, True).fill()
        ctx.rgb(0.95, 0.82, 0.2)
        ctx.arc(x - 5, y - 17, 2, 0, TAU, True).fill()
        ctx.arc(x + 5, y - 17, 2, 0, TAU, True).fill()

    def _draw_skeleton(self, ctx, x, y, phase):
        arm = math.sin(phase) * 8
        ctx.line_width = 3
        ctx.rgb(0.9, 0.87, 0.72)
        ctx.arc(x, y - 23, 10, 0, TAU, True).stroke()
        ctx.arc(x - 4, y - 25, 2, 0, TAU, True).fill()
        ctx.arc(x + 4, y - 25, 2, 0, TAU, True).fill()
        _line(ctx, x, y - 13, x, y + 10)
        _line(ctx, x - 9, y - 6, x + 9, y - 6)
        _line(ctx, x - 8, y, x + 8, y)
        _line(ctx, x - 8, y + 6, x + 8, y + 6)
        _line(ctx, x - 5, y + 10, x - 12, y + 24)
        _line(ctx, x + 5, y + 10, x + 12, y + 24)
        _line(ctx, x - 7, y - 7, x - 19, y + arm)
        _line(ctx, x + 7, y - 7, x + 19, y - arm)

    def _draw_wraith(self, ctx, x, y, phase):
        float_y = math.sin(phase) * 4
        y += float_y
        ctx.rgb(0.36, 0.24, 0.68)
        _polygon(
            ctx,
            (
                (x, y - 31),
                (x - 13, y - 27),
                (x - 20, y - 9),
                (x - 15, y + 24),
                (x - 5, y + 17),
                (x + 3, y + 26),
                (x + 11, y + 15),
                (x + 18, y + 23),
                (x + 21, y - 8),
                (x + 13, y - 27),
            ),
        )
        ctx.rgb(0.08, 0.06, 0.16).arc(x, y - 17, 10, 0, TAU, True).fill()
        ctx.rgb(0.4, 0.95, 1)
        ctx.arc(x - 4, y - 18, 2, 0, TAU, True).fill()
        ctx.arc(x + 4, y - 18, 2, 0, TAU, True).fill()

    def _draw_dragon(self, ctx, x, y, phase):
        flap = 7 + math.sin(phase * 1.4) * 6
        ctx.rgb(0.75, 0.19, 0.12)
        _polygon(ctx, ((x - 8, y - 4), (x - 31, y - 20 - flap), (x - 24, y + 7)))
        _polygon(ctx, ((x + 8, y - 4), (x + 30, y - 19 - flap), (x + 23, y + 7)))
        ctx.arc(x, y - 7, 16, 0, TAU, True).fill()
        ctx.rectangle(x - 12, y + 3, 24, 18).fill()
        ctx.rgb(0.93, 0.45, 0.12)
        _polygon(ctx, ((x - 10, y - 19), (x - 6, y - 34), (x - 1, y - 21)))
        _polygon(ctx, ((x + 3, y - 21), (x + 9, y - 35), (x + 12, y - 18)))
        ctx.rgb(1, 0.85, 0.18)
        ctx.arc(x - 6, y - 10, 2, 0, TAU, True).fill()
        ctx.arc(x + 6, y - 10, 2, 0, TAU, True).fill()
        ctx.rgb(0.45, 0.08, 0.04)
        _line(ctx, x - 7, y + 21, x - 12, y + 29)
        _line(ctx, x + 7, y + 21, x + 12, y + 29)

    def _draw_enemy(self, ctx, x, y):
        phase = self.clock_ms / 230
        kind = self.battle.enemy_kind
        if kind == "slime":
            self._draw_slime(ctx, x, y, phase)
        elif kind == "goblin":
            self._draw_goblin(ctx, x, y, phase)
        elif kind == "skeleton":
            self._draw_skeleton(ctx, x, y, phase)
        elif kind == "wraith":
            self._draw_wraith(ctx, x, y, phase)
        else:
            self._draw_dragon(ctx, x, y, phase)

    def _draw_sequence(self, ctx, y):
        sequence = self.battle.sequence
        if not sequence:
            return
        box = 15
        gap = 3
        total = len(sequence) * box + (len(sequence) - 1) * gap
        start_x = -total / 2
        for index, command in enumerate(sequence):
            x = start_x + index * (box + gap)
            visible = self.battle.state == STATE_CUE and index <= self.battle.cue_index
            complete = self.battle.state == STATE_INPUT and index < self.battle.input_index
            active = (
                self.battle.state == STATE_CUE and index == self.battle.cue_index
            ) or (
                self.battle.state == STATE_INPUT and index == self.battle.input_index
            )
            if complete:
                color = (0.24, 0.76, 0.45)
            elif active:
                color = (0.95, 0.72, 0.2)
            else:
                color = (0.18, 0.21, 0.27)
            ctx.rgb(*color).rectangle(x, y, box, box).fill()
            ctx.font_size = 9
            ctx.text_align = ctx.CENTER
            ctx.text_baseline = ctx.MIDDLE
            label = COMMAND_LABELS[command] if visible or complete else "?"
            ctx.rgb(0.04, 0.05, 0.07).move_to(x + box / 2, y + box / 2 + 1).text(label)

    def _draw_title(self, ctx):
        self._draw_stars(ctx)
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        ctx.rgb(0.94, 0.75, 0.25)
        ctx.font_size = 25
        ctx.move_to(0, -73).text("ETHAN'S")
        ctx.font_size = 29
        ctx.move_to(0, -42).text("QUEST")

        self._draw_player(ctx, -34, 16)
        self._draw_dragon(ctx, 45, 16, self.clock_ms / 220)

        ctx.rgb(0.75, 0.82, 0.9)
        ctx.font_size = 10
        ctx.move_to(0, 63).text("WATCH  REPEAT  SURVIVE")
        ctx.rgb(0.95, 0.72, 0.2)
        ctx.font_size = 12
        ctx.move_to(0, 88).text("C START     F EXIT")

    def _draw_game_over(self, ctx):
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        ctx.rgb(0.86, 0.17, 0.12)
        ctx.font_size = 25
        ctx.move_to(0, -50).text("FALLEN")
        ctx.rgb(0.78, 0.84, 0.9)
        ctx.font_size = 13
        ctx.move_to(0, -8).text("LEVEL " + str(self.battle.level))
        ctx.move_to(0, 14).text("SCORE " + str(self.battle.score))
        ctx.rgb(0.95, 0.72, 0.2)
        ctx.font_size = 12
        ctx.move_to(0, 56).text("C RISE AGAIN")
        ctx.rgb(0.55, 0.62, 0.7)
        ctx.font_size = 10
        ctx.move_to(0, 82).text("F EXIT")

    def _draw_battle(self, ctx):
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        ctx.rgb(0.86, 0.9, 0.94)
        ctx.font_size = 11
        ctx.move_to(0, -101).text("LEVEL " + str(self.battle.level))
        ctx.font_size = 9
        ctx.move_to(-65, -87).text("ETHAN")
        ctx.move_to(65, -87).text(self.battle.enemy_name.upper())
        self._draw_bar(
            ctx,
            -99,
            -78,
            77,
            self.battle.player_hp,
            self.battle.player_max_hp,
            (0.19, 0.78, 0.43),
        )
        self._draw_bar(
            ctx,
            22,
            -78,
            77,
            self.battle.enemy_hp,
            self.battle.enemy_max_hp,
            (0.86, 0.25, 0.18),
        )

        player_x, enemy_x = self._action_positions()
        ctx.rgb(0.18, 0.22, 0.28)
        _line(ctx, -96, 34, 96, 34)
        self._draw_player(ctx, player_x, 8)
        self._draw_enemy(ctx, enemy_x, 8)

        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        if self.battle.state == STATE_VICTORY:
            ctx.rgb(0.95, 0.72, 0.2)
            ctx.font_size = 18
            ctx.move_to(0, 52).text("VICTORY")
            ctx.font_size = 11
            ctx.move_to(0, 70).text(self.battle.message)
        elif self.battle.state == STATE_CUE:
            ctx.rgb(0.95, 0.72, 0.2)
            ctx.font_size = 16
            label = COMMAND_LABELS.get(self.battle.shown_command, "")
            ctx.move_to(0, 54).text("WATCH  " + label)
            self._draw_sequence(ctx, 70)
        elif self.battle.state == STATE_INPUT:
            ctx.rgb(0.8, 0.88, 0.96)
            ctx.font_size = 12
            ctx.move_to(0, 51).text(self.battle.message)
            self._draw_sequence(ctx, 65)
            ctx.rgb(0.12, 0.14, 0.17).rectangle(-70, 86, 140, 5).fill()
            ctx.rgb(0.95, 0.58, 0.15).rectangle(
                -69, 87, 138 * self.battle.response_fraction, 3
            ).fill()
        else:
            color = (0.95, 0.72, 0.2) if self.battle.state == STATE_PLAYER_ATTACK else (0.9, 0.28, 0.2)
            ctx.rgb(*color)
            ctx.font_size = 17
            ctx.move_to(0, 58).text(self.battle.message)

        ctx.text_align = ctx.CENTER
        ctx.rgb(0.48, 0.56, 0.65)
        ctx.font_size = 9
        ctx.move_to(0, 103).text("XP " + str(self.battle.xp) + "  SCORE " + str(self.battle.score) + "  F EXIT")

    def draw(self, ctx):
        ctx.save()
        ctx.rgb(0.025, 0.035, 0.055).rectangle(-120, -120, 240, 240).fill()
        self._draw_stars(ctx)
        if self.battle.state == STATE_TITLE:
            self._draw_title(ctx)
        elif self.battle.state == STATE_GAME_OVER:
            self._draw_game_over(ctx)
        else:
            self._draw_battle(ctx)
        ctx.restore()


__app_export__ = EthansQuestApp