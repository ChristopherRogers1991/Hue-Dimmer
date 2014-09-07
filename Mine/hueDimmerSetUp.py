'''
This program sets up a new user on a Phillips Hue hub.

It scans the current network to locate all hubs. If more than one
is present, it will ask the user to specify one. It will then
create the user on that hub, and out put the ip and mac address of the hub
to a hueConfig.

The output file can be used with hueDimmer.py
'''

import socket
from subprocess import Popen, PIPE


socket.gethostbyname(socket.getfqdn())


# Thanks to Jed Smith from http://stackoverflow.com/a/1750931/1406997 for this magic
pid = Popen(["arp", "-n", IP], stdout=PIPE)
s = pid.communicate()[0]
mac = re.search(r"(([a-f\d]{1,2}\:){5}[a-f\d]{1,2})", s).groups()[0]
