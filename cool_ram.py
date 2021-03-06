#!/usr/local/bin/python3

import argparse  # simple command line argument parsing library
import re        # regular expression library for search/replace
import os        # os routines for reading/writing files

import sys

from io import open


if (sys.version_info > (3, 0)):
    # Python 3 code in this block
    python3 = True
else:
    # Python 2 code in this block
    python3 = False

python2 = not python3
 

def fileWrite(file, string):
    if(python3):
        file.write(string)
    else:
        file.write(unicode(string))
        
# create an argument parser object
parser = argparse.ArgumentParser(description='Simple script to hack the gcode from Prusa Slic3r v1.41.0 to drop temp during ram',
                                 epilog = """
Example usage:
-----------
Example #1: Cool to 195 for ramming.  Stabilize at 195 before ram,
  stabilize at print temp just after tool change
  
#$ cool_ram.py -t 195    -i input.gcode -o output.gcode

-----------
Example #2: Set temp to 180 (default temp) for ram, but don't wait
  for it to stabilize.  This basically just cuts power to the nozzle
  and immediately starts ramming.  After the tool change, it restores
  temperature to the print temp, but doesn't wait for it to stabilize.

#$ cool_ram.py -nwr -nwt -i input.gcode -o output.gcode

-----------
Example #3: Same as previous, but allow the temp to stabilize
  just after the tool change before printing with the new filament.
  Might be a good idea if nozzle isn't getting hot quickly enough.

#$ cool_ram.py -nwr -i input.gcode -o output.gcode

                                 """,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)

# add the arguments
parser.add_argument("-t",    "--ram_temp",              help="Ram temperature",type=int, default=180)
parser.add_argument("-nwr",  "--no_wait_ram",           help="don't wait for stable temp when starting the ram sequence",action="store_true")
parser.add_argument("-nwt",  "--no_wait_tc",            help="don't wait for stable temp before printing with the new filament (after the tool change)",action="store_true")
parser.add_argument("-fs",   "--full_stabilization_tc", help="wait for full stable temperature before initiating the tool change",action="store_true")
parser.add_argument("--temp_change_override",           help="Retain the Slic3r inserted temperature after ramming and before tool change (default false) ",action="store_true")
parser.add_argument("-i",    "--input",                 help="input file", required=True)
parser.add_argument("-o",    "--output",                help="output file", default="none")
parser.add_argument("-b",    "--beep_after_tc",         help="beep after tool change (for tip inspection)",action="store_true")

# pull in the command line and parse all the arguments into the 'args' variable
args = parser.parse_args()


# turn the parsed arguments into clearly labelled local variables
ram_temp               = args.ram_temp
full_stabilization_tc  = args.full_stabilization_tc
no_wait_ram            = args.no_wait_ram
temp_change_override   = args.temp_change_override
beep                   = args.beep_after_tc

if(full_stabilization_tc):
    no_wait_tc = False
else:
    no_wait_tc = args.no_wait_tc

# get the input file specified, and turn it into a path variable for the current OS
inpath    = os.path.normpath(args.input)

# if there is no output specified, call it "..._ramcool.gcode" based off the input filename
if(args.output == "none"):
    outpath = os.path.normpath(os.path.splitext(inpath)[0] + "_ramcool.gcode")
else:
    outpath = os.path.normpath(args.output)

####################################

# open the input and output files (one read only, one for writing)
infile  = open(inpath, 'r', encoding="utf8")
outfile = open(outpath, 'w', encoding="utf8")

############
## set up the strings we are going to watch for, and the
##  strings we are going to add
############

# start at TOOLCHANGE START comment. "^" simply indicates "beginning of line"
start          = r"^; CP TOOLCHANGE START"

# if we are waiting, us M109.  Otherwise, M104.  This will be added
#  to the file just after the CP TOOLCHANGE START line
if(no_wait_ram):
    start_addition = "M104 S%d ; set temp for Ram cooling, no wait\n"
