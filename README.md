plcCalibration
This program accepts two or more engineering units (EU) vs count values, and
determines a linear curve fit to the given values.  Outputs are:
the measured counts and the measured EU values (given as inputs),
The min and max configured PLC counts and EU values (given as inputs),
The calculated EU min and max at the min and max PLC counts.

A curve fit is performed for the measured values. Plotted along with the
measured points is the nominal line, and the curve fit line. The curve fit is
done according to the degree of the resulting polynomial specified with the
--degree option. Default is degree 1 (linear).

The input values are taken from a file specified with the -i or
--inputFileName paraemeter.  The input file is expected to be a single
dictionary {}, or a list of one or more dictionaries [{}, ...{}], with one
dictionary per instrument in the form:
Key               Datatype
01_instName:      string
02_calDate:       string (MM/DD/YYYY HH:mm:ss)
03_EuUnits:       string
04_minMaxCounts:  list [min, max] Ints.
05_minMaxEu:      list [min, max]. Reals
06_actCounts:     [c1, ... cn] (list of ints)
07_actEus:        [e1, ... en] (list of reals)
08_notes:         string
09_Equipment:     string
10 docTitle:      string

where actCounts and actEus should be the same length

Command line paraemters are:
inputFileName (required, first positional). The name of the file where the
calibration data is stored (i.e. the file where the above dictionary is defined.

outputFilePrefix (reqiured, second positional). The prefix of the output file
where information about the calibration is written. The instrument is
appended to the specified output file name.  Also used as a file name when
creating an input file tmeplate.

--degree (optional, default value = 1) The degree polynomial to use. The 
default value of 1 creates a 1 degree, linear polynomial.

--simulate (optional) input count values are ignored, and count values
are simulated from the give EU values. Some random 'noise' is added to the
simulated count values.

-c Create input file (optional). Creates a input file to be used as a
template.  Uses the file name specified with the -o or outpuFilePrefix
option.

-verbose (optional) sends the same info going to the output file to the
screen.

Libraries used:
deepcopy
argparse -- cli arg parser
numpy (1.15.3), scipy (1.1.0), matplotlib (3.0.0)
json -- read and write JSON
-- pdf creation and merging
pyfpdf (fpdf)
PyPdf2

25 Oct 2017 (v0.1)
* Change the executable python program from linearRegress.py to plcCalibration.py

* Add a calibration note section to the input file, the output text file, and
  the screen output when using the -v option. The key is '08_notes'. The
  intended purpose is to give a place to describe include details wihc are not
  otherwise included.

* Added an equipment note to the input file, the output text file, and the
  screen output when using the -v option. The key is '09_equipment'. The
  intended purpose is to give a place to specify equipment and associated serial
  numbers, cal dates, etc. which was used for the test.

* Added a doc title to the input file, the output text file, and the screen
  output when using the -v option.  The key is  '10_docTitle'. The intended 
  purpose is to give a document title to the  generated text file

* Made the above fields (08_notes, 09_equipment, 10_docTitle) *optional* in the
  input file. The program will check for their existence before trying to use
  them.  If they are not present, then it will continue without them.

* Added a place to enter traveler number, traveler operations(s), and traveler
  page(s) at the top of the text output file. Similarly, added a place for mfg
  and QA sign/data at the bottom of the text output file.

* TODO: Change cal data from a text file to a pdf
  file so data is harder to change. Merge this with the exiting pdf created by
  matplot lib, so there is one pdf output file with all info.

* TODO: Change command line arguments: Get rid of 
  -i and -o "options", and make them positional.

* TODO: Have a command line option (-d or --degree)
  that specified the degree of the polynomial used to curve fit the data. Default
  should be 1 for a 1 degree (linear) polynomial.

* TODO: Have some indication of error, or linearity 
  of curve fit.

* TODO: Have plot axis auto scaling take into account
  the nominal, emperical, and offset lines so they all show completely on the 
  plot.

25 October 2018 (v0.2)

* Made the -i/--inputFileName a positional required argument (1st position)
  rather than an optional (required) argument.

* Made the  -o/--outputFilePrefix a positional required argument (2nd position)
  rather than an optional (required) argument.

* Since I was working on this code, I upgraded the libraries installed in the
  virtual environment.  This was just to remain current. No known functionality 
  changes or bugs were driving this change.

  numpy went to version 1.15.3 from 1.13.3
  scipy went to version 1.1.0 from 1.0.0
  matplotlib went to version 3.0.0 from 2.1.0

* Plot improvements:  
    -- Used user bpsMath library oomCeil and oomFloor functions to help
       autoscale the plot.
    -- The scales now take into account the nominal and actual
       range of values for counts and EU, as well as the calculated error values.
    -- The plot now includes the error (variance between measured and calc'd EU)
       at each of the measured points.  Use up/down trianges to symbolize deltas
       for +/- errors.
    -- Added annotations to show error values offset from the error markers.
    -- Updated legend to show error markers, and updated layout to be less 
       obtrusive by making 3 columns.
    -- Added a text annotation of the polynomial on the graph

* Added the --degree command line argument and associated functionality,
so a degree other than 1, the default, can be specified. The resulting curve
fit will be a polynomial with the specified degree.

* Used user bpsMath library polyPrettyPrint to print the polynomial
resulting from the curve fit in the output text as a prettier (better formatted)
ascii string.

* Added a table to the output text that shows measured EU vs calc EU
and the resulting error in EU values as as a percent of EU range.

26 October 2018 (v0.3)
* Changed calibration data to be a pdf rather than a plain text *.txt file.

* Merged the plot pdf at the end of the calibration data pdf (new), so now,
only a single file is created, and it is a pdf.


