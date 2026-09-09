import neopixel #importing the library
from machine import Pin # another way of importing a library
import random
import time
lights = neopixel.NeoPixel(Pin(15),2) # 0 is the Pin for neopixel and 4 is the number of lights
lights[0] = (20,0,20) # set the color of 0th light to purple
lights[1] = (0,25,25)
for i in range(0, 255):
    ##lightnum = random.randint(0,1)
    #r = random.randint(0,255)
    #g = random.randint(0,255)
    #b = random.randint(0,255)
    lights[0] = (i,i,i)
    lights[1] = (i,i,i)
    time.sleep_ms(250)
    lights.write()

