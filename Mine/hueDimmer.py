#!/usr/bin/env python

# requires python-evdev, python-requests
#from evdev import InputDevice, categorize, ecodes, DeviceInfo, UInput, InputEvent, events
#from select import select
#import threading
import os, requests, json, time
from PowerMateEventHandler import PowerMateEventHandler, ConsolidatedEventCode

max_brightness = 255
min_brightness = 0
brightness_step = 10
max_colortemp = 500 # equivalent of 2000K
min_colortemp = 153 # equivalent of 6500K
colortemp_step = -20

# mode constants
MODE_BRIGHTNESS = 0
MODE_COLORTEMP = 1
NUM_MODES = 2


mode = MODE_BRIGHTNESS

success = 200 # http response code

# The following values must be set according to your setup
ip = '192.168.1.6'

# you must have created a user named newdevolper, as per the instructions at http://developers.meethue.com/gettingstarted.html
url = 'http://' + ip + '/api/newdeveloper/groups/0/'

def get_time_in_ms():
    return int(round(time.time() * 1000))


def advance_mode():
    global mode
    mode = (mode + 1) % NUM_MODES


def handle_turn(event):
    g = requests.get(url)
    successful = False

    direction = -1
    if event == ConsolidatedEventCode.RIGHT_TURN:
        direction = 1

    if g.status_code == success:

        p = None

        if mode == MODE_BRIGHTNESS:
            bri = json.loads(g.content)['action']['bri'] + (brightness_step * direction) 

            if bri > max_brightness:
                bri = max_brightness
            elif bri < 0:
                bri = 0

            p = requests.put(url + "action", data=json.dumps({"bri": bri}))

        elif mode == MODE_COLORTEMP:
            ct = json.loads(g.content)['action']['ct'] + (colortemp_step * direction) 

            if ct > max_colortemp:
                ct = max_colortemp
            elif ct < min_colortemp:
                ct = min_colortemp 

            p = requests.put(url + "action", data=json.dumps({"ct": ct}))
        successful = (p.status_code == success)

    return successful


def toggle_all():
    g = requests.get(url)
    if g.status_code == success:
        on = json.loads(g.content)['action']['on']
        
        if on == False:
            hour = time.localtime().tm_hour
            ct = max_colortemp
            bri = min_brightness
            if hour >= 5 and hour <= 11:
                ct = min_colortemp
                bri = max_brightness
            elif hour >= 12 and hour <= 17:
                ct = 250
                bri = max_brightness
            elif hour >= 18 and hour <= 20:
                ct = 400
                bri = 150
            elif hour >= 21 and hour <= 23:
                ct = max_colortemp
                bri = 50
            #print "bri = " + str(bri) + " ct = " + str(ct) + " hour = " + str(hour)
            p = requests.put(url + "action", data=json.dumps({"on":True, "bri":bri, "ct":ct, "transitiontime":2}))
        else:
            p = requests.put(url + "action", data=json.dumps({"on":False, "transitiontime":2}))


def main():
    eh = PowerMateEventHandler(brightness=0, turn_delay=100)
    eh.start()

    while True:
        try:
            event = eh.get_next(timeout=.01)
            if event == ConsolidatedEventCode.RIGHT_TURN or event == ConsolidatedEventCode.LEFT_TURN:
                handle_turn(event)
            elif event == ConsolidatedEventCode.SINGLE_CLICK:
                toggle_all()
            elif event == ConsolidatedEventCode.LONG_CLICK:
                eh.flash_led(num_flashes=2)
                advance_mode()
        except KeyboardInterrupt:
            exit(0)


if __name__ == "__main__":
    # Use a while loop and try/except as a super hack to save time - eventually daemonize
    while True:
        try:
            main()
        except KeyboardInterrupt:
            exit(0)
        except:
            time.sleep(1)
            continue
