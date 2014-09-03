from evdev import InputDevice, categorize, ecodes
from select import select
import requests
import json
import time
from evdev import DeviceInfo
from evdev import UInput
from evdev import InputEvent
from evdev import events

dev = InputDevice('/dev/input/event0')
input = UInput(events={ecodes.EV_MSC:[ecodes.MSC_PULSELED]})
input.device = dev
input.fd = dev.fd


input.write(ecodes.EV_MSC, ecodes.MSC_PULSELED, 255)
input.syn()
time.sleep(.2)
input.write(ecodes.EV_MSC, ecodes.MSC_PULSELED, 0)
input.syn()
