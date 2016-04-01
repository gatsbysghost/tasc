#!/usr/bin/env python

import subprocess # For running commands on host CLIs
import getpass # For obscuring password inputs
import IPy # IP address verifier
import datetime # for getting system time
import re # regex for input sanitation
import paramiko # ssh methods
### import netmiko ### - reserved for future use, including additional devices
import time # for waiting
import sys # for the big red 'terminate' button 

# SSH Task Scheduler (TaSc)
# Purpose: Provide users with the ability to ssh into network devices and run commands at regular intervals.
# Scope: Presently this only provides compatibility with Show commands on ASAs.
#
# Author: Scott Reu
# Version 0.1
# Compiled March 28, 2016
#
#
#
# FORTHCOMING FEATURES:
#
# v0.1.1
# -Bugfixes based on IFT
#
# v0.2:
# -Improved logging
# -Support for SourceFire devices
# -Support for selected additional (non-show) commands
#
# v0.3:
# -Introduce support for NX-OS switches
# -Add integration for C Library installation
#
#


#
# DOCSTRING FOR PROJECT
#
'''
First, we need the SSH details and Authc. creds for the box we're logging into. Gather these
    as raw_input and getpass obscured input.

Second, we need an Enable password, if one is configured. Secure input with getpass. (This is lumped into main()).

Third, we'll need to determine the interval at which we're running the script and when we're going to stop.
    So that entails: 1-Get system time; 2-Get pause interval as raw_input; 3-Get stop time as raw_input;
    4-do some math to figure out the number of intervals necessary to fill that time; 5-put the number
    of intervals into a decrementing while loop for the time.sleep. NOTE: There's probably a less-complicated
    way to do this, but I don't know what it is, and this seems to work.

Fourth, sanitize inputs, make sure the interval is realistic, etc.

Fifth, create a logfile to write all of our show commands to.

Sixth, run the While loop and actually run the show commands at the given interval.

At the end of this entire thing, we should review the commands we'll be submitting and the ssh info
and ask the user to confirm.
'''


#
# GLOBAL VARIABLES
#
disclaimer = ('\n\n\nSSH Task Scheduler (TaSc) v0.1\nScott Reu, Cisco Systems - RTP Firewall TAC\nCompiled March 28, 2016\n\nFOR USE BY CISCO TAC ENGINEERS ONLY \n\nCisco Systems assumes no responsibility for consequences of unauthorized or improper use of this application.\n\nLimitations of v0.1:\n-Only Show commands are permitted.\n-DO NOT use this version of TaSc to run Show Tech.\n-TaSc does not validate command syntax.\n\n\n')
logfilename = 'TaSc-log-' + str(datetime.datetime.now().date()) + '.log'
logger = open(logfilename,'a',1)

# Initialize list of commands to be run.
commandlist = []

# Lists of acceptable answers to yes/no prompts
YesList = ['yes','y','Yes','Y','']
YesList2 = ['yes','y','Yes','Y'] # requires an affirmative so that users must enter a yes word explicitly
NoList = ['no','n','No','N']

# List of acceptable permutations of 'show'
goodshow = ['sh','Sh','sho','Sho','show','Show']

# Regex string to match
unacceptable = "[`~!@#$%^&\*()-_=+{}\[\]'\":;?/.]\D"

# List of acceptable responses to device question
goodDeviceList = ['asa','Asa','ASA','ios','Ios','iOS','IOS']
asaList = ['asa','Asa','ASA']
iosList = ['ios','Ios','iOS','IOS']

#
# PRIMARY FUNCTIONS
#

