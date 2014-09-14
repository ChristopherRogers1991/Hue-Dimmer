# requires python-evdev, python-requests
from evdev import InputDevice, categorize, ecodes, DeviceInfo, UInput, InputEvent, events
import select
from enum import Enum
import Queue
import os
import time
import threading


# Constants
BUTTON_PUSHED = 256
KNOB_TURNED = 7
POSITIVE = 1 # button down, or knob clockwise
NEGATIVE = -1 # button up, or knob counter-clockwise


# TODO make these instance variables, and make accessors and mutators
delay = 100 # time in milliseconds between consolidated turn events
long_press_time = .5 # time (in s) the button must be held to register a long press
time_down = 0 # time at which the button was last pressed down
led_brightness = 100
flash_duration = .2


class ConsolidatedEventCodes(Enum):
    '''
    SINGLE_CLICK = 0
    DOUBLE_CLICK = SINGLE_CLICK + 1
    LONG_CLICK = DOUBLE_CLICK + 1
    RIGHT_TURN = LONG_CLICK + 1
    LEFT_TURN = RIGHT_TURN + 1
    '''
    SINGLE_CLICK = 0
    DOUBLE_CLICK = SINGLE_CLICK + 1
    LONG_CLICK = DOUBLE_CLICK + 1
    RIGHT_TURN = LONG_CLICK + 1
    LEFT_TURN = RIGHT_TURN + 1


