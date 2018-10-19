#!/usr/local/bin/python3

import argparse  # simple command line argument parsing library
import re        # regular expression library for search/replace
import os        # os routines for reading/writing files

# create an argument parser object
parser = argparse.ArgumentParser(description='Simple script to hack the gcode from Prusa Slic3r v1.41.0 to drop temp during ram')

# add the arguments
parser.add_argument("-t", "--ram_temp",help="Ram temperature",type=int, default=180)
parser.add_argument("-nw", "--no_wait",    help="don't wait for stable temp",action="store_true")
parser.add_argument("-i", "--input",   help="input file", required=True)
parser.add_argument("-o", "--output",  help="output file", default="none")

# pull in the command line and parse all the arguments into the 'args' variable
args = parser.parse_args()


# turn the parsed arguments into clearly local variables
no_wait   = args.no_wait
ram_temp  = args.ram_temp

# get the input file specified, and turn it into a path variable for the current OS
inpath    = os.path.normpath(args.input)

# if there is no output specified, call it "..._ramcool.gcode" based off the input filename
if(args.output == "none"):
    outpath = os.path.normpath(os.path.splitext(inpath)[0] + "_ramcool.gcode")
else:
    outpath = os.path.normpath(args.output)

####################################

# open the input and output files (one read only, one for writing)
infile  = open(inpath, 'r')
outfile = open(outpath, 'w')

############
## set up the strings we are going to watch for, and the
##  strings we are going to add
############

# start at TOOLCHANGE START comment. "^" simply indicates "beginning of line"
start          = r"^; CP TOOLCHANGE START"

# if we are waiting, us M109.  Otherwise, M104.  This will be added
#  to the file just after the CP TOOLCHANGE START line
if(no_wait):
    start_addition = "M104 S%d ; set temp for Ram cooling, no wait\n"
else:    
    start_addition = "M109 R%d ; set temp for Ram cooling\n"
    

# the string that indicates the actual tool change (unload/load, after the ram)
end            = r"^T[0-9]"

# if we are waiting, us M109.  Otherwise, M104.  This will be added
#  to the file just before the "T" toolchange line
if(no_wait):
    end_addition   = "M104 S%s  ; restore temperature\n"
else:    
    end_addition   = "M109 R%s  ; restore temperature\n"

# string to check for any temperature changes.  Finds either m104 or m109, allows grabbing the temp
temperature_set = r"^M10[49] S([0-9]*)"

# turn those strings into compiled regular expressions so we can search
start_detect     = re.compile(start)
end_detect       = re.compile(end)
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
    end_match      = end_detect.search(line)
    
    # if we are at a line that set the temperature:
    if temp_set_match is not None:
        # "group(1)" of the temp_set_match will contain the
        #    temperature being set as a string variable ("200" or whatever)
        current_temp = temp_set_match.group(1)

        # output the temperature set line to the output file
        outfile.write(line)
        # output a comment line indicating we grabbed this temperature (debugging only)
        outfile.write(";matched temp! :" +  current_temp + "\n")


    # if we are in idle state and match the 'start' pattern        
    elif (state == "idle") and (start_match is not None):
        # output the start pattern line to the output file
        outfile.write(line)
        # add the "cool down" line, with the %d in the pattern replaced with the
        #   temperature specified on the command line
        outfile.write(start_addition % ram_temp )

        # remember that we are currently in the 'temp dropped' state
        state = "cooled"

    # if we are already in 'cooled' state (temperature dropped) and we detect
    #    the 'end' pattern (tool change):
    elif (state == "cooled") and (end_match is not None):

        # output the "restore temperature" string, with the most recently
        #    detected temperature in the original gcode
        outfile.write(end_addition % current_temp)

        # don't forget to output the tool change line
        outfile.write(line)

        # go back to printing state (normal temperature)
        state = "idle"

    else:
        # if we haven't matched one of the magic patterns, just print
        # the normal line
        outfile.write(line)
        





