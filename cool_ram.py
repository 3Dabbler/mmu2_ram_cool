#!/usr/local/bin/python3

import argparse
import re
import os

# cool_ram.py temp infile outfile
# cool_ram.py -t 170 testin.gcode testout.gcode


parser = argparse.ArgumentParser()

parser.add_argument("-t", "--ram_temp",help="Ram temperature",type=int, default=180)
parser.add_argument("-nw", "--no_wait",    help="don't wait for stable temp",action="store_true")
parser.add_argument("-i", "--input",   help="input file", required=True)
parser.add_argument("-o", "--output",  help="output file", default="none")

args = parser.parse_args()

inpath    = os.path.normpath(args.input)
no_wait      = args.no_wait
ram_temp = args.ram_temp

if(args.output == "none"):
    outpath = os.path.normpath(os.path.splitext(inpath)[0] + "_ramcool.gcode")
else:
    outpath = os.path.normpath(args.output)

print(ram_temp, no_wait, inpath, outpath)

####################################

infile  = open(inpath, 'r')
outfile = open(outpath, 'w')


# watch all m104 lines, keep track of current desired tempperature
# track two temperatures:
#  current_temp
#  ram_temp

# start at TOOLCHANGE START comment
start          = r"^; CP TOOLCHANGE START"

if(no_wait):
    start_addition = "M104 S%d ; set temp for Ram cooling, no wait\n"
else:    
    start_addition = "M109 R%d ; set temp for Ram cooling\n"
    

# end before the actual tool change (and hopefully heat back up before the next move)
end            = r"^T[0-9]"

if(no_wait):
    end_addition   = "M104 S%s  ; restore temperature\n"
else:    
    end_addition   = "M109 R%s  ; restore temperature\n"


temperature_set = r"M104 S([0-9]*) "

# set up regex

start_detect     = re.compile(start)
end_detect       = re.compile(end)
temp_set_detect  = re.compile(temperature_set)

current_temp = 0
state = "idle"

for line in infile:

    
    temp_set_match = temp_set_detect.search(line)
    if temp_set_match is not None:
        # matched a temperature set
        current_temp = temp_set_match.group(1)
        outfile.write(line)
        outfile.write(";matched temp! :" +  current_temp + "\n")

    start_match = start_detect.search(line)
    if (state == "idle") and (start_match is not None):
        outfile.write(line)
        outfile.write(start_addition % ram_temp )
        state = "cooled"
    
    end_match   = end_detect.search(line)
    if (state == "cooled") and (end_match is not None):
        outfile.write(end_addition % current_temp)
        outfile.write(line)
        state = "idle"
        





