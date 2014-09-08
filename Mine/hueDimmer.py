#!/usr/bin/env python

# requires python-evdev, python-requests
import threading
from evdev import InputDevice, categorize, ecodes, DeviceInfo, UInput, InputEvent, events
from select import select
import os, requests, json, time


DEV_DIR = '/dev/input/'
max_brightness = 255
min_brightness = 0
brightness_step = 10
max_colortemp = 500 # equivalent of 2000K
min_colortemp = 153 # equivalent of 6500K
colortemp_step = -20
delay = 100 # in milliseconds
long_press_time = 500 # time (in ms) the button must be held to register a long press
time_down = 0 # time at which the button was last pressed down
led_brightness = 100
flash_duration = .2

# mode constants
MODE_BRIGHTNESS = 0
MODE_COLORTEMP = 1
NUM_MODES = 2


max_devices = 16 # max number of input devices

button_pushed = 256
knob_turned = 7
positive = 1 # button down, or knob clockwise
negative = -1 # button up, or knob counter-clockwise


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


def flash_led(uinput, num_flashes, brightness, duration):
    for i in range(num_flashes):
        uinput.write(ecodes.EV_MSC, ecodes.MSC_PULSELED, brightness)
        uinput.syn()
        time.sleep(duration)
        uinput.write(ecodes.EV_MSC, ecodes.MSC_PULSELED, 0)
        uinput.syn()
        time.sleep(.2)
        

was_long = False
button_up = True # This is used to track the state of the button between threads

def button_down(uinput, time_pressed):
    '''
    This function is intended to be run on its own thread,
    and is used to determine whether a button press was a normal/short
    press, or a long press.

    Once it registers a long press, it should flash the led on the device.

    PARAM time_pressed = int representing when the button was pressed
        Note that this is passed in rather than calculated here to
        account for any overhead spinning off the new thread.

    PARAM uinput = the PowerMat device

    Side Effects:
        LED is flashed
        was_long is set to True

   '''
    global was_long
    global button_up

    last_checked_at = get_time_in_ms()

    while not button_up:
        if last_checked_at - time_pressed > long_press_time:
            was_long = True
            flash_led(uinput, 1, led_brightness, flash_duration)
            return
        time.sleep(.01)
        last_checked_at = get_time_in_ms()
    return



def handle_turn(event):
    g = requests.get(url)
    successful = False

    if g.status_code == success:

        p = None

        if mode == MODE_BRIGHTNESS:
            bri = json.loads(g.content)['action']['bri'] + (brightness_step * event.value) # event.value is always +1 or -1

            if bri > max_brightness:
                bri = max_brightness
            elif bri < 0:
                bri = 0

            p = requests.put(url + "action", data=json.dumps({"bri": bri}))

        elif mode == MODE_COLORTEMP:
            ct = json.loads(g.content)['action']['ct'] + (colortemp_step * event.value) # event.value is always +1 or -1

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
    global was_long
    global button_up
    global time_down

    dev = None
    for dev in os.listdir(DEV_DIR):
        if dev.find("event") == 0:
            dev = InputDevice(DEV_DIR + dev)
            print dev
            if dev.name.find('Griffin PowerMate') >= 0:
                break;

    print dev
    uinput = UInput(events={ecodes.EV_MSC:[ecodes.MSC_PULSELED]})
    uinput.device = dev
    uinput.fd = dev.fd
    uinput.write(ecodes.EV_MSC, ecodes.MSC_PULSELED, 0)
    uinput.syn()

    time_of_last_turn = int(round(time.time() * 1000)) # this is used to create a delay, so the lights aren't spammed with dim events

    while True:
        r,w,x = select([dev], [], [])

        for event in dev.read():

            # if the knob has been turned and our delay period has passed
            if event.code == knob_turned and get_time_in_ms() - delay > time_of_last_turn:
                if handle_turn(event):
                    time_of_last_turn = int(round(time.time() * 1000))

            # if the button has been activated                
            elif event.code == button_pushed:
                if event.value == positive: # button pressed
                    button_up = False
                    time_down = get_time_in_ms()
                    t = threading.Thread(target = button_down, args = (uinput, time_down))
                    t.daemon = True
                    t.start()

                else: # button released
                    button_up = True
                    if was_long: # long press
                        advance_mode()
                        was_long = False
                    else:
                        toggle_all()


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
