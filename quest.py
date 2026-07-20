COMMANDS = ("UP", "RIGHT", "CONFIRM", "DOWN", "LEFT")

STATE_TITLE = "title"
STATE_CUE = "cue"
STATE_INPUT = "input"
STATE_PLAYER_ATTACK = "player_attack"
STATE_ENEMY_ATTACK = "enemy_attack"
STATE_VICTORY = "victory"
STATE_GAME_OVER = "game_over"

ACTION_DURATION_MS = 520
VICTORY_DURATION_MS = 1450

ENEMIES = (
    ("Moss Slime", "slime", 2, 1),
    ("Cave Goblin", "goblin", 3, 1),
    ("Bone Guard", "skeleton", 4, 1),
    ("Night Wraith", "wraith", 5, 1),
    ("Ash Dragon", "dragon", 7, 2),
)


class QuestBattle:
    def __init__(self, seed=1):
        self.seed = seed & 0x7FFFFFFF or 1
        self.state = STATE_TITLE
        self.level = 1
        self.xp = 0
        self.score = 0
        self.player_max_hp = 5
        self.player_hp = self.player_max_hp
        self.enemy_name = ""
        self.enemy_kind = ""
        self.enemy_max_hp = 0
        self.enemy_hp = 0
        self.enemy_attack = 1
        self.sequence = []
        self.cue_index = 0
        self.input_index = 0
        self.elapsed_ms = 0
        self.message = "PRESS C TO BEGIN"
        self.last_command = None
        self.combo = 0

    @property
    def sequence_length(self):
        return min(9, 3 + (self.level - 1) // 2)

    @property
    def cue_interval_ms(self):
        return max(400, 1500 - (self.level - 1) * 80)

    @property
    def command_window_ms(self):
        return max(700, 3000 - (self.level - 1) * 140)

    @property
    def expected_command(self):
        if self.state != STATE_INPUT or self.input_index >= len(self.sequence):
            return None
        return self.sequence[self.input_index]

    @property
    def shown_command(self):
        if self.state != STATE_CUE or self.cue_index >= len(self.sequence):
            return None
        return self.sequence[self.cue_index]

    @property
    def response_fraction(self):
        if self.state != STATE_INPUT:
            return 0
        remaining = max(0, self.command_window_ms - self.elapsed_ms)
        return remaining / self.command_window_ms

    def _random_command(self):
        self.seed = (1103515245 * self.seed + 12345) & 0x7FFFFFFF
        return COMMANDS[self.seed % len(COMMANDS)]

    def _make_sequence(self):
        result = []
        while len(result) < self.sequence_length:
            command = self._random_command()
            if len(result) >= 2 and result[-1] == result[-2] == command:
                continue
            result.append(command)
        return result

    def _load_enemy(self):
        profile_index = (self.level - 1) % len(ENEMIES)
        cycle = (self.level - 1) // len(ENEMIES)
        name, kind, base_hp, base_attack = ENEMIES[profile_index]
        self.enemy_name = name if cycle == 0 else name + " +" + str(cycle)
        self.enemy_kind = kind
        self.enemy_max_hp = base_hp + cycle * 2
        self.enemy_hp = self.enemy_max_hp
        self.enemy_attack = min(3, base_attack + cycle // 2)

    def start_game(self):
        self.level = 1
        self.xp = 0
        self.score = 0
        self.player_max_hp = 5
        self.player_hp = self.player_max_hp
        self.combo = 0
        self._load_enemy()
        self._begin_round()

    def _begin_round(self):
        self.sequence = self._make_sequence()
        self.cue_index = 0
        self.input_index = 0
        self.elapsed_ms = 0
        self.last_command = None
        self.message = "WATCH"
        self.state = STATE_CUE

    def _fail_round(self, message):
        self.player_hp = max(0, self.player_hp - self.enemy_attack)
        self.combo = 0
        self.elapsed_ms = 0
        self.message = message
        self.state = STATE_ENEMY_ATTACK

    def press(self, command):
        if command not in COMMANDS:
            return False
        if self.state == STATE_TITLE or self.state == STATE_GAME_OVER:
            if command == "CONFIRM":
                self.start_game()
                return True
            return False
        if self.state != STATE_INPUT:
            return False

        self.last_command = command
        self.elapsed_ms = 0
        if command != self.expected_command:
            self._fail_round("WRONG MOVE")
            return True

        self.input_index += 1
        self.score += 5 + self.level
        if self.input_index < len(self.sequence):
            self.message = "COMBO " + str(self.input_index) + "/" + str(len(self.sequence))
            return True

        self.combo += 1
        damage = 1 + (1 if self.combo > 0 and self.combo % 4 == 0 else 0)
        self.enemy_hp = max(0, self.enemy_hp - damage)
        self.elapsed_ms = 0
        self.message = "STRIKE!" if damage == 1 else "CRITICAL!"
        self.state = STATE_PLAYER_ATTACK
        return True

    def update(self, delta_ms):
        delta_ms = max(0, delta_ms)
        self.elapsed_ms += delta_ms

        if self.state == STATE_CUE:
            while self.elapsed_ms >= self.cue_interval_ms:
                self.elapsed_ms -= self.cue_interval_ms
                self.cue_index += 1
                if self.cue_index >= len(self.sequence):
                    self.state = STATE_INPUT
                    self.input_index = 0
                    self.elapsed_ms = 0
                    self.message = "YOUR TURN"
                    break
        elif self.state == STATE_INPUT:
            if self.elapsed_ms >= self.command_window_ms:
                self._fail_round("TOO SLOW")
        elif self.state == STATE_PLAYER_ATTACK:
            if self.elapsed_ms >= ACTION_DURATION_MS:
                if self.enemy_hp <= 0:
                    self.state = STATE_VICTORY
                    self.elapsed_ms = 0
                    reward = self.level * 25
                    self.xp += reward
                    self.score += reward
                    self.message = "+" + str(reward) + " XP"
                else:
                    self._begin_round()
        elif self.state == STATE_ENEMY_ATTACK:
            if self.elapsed_ms >= ACTION_DURATION_MS:
                if self.player_hp <= 0:
                    self.state = STATE_GAME_OVER
                    self.elapsed_ms = 0
                    self.message = "PRESS C TO RISE"
                else:
                    self._begin_round()
        elif self.state == STATE_VICTORY:
            if self.elapsed_ms >= VICTORY_DURATION_MS:
                self.level += 1
                if self.level % 3 == 1:
                    self.player_max_hp += 1
                self.player_hp = min(self.player_max_hp, self.player_hp + 2)
                self._load_enemy()
                self._begin_round()
