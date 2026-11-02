# test.py -- MicroPython, ESP32. Live KNN color test (VEML6040 + knn.json).
from machine import Pin, I2C
import time, json, math
import veml6040

K = 3
MAX_DIST = None     # e.g. 0.1 to print "unknown" when far from every sample
PERIOD_MS = 100

i2c = I2C(0, sda=Pin(21), scl=Pin(22), freq=400000)
print("I2C devices:", i2c.scan())            # should show [16]
sensor = veml6040.VEML6040(i2c)
sensor.set_integration_time(veml6040.IT_80MS)   # same as train.py

with open("knn.json") as f:
    DATA = [(x[0], x[1], x[2], label) for x, label in json.load(f)]
print("Loaded %d samples: %s" % (len(DATA), sorted(set(d[3] for d in DATA))))


def classify(nr, ng, nb):
    dists = sorted(
        [math.sqrt((nr - d[0]) ** 2 + (ng - d[1]) ** 2 + (nb - d[2]) ** 2), d[3]]
        for d in DATA
    )
    nearest = dists[:K]
    if MAX_DIST is not None and nearest[0][0] > MAX_DIST:
        return "unknown", nearest[0][0]
    classes = [c[1] for c in nearest]
    return max(set(classes), key=classes.count), nearest[0][0]


while True:
    r, g, b, w = sensor.read_rgbw()
    if w == 0:
        print("no light on white channel")
    else:
        nr, ng, nb = r / w, g / w, b / w
        label, d = classify(nr, ng, nb)
        print("%-8s rgb/w=(%.3f, %.3f, %.3f) nearest=%.3f" % (label, nr, ng, nb, d))
    time.sleep_ms(PERIOD_MS)