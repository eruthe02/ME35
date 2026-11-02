# line_follow.py -- MicroPython, ESP32. Needs veml6040.py and knn.json on the board.
# CENTER = VEML6040 on I2C bus 0 (SDA 21, SCL 22), on the line.
# SIDE   = VEML6040 on SoftI2C (SDA 17, SCL 16), to the RIGHT of center,
#          over floor when on track.
# Line = ANY non-floor color from knn.json. NeoPixels show the color under
# the center sensor. Ctrl+C stops it.
#
# Color effects start ONCE the first time a color is seen, run in the background,
# and never stop the car -- steering keeps running the whole time.
from machine import Pin, PWM, I2C, SoftI2C
from neopixel import NeoPixel
import time, json, math
import veml6040

# ---------------- settings ----------------
BASE = 0.3
KP = 0.25
DEADBAND = 0.10
LOST_TIMEOUT = 2.0
FLOOR_LABEL = "floor"
THIN = 3
INTEGRATION = veml6040.IT_40MS   # IT_80MS matches training; 40 ms is faster

NEOPIXEL_PIN = 15    # change to the pin your strip's data wire is on
NUM_PIXELS = 2       # change to your pixel count
LIGHT_COLORS = {     # label -> (R, G, B); keep values low to limit current
    "floor": (4, 4, 4),
    "black": (40, 40, 40),
    "blue": (0, 0, 60),
    "green": (0, 60, 0),
    "red": (60, 0, 0),
}
OTHER_COLOR = (40, 0, 40)   # any label not listed above

ENABLED_EFFECTS = ("blue", "red")   # add "green" here to turn the green flash back on
CONFIRM_ACTION = 4    # reads in a row a color must hold before its effect starts
FLASH_MS = 250        # length of each flash phase
FLASH_TOTAL_MS = 2500 # how long a flash effect lasts
VOLUME = 0.3          # buzzer volume: 0.0 = silent, 1.0 = loudest
# ------------------------------------------

# motor outputs: start at zero duty
left_pin = Pin(14, Pin.OUT)
right_pin = Pin(13, Pin.OUT)
left_pin.value(0)
right_pin.value(0)
left_pwm = PWM(Pin(27), freq=5000, duty_u16=0)
right_pwm = PWM(Pin(12), freq=5000, duty_u16=0)

pixels = NeoPixel(Pin(NEOPIXEL_PIN), NUM_PIXELS)
buzzer = PWM(Pin(23), freq=1000, duty_u16=0)


def set_light(color):
    pixels.fill(color)
    pixels.write()


def drive(left, right):
    left = max(0.0, min(1.0, left))
    right = max(0.0, min(1.0, right))
    left_pin.value(0)
    right_pin.value(0)
    left_pwm.duty_u16(int(left * 65535))
    right_pwm.duty_u16(int(right * 65535))


def stop():
    left_pwm.duty_u16(0)
    right_pwm.duty_u16(0)
    left_pin.value(0)
    right_pin.value(0)


floor_pts = []
line_pts = []
seen = {}
with open("knn_old.json") as f:
    for x, label in json.load(f):
        k = seen.get(label, 0)
        seen[label] = k + 1
        if k % THIN:
            continue
        if label == FLOOR_LABEL:
            floor_pts.append((x[0], x[1], x[2]))
        else:
            line_pts.append((x[0], x[1], x[2], label))
print("floor pts:", len(floor_pts), " tape pts:", len(line_pts))


def tape_score(sensor):
    """0 = floor, 1 = tape of any trained color. Returns (score, nearest_label)."""
    r, g, b, w = sensor.read_rgbw()
    if w == 0:
        return 1.0, "dark"
    x, y, z = r / w, g / w, b / w
    df = min((x - p[0]) ** 2 + (y - p[1]) ** 2 + (z - p[2]) ** 2 for p in floor_pts)
    dl, label = 1e9, "?"
    for p in line_pts:
        d = (x - p[0]) ** 2 + (y - p[1]) ** 2 + (z - p[2]) ** 2
        if d < dl:
            dl, label = d, p[3]
    df, dl = math.sqrt(df), math.sqrt(dl)
    score = df / (df + dl + 1e-6)
    return score, (FLOOR_LABEL if score < 0.5 else label)


def clamp01(v):
    return max(0.0, min(1.0, v))


# ---------------- color effects (non-blocking) ----------------
LIGHT_BLUE = (60, 140, 255)
DARK_BLUE = (0, 0, 40)
FLASH_COLORS = {                      # label -> (color on, color off)
    "blue": (LIGHT_BLUE, DARK_BLUE),
    "green": ((0, 255, 0), (0, 0, 0)),
}

C4, D4, E4, F4, G4, A4, B4, C5 = 262, 294, 330, 349, 392, 440, 494, 523
SONG = [(C4, 250), (D4, 250), (E4, 250), (F4, 250),
        (G4, 250), (A4, 250), (B4, 250), (C5, 500),
        (B4, 250), (A4, 250), (G4, 250), (F4, 250),
        (E4, 250), (D4, 250), (C4, 500)]
NOTE_GAP_MS = 30
BUZZ_DUTY = int(VOLUME * 32768)

effect = None         # name of the effect currently running (None = nothing)
effect_start = 0      # when it started
song_idx = 0          # current note, for the red song
song_start = 0        # when the current note started


