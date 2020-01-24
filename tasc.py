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
import os, os.path #for creating the logging fsys
import argparse #for CLI arguments
import progressbar #for the progress bar

# SSH Task Scheduler (TaSc)
# Purpose: Provide users with the ability to ssh into network devices and run commands at regular intervals.
# Scope: Presently this only provides compatibility with Show, Clear, and Debug commands on ASAs and IOS devices.
# Use Case: This is much easier to use than EEM, and it's remote, so it's not intrusive.
#
# Author: Scott Reu
# Originally written in Python2.7, now runs only in Python3.5
tascVersion = '0.3.6'
tascDate = 'July 4th, 2016'
#
#
# ROAD MAP FOR DEVELOPMENT:
#
# v0.1.1
# -Bugfixes based on IFT
# -New logging destination to foster compatibility with Mac OS and improve readability
#
# v0.2:
# -Windows Installer executable
# -Improved logging
# -Support for selected additional (non-show) commands: Clear and Debug
#
# v0.2.1:
# -Logging to a file in a folder on ~/Desktop rather than to the application directory
# -Unique per-session log files based on granular timestamp rather than one per day
#
# v0.2.1.100:
# -Engineering Special feature set for jluber: added support for Unix devices
#
# v0.3:
# -Interim build for development; not released publicly
# -Bugfixes based on Unix integration in 0.2.1.100
# -Migrate from manually-defined Stop Time to a loop count
# -Classify application and SSH session logs as 'verbose' and make their output optional
#
# v0.3.1:
# -SSH connectivity is now tested automatically before the loop starts running
# -You can now SSH to ports other than 22 using the setup dialog.
#
# v0.3.2:
# -Syntax for getting commands from the user has been overhauled for ease of use
# -Cleaned up unused functions
#
# v0.3.3:
# -Interim release for testing 0.4 features (not for public distribution)
# -Added progress bar to give greater transparency into runtime progress
# -Bugfix: debug commands didn't work properly before, but they should now.
# -Code cleanup
#
# v0.3.4:
# -Interim release for testing 0.4 features (not for public distribution)
# -Bugfix: fixed fallback IP address input verification
# -Migrated from Python 2.7 to 3.5
# -Reworked SSH syntax to use paramiko's exec_command method rather than the clunkier invoke_shell
# -Improved runtime speed
# -TaSc can now capture Show Tech outputs
#
# v0.3.5:
# -Initial commit of ASA pcap feature
#
# v0.3.5.100:
# -Engineering Special feature set for SR 680395105
# -Ring buffer with separate folders and files per session
# -Static timer values
# -Improvements to logfile naming (for clarity)
# -Commented out ASA pcap code
# -Improved Regex for unacceptable characters
#
# v0.3.6
# -Fork from 0.3.5.100 maintaining ring buffer and improved logging
# -Allow users to select interval between sessions; integrate this improvement with progressbar.
# -Further improvements to pcap
#
# v0.4:
# -Support for arguments on the CLI (-v verbosity, -i interval, -ip address,
#       -u username -p password, -e enable password, -t device type, -l loop count,
#       -c command). So the script need not be run interactively.
# -Support for ASA packet captures
# -Explicit support for SourceFire CLIsh and sudo access to run commands in expert mode
#
# v1.0:
# -GUI
# -Manual specification of logfile location
#
# v1.1:
# -Mac OS App to launch GUI
#


#
# DOCSTRING FOR PROJECT
#
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


#
# GLOBAL VARIABLES
#
disclaimer = ('\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n'+
            'SSH Task Scheduler (TaSc) '+ tascVersion +'\nScott Reu, Cisco Systems - RTP Firewall TAC'
            '\nCompiled '+ tascDate +'\n\nFOR USE BY CISCO TAC ENGINEERS ONLY \n\nCisco Systems '
            'assumes no responsibility for consequences of unauthorized or improper use of this '
            'application.\n\nVersion '+ tascVersion +' Notes:'
            '\n-TaSc DOES NOT validate command syntax, so be sure to check your inputs in advance!' +
            '\n-TaSc maintains a ring buffer with a fixed number of files (120).' +
            '\n-ASA Packet capture is currently only functional for single-context ASAs; in multiple mode, captures will fail.'
            '\n\n\nDEBUG Command Guidelines:\n-If a DEBUG command is used, UNDEBUG ALL will automatically '
            'be executed after each session.\n-TaSc will give you roughly 60 seconds of debug output each time ' 
            'the command is run.\n\n\n')