# ssh() is adapted from the work of Kirk Byers
# see: https://pynet.twb-tech.com/blog/python/paramiko-ssh-part1.html
def ssh(ip,user,pw,enpw,cmds,dtype):
    '''
    Input: IP address (string), username (string), password (string), enable password (string), list of commands to run (list), device type (string).
    Action: Log into an ASA, run commands, log commands, log out of ASA.
    Output: Debug output to terminal, main output written to logfile.
    '''
    # Create instance of SSHClient object
    run_pre = paramiko.SSHClient()
    # Automatically add untrusted hosts (make sure okay for security policy in your environment)
    run_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # initiate SSH connection
    try:
        run_pre.connect(ip, username=user, password=pw, look_for_keys=False, allow_agent=False)
    except:
        print '\nERROR: SSH Error.\nCheck credentials and target IP address, and verify that target is configured to allow SSH access from this host.'
        logger.write('[' + str(datetime.datetime.now()) + '] ' + 'Error establishing SSH connection to host. Terminating thread.\n\n')
        sys.exit(0)
    else:
        logger.write('[' + str(datetime.datetime.now()) + '] ' + 'SSH connection established to ' + ip + '\n\n')
    # Use invoke_shell to establish an 'interactive session'
    remote_conn = run_pre.invoke_shell()
    logger.write('[' + str(datetime.datetime.now()) + '] ' + 'Interactive SSH session established \n\n')
    # Enable
    remote_conn.send('enable\n')
    time.sleep(1)
    remote_conn.send(enpw + '\n')
    time.sleep(1)
    # Turn off paging on ASAs
    if str(dtype) in asaList:
        remote_conn.send("terminal page 0\n")
        time.sleep(1)
    # The command is different on IOS
    # Note: I sanitized this elsewhere. If the syntax is different in NXOS, we need to add an elif when we add support.
    else:
        remote_conn.send("terminal length 0\n")
        time.sleep(1)
    # Send commands to device
    for cmd in cmds:
        remote_conn.send(cmd + '\n')
        time.sleep(45)
    output = remote_conn.recv(10000)
    logger.write('[' + str(datetime.datetime.now()) + '] Session output:\n' + output + '\n')
    remote_conn.close()
    logger.write('[' + str(datetime.datetime.now()) + '] Terminating SSH session gracefully. (This is part of normal operation).\n')

#
# SANITATION AND INPUT LOOPS
#

def sanitize_interval(good):
    '''
    Input: Boolean value. This should be set to False for the loop to work as designed.
    Action: Retrieve an integer from the user and 
    Output: Interval value in minutes as an integer.
    '''
    while good == False:
        interval = raw_input('How frequently should this script be run, in minutes (min. 3, max. 2880): ')
        try:
            iint = int(interval)
        except:
            print 'Time interval must be an integer.'
        if 3 <= iint <= 2880:
            good = True
            return iint
        else:
            print 'Time interval must be between 3 and 2880 minutes.'
            good = False
                

def enough_cmds(nuffcmds):
    '''
    Input: Boolean value, must be False.
    Action: Get commands to populate a list of commands to be run at the specified interval.
    Output: None, but the global commandlist should be populated.
    '''
    while nuffcmds == False:
        more = raw_input('Any other commands to run? [Y/n]: ')
        if more in NoList:
            nuffcmds = True
        elif more in YesList:
            getCommand(False,'Enter another command: ')
        else:
            print 'Please enter "Y or "N".\n'

def sanitize_cmds(cmds):
    '''
    Input: List (this should be the global commandlist)
    Action: Verify that the commands being run look like valid ASA/IOS show commands (currently
    we are not actually running a full-blown validator to check against a database of valid show commands,
    but future releases might want to go in that direction.) This will be accomplished with
    a regex match to confirm that the first word is "show" or a working approximation of "show".
    
    If a command doesn't look like the correct syntax, prompt the user to either remove the command
    or 
    Output: Nothing if it works, exception and prompt to modify if it doesn't.
    '''
    for cmd in cmds:
        notnum = re.search(unacceptable,cmd)
        if notnum:
            print 'Command "' + str(cmd) + '" contains special characters. Commands must be strings of alphanumeric characters. Removing command from list.'
            cmds.remove(cmd)
        else:
            pass
    
    for cmd in cmds:
        if cmd == '':
            print 'Command "' + str(cmd) + '" is blank. Removing command from list.'
            cmds.remove(cmd)
        else:
            pass
    
    for cmd in cmds:
        split = cmd.split(' ')
        if len(split) <= 1:
            print 'Command "' + str(cmd) + '" contains only one word. Show commands have at least two items. Removing command from list.'
            cmds.remove(cmd)
        else:
            pass
        
    for cmd in cmds:
        split2 = cmd.split(' ')
        if split2[0] not in goodshow:
            print 'Command "' + str(cmd) + '" is not a Show command. Currently only Show commands are supported. Removing command from list.'
            cmds.remove(cmd)
        else:
            pass
    
    if len(cmds) == 0:
        print '\n\nERROR: List of commands is empty. Terminating TaSc.\n\n'
        sys.exit(0)

