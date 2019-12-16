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
# 04_minMaxCounts:  list [min, max] Reals or Ints that get converted to reals.
# 05_minMaxEu:      list [min, max]. Reals
# 06_actCounts:     [c1, ... cn] (list of reals or ints that get converted to reals)
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
# -c Create input file (optional). Creates a input file to be used as a
# template.  Uses the file name specified with the -o or outpuFilePrefix
# option.
#
# -verbose (optional) sends the same info going to the output file to the
# screen.
#
# Libraries used:
# copy -- for copying elements
# os -- file delete
# argparse -- cli arg parser
# numpy (1.15.3), scipy (1.1.0), matplotlib (3.0.0)
# json -- read and write JSON
# -- pdf creation and merging
# pyfpdf (fpdf)
# PyPdf2
#
# imports
from copy import deepcopy

import os # file delete

# import arg parser
import argparse

# import numerical manipulation libraries
from scipy import stats, polyval, polyfit
import numpy as np
import matplotlib.pyplot as plt # for plotting
import matplotlib.font_manager as fontmgr # for managing fonts

# read and write in JSON format
import json

# pdf creation
from fpdf import FPDF
# pdf manipulation
from PyPDF2 import PdfFileMerger, PdfFileReader

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
    # Counts may be integers or floats. Making them floats allows
    # usage of the numpy.interp and other functions
    minMaxEu = np.array(instr['05_minMaxEu'], dtype=np.float32)
    minMaxCounts = np.array(instr['04_minMaxCounts'], dtype=np.float32)

    # **** Get empirical (actual) values determined during calibration.
    actEus = np.array(instr['07_actEus'], dtype=np.float32)
    actCounts = np.array(instr['06_actCounts'], dtype=np.float32)

    # **** Generate nominal EU values
    # Generate some EU values at a hand full of count values between min/max
    # Interpolate given the min/max counts and EU values
    nomCounts = np.linspace(minMaxCounts[0], minMaxCounts[1], 5, dtype=np.float32)
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
    # offsetCounts = (np.round(actCounts - countOffset,
                    # decimals=0)).astype(np.int32)
    offsetCounts = actCounts - countOffset
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
    # argument, or if the outputFilePrefix is not empty.
    # If it is empty, then don't write to a file.
    if args.outputFilePrefix != '' or args.v:
        fnameData= '__zzqq__plcCalData.pdf' # not likely to exist and be something else
        # **** Page 1
        outputMsgp1 = '*' * 70 + '\n'
        outputMsgp1 += 'Traveler Number _____________________________________________________\n\n'
        outputMsgp1 += 'Traveler Operation(s) _______________  Traveler Page(s) _____________\n\n'
        outputMsgp1 += docTitle + '\n\n'
        outputMsgp1 += 'Nominal and Actual Calibration Data\n'
        outputMsgp1 += InstName + '\n'
        outputMsgp1 += calDate + '\n\n'
        outputMsgp1 += 'Equipment Used: ' + equipNotes + '\n\n'
        outputMsgp1 += 'NOTE: ' + calNotes + '\n\n'
        outputMsgp1 +='{:37} {:9.2f} {:9.2f}\n' \
                .format('Min and Max PLC Nominal Counts: ', minMaxCounts[0], \
                                                    minMaxCounts[1])
        outputMsgp1 += '{:37} {:9.2f} {:9.2f} \n\n' \
                .format('Min and Max Nominal EU (' + EuUnitsLabel + '): ', \
                        minMaxEu[0], minMaxEu[1])
        # Measured counts vs Measured EU table
        outputMsgp1 +='{:16}  {:30}\n'.format('Measured Counts', \
                                    'Measured EU (' + EuUnitsLabel + ')')
        outputMsgp1 +='{:16}  {:30}\n'.format('_' * 15, '_' * 30)
        # loop thru the counts and print a list of counts vs eu values
        for idx in range(actCounts.size):
            outputMsgp1 +='{: >14.2f}  {: >14.6f}\n'.format(actCounts[idx], \
                                                          actEus[idx])
        outputMsgp1 += '\nThe least squares fit {:d} degree polynomial is:\n' \
                    .format(empPolyDegree)
        outputMsgp1 += polyPrettyPrint(coeffs) + '\n\n'
        # Measured EU vs Calc EU vs Error table
        outputMsgp1 +='{:>14}  {:>14}  {:^23}\n'.format('Measured EU', \
                                                  'Calc''d EU', \
                                                  '  Error   % of EU Range')
        outputMsgp1 +='{:14}  {:14}  {:23}\n'.format('_' * 14, '_' * 14, '_' * 23)
        # loop thru the counts and print a list of counts vs eu values and %error
        # calc eu range so it can be used to calc error pct
        euRange = minMaxEu[1] - minMaxEu[0]
        for idx in range(actCounts.size):
            # calc error and pct error
            error= empErrors[idx]
            errorPct = (error / euRange) * 100.0
            outputMsgp1 +='{: >14.6f}  {: >14.6f}  {: >11.6f}   {: >8.3f}%\n' \
                                                            .format(actEus[idx],
                                                                   calcVals[idx],
                                                                   error,
                                                                   errorPct)
        outputMsgp1 += '\nCalibrated engineering units for the min and max \n'
        outputMsgp1 += 'PLC counts are as follows:\n'
        outputMsgp1 += 'EU at min and max PLC Counts:  {:14.6f}   {:14.6f}\n\n' \
                .format(empMinMax[0], empMinMax[1])
        # **** Page 2
        outputMsgp2 = 'Compensate for a non-zero count value at zero EU.\n'
        outputMsgp2 += 'Shift the curve fit up or down by the count value of \n'
        outputMsgp2 += 'the zero EU value (the x-intercept of EU axis).\n'
        outputMsgp2 += 'The adjusted count values vs EU values are:\n\n'
        # Adjusted counts vs Measured EU table
        outputMsgp2 +='{:16}  {:30}\n'.format('Adjusted Counts', \
                                    'Measured EU (' + EuUnitsLabel + ')')
        outputMsgp2 +='{:16}  {:30}\n'.format('_' * 15, '_' * 30)
        # loop thru the counts and print a list of counts vs eu values
        for idx in range(actCounts.size):
            outputMsgp2 +='{: >14.6f}  {: >14.6f}\n'.format(offsetCounts[idx], \
                                                        actEus[idx])
        outputMsgp2 += '\nThe least squares fit {:d} degree polynomial \
for the adjusted counts is:\n'.format(empPolyDegree)
        outputMsgp2 += polyPrettyPrint(offsetCoeffs) + '\n\n'

        outputMsgp2 += 'Calibrated engineering units for the adjusted \n'
        outputMsgp2 += 'min and max PLC counts are as follows:\n'
        outputMsgp2 += 'EU at min and max PLC Counts:  {:14.6f}   {:14.6f}\n' \
                .format(offsetMinMax[0], offsetMinMax[1])
        outputMsgp2 += '\n\n\nENGMfg Sign/date  ' + '_' * 50 + '\n\n\n'
        outputMsgp2 +='*' * 70 + '\n'

        # **** Write output to a pdf file if there is an output file specified
        if args.outputFilePrefix != '':
            # **** Begin Class Dfn
            # Extend the FPDF class to add a header and a footer.
            # This class also contains a tuple of font names (fontNames) that can be
            # compared with the default font names (defaultFontNames).
            # If non-default fonts are used, they must first be added using add_font().
            # If default font names are used, an add_font() call results in an error.
            class cPdf(FPDF):
                def __init__(self, orientation, unit, format):
                    # init the base FPDF
                    super().__init__(orientation=orientation, unit=unit, format=format)
                    # define a tuple holding default font names
                    # (regular mono, bold mono, regular proportional, bold proportional)
                    # These are intended to be safe (read: always installed) fonts.
                    self.defaultFontNames= ("Courier", "Courier", "Helvetica", "Helvetica")

                   # Init the desired font names in a tuple
                    # Get a font list
                    fontList= fontmgr.findSystemFonts()
                    self.fontNames= self.getFontNames(fontList)
                    # Add non-default font names. Explicitly adding a default
                    # font is an error.
                    if self.fontNames[0] != self.defaultFontNames[0]:
                        self.add_font(family="regularMono", style='',
                                    fname=self.fontNames[0], uni=True)
                    if self.fontNames[1] != self.defaultFontNames[1]:
                        self.add_font(family="boldMono", style='',
                                    fname=self.fontNames[1], uni=True)
                    if self.fontNames[2] != self.defaultFontNames[2]:
                        self.add_font(family="regularProp", style='',
                                    fname=self.fontNames[2], uni=True)
                    if self.fontNames[3] != self.defaultFontNames[3]:
                        self.add_font(family="boldProp", style='',
                                    fname=self.fontNames[3], uni=True)

                # define the page header
                def header(self):
                    # use the bold proportional font
                    if self.fontNames[3] != self.defaultFontNames[3]:
                        # non-default
                        self.set_font("boldProp", '', 10)
                    else:
                        # default
                        self.set_font(self.defaultFontNames[3], 'B', 10)
                    self.cell(20, -40, InstName + ' Calibration Data')
                    self.ln(10) # line break

                # define the page footer
                def footer(self):
                    # use the regular proportional font
                    if self.fontNames[2] != self.defaultFontNames[2]:
                        # non-default
                        self.set_font("regularProp", '', 10)
                    else:
                        # default
                        self.set_font(self.defaultFontNames[2], '', 10)
                    # position off the bottom
                    self.set_y(-40)
                    # print page number
                    # hard code 3 total pages, since plot gets appended
                    # after the data pdf is created
                    self.cell(20, 0, 'Page ' + str(self.page_no()) + ' of 3')

                # Create a function which, given a font list, 
                # returns a tuple of font names for 4 fonts:
                # (regular mono, bold mono, regular prop, bold prop)
                def getFontNames(self, fontList):
                    # Want to use a monospace font for the body text,
                    # so the tables look good, but a proportional spaced font
                    # for the headings. For non-standard fonts, it cannot be 
                    # assumed they are installed. In order of preference, try
                    # source code pro, then DejaVuSansMono, then default to
                    # Courier, which comes with pyfpdf.
                    # For the porportional fonts, use Helvetica, which comes
                    # with pyfpdf.
                    #
                    # Assume a list of avialable fonts is passed in.
                    # *** Regular Mono Style
                    fontShortName= 'SourceCodePro-Regular.ttf'
                    # generator returning an iterable being accessed with next
                    # This will return the path to the font install location 
                    # if it is installed, or come back with None.
                    regularMonoName= next((font for font in fontList if fontShortName in font), None)
                    if regularMonoName is None:
                        # source code pro is not installed.
                        # try DejaVu
                        fontShortName= 'DejaVuSansMono.ttf'
                        regularMonoName= next((font for font in fontList if fontShortName in font), None)
                    if regularMonoName is None:
                        # DejaVu Sans Mono not installed. 
                        # default to Courier
                        regularMonoName= 'Courier'
                    # *** Bold Mono Style
                    fontShortName= 'SourceCodePro-Bold.ttf'
                    # This will return the path to the font install location 
                    # if it is installed, or come back with None.
                    boldMonoName= next((font for font in fontList if fontShortName in font), None)
                    if boldMonoName is None:
                        # source code pro is not installed.
                        # try DejaVu
                        fontShortName= 'DejaVuSansMono-Bold.ttf'
                        boldMonoName= next((font for font in fontList if fontShortName in font), None)
                    if boldMonoName is None:
                        # DejaVu Sans Mono Bold not installed. 
                        # default to Courier
                        boldMonoName= 'Courier'
                    # *** Regular Proportional Style
                    regularPropName= 'Helvetica'
                    boldPropName= 'Helvetica'

                    # return the tuple of font names
                    return(regularMonoName, boldMonoName, regularPropName, boldPropName)
            # **** End Class Dfn


            # Instantiate the new class and get on with making the pdf
            # Units are in points (pt)
            pdf = cPdf(orientation = 'P', unit = 'pt', format='Letter')
            # define the nb alias for total page numbers used in footer 
            # pdf.alias_nb_pages() # {nb} not used, as total pages is hard coded
            pdf.set_margins(54, 72, 54) # left, top, right margins (in points)
            #pdf.add_page() # use ctor params

            # Set the font for the main content
            # use the bold proportional font
            if pdf.fontNames[0] != pdf.defaultFontNames[0]:
                # non-default
                pdf.set_font("regularMono", '', 10)
            else:
                # default
                pdf.set_font(pdf.defaultFontNames[0], '', 10)

            # add the content put into outputMsg above
            pdf.add_page() # use ctor params
            #pdf.multi_cell(w=0, h=13, txt=outputMsgp1, border=0, align='L', fill=False )
            #pdf.add_page() # use ctor params
            #pdf.multi_cell(w=0, h=13, txt=outputMsgp2, border=0, align='L', fill=False )
            pdf.multi_cell(w=0, h=13, txt=outputMsgp1+outputMsgp2, border=0, align='L', fill=False )
            pdf.output(name = fnameData, dest='F') 
        
        # Output to the terminal if the -v option is used
        if args.v:
            print(outputMsgp1)
            print(outputMsgp2)

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
            markersize=2.5, marker='x', label='meas.')
    # plot the nominal line
    ax.plot(nomCounts, nomEus, color='green', \
            linewidth=1.0, linestyle='-', marker='', label='nominal')
    # plot the curve fit line
    ax.plot(nomCounts, empLine, color='red', \
            linewidth=1.0, linestyle='-', marker='', label='crv. fit')
    # plot the offset curve fit line
    ax.plot(nomCounts, offsetLine, color='orange', \
            linewidth=1.0, linestyle='-', marker='', label='offset')

    # The errors are plotted as individual points below, but this will create
    # multiple legend entries if we are not careful.... so....
    # Plot "dummy" error points, so a single legend entry is made for each error
    # type (+/-), then draw the legend, then plot the real error points.
    #
    # Make a dummy +/- error point
    ax.plot([], [], color='red', \
                    linewidth=1.0, linestyle='', \
                    markersize=1.5, marker='^', label='+ error')
    ax.plot([], [], color='red', \
                    linewidth=1.0, linestyle='', \
                    markersize=1.5, marker='v', label='- error')

    # Everything we want represented on the legend is plotted now, so make the legend
    ax.legend(loc='upper left', bbox_to_anchor=(0.0, 1.0), ncol=3, frameon=True)

    # plot each error marker and annotate each with the error value
    # for each coord of a error marker, place an annotation with an offset
    # plot negative and positve errors seperately so they can use "up" or "down"
    # symbols.
    #
    # create a text style
    txStyle = dict(fontsize=6, color='gray', horizontalalignment='center')
    # plot an annotate the error points
    for c,e in zip(actCounts, empErrors):
        if e < 0:
            ax.plot(c, e, color='red', \
                    linewidth=1.0, linestyle='', \
                    markersize=1.5, marker='v', label='error')
            ax.annotate('{:0.4G}'.format(e), xy=(c,e), xytext=(0,-8),
                        textcoords='offset points', **txStyle)
        else: # treat 0 error (unlikely) as positive
            ax.plot(c, e, color='red', \
                    linewidth=1.0, linestyle='', \
                    markersize=1.5, marker='^', label='error')
            ax.annotate('{:0.4G}'.format(e), xy=(c,e), xytext=(0,-8),
                        textcoords='offset points', **txStyle)
    

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

    # print the polynomial in the lower left of the graph, offset a
    # bit from (count min, eu min)
    txStyle = dict(fontsize=8, color='black', horizontalalignment='left')
    ax.text(axCountsMin + (0.01 * countRange),
            axEuMin + (-0.04 * euRange),
            'EU='+ polyPrettyPrint(coeffs), **txStyle)

    
    # set x and y ticks
    #
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

    # put page numbers (3 of 3) in the lower left
    txStyle = dict(fontsize=8, color='black', horizontalalignment='left')
    plt.text(0.05, 0, 'Page 3 of 3', transform=plt.gcf().transFigure, **txStyle)

    # Save the plot if the outFilePrefix is not empty. If it is empty, don't
    # save the plot.
    if args.outputFilePrefix != '':
        fnamePlot= '__zzqq__plcCalPlot.pdf' # not likely to exist and be something else
        try:
            # not sure what the possible exceptions are. Take a guess, and raise
            # in the 'generic' case
            plt.savefig(fnamePlot, orientation='portrait', papertype='letter',
                       format='pdf', transparent=False, frameon=False,
                       bbox_inches='tight', pad_inches=0.25)
        except IOError as ioe:
            print('I/O error when saving the plot:')
            print(ioe)
        except:
            print('Unexpcted error saving the plot: ', sys.exc_info()[0])
            raise

        # Now merge the plot pdf onto the end of the cal data pdf
        merger= PdfFileMerger()
        try:
            fileData= open(fnameData, 'rb')
            filePlot= open(fnamePlot, 'rb')
            merger.append(PdfFileReader(fileData))
            merger.append(PdfFileReader(filePlot))
            fname = args.outputFilePrefix + '_' + InstName + '.pdf'
            merger.write(fname)
            filePlot.close()
            fileData.close()
            # delete the individual files
            if os.path.exists(fnameData):
                os.remove(fnameData)
            if os.path.exists(fnamePlot):
                os.remove(fnamePlot)

        except IOError as ioe:
            print('I/O error when merging the data and plot files:')
            print(ioe)
        except:
            print('Unexpcted error merging the data and plot files: ', sys.exc_info()[0])
            raise

    # Draw the plot if the -v option is set. The user will close the plot.
    # Otherwise close the plot so it no longer consumes memory
    if args.v:
        plt.show()
    else:
        plt.close()