# Logging File Setup
logfileprefix = ('TaSc-log-' + str(datetime.datetime.now().year) + '-' + str(datetime.datetime.now().month)
               + '-' + str(datetime.datetime.now().day) + '_' + str(datetime.datetime.now().time())[0:2]
               + '-' + str(datetime.datetime.now().time())[3:5])
logfilename = logfileprefix + '.log'
# Create a log folder on the Desktop
# This should actually work on windows, too, because reasons (Python's ~ is translated to %HOMEPATH% in Windows)
logloc = os.path.join(os.path.expanduser('~'), 'Desktop')
if not os.path.exists(logloc+'/TaScLog'):
    os.makedirs(logloc+'/TaScLog')
os.chdir(logloc+'/TaScLog/')
if not os.path.exists(logloc+'/TaScLog/'+logfileprefix):
    os.makedirs(logloc+'/TaScLog/'+logfileprefix)
else:
    n = 1
    dupFolder = True
    while dupFolder == True:
        logfileprefix += ('-' + str(n))
        n +=1
        if not os.path.exists(logloc+'/TaScLog/'+logfileprefix):
            os.makedirs(logloc+'/TaScLog/'+logfileprefix)
        else:
            pass
os.chdir(logloc+'/TaScLog/'+logfileprefix+'/')
logger = open(logfilename,'a',1)
# Initialize list of commands to be run.
commandlist = []
# Verbose output - default to False
verbose = False
# Initialize parser for argparse
#parser = argparse.ArgumentParser(description='Process command line arguments to run TaSc from CLI.')

#
# REGEX IS FOR SUCKERS
#

# Lists of acceptable answers to yes/no prompts
YesList = ['yes','y','Yes','Y',''] # allows a blank response for default Y answers
YesList2 = ['yes','y','Yes','Y'] # requires an affirmative so that users must enter a yes word explicitly
NoList = ['no','n','No','N']
NoList2 = ['no','n','No','N','']

# List of acceptable permutations of 'show' and other acceptable commands
goodshow = ['sh','Sh','sho','Sho','show','Show','clear','clea','cle','Clear','Clea','Cle','debug','deb',
            'Debug','Deb','debu','Debu','Un','un','Und','und','Unde','unde','Undebug','undebug']

debuglist = ['debug','deb','Debug','Deb','debu','Debu']

# Regex string to match
unacceptable = "[^\d\s\w/\.\:\|\-\_]"

# List of acceptable responses to device question
goodDeviceList = ['asa','Asa','ASA','ios','Ios','iOS','IOS','unix',
                  'Unix','uni','Uni','un','Un','U','u','s','S','sf','SF',
                  'sfr','SFR']
asaList = ['asa','Asa','ASA']
iosList = ['ios','Ios','iOS','IOS']
nixList = ['unix','Unix','uni','Uni','un','Un','U','u']
sfrList = ['s','S','sf','SF','sfr','SFR']
sfrclishList = ['s','S','sf','SF','sfr','SFR','sfrclish']

#
# PRIMARY FUNCTIONS
#

def newLog():
    loglist = [name for name in os.listdir('.') if os.path.isfile(name)]
    logfilename = ('TaSc-log-' + str(datetime.datetime.now().year) + '-' + str(datetime.datetime.now().month)
               + '-' + str(datetime.datetime.now().day) + '_' + str(datetime.datetime.now().time())[0:2]
               + '-' + str(datetime.datetime.now().time())[3:5] + '.log')
    n = 1
    while str(logfilename) in loglist:
        logfilename = logfilename[:-4]
        logfilename += '_'
        logfilename += str(n)
        logfilename += '.log'
        n +=1
    logger = open(logfilename,'a',1)
    numlogs = len(loglist)
    if numlogs >= 121:
        os.remove(loglist[0])
    else:
        pass
    return logger


