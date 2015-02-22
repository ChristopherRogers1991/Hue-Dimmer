Hue-Dimmer
==========

# Overview

This repository contains several programs which can be used to control
Phillips Hue lights. At the moment, they are functional but hacky.

# Purpose

Using a phone to control your lights is tedious when you just want to do
something simple. The programs eliminate the need for the phone, and allow
controlling the ligths with a GriffinPowerMate and a universal remote (via
an flirc dongle).

# A Note

While things being hacky is gross, at the moment, things work the way I
need them to, so forward progress is likely to be slow. Typically I write things
in a VERY iterative process, in which the first attemt is very hacked together
mostly to get a proof of concept, and then things get more organized as the
project grows. With this project, I didn't need much beyond proof of concept
to make myself happy, so until I need more, things are likely to stay gross.
That is of course unless someone takes interest in the project - if you'd like
to use it, and need it to be less gross, email me at the address below.

# Basic usage

1. Create a user on your hue hub called newDeveloper (follow the instructions on their website)
2. Grab PowerMateEventHandler.py from my other repository, and stick it in the same directory as hueDimmer\*.py
3. Check the imports to make sure you have all the other dependencies
4. Change the ip in hueDimmer\*.py
5. Run hueDimmer\*.py

# Questions, Comments, Concerns

Email me: ChristopherRogers1991@gmail.com
