# Sir Wobbles - hydration butler (ME 35 midterm)
# MicroPython, ESP32 Robo board.
# Arm creeps from the HAPPY end to the DRINK! end of the dial. A KNN gesture
# classifier (LIS3DH on the bottle, data in /training.json) decides what you did:
#   sip   -> celebrate, arm glides back to HAPPY, timer resets
#   shake -> snooze, arm backs off part of the way
import time, math, json
from machine import Pin, I2C, PWM
import neopixel

# ---------------- CONFIG ----------------
SDA_PIN, SCL_PIN = 21, 22
LIS_ADDR = 0x19
NEO_PIN, NEO_COUNT = 15, 2
SERVO_PIN = 19
BUZZER_PIN = 23
FILE = "/training.json"

SWEEP_SECONDS = 60          # time for the arm to cross the dial (60 for demo, 1800 for real use)
LEFT_DEG, RIGHT_DEG = 45, 135   # HAPPY end / DRINK! end (swap if the arm moves the wrong way)
SNOOZE_BACK = 0.35          # a shake moves the arm back by this fraction of the dial
WIN = 20                    # must match the recorder
K = 5
CONFIRM = 2                 # same gesture this many checks in a row before acting
COOLDOWN_MS = 3000          # ignore gestures this long after a sip/shake

# ---------------- hardware ----------------
i2c = I2C(0, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=100000)
i2c.writeto_mem(LIS_ADDR, 0x20, b'\x57')
i2c.writeto_mem(LIS_ADDR, 0x23, b'\x88')
np = neopixel.NeoPixel(Pin(NEO_PIN), NEO_COUNT)
servo = PWM(Pin(SERVO_PIN), freq=50)
buzzer = PWM(Pin(BUZZER_PIN), duty_u16=0)

def read_g():
    d = i2c.readfrom_mem(LIS_ADDR, 0x28 | 0x80, 6)
    out = []
    for i in range(0, 6, 2):
        v = d[i] | (d[i + 1] << 8)
        if v & 0x8000:
            v -= 65536
        out.append((v >> 4) / 1000.0)
    return out

def lights(c):
    for i in range(NEO_COUNT):
        np[i] = c
    np.write()

def tone(freq, ms):
    buzzer.freq(freq)
    buzzer.duty_u16(20000)
    time.sleep_ms(ms)
    buzzer.duty_u16(0)

_arm = [None]
def set_arm(deg):
    if _arm[0] is not None and abs(deg - _arm[0]) < 0.4:
        return                                   # skip tiny moves to avoid jitter
    _arm[0] = deg
    pulse_ms = 0.5 + (deg / 180.0) * 2.0
    servo.duty_u16(int(pulse_ms / 20.0 * 65535))