# ssh() is adapted from the work of Kirk Byers
# see: https://pynet.twb-tech.com/blog/python/paramiko-ssh-part1.html
def ssh(ip,user,pw,enpw,cmds,dtype,dbug,vb,port,tvalue,log):
    '''
    Input: IP address (string), username (string), password (string), enable password (string),
    list of commands to run (list), device type (string), are we running a debug command? (boolean),
    are we logging SSH verbosely? (boolean), ssh dest port(int), value for calculating progressbar time (int).
    Action: Log into an ASA, run commands, log commands, log out of ASA. If a debug command was run,
    then at the end of the session we need to undebug all.
    Output: Debug output to terminal, main output written to logfile.
    '''
    #Initialize progress bar
    pbar = progressbar.ProgressBar().start()
    pvalue=5
    pbar.update(value=pvalue)
    # Create instance of SSHClient object
    run = paramiko.SSHClient()
    # Automatically add untrusted host keys
    run.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # initiate SSH connection
    try:
        run.connect(ip, username=user, password=pw, look_for_keys=False, allow_agent=False, port=port)
        pvalue=10
        pbar.update(value=pvalue)
    except:
        msg = ('\nSSH ERROR: Check credentials and target IP address, and verify that '
               'the target is configured to allow SSH access from this host.')
        print(msg)
        log.write('[' + str(datetime.datetime.now()) + '] ' + 'Error establishing'
                     ' SSH connection to host. Terminating thread.\n\n')
        sys.exit(0)
    else:
        if vb == True:
            log.write('[' + str(datetime.datetime.now()) + '] SSH connection established to '
                         + ip + ':' + str(port) + '\n\n')
        else:
            pass
    # Enable password, unless you're using a Unix device
    if str(dtype) not in nixList:
        if str(dtype) in sfrList:
            stdin, stdout, stderr = run.exec_command(('expert\nsudo -i\n'+pw),bufsize=10000000)
            time.sleep(3)
        elif str(dtype) in sfrclishList:
            pass
        else:
            stdin, stdout, stderr = run.exec_command(('enable\n'+enpw+'\n'),bufsize=10000000)
            time.sleep(1)
    else:
        pass
    pvalue=12
    pbar.update(value=pvalue)
    # Turn off paging on ASAs
    if str(dtype) in asaList:
        stdin.write("terminal page 0\n")
        stdin.flush()
        time.sleep(1)
    # The command is different on IOS
    # Note: I sanitized this elsewhere. If the syntax is different in NXOS,
    # we need to add an elif when we add support.
    elif str(dtype) in iosList:
        stdin.write("terminal length 0\n")
        stdin.flush()
        time.sleep(1)
    elif str(dtype) in nixList:
        stdin.write("\n")
        stdin.flush()
        time.sleep(1)
    pvalue=15
    pbar.update(value=pvalue)
    # Send commands to device
    for cmd in cmds:
        split3 = cmd.split(' ')
        if split3[0] in debuglist:
            seconds60 = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,
                         31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,
                         58,59,60]
            stdin.write(cmd + '\n')
            stdin.flush()
            for second in seconds60:
                pvalue += tvalue
                pbar.update(value=pvalue)
                time.sleep(1)
            d_out1 = stdout.channel.recv(10000000)
            d_out2 = d_out1.decode('ISO-8859-1')
            log.write('\n[' + str(datetime.datetime.now()) + '] Debug output from command "' + cmd + '":\n' + d_out2 + '\n')
            pbar.update(value=pvalue)
        else:
            seconds45 = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,
                         31,32,33,34,35,36,37,38,39,40,41,42,43,44,45]
            stdin.write(cmd + '\n')
            stdin.flush()
            for second in seconds45:
                pvalue += tvalue
                pbar.update(value=pvalue)
                time.sleep(1)
            output = stdout.channel.recv(10000000)
            output2 = output.decode('ISO-8859-1')
            log.write('\n[' + str(datetime.datetime.now()) + '] Output from command "' + cmd + '":\n' + output2 + '\n')
            pbar.update(value=pvalue)
    pbar.update(value=90)
    if dbug == True:
        stdin.write('undebug all\n')
        stdin.flush()
        c_output = stdout.channel.recv(4000)
        c_output2 = output.decode('ISO-8859-1')
        pbar.update(value=95)
        if vb == True:
            log.write('[' + str(datetime.datetime.now()) + '] Verifying undebug all:\n' + c_output2 + '\n')
        else:
            pass
    else:
        pass
    pbar.update(value=99)
    # Close connection and log success
    run.close()
    if vb == True:
        log.write('[' + str(datetime.datetime.now()) + '] Terminating SSH session gracefully.'
                     ' (This is part of normal operation).\n')
    else:
        pass
    pbar.update(value=100)
    pbar.finish()

#
# INPUT SANITY CHECKS
#

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
        print('Invalid IP Address')
        return False
    else:
        return True

