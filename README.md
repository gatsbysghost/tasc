# SSH Task Scheduler (TaSc)
# Purpose
Provide users with the ability to ssh into network devices and run commands at regular intervals.
# Scope
Presently this only provides compatibility with Show, Clear, and Debug commands on ASAs and IOS devices.
# Use Case
This is much easier to use than EEM, and it's remote, so it's not intrusive.

# Details
-Author: Scott Reu
-Current Version 0.2.1
-March 31, 2016

# Roadmap for Development:

## v0.1.1
-Bugfixes based on IFT
-New logging destination to foster compatibility with Mac OS and improve readability

## v0.2:
-Windows Installer MSI
-Improved logging
-Support for selected additional (non-show) commands: Clear and Debug

## v0.2.1:
-Mac OS .app availability
-Unique per-session log files based on granular timestamp rather than one per day.

## v0.3:
-Support for NX-OS switches
-Support for packet capture commands
-Add integration for C Library installation

# Original Project Docstring

'''
First, we need the SSH details and Authc. creds for the box we're logging into. Gather these
    as raw_input and getpass obscured input.

Second, we need an Enable password, if one is configured. Secure input with getpass.
    (This is lumped into main()).

Third, we'll need to determine the interval at which we're running the script
    and when we're going to stop. So that entails: 1-Get system time; 2-Get pause
    interval as raw_input; 3-Get stop time as raw_input; 4-do some math to figure
    out the number of intervals necessary to fill that time; 5-put the number of
    intervals into a decrementing while loop for the time.sleep. NOTE: There's probably
    a less-complicated way to do this, but I don't know what it is, and this seems to work.

Fourth, sanitize inputs, make sure the interval is realistic, etc.

Fifth, create a logfile to write all of our show commands to.

Sixth, run the main While loop and actually run the ASA/IOS commands at the given interval.

At the end of this entire thing, we should review the commands we'll be submitting and the
ssh info and ask the user to confirm.
'''