def start_effect(label):
    """Begin an effect. Returns right away; effect_update() runs it."""
    global effect, effect_start, song_idx, song_start
    effect = label
    effect_start = time.ticks_ms()
    if label == "red":
        song_idx = 0
        song_start = effect_start
        buzzer.freq(SONG[0][0])
        buzzer.duty_u16(BUZZ_DUTY)


def end_effect(shown):
    global effect
    effect = None
    buzzer.duty_u16(0)
    set_light(LIGHT_COLORS.get(shown, OTHER_COLOR))   # back to the normal color


def effect_update(shown):
    """Call once per loop. Advances the running effect a small step, never waits."""
    global song_idx, song_start
    if effect is None:
        return
    now = time.ticks_ms()
    if effect in FLASH_COLORS:
        elapsed = time.ticks_diff(now, effect_start)
        if elapsed >= FLASH_TOTAL_MS:
            end_effect(shown)
            return
        on_color, off_color = FLASH_COLORS[effect]
        set_light(on_color if (elapsed // FLASH_MS) % 2 == 0 else off_color)
    elif effect == "red":
        ms = SONG[song_idx][1]
        elapsed = time.ticks_diff(now, song_start)
        if elapsed >= ms:                 # note over: next one
            song_idx += 1
            if song_idx >= len(SONG):
                end_effect(shown)
                return
            song_start = now
            buzzer.freq(SONG[song_idx][0])
            buzzer.duty_u16(BUZZ_DUTY)
        elif elapsed >= ms - NOTE_GAP_MS:
            buzzer.duty_u16(0)            # short gap between notes
# ---------------------------------------------------------------


i2c_center = I2C(0, sda=Pin(21), scl=Pin(22), freq=400000)
i2c_side = SoftI2C(sda=Pin(17), scl=Pin(16), freq=400000)
print("center bus:", i2c_center.scan(), " side bus:", i2c_side.scan())  # both [16]

center = veml6040.VEML6040(i2c_center)
side = veml6040.VEML6040(i2c_side)
for s in (center, side):
    s.set_integration_time(INTEGRATION)

try:
    stop()
    set_light((40, 30, 0))   # amber while waiting to start
    print("Put the car on the line: center sensor on tape, side sensor on floor.")
    print("Starting in 5 s")
    time.sleep(5)

    # ---- startup check + baseline ----
    N = 10
    cs = ss = 0.0
    for _ in range(N):
        a, c_lab = tape_score(center)
        b, s_lab = tape_score(side)
        cs += a
        ss += b
        time.sleep_ms(60)
    c1, s0 = cs / N, ss / N
    print("START CHECK: center score %.2f (%s), side score %.2f (%s)" % (c1, c_lab, s0, s_lab))
    if c1 < 0.5 and s0 > 0.5:
        print("Center looks like FLOOR and side looks like TAPE.")
        print("The two sensors are probably swapped. Swap the I2C bus lines in the code.")
        raise SystemExit
    if c1 < 0.5:
        print("The center sensor doesn't see tape. Check its position and the training data.")
        raise SystemExit
    if s0 > 0.5:
        print("The side sensor sees a tape-like color on the floor. Check its position/height,")
        print("or retrain with the sensor mounted on the car.")
        raise SystemExit
    print("GO")

    lost_since = None
    acted = None        # color whose effect already started on this patch of tape
    shown = None        # label currently shown on the pixels
    pending, pending_n = None, 0
    n = 0
    while True:
        c_raw, c_label = tape_score(center)
        s_raw, s_label = tape_score(side)

        # track the center sensor's color (2 reads in a row to avoid flicker)
        if c_label == pending:
            pending_n += 1
        else:
            pending, pending_n = c_label, 1
        if pending_n >= 2 and pending != shown:
            shown = pending
            if effect is None:
                set_light(LIGHT_COLORS.get(shown, OTHER_COLOR))

        # start an effect the FIRST time a color is confirmed; the car keeps driving
        if (pending in ENABLED_EFFECTS and pending != acted
                and pending_n >= CONFIRM_ACTION and effect is None):
            acted = pending
            start_effect(pending)
        elif pending not in ENABLED_EFFECTS and pending_n >= 2:
            acted = None    # off the colored tape, so it can trigger again later

        effect_update(shown)

        # normalize against the startup baseline
        c = clamp01(c_raw / max(c1, 0.2))
        s = clamp01((s_raw - s0) / max(1.0 - s0, 0.2))

        # pos > 0: tape is to the RIGHT -> steer right
        # pos < 0: center is losing the tape (drifted left) -> steer left
        pos = s if s > DEADBAND else -(1.0 - c)

        if c < 0.1 and s < 0.1:
            if lost_since is None:
                lost_since = time.ticks_ms()
            elif time.ticks_diff(time.ticks_ms(), lost_since) > LOST_TIMEOUT * 1000:
                print("Line lost, stopping")
                break
        else:
            lost_since = None

        drive(BASE + KP * pos, BASE - KP * pos)

        n += 1
        if n % 5 == 0:
            print("c=%.2f(%s) s=%.2f(%s) pos=%+.2f" % (c, c_label, s, s_label, pos))
        time.sleep_ms(10)

finally:
    stop()
    buzzer.duty_u16(0)
    set_light((0, 0, 0))