def sanitize_cmds(cmds):
    '''
    Input: List (this should be the global commandlist)
    Action: Verify that the commands being run look like valid ASA/IOS show commands (currently
    we are not actually running a full-blown validator to check against a database of valid show commands,
    but future releases might want to go in that direction.) This will be accomplished with
    a regex match to confirm that the first word is "show" or a working approximation of "show".
    
    If a command doesn't look like the correct syntax, prompt the user to either remove the command
    or 
    Output: Returns boolean value of True if a debug command has been used, and False otherwise.
    '''
    for cmd in cmds:
        notnum = re.search(unacceptable,cmd)
        if notnum:
            print(('Command "' + str(cmd) + '" contains special characters. '
            'Commands must be strings of alphanumeric characters. Removing command from list.'))
            cmds.remove(cmd)
        else:
            pass
    
    for cmd in cmds:
        if cmd == '':
            print('Command "' + str(cmd) + '" is blank. Removing command from list.')
            cmds.remove(cmd)
        else:
            pass
    
    for cmd in cmds:
        split = cmd.split(' ')
        if len(split) <= 1:
            print(('Command "' + str(cmd) + '" contains only one word. Show commands have at '
                   'least two items. Removing command from list.'))
            cmds.remove(cmd)
        else:
            pass
        
    for cmd in cmds:
        split2 = cmd.split(' ')
        if split2[0] not in goodshow:
            print(('Command "' + str(cmd) + '" is not a Show command. Currently only Show and Debug '
                   'commands are supported. Removing command from list.'))
            cmds.remove(cmd)
        else:
            pass
    
    if len(cmds) == 0:
        print('\n\nERROR: List of commands is empty. Terminating TaSc.\n\n')
        sys.exit(0)

    # Debug command notifier
    split3 = cmd.split(' ')   
    if split3[0] in debuglist:
        print ('NOTICE: at least one of your commands has been recognized as a DEBUG command. '
               'UNDEBUG ALL will be automatically applied at the end of each SSH session '
               'in order to preserve resources.')
        return True
    else:
        return False

def isIntOrBlank(foo):
    '''
    Input: Any variable.
    Action: Determine if a foo is an integer in range 1-65535 or a blank space (input sanitization for getPort)
    Output: True if foo is an integer 1-65535 or blank; False otherwise.
    '''
    footoo = 0
    try:
        footoo = int(foo)
    except:
        pass
    if isinstance(footoo,int):
        if 1 <= footoo <= 65535:
            return True
    else:
        var = foo.strip(' ')
        if foo == '':
            return True
        else:
            return False

#
# INPUT COLLECTION LOOPS
#

def getCommand(goodcmd,prompt):
    '''
    Input: Boolean value (must be false for the loop to work), string containing prompt for raw input.
    Action: Validate input to make sure that command is not blank
    Output: None, but the global commandlist should be appended with valid commands.
    '''
    while goodcmd == False:
        more = input(prompt)
        if more != '':
            goodcmd = True
            commandlist.append(more)
        else:
            print('This field cannot be left blank!\n')

def enough_cmds(nuffcmds):
    '''
    Input: Boolean value, must be False.
    Action: Get commands to populate a list of commands to be run at the specified interval.
    Output: None, but the global commandlist should be populated.
    '''
    while nuffcmds == False:
        more = input('Enter an additional command to run (or strike Enter to get started): ')
        if more == '':
            nuffcmds = True
        else:
            commandlist.append(more)

def amVerbose(goodanswer,prompt):
    '''
    Input: Boolean value, must be False.
    Action: Get a yes or no answer w/r/t whether we are running in debug/verbose mode (default to No/False)
    Output: True if verbose, False if not verbose
    '''
    while goodanswer == False:
        more = input(prompt)
        if more in NoList2:
            goodanswer = True
            return False
        elif more in YesList2:
            goodanswer = True
            return True
        else:
            goodanswer = False
            print('Please enter "Y" or "N".\n')

def bigredbutton():
    '''
    Confirm that the user wants to go ahead with the action and provide an escape.
    '''
    looper = False
    while looper == False:
        uin = input('CONFIRM [Type "yes" or "no"]: ')    
        if uin in NoList:
            print('\nOk! Terminating thread. Thanks for using TaSc.\n')
            sys.exit(0)
        elif uin in YesList2:
            print('\nOk! Initializing...\n')
            looper = True