else:    
    start_addition = "M109 R%d ; set temp for Ram cooling\n"
    

# the string that indicates the actual tool change (unload/load, after the ram)
end1           = r"^T[0-9]"
end2           = "^; CP TOOLCHANGE END"

# Three options for the end:

# -full_stabilization_tc specified
#    m109 before tool change
#
# default (no options)
#    m104 before tool change
#    m109 after  tool change

# -no_wait_tc specified
#    m104 before tool change

if(beep):
    beep_addition = "M300\n"
else:
    beep_addition = ""
    
if(full_stabilization_tc):
    pre_tc_addition  = "M109 R%s  ; restore temperature, stabilize before TC\n"
    post_tc_addition = ""
    
elif(no_wait_tc):
    pre_tc_addition  = "M104 S%s  ; restore temperature\n"
    post_tc_addition = ""
else:    # default
    pre_tc_addition  = "M104 S%s  ; restore temperature before TC\n"
    post_tc_addition = "M109 R%s  ; restore temperature stabilize after TC\n"

# string to check for any temperature changes.  Finds either m104 or m109, allows grabbing the temp
temperature_set = r"^M10[49] S([0-9]*)"

# turn those strings into compiled regular expressions so we can search
start_detect     = re.compile(start)
end1_detect       = re.compile(end1)
end2_detect       = re.compile(end2)
temp_set_detect  = re.compile(temperature_set)

# current temp will track the most recently set temperature in the original gcode
#  which will be used for restoring.  Set to 0 to start
current_temp = 0

# Two "states" for the program:
#   idle:   we are in normal printing mode (start here)
#   cooled: we have dropped the temp and are ramming
state = "idle"


# walk through each line in the file
for line in infile:

    # see if the current line matches any of the start/end/temp_set patterns
    temp_set_match = temp_set_detect.search(line)
    start_match    = start_detect.search(line)
    end_match      = end1_detect.search(line) or end2_detect.search(line)
    
    # if we are at a line that set the temperature:
    if temp_set_match is not None:
        # "group(1)" of the temp_set_match will contain the
        #    temperature being set as a string variable ("200" or whatever)
        current_temp = temp_set_match.group(1)
        
        # output a comment line indicating we grabbed this temperature (debugging only)
        fileWrite(outfile,";matched temp! :" +  current_temp + "\n")

        # if this temperature change is happening in the 'cooled' state,
        #  it is adjusting the temperature for the next filament, and
        #  likely doing it too soon.  We'll delete that and depend on the
        #  temperature change near the actual tool change

        # if we aren't in cooled state, print the temperature change
        #   if we are in cooled state, but the temp_change_override option is set, print the temperature change
        if(  (state != "cooled") or (temp_change_override)):
            # output the temperature set line to the output file
            fileWrite(outfile,line)

    # if we are in idle state and match the 'start' pattern        
    elif (state == "idle") and (start_match is not None):
        # output the start pattern line to the output file
        fileWrite(outfile,line)
        # add the "cool down" line, with the %d in the pattern replaced with the
        #   temperature specified on the command line
        fileWrite(outfile,start_addition % ram_temp )

        # remember that we are currently in the 'temp dropped' state
        state = "cooled"

    # if we are already in 'cooled' state (temperature dropped) and we detect
    #    the 'end' pattern (tool change):
    elif (state == "cooled") and (end_match is not None):
        
        # output the "restore temperature" string, with the most recently
        #    detected temperature in the original gcode
        fileWrite(outfile,pre_tc_addition % current_temp)

        # don't forget to output the tool change line
        fileWrite(outfile,line)

        # output the "stabilization" temp if needed
        if(post_tc_addition != ""):
            fileWrite(outfile,post_tc_addition % current_temp)

        if(beep):
            fileWrite(outfile,beep_addition)

        # go back to printing state (normal temperature)
        state = "idle"

    else:
        # if we haven't matched one of the magic patterns, just print
        # the normal line
        fileWrite(outfile,line)
        

# at the end,         





