from machine import Pin, PWM
import time

servo = PWM(Pin(5), freq=50, duty_u16=0)
tilt_servo = PWM(Pin(4), freq=50, duty_u16=0)

# same bucket layout as main.py
BUCKET_ANGLE_MIN = 30
BUCKET_ANGLE_MAX = 120
BUCKET_ANGLES = {
    1: BUCKET_ANGLE_MIN,
    2: BUCKET_ANGLE_MIN + (BUCKET_ANGLE_MAX - BUCKET_ANGLE_MIN) / 3,
    3: BUCKET_ANGLE_MIN + 2 * (BUCKET_ANGLE_MAX - BUCKET_ANGLE_MIN) / 3,
    4: BUCKET_ANGLE_MAX,
}
BUCKET_ORDER = [1, 2, 3, 4]

button_Tilt = Pin(34, Pin.IN, Pin.PULL_UP)
button_Bucket = Pin(35, Pin.IN, Pin.PULL_UP)

def angle_to_duty_ns(angle):
    us = 500 + (angle / 180) * (2500 - 500)
    return int(us * 1000)

def move_to_bucket(bucket):
    angle = BUCKET_ANGLES[bucket]
    servo.duty_ns(angle_to_duty_ns(angle))
    print("Bucket servo -> bucket", bucket, "(", angle, "deg )")

def tilt_90():
    tilt_servo.duty_ns(angle_to_duty_ns(60))
    time.sleep(0.5)
    tilt_servo.duty_ns(angle_to_duty_ns(90))

    
    print("Tilt servo -> 90 deg")
    

tilt_pressed = False
bucket_pressed = False

def tiltButton(p):
    global tilt_pressed
    tilt_pressed = True

def bucketButton(p):
    global bucket_pressed
    bucket_pressed = True

button_Tilt.irq(trigger=Pin.IRQ_RISING, handler=tiltButton)
button_Bucket.irq(trigger=Pin.IRQ_RISING, handler=bucketButton)

bucket_index = 0
move_to_bucket(BUCKET_ORDER[bucket_index])

while True:
    if tilt_pressed:
        tilt_90()
        tilt_pressed = False

    if bucket_pressed:
        bucket_index = (bucket_index + 1) % len(BUCKET_ORDER)
        move_to_bucket(BUCKET_ORDER[bucket_index])
        bucket_pressed = False

    time.sleep(0.1)
