#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# plcCalibration
# This program accepts two or more engineering units (EU) vs count values, and
# determines a linear curve fit to the given values.  Outputs are:
# the measured counts and the measured EU values (given as inputs),
# The min and max configured PLC counts and EU values (given as inputs),
# The calculated EU min and max at the min and max PLC counts.

# A curve fit is performed for the measured values. Plotted along with the
# measured points is the nominal line, and the curve fit line. The curve fit is
# done according to the degree of the resulting polynomial specified with the
# -d/--degree option. Default is degree 1 (linear).

# The input values are taken from a file specified with the -i or
# --inputFileName paraemeter.  The input file is expected to be a single
# dictionary {}, or a list of one or more dictionaries [{}, ...{}], with one
# dictionary per instrument in the form:
# Key               Datatype
# 01_instName:      string
# 02_calDate:       string (MM/DD/YYYY HH:mm:ss)
# 03_EuUnits:       string
# 04_minMaxCounts:  list [min, max] Ints.
# 05_minMaxEu:      list [min, max]. Reals
# 06_actCounts:     [c1, ... cn] (list of ints)
# 07_actEus:        [e1, ... en] (list of reals)
# 08_notes:         string
# 09_Equipment:     string
# 10 docTitle:      string
#
# where actCounts and actEus should be the same length

# Command line paraemters are:
# inputFileName (required, first positional). The name of the file where the
# calibration data is stored (i.e. the file where the above dictionary is defined.
#
# outputFilePrefix (reqiured, second positional). The prefix of the output file
# where information about the calibration is written. The instrument is
# appended to the specified output file name.  Also used as a file name when
# creating an input file tmeplate.
#
# --degree (optional, default value = 1) The degree polynomial to use. The 
# default value of 1 creates a 1 degree, linear polynomial.
#
# --simulate (optional) input count values are ignored, and count values
# are simulated from the give EU values. Some random 'noise' is added to the
# simulated count values.
#
# -c Create input file (optional). Creates a input file to be used as a
# template.  Uses the file name specified with the -o or outpuFilePrefix
# option.
#
# -verbose (optional) sends the same info going to the output file to the
# screen.
#
# Libraries used:
# deepcopy, argparse
# numpy (1.15.3), scipy (1.1.0), matplotlib (3.0.0)
# json
#
# imports
from copy import deepcopy

# import arg parser
import argparse

# import numerical manipulation libraries
from scipy import stats, polyval, polyfit
import numpy as np
import matplotlib.pyplot as plt # for plotting

# read and write in JSON format
import json

# user libraries
# Note: May need PYTHONPATH (set in ~/.profile?) to be set depending
# on the location of the imported files
from bpsMath import oomFloor, oomCeil, polyPrettyPrint

# **** argument parsing
# define the arguments
# create an epilog string to further describe the input file
eplStr="""The format of the input file specified with the -i or inputFileName
parameter should be a list of dictionaries, or a single dictionary. Below 
shows the configuration as a list with two elements. The first element is a
dictionary for 'Instrument A' and the second element is a dictionary for
'Instrument B'. If only one instrument is being configured, the input file
can contain a list with only a single element, or just a single dictionary,
not in the [] notation.\n
[{'01_instName': 'Instrument A',
  '02_calDate': '10/5/2017 12:10',
  '03_EuUnits': 'units',
  '04_minMaxCounts': (0, 32767),
  '05_minMaxEu': (0.0, 100.0),
  '06_actCounts': [1265, 12093, 26989],
  '07_actEus': [0.0, 50.0, 90.0],
  '08_notes': 'calibration notes',
  '09_equipment': 'equipment notes',
  '10_docTitle': 'Document Title'},
 {'01_instName': 'Instrument B',
  '02_calDate': '10/5/2017 12:10',
  '03_EuUnits': 'units',
  '04_minMaxCounts': (-27648, 27648),
  '05_minMaxEu': (-100.0, 100.0),
  '06_actCounts': [1265, 5209, 10093, 22345, 26989],
  '07_actEus': [-90.0, -50.0, 0.0, 50.0, 90.0],
  '08_notes': 'calibration notes',
  '09_equipment': 'equipment notes',
  '10_docTitle': 'Document Title'}]\n
  NOTE: The key values must not be modified.
  NOTE: The minMaxCounts and miunMaxEU are tuples, while the \
actCounts and actEus are lists and should be the same length as each other.\
"""

