# requires python-evdev, python-requests
from evdev import InputDevice, categorize, ecodes, DeviceInfo, UInput, InputEvent, events
from select import select
from enum import Enum
import Queue
import os
import time
import threading

class ConsolidatedEventCodes(Enum):
    SINGLE_CLICK = 0
    DOUBLE_CLICK = SINGLE_CLICK + 1
    LONG_CLICK = DOUBLE_CLICK + 1
    RIGHT_TURN = LONG_CLICK + 1
    LEFT_TURN = RIGHT_TURN + 1

DEV_DIR = '/dev/input/'


# TODO make these instance variables, and make accessors and mutators
delay = 100 # in milliseconds
long_press_time = .5 # time (in s) the button must be held to register a long press
time_down = 0 # time at which the button was last pressed down
led_brightness = 100
flash_duration = .2

max_devices = 16 # max number of input devices

button_pushed = 256
knob_turned = 7
positive = 1 # button down, or knob clockwise
negative = -1 # button up, or knob counter-clockwise


class PowerMateEventHandler:

    def __init__(self, brightness=255):
        dev = self.find_device()

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
        return int(round(time.time() * 1000))


    def __raw(self):
        while True:

            if not self.__event_capture_running:
                return

            # Wait until the device is ready for reading
            r,w,x = select([self.__dev], [], [])
            
            # TODO need to find a non-blocking way to determine when
            # the device is ready to be read
            # possible workaround is to just catch the error
            # through when it's not ready, but that seems
            # crappy. Blocking, however, prevents being able to
            # end the thread and join it with main - which
            # for some reason seems desireable - might actually
            # be irrelevant. I guess I have a lot to ponder.

            if not r == None:
                event = self.__dev.read_one()
                if not event == None:
                    self.__raw_queue.put(event)
            time.sleep(.01)


    def __consolidated(self):

        time_of_last_turn = 0

        while True:
            
            if not self.__event_capture_running:
                return

            # Allows the thread to be joinable (i.e. stoppable) without
            # waiting for another event (without the timeout, get would
            # block until the next event)
            try:
                event = self.__raw_queue.get(timeout=.01)
            except Queue.Empty:
                continue
            

            if event.code == knob_turned and self.__get_time_in_ms() - delay > time_of_last_turn:
                if event.value > 0:
                    self.__consolidated_queue.put(ConsolidatedEventCodes.RIGHT_TURN)
                else:
                    self.__consolidated_queue.put(ConsolidatedEventCodes.LEFT_TURN)
                time_of_last_turn = self.__get_time_in_ms()

            elif event.code == button_pushed:
                if event.value == positive: # button pressed
                    time_down = self.__get_time_in_ms()
                    self.__button_press(time_down)


    def __button_press(self, time_pressed):
        x = long_press_time
        check_time = time_pressed

        try:
            event = self.__raw_queue.get(timeout=x)
        except Queue.Empty:
            event = None
        x = x - ((self.__get_time_in_ms() - check_time) / float(1000))

        while ((event == None) or (event.code != button_pushed)) and (x > 0):
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
            while event.code != button_pushed:
                event = self.__raw_queue.get()

        else:
            # TODO handle double
            self.__consolidated_queue.put(ConsolidatedEventCodes.SINGLE_CLICK)
        return



    def find_device(self):
        '''
        Finds and returns the device in DEV_DIR

        RETURN dev = An evdev.InputDevice. None if the device
        is not found.
        '''
        dev = None
        for dev in os.listdir(DEV_DIR):
            if dev.find("event") == 0:
                dev = InputDevice(DEV_DIR + dev)
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
        

    def flash_led(self, num_flashes, brightness=led_brightness, duration=flash_duration):
        '''
        Convenience function to flash the led in the base.
        PARAM num_flashes = number times to flash
        PARAM brightness = the brightness of the flashes (range defined by set_led_brightness)
        '''
        for i in range(num_flashes):
            self.uinput.write(ecodes.EV_MSC, ecodes.MSC_PULSELED, brightness)
            self.uinput.syn()
            time.sleep(duration)
            self.uinput.write(ecodes.EV_MSC, ecodes.MSC_PULSELED, 0)
            self.uinput.syn()
            time.sleep(.2)



    def start(self):
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
        if self.__event_capture_running:
            self.__event_capture_running = False
            self.__consolidated_thread.join()
            print("c joined")
            self.__raw_thread.join()
            print("raw joined")


    def get_next(self, block=True, timeout=None):
        if not self.__event_capture_running:
            raise Exception("CaptureNotStarted")
        try:
            return self.__consolidated_queue.get(block, timeout)
        except Queue.Empty:
            return None