def getSSHlogin(goodlogin):
    '''
    Input: Boolean value (must be false for the loop to work).
    Action: Validate input to make sure that ssh username is not blank
    Output: SSH Username as a string.
    '''
    while goodlogin == False:
        more = input('SSH Username: ')
        if more != '':
            goodlogin = True
            return more
        else:
            print('Username cannot be blank.\n')

def getDevice(goodvalue,prompt):
    '''
    Input: Boolean value (must be false for the loop to work), string containing prompt for raw input.
    Action: Validate input to make sure that device type is not blank
    Output: Returns either 'ASA', 'IOS', 'SFR', or 'Unix'
    '''
    while goodvalue == False:
        more = input(prompt)
        if more != '':
            if more in goodDeviceList:
                goodvalue = True
                if more in sfrList:
                    sfrmore = input('Run commands in CLIsh? (y/N): ')
                    goodanswer = False
                    while goodanswer == False:
                        if sfrmore in NoList2:
                            goodanswer = True
                            return more
                        elif sfrmore in YesList2:
                            goodanswer = True
                            return 'sfrclish'
                        else:
                            goodanswer = False
                            print('Please enter "Y" or "N".\n')
                else:
                    return more
            else:
                print('Valid responses: "ASA", "IOS", "SFR", or "Unix".\n')
        else:
            print('This field cannot be left blank!\n')
    
def getPort():
    '''
    Input: None
    Action: Get port from raw input.
    Output: If raw input empty, return 22. Else, return specified port.
    '''
    validate = False
    anyOldPort = input('Port [defaults to 22 if left blank]: ')
    validate = isIntOrBlank(anyOldPort)
    while validate == False:
        anyOldPort = input('Please either enter an integer (1-65535) or leave this field blank to use 22: ')
        validate = isIntOrBlank(anyOldPort)
    if anyOldPort == '':
        return 22
    else:
        return anyOldPort

def getLoops(prompt):
    '''
    Input: A prompt (str) to feed to the user to retrieve the number of loops to run.
    Action: Get loop count & verify format.
    Output: Return loop count as an integer.
    '''
    goodLoop = False
    while goodLoop == False:
        more = input(prompt)
        try:
            intmore = int(more)
        except:
            print('\nError: Value must be an integer between 0 and 25000.\n')
        else:
            if intmore < 0:
                goodLoop = False
                print('\nError: Value must be an integer between 0 and 25000.\n')
            elif intmore > 25000:
                goodLoop = False
                print('\nError: Value must be an integer between 0 and 25000.\n')
            else:
                goodLoop = True
                return intmore

def verifySSH(ip,user,pw,port,dtype):
    '''
    Input: SSH IP address, username, password, device type
    Action: SSH/login to specified address with given credentials.
    Output: True if SSH connection works, False if it fails in some way.
    '''
    # Create instance of SSHClient object
    run_pre = paramiko.SSHClient()
    # Automatically add untrusted hosts (make sure okay for security policy in your environment)
    run_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # initiate test SSH connection
    value = False
    if str(dtype) not in sfrclishList:
        try:
            run_pre.connect(ip, username=user, password=pw, look_for_keys=False, allow_agent=False, timeout=4, port=port)
        except:
            value = False
        else:
            value = True
    else:
        try:
            run_pre.connect(ip, username=user, password=pw, port=port)
        except:
            value = False
        else:
            value = True
    # Close connection
    run_pre.close()
    return value

#
# INTERACTIVE ASA PACKET CAPTURE
#

def shallWePlay(prompt):
    '''
    Input: Prompt to display to user
    Action: Get a yes or no answer w/r/t whether to take an ASA pcap
    Output: True if taking a pcap, False if not taking a pcap
    '''
    goodanswer = False
    while goodanswer == False:
        more = input(prompt)
        if more in NoList2:
            goodanswer = True
            return False
        elif more in YesList2:
            goodanswer = True
            return True
        else:
            goodanswer = False
            print('Please enter "Y" or "N".\n')