descrStr="Linear curve fit of measured calibration data (EU vs counts)."

# define the type definition function for the degree argument option
# degree must be an integer >= 1
# Accept anything convertable to an integer, but also make sure it is >= 1
def intDegree(degArg):
    value=int(degArg)
    if not isinstance(value, int) or value < 1:
        msg = "The --degree argument, value %r, is not an integer >=1" % degArg
        raise argparse.ArgumentTypeError(msg)
    return value

parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, \
                                 description=descrStr,
                                 epilog=eplStr)
parser.add_argument('inputFileName', default='', \
                    help='Input file containing calibration data as a \
single dictionary {} or list of dictionaries [{}, ... {}]')
parser.add_argument('outputFilePrefix', default='', \
                    help= 'Output file prefix where calibration data and \
plot are saved.  The created file names will be this prefix appended with an \
underscore(_) and the instrument name. The calibration data filename will \
end in .txt, and the plot will be saved as a pdf and the filename will \
end in .pdf.')
parser.add_argument('--degree', default=1, type=intDegree, \
                    metavar='', help='Polynomial degree used to \
curve fit the data. Default value is 1 for linear curve fit.')
parser.add_argument('--simulate', action='store_true', default=False, \
                    help='Ignore given count values \
and simulate (noisy) count values at given EU values.')
parser.add_argument('-c', action='store_true', default=False, \
                    help='Create an input file to use as a template. Uses \
the file name specified with the -o or outputFilePrefix option.')
parser.add_argument('-v', action='store_true', default=False, \
                    help='Print calibration data to the terminal, and \
display the generated plot.')
# parse the arguments
args = parser.parse_args()

# At this point, the arguments will be:
# Argument          Values      Description
# args.c            True/False  Create a template input file
# args.degree       integers    Polynomial degree
# args.inputFileName    string  file to get cal data from
# args.outputFilePreix  string  file to write cal data to
# args.simulate     True/False  Simulate count values 
# args.v            True/False  Print calibratoin data to the terminal

# **** Create an input template file if the -c argument was specified.
# The -o filename also needs to be specified. Once done, exit either way.
if (args.c and args.outputFilePrefix != ''):
    calData=[{'01_instName': 'Instrument A',
              '02_calDate': '10/5/2017 12:10',
              '03_EuUnits': 'units',
              '04_minMaxCounts': (0, 32767),
              '05_minMaxEu': (0.0, 100.0),
              '06_actCounts': [1265, 12093, 26989],
              '07_actEus': [0.0, 50.0, 90.0],
              '08_notes': 'calibration notes',
              '09_equipment': 'equipment notes',
              '10_docTitle': 'Document Title'},
             {'01_instName': 'Instrument B',
              '02_calDate': '10/5/2017 12:10',
              '03_EuUnits': 'units',
              '04_minMaxCounts': (-27648, 27648),
              '05_minMaxEu': (-100.0, 100.0),
              '06_actCounts': [1265, 5209, 10093, 22345, 26989],
              '07_actEus': [-90.0, -50.0, 0.0, 50.0, 90.0],
              '08_notes': 'calibration notes',
              '09_equipment': 'equipment notes',
              '10_docTitle': 'Document Title'}]
    with open(args.outputFilePrefix, 'w') as outfile:
        json.dump(calData, outfile, sort_keys=True, indent= 4)
        outfile.close()
    quit()
elif(args.c and args.outputFilePrefix == ''):
    print('An output file name must be specified when using \
the create template (-c) option.')
    quit()

# *** Check for an input file.  It is required in all cases except for the
# template creation option handled above.
if args.inputFileName == '':
    print('An input file name must be specified.')
    quit()