def sanitize_ip(ip):
    '''
    Input: a string containing the IP address that SSH traffic will be destined to.
    
    Action: verify that the string provided is a valid IP (my instinct is to split it up
    into a list of octets, make sure that there are four of them and that each one is 255
    or less, etc., but instead we'll be using IPy.)
    
    Output: Return nothing if the IP is invalid, return True if the IP is good. main()
    will have a While loop and a variable we can initially set to False so that when this
    function returns True, you can move on to the next stage.
    '''
    try:
        IPy.IP(ip)
    except:
        print 'Invalid IP Address'
        return False
    else:
        return True

def howmanytimes(stoptime,interval):
    '''
    Input: Date and time the loop is stopping; interval of time the function should sleep in minutes.
    Output: Number of times the loop will run.
    '''
    runtime = int((stoptime - datetime.datetime.now()).total_seconds())
    num_times = int(runtime/(int(interval)*60))
    return num_times

def howlong(stoptime,interval):
    '''
    Input: Number of times to run, date/time the loop is stopping, interval of time the function should sleep in minutes.
    Output: Number of seconds between each run.
    '''
    runtime = int((stoptime - datetime.datetime.now()).total_seconds())
    num_times = int(runtime/(int(interval)*60))
    return int(runtime/num_times)

# Adapted this one from StackOverflow
def ObtainDate():
    '''
    Input: Ask the user for the date/time when TaSc should stop running.
    Action: Validate that the provided date/time is in the correct format and not in the past.
    Output: datetime object for when TaSc should stop running.
    '''
    now = datetime.datetime.now()
    print 'The current date/time on this host is: ' + str(now) + '.\n'
    isValid = False
    while not isValid:
        userIn = raw_input("When should TaSc stop running? (Time/date format is 24-hr, HH:MM mm/dd/yy): ")
        try:
            d1 = datetime.datetime.strptime(userIn, "%H:%M %m/%d/%y")
            isValid=True
        except:
            print "Invalid Format!\n"
    totaltime = int((d1 - datetime.datetime.now()).total_seconds())
    goodTime = notneg(totaltime)
    while goodTime == False:
        retry = raw_input('Time Travel Error: Date must be in the future. When should TaSc stop running? (Time/date format is 24-hr, HH:MM mm/dd/yy): ')
        d1 = datetime.datetime.strptime(retry, "%H:%M %m/%d/%y")
        totaltime = int((d1 - datetime.datetime.now()).total_seconds())
        goodTime = notneg(totaltime)
    return d1
               
def notneg(number):
    '''
    Input: an integer
    Output: False if the integer is either zero nor negative, True otherwise.
    '''
    if number <= 0:
        return False
    else:
        return True

def bigredbutton():
    '''
    Confirm that the user wants to go ahead with the action and provide an escape.
    '''
    looper = False
    while looper == False:
        uin = raw_input('CONFIRM [Type "yes" or "no"]: ')    
        if uin in NoList:
            print '\nOk! Terminating thread. Thanks for using TaSc.\n'
            sys.exit(0)
        elif uin in YesList2:
            print '\nOk! Initializing...\n'
            looper = True
            