def pcap(asaip,port,user,pw,enpw,vb):
    '''
    Outline: This function steps in after we give the details for an ASA in the Main() loop and verify it.
                We'll ask if they want to run a packet capture. If yes, get a server for the ASA to dump the pcaps,
                the five-tuple, the interface, and an interval to run at.
    
    Input: The following should be passed from Main():
            IP address of ASA, dest port for SSH (if not 22), username, password, enable password,
            whether we're verbose.
           
           pcap() should get the following from the user:
            Five-tuple, interface (list nameifs on ASA for user and pass them back as a reminder),
            IP address for (t)ftp server to send captures to, 
    '''
    # Initialize list for nameifs
    nameifList = []
    # Initialize list of (ifc_id,nameif) tuples
    nameifTuples = []
    # Initialize ifc_id for for-loop
    ifc_id=0
    # Create instance of SSHClient object
    run = paramiko.SSHClient()
    # Automatically add untrusted hosts
    run.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # Connect to ASA
    run.connect(asaip, username=user, password=pw, port=port, look_for_keys=False, allow_agent=False)
    # Enable
    stdin, stdout, stderr = run.exec_command(('enable\n'+enpw+'\n'),bufsize=10000000)
    time.sleep(1)
    # Term page 0
    stdin.write("terminal page 0\n")
    stdin.flush()
    time.sleep(1)
    d_out1 = stdout.channel.recv(10000000)
    d_out2 = d_out1.decode('ISO-8859-1')
    # Get nameifs for dialogue
    stdin.write("show nameif\n")
    stdin.flush()
    d_out1 = stdout.channel.recv(10000000)
    d_out2 = d_out1.decode('ISO-8859-1')
    nameifList = d_out2.split('\n')
    # Get a list of nameifs and assign an ifc id to each one
    # So we can later verify that the nameif given is valid
    #
    for line in nameifList[2:]:
        noSpacesLine = line.split(' ')
        nameifTuples.append((ifc_id,noSpacesLine[1]))
        ifc_id +=1
    # Result = we now have a list of ASA nameifs, each assigned to an ifc id
    # inside nameifTuples, which now looks like [(0,'inside'),(1,'dmz'),(2,'outside')]
    #
    #
    # Give user a list of ASA nameifs to help with the capture tool
    print('\n\n Current interface names on device:\n')
    n = 1
    for line in nameifList[1:]:
        print(str(n) + '.     ' + str(line))
        n+=1
    ingress_ifc = input('Select the ingress interface (Enter a number from the list 1-'+str(n-1)+':\n\n')
    pass


#
# MAIN
#

