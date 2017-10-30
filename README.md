# PlcCalibration
Python program which takes in calibration input data in the form of a json file, does a linear curve fit, and outputs calibration data (.txt) and a plot (.pdf)

25 Oct 2017
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


