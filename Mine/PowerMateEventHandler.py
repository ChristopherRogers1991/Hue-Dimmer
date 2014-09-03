# requires python-evdev, python-requests
from evdev import InputDevice, categorize, ecodes
from select import select
from evdev import DeviceInfo
from evdev import UInput
from evdev import InputEvent
from evdev import events


delay = 100 # in milliseconds
long_press_time = 500 # time (in ms) the button must be held to register a long press
time_down = 0 # time at which the button was last pressed down
led_brightness = 100
flash_duration = .2

max_devices = 16 # max number of input devices

button_pushed = 256
knob_turned = 7
positive = 1 # button down, or knob clockwise
negative = -1 # button up, or knob counter-clockwise


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




def main():
    global time_down

    dev = None
    for i in range(0, max_devices):
        dev = InputDevice('/dev/input/event' + str(i))
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
		    time_down = get_time_in_ms()
                else: # button released
	            if get_time_in_ms() - time_down > long_press_time: # long press
		        advance_mode()
                        flash_led(uinput, (mode + 1), led_brightness, flash_duration)
                    else:
                        toggle_all()


if __name__ == "__main__":
    main()