def main():
    print(disclaimer)
    verbose = amVerbose(False,'\n\nRun in verbose mode? (y/N): ')
    #
    # SSH info
    #
    cmdchk = True
    goodIP = False
    goodSSH = False
    while goodIP == False:
        sship = input('IP of target host: ')
        goodIP = sanitize_ip(sship)
    sshport = getPort()
    deviceType = getDevice(False,'What type of device is this? (ASA/IOS/SFR/Unix): ')
    if str(deviceType) not in nixList:
        sshuser = getSSHlogin(False)
    sshpw = getpass.getpass('SSH Password: ')
    if str(deviceType) not in nixList:
        if str(deviceType) in sfrList:
            #Need a var for sshenpw, and since SFR's sudo pw IS the SSH pw...
            sshenpw = sshpw
        elif str(deviceType) == 'sfrclish':
            sshenpw = 'CLIshHasNoEnablePassword'
        else:
            sshenpw = getpass.getpass('Enable Password (leave blank if none): ')
    else:
        #ssh() doesn't like NoneType for this var
        #so it was honestly just easier to feed a dummy password to the ssh function than to make the infrastructure play nice natively
        sshenpw = 'UnixHasNoEnablePassword'
    while goodSSH == False:
        print('Testing connectivity...')
        goodSSH = verifySSH(sship,sshuser,sshpw,sshport,deviceType)
        if goodSSH == False:
            while goodSSH == False:
                print('Error connecting to remote host! Please re-enter IP address and credentials:\n')
                goodIP = False
                while goodIP == False:
                    sship = input('IP of target host: ')
                    goodIP = sanitize_ip(sship)
                sshport = getPort()
                sshuser = getSSHlogin(False)
                sshpw = getpass.getpass('SSH Password: ')
                print('Testing connectivity...')
                goodSSH = verifySSH(sship,sshuser,sshpw,sshport,deviceType)
                if goodSSH:
                    print('Success!')
        else:
            goodSSH = True
            print('Success!')
    #
    # Check whether we want to run a pcap
    #
    if str(deviceType) in asaList:
        upForCap = shallWePlay('\n\nWould you like to run a Packet Capture on this ASA? (y/N): ')
    if upForCap == True:
        pcap(sship,sshport,sshuser,sshpw,sshenpw,verbose)
    else:
        pass
    #
    # Commands to run on device
    #
    getCommand(False,'Enter a command to run on the target host: ')
    enough_cmds(False)
    if str(deviceType) not in nixList:
        if str(deviceType) not in sfrclishList:
            debugchk = sanitize_cmds(commandlist)
        else:
            debugchk = False
    else:
        debugchk = False
    #
    # Time
    #
    numberoftimes = getLoops('How many times should TaSc run? (0-25000; 0 = infinite loop): ')
    #
    # Log
    #
    print(('\n\nA directory called TaScLog has been generated on your Desktop. This program will '
           'write to a ring buffer of timestamped files in this directory and has been hard-coded '
           'not to exceed 120 files. This should allow sufficient space for approximately 10 hours of logs.'))
    #
    # Confirm
    #
    if numberoftimes != 0:
        print(('\nThe script will run the following commands:\n' + '\n'.join(commandlist) + '\n\n'
                + 'These commands will be run ' + str(numberoftimes) + ' times.\n\n'))
    else:
        print(('TaSc will run the following commands continuously, either until it is manually stopped '
               'with Ctrl+C or until it encounters an error:\n' + '\n'.join(commandlist) + '\n\n'))
    bigredbutton()
    #
    # PROGRESS BAR
    #
    #
    # Find how much we can increment progress bar every second
    # total time the full operation will take is equal to t
    # so t = (num of non-debug events * 45) + (num of debug events * 60)
    # and we will come up with a tvalue (sshtvalue), which is
    # the amount that we need to increment the bar every second to ensure
    # that we hit 75 units of bar in the anticipated amount of time.
    t = float(0)
    for cmd in commandlist:
        split3 = cmd.split(' ')   
        if split3[0] in debuglist:
            t += 60.0
        else:
            t += 45.0
    sshtvalue = float(75/t)
    #
    # Run
    #
    # Loop counters
    i = numberoftimes
    n = 1
    if verbose == True:
        logger.write('\n\n[' + str(datetime.datetime.now()) + '] Initializing main loop.\n')
        logger.write('\n\n[' + str(datetime.datetime.now()) + '] Vars: ' + 'sship=' + str(sship) +
                     ', sshuser=' + sshuser + ', commandlist=' + str(commandlist) + ', deviceType=' +
                     deviceType + ', debugchk=' + str(debugchk) + ', verbose='+str(verbose) + ', sshport=' +
                     str(sshport) + ', sshtvalue=' + str(sshtvalue) + '\n')        
        logger.close()
    else:
        pass
    #
    # MAIN LOOP
    #
    if i == 0:
        while True:
            print('Running TaSc event number ' + str(n) + '...')
            log = newLog()
            try:
                ssh(sship,sshuser,sshpw,sshenpw,commandlist,deviceType,debugchk,verbose,sshport,sshtvalue,log)
                print('Data for TaSc event ' + str(n) + ' written to log.')
                n += 1
            except:
                print ('\nTaSc encountered an error or an escape sequence was detected.'
                       '\nShutting down as gracefully as possible, given the circumstances.')
                log.write('\n\n[' + str(datetime.datetime.now()) + '] Detected an error or '
                             'escape sequence; exiting main loop.\n')
                log.close()
                sys.exit(0)
    else:
        while i > 0:
            print('Running TaSc event number ' + str(n) + '...')
            log = newLog()
            try:
                ssh(sship,sshuser,sshpw,sshenpw,commandlist,deviceType,debugchk,verbose,sshport,sshtvalue,log)
                i -= 1
                print('Data for TaSc event ' + str(n) + ' written to log.')
                n += 1
            except:
                print ('\nTaSc encountered an error or an escape sequence was detected.'
                       '\nShutting down as gracefully as possible, given the circumstances.')
                log.write('\n\n[' + str(datetime.datetime.now()) + '] Detected an error or '
                             'escape sequence; exiting main loop.\n')
                log.close()
                sys.exit(0)
    print('Thanks for using TaSc! Bye!\n')
    log.write('****************************\n****************************\n**************'
                 '**************\n****************************\n****************************\n['
                 + str(datetime.datetime.now()) + '] TaSc runtime gracefully shutdown.' +
                 '\n\nEnd of logging for this session.\n')
    log.close()
    exit()

if __name__ == "__main__":
    main()