class PowerMateEventHandler:

    def __init__(self, brightness=255, dev_dir='/dev/input/'):
        '''
        Find the PowerMateDevice, and get set up to
        start reading from it.

        PARAM brightness = the inital brightness of the led in the base
        PARAM dev_dir = the directory in which to look for the device
        '''
        dev = self.find_device(dev_dir)

        if dev is None:
            raise Exception("DeviceNotFound")
        else:
            self.__dev = dev

        self.__raw_queue = Queue.Queue()
        self.__raw_thread = None

        self.__consolidated_queue = Queue.Queue()
        self.__consolidated_thread = None

        uinput = UInput(events={ecodes.EV_MSC:[ecodes.MSC_PULSELED]})
        uinput.device = self.__dev
        uinput.fd = self.__dev.fd
        self.uinput = uinput

        self.set_led_brightness(brightness)
        
        self.__event_capture_running = False



    def __get_time_in_ms(self):
        '''
        return the currnt time in ms
        '''

        return int(round(time.time() * 1000))


    def __raw(self):
        '''
        Begin raw capture of events, and add them to
        the raw queue.
        '''

        while True:

            if not self.__event_capture_running:
                return

            # Check if the device is readable
            r,w,x = select.select([self.__dev], [], [], .01)
            if r:
                event = self.__dev.read_one()
                if not event == None:
                    self.__raw_queue.put(event)
            time.sleep(.01)


    def __consolidated(self):
        '''
        Begin consolidating events from the raw queue,
        and placing them on the consolidated queue
        '''

        time_of_last_turn = 0

        while True:
            
            if not self.__event_capture_running:
                return

            # Allows the thread to be joinable (i.e. stoppable) without
            # waiting for another event (without the timeout, get would
            # block until the next event)
            try:
                print("here")
                event = self.__raw_queue.get(timeout=.01)
            except Queue.Empty:
                continue
            

            if event.code == KNOB_TURNED and self.__get_time_in_ms() - delay > time_of_last_turn:
                if event.value > 0:
                    self.__consolidated_queue.put(ConsolidatedEventCodes.RIGHT_TURN)
                else:
                    self.__consolidated_queue.put(ConsolidatedEventCodes.LEFT_TURN)
                time_of_last_turn = self.__get_time_in_ms()

            elif event.code == BUTTON_PUSHED:
                if event.value == POSITIVE: # button pressed
                    self.__button_press(self.__get_time_in_ms())


    def __button_press(self, time_pressed):
        '''
        Helper function for __consolidated.

        Handle a button press event (i.e. consolidtate raw events into
        a single, double, or long click event)

        PARAM time_pressed = the time the button was first pressed.
        '''

        x = long_press_time
        check_time = time_pressed

        try:
            event = self.__raw_queue.get(timeout=x)
        except Queue.Empty:
            event = None
        x = x - ((self.__get_time_in_ms() - check_time) / float(1000))

        while ((event == None) or (event.code != BUTTON_PUSHED)) and (x > 0):
            check_time = self.__get_time_in_ms()
            try:
                event = self.__raw_queue.get(timeout=x)
            except Queue.Empty:
                event = None
            x = x - ((self.__get_time_in_ms() - check_time) / float(1000))

        if x <= 0: # was long
            self.__consolidated_queue.put(ConsolidatedEventCodes.LONG_CLICK)
            # pull events until button is release (disallow turns while button is down)
            event = self.__raw_queue.get()
            while event.code != BUTTON_PUSHED:
                event = self.__raw_queue.get()

        else:
            # TODO handle double
            self.__consolidated_queue.put(ConsolidatedEventCodes.SINGLE_CLICK)
        return



    def find_device(self, dev_dir):
        '''
        Finds and returns the device in DEV_DIR

        RETURN dev = An evdev.InputDevice. None if the device
        is not found.
        '''
        dev = None
        for dev in os.listdir(dev_dir):
            if dev.find("event") == 0:
                dev = InputDevice(dev_dir + dev)
                if dev.name.find('Griffin PowerMate') >= 0:
                    break
        return dev


    def set_led_brightness(self, brightness):
        '''
        Sets the led in the base to the specified brightness.
        The valid range is 0-255, where 0 is off. Anything
        less than 0 will be treated as zero, anything greater
        than 255 will be treated as 255.
        '''

        if brightness < 0:
            brightness = 0
        elif brightness > 255:
            brightness = 255

        self.uinput.write(ecodes.EV_MSC, ecodes.MSC_PULSELED, brightness)
        self.uinput.syn()
        self.__led_brightness = brightness
        

    def flash_led(self, num_flashes=2, brightness=led_brightness, duration=flash_duration, sleep=.2):
        '''
        Convenience function to flash the led in the base.
        PARAM num_flashes = number times to flash
        PARAM brightness = the brightness of the flashes (range defined by set_led_brightness)
        '''

        reset = self.__led_brightness

        for i in range(num_flashes):
            self.set_led_brightness(brightness)
            time.sleep(duration)
            self.set_led_brightness(0)
            time.sleep(sleep)

        self.__led_brightness = reset



    def start(self):
        '''
        Begin capturing/queueing events. Once this has been run,
        get_next() can be used to start pulling events off the
        queue.
        '''

        self.__event_capture_running = True

        raw = threading.Thread(target = self.__raw)
        raw.daemon = True
        raw.start()

        cons = threading.Thread(target = self.__consolidated)
        cons.daemon = True
        cons.start()

        self.__raw_thread = raw
        self.__consolidated_thread = cons


    def stop(self):
        '''
        Stop the capture/queuing of events.
        '''

        if self.__event_capture_running:
            self.__event_capture_running = False
            self.__consolidated_thread.join()
            print("c joined")
            self.__raw_thread.join()
            print("raw joined")


    def get_next(self, block=True, timeout=None):
        '''
        Pull the next consolidated event off the queue, and return it.

        PARAM block
        PARAM timeout

        block and timeout are passed directly to queue.get().
        If block is TRUE, the thread will block for timeout seconds for
        the next event. If timeout is None, it will wait indefinitely.
        If block is False, an event will be grabbed only if one is ready
        immediately.

        RETURN a ConsolidatedEventCode; None if there is not an event ready
        and block is False, or timeout is reached.
        '''

        if not self.__event_capture_running:
            raise Exception("CaptureNotStarted")
        try:
            return self.__consolidated_queue.get(block, timeout)
        except Queue.Empty:
            return None