def getSSHlogin(goodlogin):
    '''
    Input: Boolean value (must be false for the loop to work).
    Action: Validate input to make sure that ssh username is not blank
    Output: SSH Username as a string.
    '''
    while goodlogin == False:
        more = raw_input('SSH Username: ')
        if more != '':
            goodlogin = True
            return more
        else:
            print 'Username cannot be blank.\n'

def getCommand(goodcmd,prompt):
    '''
    Input: Boolean value (must be false for the loop to work), string containing prompt for raw input.
    Action: Validate input to make sure that command is not blank
    Output: None, but the global commandlist should be appended with valid commands.
    '''
    while goodcmd == False:
        more = raw_input(prompt)
        if more != '':
            goodcmd = True
            commandlist.append(more)
        else:
            print 'This field cannot be left blank!\n'

def getDevice(goodvalue,prompt):
    '''
    Input: Boolean value (must be false for the loop to work), string containing prompt for raw input.
    Action: Validate input to make sure that device type is not blank
    Output: Returns either 'ASA' or 'IOS'
    '''
    while goodvalue == False:
        more = raw_input(prompt)
        if more != '':
            if more in goodDeviceList:
                goodvalue = True
                return more
            else:
                print 'Valid responses: "ASA" or "IOS".\n'
        else:
            print 'This field cannot be left blank!\n'

#
# MAIN
#

def main():
    print disclaimer
    #
    # SSH info
    #
    goodIP = False
    while goodIP == False:
        sship = raw_input('IP of target host: ')
        goodIP = sanitize_ip(sship)
    deviceType = getDevice(False,'What type of device is this? (ASA/IOS): ')
    sshuser = getSSHlogin(False)
    sshpw = getpass.getpass('SSH Password: ')
    sshenpw = getpass.getpass('Enable Password (leave blank if none): ')
    #
    # Commands to run on device
    #
    getCommand(False,'Enter a command to run on the target host. Currently only Show commands are supported: ')
    enough_cmds(False)
    print '\nVerifying that requested commands are permitted in this version...\n'
    sanitize_cmds(commandlist)
    #
    # Time
    #
    runinterval = sanitize_interval(False)
    now = datetime.datetime.now()
    stoptime = ObtainDate()
    numberoftimes = howmanytimes(stoptime,runinterval)
    secondsPerRun = howlong(stoptime,runinterval)
    #
    # Log
    #
    # Each time we session to the device, it'll be logger.write(thing to write)
    # Don't forget to logger.close as part of graceful shutdown
    print '\n\nA logging file called ' + logfilename + ' has been generated in the directory where this application is located.\nThis file will contain the output of TaSc.'
    #
    # Confirm
    #
    print '\nThe script will run the following commands:\n' + '\n'.join(commandlist) + '\n\n' + 'These commands will be run ' + str(numberoftimes) + ' times. TaSc will stop running at the following date and time: ' + str(stoptime) + '\n\n'
    bigredbutton()
    #
    # Run
    #
    i = numberoftimes
    n = 1
    logger.write('\n\n[' + str(datetime.datetime.now()) + '] Initializing main loop.\n')
    while i > 0:
        print 'Running TaSc event number ' + str(n) + '...'
        try:
            ssh(sship,sshuser,sshpw,sshenpw,commandlist,deviceType)
            i -= 1
            print 'Data for TaSc event ' + str(n) + ' written to log.'
            n += 1
            if i > 0:
                print 'Waiting to run task again...\n'
                time.sleep(secondsPerRun)
            else:
                pass
        except:
            print '\nTaSc encountered an error or an escape sequence was detected.\nShutting down as gracefully as possible, given the circumstances.'
            logger.write('\n\n[' + str(datetime.datetime.now()) + '] Detected an error or escape sequence; exiting main loop.\n')
            logger.close()
            sys.exit(0)
    print 'Thanks for using TaSc! Exiting...\n'
    now = datetime.datetime.now()
    logger.write('****************************\n****************************\n****************************\n****************************\n****************************\n[' + str(now) + '] TaSc runtime gracefully shutdown.' + '\n\nEnd of logging for this session.\n')
    logger.close()
    exit()

if __name__ == "__main__":
    main()