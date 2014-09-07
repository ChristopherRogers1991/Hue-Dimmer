import threading
from evdev import InputDevice, categorize, ecodes, DeviceInfo, UInput, InputEvent, events
from select import select
import os, requests, json, time


DEV_DIR = '/dev/input/'

button_up = True # This is used to track the state of the button between threads
time_down = 0 # Time at which the button was last pushed down


def get_time_in_ms():
    return int(round(time.time() * 1000))


def flash_led(uinput, num_flashes, brightness, duration):
    for i in range(num_flashes):
        uinput.write(ecodes.EV_MSC, ecodes.MSC_PULSELED, brightness)
        uinput.syn()
        time.sleep(duration)
        uinput.write(ecodes.EV_MSC, ecodes.MSC_PULSELED, 0)
        uinput.syn()
        time.sleep(.2)


# For button_down
long_press_time = 500 # time (in ms) the button must be held to register a long press
was_long = False

# These constants define what can be returned by button_down
# (should be enums - python 2 enums?)

SHORT_PRESS = 0
LONG_PRESS = SHORT_PRESS + 1

def button_down(uinput, time_pressed):
    '''
    This function is intended to be run on its own thread,
    and is used to determine whether a button press was a normal/short
    press, or a long press.

    Once it registers a long press, it should flash the led on the device.

    PARAM time_pressed = int representing when the button was pressed
        Note that this is passed in rather than calculated here to
        account for any overhead spinning off the new thread.

    RETURN an int representing the type of press. These are defined as
    follows:
        SHORT_PRESS = 0
        LONG_PRESS = SHORT_PRESS + 1
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



button_pushed = 256
knob_turned = 7
positive = 1 # button down, or knob clockwise
negative = -1 # button up, or knob counter-clockwise


flash_duration = .2
led_brightness = 100


def main():
    global was_long
    global button_up
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


    while True:
        r,w,x = select([dev], [], [])

        for event in dev.read():

            # if the knob has been turned and our delay period has passed
            if event.code == knob_turned: #and get_time_in_ms() - delay > time_of_last_turn:
                print event

            # if the button has been activated                
            elif event.code == button_pushed:
                if event.value == positive: # button pressed
                    button_up = False
                    time_down = get_time_in_ms()
                    t = threading.Thread(target = button_down, args = (uinput, time_down))
                    t.daemon = True
                    t.start()
                    print event
                else: # button released
                    button_up = True
                    if was_long: # long press
                        was_long = False
                    else:
                        print event

if __name__ == "__main__":
    main()
