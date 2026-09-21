from machine import Pin
from time import ticks_ms, ticks_diff
import time
import neopixel

btn = Pin(34, Pin.IN, Pin.PULL_UP) 
DEBOUNCE_MS = 20
lights = neopixel.NeoPixel(Pin(15),2) # 0 is the Pin for neopixel and 4 is the number of lights


while True:
    if btn.value() == 0:
        time.sleep_ms(DEBOUNCE_MS)
        if btn.value() == 0:
            while btn.value() == 0:
                lights[0] = (100,100,100)
                lights[1] = (100,100,100)
                lights.write()
    lights[0] = (0,0,0)
    lights[1] = (0,0,0)
    lights.write()
            

            