def glide(to_deg, ms=1000):
    start = _arm[0] if _arm[0] is not None else to_deg
    steps = 25
    for i in range(1, steps + 1):
        set_arm(start + (to_deg - start) * i / steps)
        time.sleep_ms(ms // steps)

# ---------------- sounds ----------------
def fanfare():
    for f in (523, 659, 784, 1047):
        tone(f, 110)

def happy():
    for f in (784, 988, 1175, 1568):
        tone(f, 90)

def sad():
    tone(330, 220); tone(262, 320)

# ---------------- KNN (features identical to the recorder) ----------------
def norm(v):
    return math.sqrt(v[0]**2 + v[1]**2 + v[2]**2) or 1e-6

def features(window, ref):
    tilts, mags = [], []
    for v in window:
        dot = sum(a * b for a, b in zip(v, ref)) / (norm(v) * norm(ref))
        tilts.append(math.degrees(math.acos(max(-1.0, min(1.0, dot)))))
        mags.append(norm(v))
    mean_tilt = sum(tilts) / len(tilts)
    m = sum(mags) / len(mags)
    std = math.sqrt(sum((x - m) ** 2 for x in mags) / len(mags))
    spike = max(abs(x - 1.0) for x in mags)
    return [round(mean_tilt / 90, 3), round(std / 0.5, 3), round(spike / 1.5, 3)]

def knn_predict(feat, train, k=K):
    dists = []
    for f, label in train:
        dists.append((sum((a - b) ** 2 for a, b in zip(feat, f)), label))
    dists.sort(key=lambda x: x[0])
    votes = {}
    for d, label in dists[:k]:
        votes[label] = votes.get(label, 0) + 1
    best = max(votes, key=votes.get)
    return best, votes[best] / k

# ---------------- reactions ----------------
GREEN, YELLOW, RED, BLUE, GOLD = (0, 40, 0), (60, 40, 0), (70, 0, 0), (0, 0, 60), (80, 55, 0)

def greet():
    set_arm(LEFT_DEG)
    lights(GOLD)
    fanfare()
    glide((LEFT_DEG + RIGHT_DEG) / 2, 700)       # a little bow
    glide(LEFT_DEG, 700)

def celebrate():
    for c in ((0, 120, 0), (0, 100, 100), GOLD, (0, 120, 0)):
        lights(c)
        tone(988, 90)
    happy()
    glide(LEFT_DEG, 1000)

def snooze(progress):
    lights(BLUE)
    sad()
    glide(LEFT_DEG + (RIGHT_DEG - LEFT_DEG) * max(0.0, progress - SNOOZE_BACK), 800)

# ---------------- main ----------------
def main():
    with open(FILE) as f:
        saved = json.load(f)
    ref = saved["ref"]
    train = [(d[0], d[1]) for d in saved["data"]]
    print("Loaded %d training samples" % len(train))

    greet()
    t0 = time.ticks_ms()
    window, n = [], 0
    last_label, streak = None, 0
    cooldown_until = time.ticks_ms()
    last_zone, last_beep = 0, 0

    while True:
        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, t0) / 1000
        progress = min(1.0, elapsed / SWEEP_SECONDS)
        set_arm(LEFT_DEG + (RIGHT_DEG - LEFT_DEG) * progress)

        # zone -> lights (0 happy, 1 thirsty, 2 parched, 3 DRINK!)
        zone = 0 if progress < 1/3 else 1 if progress < 2/3 else 2 if progress < 1 else 3
        if zone > last_zone:
            tone(660 + 110 * zone, 120)                 # small chime when the zone changes
        last_zone = zone
        if zone == 0:
            lights(GREEN)
        elif zone == 1:
            lights(YELLOW)
        elif zone == 2:
            lights(RED)
        else:                                           # time to drink: flash and beep
            lights(RED if (now // 250) % 2 == 0 else (0, 0, 0))
            if time.ticks_diff(now, last_beep) > 2000:
                tone(880, 150); tone(880, 150)
                last_beep = now

        # gesture recognition
        window.append(read_g())
        if len(window) > WIN:
            window.pop(0)
        n += 1
        if len(window) == WIN and n % 5 == 0 and time.ticks_diff(now, cooldown_until) >= 0:
            label, conf = knn_predict(features(window, ref), train)
            streak = streak + 1 if label == last_label else 1
            last_label = label
            if streak >= CONFIRM and label in ("sip", "shake"):
                print("gesture:", label, "conf", conf)
                if label == "sip":
                    celebrate()
                    t0 = time.ticks_ms()
                    last_zone = 0
                else:
                    snooze(progress)
                    new_progress = max(0.0, progress - SNOOZE_BACK)
                    t0 = time.ticks_add(time.ticks_ms(), -int(new_progress * SWEEP_SECONDS * 1000))
                    last_zone = 0 if new_progress < 1/3 else 1 if new_progress < 2/3 else 2
                window.clear()
                streak, last_label = 0, None
                cooldown_until = time.ticks_add(time.ticks_ms(), COOLDOWN_MS)
        time.sleep_ms(50)

try:
    main()
finally:
    lights((0, 0, 0))
    buzzer.duty_u16(0)
    set_arm(LEFT_DEG)
    time.sleep_ms(400)
    servo.duty_u16(0)          # stop pulses so the servo doesn't buzz