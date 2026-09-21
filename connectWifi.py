#importing the libraries
import network
import urequests
import time
import secrets
 
#setting up SSID and password 
 
SSID = secrets.SSID
PASSWORD = secrets.PASSWORD


#function definition 
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(SSID, PASSWORD)
        while not wlan.isconnected():
            time.sleep(0.5)
    print("Connected! IP address:", wlan.ifconfig()[0])
    return wlan
 
 #function call
connect_wifi()
 
 #ON REPL you can type wlan.isconnected() hit ENTER. it will return True
 