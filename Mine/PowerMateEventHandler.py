# requires python-evdev, python-requests
from evdev import InputDevice, ecodes, UInput
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
time_down = 0 # time at which the button was last pressed down
led_brightness = 100
flash_duration = .15


class ConsolidatedEventCode(Enum):
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

    def __init__(self, brightness=255, read_delay=None, turn_delay=0, long_press_time=.5, double_click_time=.3, dev_dir='/dev/input/'):
        '''
        Find the PowerMateDevice, and get set up to
        start reading from it.

        PARAM brightness = The inital brightness of the led in the base.
        PARAM read_delay = Timeout when waiting for the device to be readable.
            Having a time out allows the threads to be joinable without waiting
            for another event. None (default) means to wait indefinitely for the device
            to be readable.
        PARAM turn_delay = Time in ms between consolidated turns.
        PARAM long_press_time = time (in s) the button must be held to register a long press
        PARAM double_click_time = time (in s) the button must be pressed again after a single press to register as a double
        PARAM dev_dir = The directory in which to look for the device.
        '''

        dev = find_device(dev_dir)

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
        self.__turn_delay = turn_delay
        self.__read_delay = read_delay

        self.__long_press_time = long_press_time
        self.__double_click_time = double_click_time


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

            try:
                # Check if the device is readable
                r,w,x = select.select([self.__dev], [], [], self.__read_delay)
                if r:
                    event = self.__dev.read_one()
                    if not event == None:
                        self.__raw_queue.put(event)
                #time.sleep(delay)
            except IOError:
                self.__dev = find_device()
                while self.__dev == None:
                    time.sleep(.5)
                    self.__dev = find_device()


    def __consolidated(self):
        '''
        Begin consolidating events from the raw queue,
        and placing them on the consolidated queue

        PARAM delay = Time seconds to wait for events to be on the raw queue.
            This was intendted to allow the reading of events to be stoppable (i.e
            to keep from blocking the thread indefinitely). It was made tunable to
            allow good performance on fast CPUs, but not hog resources on slower
            machines.

            Setting delay to None will cause the thread to block indefinitely. This
            will probably yield the best performance, but means the thread will not
            stop after a call to stop() until a new event is triggered.
        '''

        time_of_last_turn = 0

        while True:
            
            if not self.__event_capture_running:
                return

            # Allows the thread to be joinable (i.e. stoppable) without
            # waiting for another event (without the timeout, get would
            # block until the next event)
            try:
                event = self.__raw_queue.get(timeout=self.__read_delay)
            except Queue.Empty:
                continue
            

            if event.code == KNOB_TURNED and self.__get_time_in_ms() - self.__turn_delay > time_of_last_turn:
                if event.value > 0:
                    self.__consolidated_queue.put(ConsolidatedEventCode.RIGHT_TURN)
                else:
                    self.__consolidated_queue.put(ConsolidatedEventCode.LEFT_TURN)
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
        TODO = remove thie parameter, and uses of get_time_in_ms that are
        unnecessary. The time can be gotten directly from the event.
        '''

        x = self.__long_press_time
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
            self.__consolidated_queue.put(ConsolidatedEventCode.LONG_CLICK)
            # pull events until button is release (disallow turns while button is down)
            event = self.__raw_queue.get()
            while event.code != BUTTON_PUSHED:
                event = self.__raw_queue.get()

        else:
            # TODO handle double
            try:
                self.__raw_queue.get() # drop the null event
                event = self.__raw_queue.get(timeout=self.__double_click_time)
            except Queue.Empty:
                event = None

            if event == None: # Single click
                self.__consolidated_queue.put(ConsolidatedEventCode.SINGLE_CLICK)

            elif event.code == BUTTON_PUSHED: # Double click
                self.__consolidated_queue.put(ConsolidatedEventCode.DOUBLE_CLICK)

            else: # turn
                # This is just being dropped for now; as it generally shouldn't matter,
                # and handling the event could cause problems.
                # No peek funciton exists, so the event must be pulled off the queue.
                # It can be put back, but would go on the end of the queue, meaning
                # it could be put behind things with older timestamps. In the current
                # Implementation, this probably wouldn't matter much, but if uses of
                # get_time_in_ms are replaced with the actual time stamps, order of
                # events might matter.
                #
                # self.__raw_queue.put(event)
                pass

        return
    

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
        

    def flash_led(self, num_flashes=2, brightness=led_brightness, duration=flash_duration, sleep=.15):
        '''
        Convenience function to flash the led in the base. After the flashes, the brightness
        will be reset to whatever it was when this function was called.

        PARAM num_flashes = number times to flash
        PARAM brightness = the brightness of the flashes (range defined by set_led_brightness)
        PARAM flash_duration = length of each flash in seconds (decimals accepted)
        PARAM sleep = time between each flash in seconds (decimals accepted)
        '''

        reset = self.__led_brightness

        for i in range(num_flashes):
            self.set_led_brightness(brightness)
            time.sleep(duration)
            self.set_led_brightness(0)
            time.sleep(sleep)

        self.__led_brightness = reset



    def start(self, raw_only=False):
        '''
        Begin capturing/queueing events. Once this has been run,
        get_next() can be used to start pulling events off the
        queue.
        '''

        self.__event_capture_running = True

        raw = threading.Thread(target = self.__raw)
        raw.daemon = True
        raw.start()

        cons = None
        if not raw_only:
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
            if self.__consolidated_thread != None:
                self.__consolidated_thread.join()
            #print("c joined")
            self.__raw_thread.join()
            #print("raw joined")


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

        RETURN:
            If start was run with rawOnly=True, an evdev.events.InputEvent;
            Otherwise, a ConsolidatedEventCode.
            In either case, None if there is not an event ready and block
            is False, or timeout is reached.
        '''

        event = None
        if not self.__event_capture_running:
            raise Exception("CaptureNotStarted")
        try:
            if self.__consolidated_thread != None:
                event = self.__consolidated_queue.get(block, timeout)
            else:
                event = self.__raw_queue.get(block, timeout)
        except Queue.Empty:
            pass

        return event


    def set_turn_delay(self, delay):
        '''
        Set the delay between when consolidated events will be registered.

        In an effort to reduce spam from a failry sensative device, this variable
        was created. If multiple turn events come in, the first will register
        a consolidated event, and those that come in within the delay time will
        be ignored. Once the delay threshold has been reached, another consolidated
        event will be registered.

        PARAM delay = time in ms between turn events.
        '''

        self.__turn_delay = delay


    def set_read_delay(self, delay):
        '''
        This was intendted to allow the reading of events to be stoppable (i.e
        to keep from blocking the thread indefinitely). It was made tunable to
        allow good performance on fast CPUs, but not hog resources on slower
        machines.

        Setting delay to None will cause the thread to block indefinitely. This
        will probably yield the best performance, but means the thread will not
        stop after a call to stop() until a new event is triggered.

        PARAM delay = Time in seconds to wait for the device to be readable. 
        '''

        self.__read_delay(delay)


    def set_double_click_time(self, time):
        '''
        PARAM time (in s) the button must be pressed again after a single press to register as a double
        '''
        self.__double_click_time = time


    def set_long_click_time(self, time):
        '''
        PARAM time (in s) the button must be held to register a long press
        '''
        self.__long_click_time = time


def find_device(dev_dir='/dev/input/'):
    '''
    Finds and returns the device in dev_dir

    If the user does not have permission to access the device, an OSError
    Exception will be raised.

    RETURN dev = An evdev.InputDevice. None if the device
    is not found.
    '''
    if dev_dir[-1] != '/':
        dev_dir = dev_dir + '/'
    dev = None
    for dev in os.listdir(dev_dir):
        if dev.find("event") == 0:
            dev = InputDevice(dev_dir + dev)
            if dev.name.find('Griffin PowerMate') >= 0:
                break
    return dev


def event_time_in_ms(event):
    '''
    PARAM InputEvent event

    RETURN The time in ms the event occurred (as an int)

    Does this by converting the event microseconds (event.usec) to
    seconds (multiply by 1000000), adding the event seconds (event.sec),
    converting to ms (multiply by 1000), then casting to an int.
    '''

    return int((event.usec / 1000000.0 + event.sec) * 1000) 
