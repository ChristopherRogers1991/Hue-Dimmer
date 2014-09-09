# requires python-evdev, python-requests
from evdev import InputDevice, categorize, ecodes, DeviceInfo, UInput, InputEvent, events
from select import select
from enum import Enum
import Queue


class ConsolidatedEventCodes(Enum):
    SINGLE_CLICK = 0
    DOUBLE_CLICK = SINGLE_CLICK + 1
    LONG_CLICK = DOUBLE_CLICK + 1
    RIGHT_TURN = LONG_CLICK + 1
    LEFT_TURN = RIGHT_TURN + 1
    


class PowerMateEventHandler(object):

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


    def __init__(self):
        self.__raw_queue = Queue.Queue()
        self.__consolidated_queue = Queue.Queue()
        self.__dev = __find_device()

        self.__button_up = True
        self.__was_long = False
    
    def get_time_in_ms(self):
        return int(round(time.time() * 1000))
    
    
    def flash_led(self, uinput, num_flashes, brightness, duration):
        for i in range(num_flashes):
            uinput.write(ecodes.EV_MSC, ecodes.MSC_PULSELED, brightness)
            uinput.syn()
            time.sleep(duration)
            uinput.write(ecodes.EV_MSC, ecodes.MSC_PULSELED, 0)
            uinput.syn()
            time.sleep(.2)
    
    
    def __find_device(self):
        '''
        Finds and returns the device in /dev/input/event
    
        RETURN dev = An evdev.InputDevice
        '''
        dev = None
        for i in range(0, max_devices):
            dev = InputDevice('/dev/input/event' + str(i))
            if dev.name.find('Griffin PowerMate') >= 0:
                break;
        return dev
    
    
    def turn_off_led(self):
        '''
        Turns off the led in the base.
        '''
        uinput = UInput(events={ecodes.EV_MSC:[ecodes.MSC_PULSELED]})
        uinput.device = dev
        uinput.fd = dev.fd
        uinput.write(ecodes.EV_MSC, ecodes.MSC_PULSELED, 0)
        uinput.syn()
    
    
    
    def __raw(self):
    
        while True:
            r,w,x = select([self.dev], [], [])
    
            for event in self.dev.read():
                self.__raw_queue.put(event)


    def __button_down(self, time_pressed):
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
    
        last_checked_at = get_time_in_ms()
    
        while not button_up:
            if last_checked_at - time_pressed > long_press_time:
                self.was_long = True
                flash_led(uinput, 1, led_brightness, flash_duration)
                return
            time.sleep(.01)
            last_checked_at = get_time_in_ms()
        return


    
    
    def __consolidated(self):
    
        time_of_last_turn = 0

        while True:
            curr = self.__raw_queue.get()

            if event.code == knob_turned and get_time_in_ms() - delay > time_of_last_turn:
                if event.value > 0:
                    self.__consolidated_queue.put(RIGHT_TURN)
                else:
                    self.__consolidated_queue.put(LEFT_TURN)
                time_of_last_turn = get_time_in_ms()

            elif event.code == button_pushed:
                if event.value == positive: # button pressed
                    self.button_up = False
                    time_down = get_time_in_ms()
                    t = threading.Thread(target = button_down, args = (time_down))
                    t.daemon = True
                    t.start()

                else: # button released
                    button_up = True
                    if was_long: # long press
                        self.__consolidated_queue.put(LONG_CLICK)
                        was_long = False
                    else:
                        self.__consolidated_queue.put(SINGLE_CLICK)


    def start(self):
        raw = threading.Thread(target = __raw)
        raw.daemon = True
        raw.start()

        cons = threading.Thread(target = __consolidated)
        cons.daemon = True
        con.start()


    def get_next(self):
        return self.__consolidated_queue.get()


