# NCCS Core File Processing
*Written by Jeff Levy (jlevy@urban.org) using Python 3.5.3, Pandas 20.1, Numpy 1.11.2 and Requests 2.14.2 from Anaconda*

This program will create the final NCCS core files.  It requires the following input data:

  - IRS form 990                                     (downloaded automatically from IRS)
  - IRS form 990EZ                                   (downloaded automatically from IRS)
  - IRS form 990PF                                   (downloaded automatically from IRS)
  - IRS form 990N                                    (downloaded automatically from IRS)
  - IRS Business Master Files (BMF)                  (downloaded automatically from IRS)
  - National Taxonomy of Exempt Entities (NTEE)      (downloaded automatically from SQL)
  - FIPS/MSA data                                    (downloaded automatically from SQL)
  - Prior NCCS releases                              (downloaded automatically from SQL)

It produces the following files:

  - A log_YYYY.txt file detailing every step the last run went through
  - NCCS validation files 							  (when validations steps detect failures)
  - NCCS Core CO file 								  (if both 990 EZ and Full are used)
  - NCCS Core PC file 								  (if both 990 EZ and Full are used)
  - NCCS Core PF file 								  (if the 990PF is used)
  - NCCS Core CO_full file 						      (if the 990 Full is used)
  - NCCS Core PC_full file 						      (if the 990 Full is used)
  
For documentation of the build process, see our [readthedocs site](https://nccs-public.readthedocs.io/en/latest/index.html).  For the release data, see the [NCCS data archive](http://nccs-data.urban.org/data.php?ds=core).