# **** Read from the specified input file
# Set calData up to be an empty list, and then extend it by what is read.
# This is done so the input file can be a properly formed dictionary or a list
# of dictionaries, and the resulting calData should always be a list, perhaps
# with only one element.
calData=[]
with open(args.inputFileName, 'r') as infile:
    inData= json.load(infile)
    infile.close()
    # deal with the list of dictionaryies, or the single dictionary case
    if (type(inData) is list):
        # presumably a list of dictionaries
        # Use extend to add list elements. Append would put a list in a list
        calData.extend(deepcopy(inData))
    elif (type(inData) is dict):
        # A single dictionary entry. Append the dict object to the list.
        # Extend would make a list of dictionary keys.
        calData.append(deepcopy(inData))
    else:
        print('Invalid input data. Exiting.')
        quit()

# **** Loop thru the list from the file.  It should be a list of dictionaries,
# with one list entry per instrument.
for instr in calData:

    # **** Unpack the dictionary entry into into NumPy
    # friendly datatypes and local variables
    # verify notes, equipment, and doc title are present. Treat them as
    # optional
    if '10_docTitle' in instr:
        docTitle= instr['10_docTitle']
    else:
        docTitle= instr['01_instName'] + ' Calibration'
    InstName= instr['01_instName']
    EuUnitsLabel= instr['03_EuUnits']
    calDate= instr['02_calDate']
    if '08_notes' in instr:
        calNotes= instr['08_notes']
    else:
        calNotes= ''
    if '09_equipment' in instr:
        equipNotes= instr['09_equipment']
    else:
        equipNotes= ''

    # Print a user friendly message showing what instrument is being processed
    print('Processing ' + InstName)

    # **** Get Min and Max values for EU and counts.
    # Counts would be integers, except making them floats allows
    # usage of the numpy.interp and other functions
    minMaxEu = np.array(instr['05_minMaxEu'])
    minMaxCounts = np.array(instr['04_minMaxCounts'])

    # **** Get empirical (actual) values determined during calibration.
    actEus = np.array(instr['07_actEus'], dtype=np.float32)
    actCounts = np.array(instr['06_actCounts'], dtype=np.int32)

    # **** Simulate count values for given EU values if the -s or --simulate
    # option is specified.
    # Create count values based on actual EU values.
    if args.simulate:
        # Generate some fake empirical data. Normally this will be
        # entered up above. For the entered EU values generate some counts
        # values based on the nominal slope and intercept, but include
        # some noise as an artificial error.

        # Use interp to interpolate count values given EU values.
        # For this, the EU is the x-axis, and the counts are the y-axis
        actCounts = np.interp(actEus, minMaxEu, minMaxCounts)
        # and then randomize them a bit
        for idx, actCount in enumerate(actCounts):
             # make sure min < max
            if actCount < 0:
                # make sure min < max
                actCounts[idx] = np.random.randint(actCount * 1.2, \
                                                   actCount * 0.8)
            elif actCount > 0:
                actCounts[idx] = np.random.randint(actCount * 0.8, \
                                                   actCount * 1.2)
            else:
                # at zero
                actCounts[idx]= 0
        # convert the counts back to integers. Round first just to be safe
        actCounts=np.round(actCounts, decimals=0).astype(np.int32)
    # **** End Simulate section

    # **** Generate nominal EU values
    # Generate some EU values at a hand full of count values between min/max
    # Interpolate given the min/max counts and EU values
    nomCounts = np.linspace(minMaxCounts[0], minMaxCounts[1], 5, dtype=np.int32)
    nomEus = np.interp(nomCounts, minMaxCounts, minMaxEu)

    # **** Curve fit the empirical data
    # Curve fit the empirical data to a polynomial of the degree specified.
    # polyfit returns the coefficients (highest power first)
    # given the data set and a degree
    coeffs = polyfit(actCounts, actEus, args.degree)
    # Get the calc values and errors at the measured (emperical) points
    calcVals= np.polyval(coeffs, actCounts) 
    empErrors = calcVals - actEus
    # get a polynomial object so we can print it, and so we can get the roots
    # and compensate for a count offset below
    empPoly = np.poly1d(coeffs)
    empPolyDegree = empPoly.order
    # make a curve fit line which spans the nominal count values 
    empLine = polyval(coeffs, nomCounts)
    # get curve fit values at count min/max
    empMinMax = polyval(coeffs, minMaxCounts)

    # **** Compensate for a non-zero count at zero EU, which is essentially the
    # x-intercept of the EU axis.  Get the offset, and apply it to the measured
    # count values, and curve fit to get a new formula.
    # Create a 1 dimensional polynomial object, and get the roots. If the degree
    # (--degree option) of the polynomial is 1, the root will be a scalar (a
    # single value). 
    # If the degree of the polynomial is > 1, there are more than 1 root. Assume
    # root closest to zero (the others may be wild!) is the one we want. 
    # In both these cases, the root is the value of x (counts) where Y (EU) is zero.
    countOffset = (empPoly).roots
    # if degree is one, count offset is a single value, and can be used directly.
    # Otherwise, find the root closest to zero and use it.
    if args.degree > 1:
        idx = (np.abs(countOffset)).argmin()
        countOffset = countOffset[idx] # root closest to zero

    # Shift the measured count values by this offset.
    # NOTE: This works because the code above takes into account the polynomial
    # degree, and makes sure we have a single root at this point.
    offsetCounts = (np.round(actCounts - countOffset,
                    decimals=0)).astype(np.int32)
    # Make a curve fit for the new line. This is a bit heavy-handed for lines 
    # (one degree polynomials), since this could be done by adjusting count
    # values, and not doing an additional curve fit, but do this so it handles
    # the higher degree polynomial cases.
    offsetCoeffs = polyfit(offsetCounts, actEus, args.degree)
    # get a polynomial object so we can print it
    offsetPoly = np.poly1d(offsetCoeffs)
    # make a new line using the new offset curve fit. Span the nominal counts.
    offsetLine = polyval(offsetCoeffs, nomCounts)
    # get offset values at count min/max
    offsetMinMax = polyval(offsetCoeffs, minMaxCounts)

    # **** Create string to write to the terminal or a file depending on the -v
    # and -o arguments. 
    # outputFilePrefix is not empty. If it is empty, then don't write to a
    # file.
    if args.outputFilePrefix != '' or args.v:
        fname = args.outputFilePrefix + '_' + InstName + '.txt'
        outputMsg = '*' * 70 + '\n'
        outputMsg += 'Traveler Number _____________________________________________________\n\n'
        outputMsg += 'Traveler Operation(s) _______________  Traveler Page(s) _____________\n\n'
        outputMsg += docTitle + '\n\n'
        outputMsg += 'Nominal and Actual Calibration Data\n'
        outputMsg += InstName + '\n'
        outputMsg += calDate + '\n\n'
        outputMsg += 'Equipment Used: ' + equipNotes + '\n\n'
        outputMsg += 'NOTE: ' + calNotes + '\n\n'
        outputMsg +='{:37} {:9d} {:9d}\n' \
                .format('Min and Max PLC Nominal Counts: ', minMaxCounts[0], \
                                                    minMaxCounts[1])
        outputMsg += '{:37} {:9.2f} {:9.2f} \n\n' \
                .format('Min and Max Nominal EU (' + EuUnitsLabel + '): ', \
                        minMaxEu[0], minMaxEu[1])
        # Measured counts vs Measured EU table
        outputMsg +='{:16}  {:30}\n'.format('Measured Counts', \
                                    'Measured EU (' + EuUnitsLabel + ')')
        outputMsg +='{:16}  {:30}\n'.format('_' * 15, '_' * 30)
        # loop thru the counts and print a list of counts vs eu values
        for idx in range(actCounts.size):
            outputMsg +='{: <16d}  {: <30.2f}\n'.format(actCounts[idx], \
                                                          actEus[idx])
        outputMsg += '\nThe least squares fit {:d} degree polynomial is:\n' \
                    .format(empPolyDegree)
        outputMsg += polyPrettyPrint(coeffs) + '\n\n'
        # Measured EU vs Calc EU vs Error table
        outputMsg +='{:11}  {:11}  {:23}\n'.format('Measured EU', \
                                                  'Calc''d EU', \
                                                  'Error    % of EU Range')
        outputMsg +='{:11}  {:11}  {:23}\n'.format('_' * 11, '_' * 11, '_' * 23)
        # loop thru the counts and print a list of counts vs eu values and %error
        # calc eu range so it can be used to calc error pct
        euRange = minMaxEu[1] - minMaxEu[0]
        for idx in range(actCounts.size):
            # calc error and pct error
            error= empErrors[idx]
            errorPct = (error / euRange) * 100.0
            outputMsg +='{: <11.2f}  {: <11.2f}  {: >8.3f}   {: >8.3f}%\n' \
                                                            .format(actEus[idx], 
                                                                   calcVals[idx],
                                                                   error,
                                                                   errorPct)
        outputMsg += '\nCalibrated engineering units for the min and max \n'
        outputMsg += 'PLC counts are as follows:\n'
        outputMsg += 'EU at min and max PLC Counts:  {:11.4f}   {:11.4f}\n\n' \
                .format(empMinMax[0], empMinMax[1])
        outputMsg += 'Compensate for a non-zero count value at zero EU.\n'
        outputMsg += 'Shift the curve fit up or down by the count value of \n'
        outputMsg += 'the zero EU value (the x-intercept of EU axis).\n'
        outputMsg += 'The adjusted count values vs EU values are:\n\n'
        # Adjusted counts vs Measured EU table
        outputMsg +='{:16}  {:30}\n'.format('Adjusted Counts', \
                                    'Measured EU (' + EuUnitsLabel + ')')
        outputMsg +='{:16}  {:30}\n'.format('_' * 15, '_' * 30)
        # loop thru the counts and print a list of counts vs eu values
        for idx in range(actCounts.size):
            outputMsg +='{: <16d}  {: <30.2f}\n'.format(offsetCounts[idx], \
                                                        actEus[idx])
        outputMsg += '\nThe least squares fit {:d} degree polynomial \
for the adjusted counts is:\n'.format(empPolyDegree)
        outputMsg += polyPrettyPrint(offsetCoeffs) + '\n\n'

        outputMsg += 'Calibrated engineering units for the adjusted \n'
        outputMsg += 'min and max PLC counts are as follows:\n'
        outputMsg += 'EU at min and max PLC Counts:  {:11.4f}   {:11.4f}\n' \
                .format(offsetMinMax[0], offsetMinMax[1])
        outputMsg += '\n\n\nMfg Sign/Date  ' + '_' * 50 + '\n\n\n'
        outputMsg += 'QA Sign/Date   ' + '_' * 50 + '\n\n\n'
        outputMsg +='*' * 70 + '\n'

        # output to a file if the -o option is used
        if args.outputFilePrefix != '':
            outFile = open(fname, 'a+')
            outFile.write(outputMsg)
            outFile.close()

        # output to the terminal if the -v option is used
        if args.v:
            print(outputMsg)

    # **** End writing to file or the terminal
    #
    # **** Plot the data

    # get a figure and a single sub-plot to allow better control
    # than using no sub-plots
    fig, ax = plt.subplots()

    # set the titles
    fig.suptitle('Nominal and Actual Calibration Curves', \
                fontsize=14, fontweight='bold')
    plt.title(InstName + '    ' + calDate, fontsize=12, fontweight='bold')
    ax.set_xlabel('counts')
    ax.set_ylabel('Engineering Units (EU)\n' + EuUnitsLabel)

    # make additional room for the labels
    plt.subplots_adjust(left=0.18, bottom=0.18)
    # plot horizontal and vertical lines at zero
    plt.axhline(0, color='black', linewidth = 0.5) 
    plt.axvline(0, color='black', linewidth = 0.5) 

    # add the data to the plot
    # plot the measurments as points
    ax.plot(actCounts, actEus, color='blue', \
            linewidth=1.0, linestyle='', \
            markersize=2.8, marker='x', label='meas.')
    # plot the nominal line
    ax.plot(nomCounts, nomEus, color='green', \
            linewidth=1.0, linestyle='-', marker='', label='nominal')
    # plot the curve fit line
    ax.plot(nomCounts, empLine, color='red', \
            linewidth=1.0, linestyle='-', marker='', label='crv. fit')
    # plot the offset curve fit line
    ax.plot(nomCounts, offsetLine, color='orange', \
            linewidth=1.0, linestyle='-', marker='', label='offset')
    # plot the errors at the measured points
    ax.plot(actCounts, empErrors, color='red', \
            linewidth=1.0, linestyle='', \
            markersize=2.8, marker='x', label='error')
    # annotate (label) each error marker with the error value
    # for each coord of a error marker, place an annotation with an offset
    # create a text style
    txStyle = dict(fontsize=6, color='gray', horizontalalignment='center')
    for c,e in zip(actCounts, empErrors):
        ax.annotate('{:0.4G}'.format(e), xy=(c,e), xytext=(0,-8),
                   textcoords='offset points', **txStyle)
    

    # set the legend
    ax.legend(loc='upper left', frameon=True)

    # Set axis limits. Extend a bit past the min/max values
    # Consider the nominal and actual when determining min/max limits.
    # Use oomFloor and oomCeil to "auto scale" the axes, rounding up 
    # and down to the next boundry value in the same order of magnatude
    axCountsMin = oomFloor(min(minMaxCounts[0], np.amin(actCounts)))
    axCountsMax = oomCeil(max(minMaxCounts[1], np.amax(actCounts)))
    axEuMin = oomFloor(min(minMaxEu[0], np.amin(actEus), np.amin(empErrors)))
    axEuMax = oomCeil(max(minMaxEu[1], np.amax(actEus), np.amax(empErrors)))
    countRange = (axCountsMax - axCountsMin)
    euRange = (axEuMax - axEuMin)
    plt.xlim(axCountsMin - (countRange * 0.05), \
             axCountsMax + (countRange * 0.05))

    plt.ylim(axEuMin - (euRange * 0.05), \
             axEuMax + (euRange * 0.05))

    # set x and y ticks

    # create a two line x-axis labeling with the counts on the top and the 
    # percentages on the bottom
    # first get the values (counts)
    xAxVals=np.linspace(axCountsMin, axCountsMax, 5, endpoint = True)
    # force the x axis value to be integers
    xAxValss=xAxVals.astype(np.int32)
    # then use list comprehension to get corresponding percentages
    xAxPct=[(((x - axCountsMin) / countRange) * 100) for x in xAxVals]
    # now append them into a string
    xAxLabels=[]
    for idx in range(len(xAxVals)):
        xAxLabels.append(str(xAxVals[idx]) + '\n' + str(xAxPct[idx]) + '%')

    plt.setp(ax, \
            xticks=(np.linspace(axCountsMin, \
                    axCountsMax, 5, endpoint = True)),
            xticklabels=xAxLabels,
            yticks=(np.linspace(axEuMin, axEuMax, 9, endpoint = True)))


    # show the grid
    ax.grid(b=True, which='both', linewidth=0.5, linestyle='-.')

    # Save the plot if the outFilePrefix is not empty. If it is empty, don't
    # save the plot.
    if args.outputFilePrefix != '':
        fname= args.outputFilePrefix + '_' + InstName + '.pdf'
        plt.savefig(fname, orientation='portrait', papertype='letter',
                   format='pdf', transparent=False, frameon=False,
                   bbox_inches='tight', pad_inches=0.25)

    # Draw the plot if the -v option is set. The user will close the plot.
    # Otherwise close the plot so it no longer consumes memory
    if args.v:
        plt.show()
    else:
        plt.close()

