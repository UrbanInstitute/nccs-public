import os
import sys
import data
import process
import write
import logging
import validate
import datetime

# Code by Jeff Levy (jlevy@urban.org), 2016-2017

class BuildNCCS():
    """
    This is the top-level class.  It initializes the other classes of the program and holds the methods
    related to logging.
    """
    def __init__(self, path, current_yr=None, force_new_download=False, forms=['PF', 'EZ', 'Full'], backfill=2, tolerance=1000, do_validation=True, clear_old=True, partial_validation=True, get_from_sql=True, output_full=True):

        forms = [f.upper() for f in forms]
        self.forms = ['Full' if f == 'FULL' else f for f in forms]
        self.path = path
        self.force_new_download = force_new_download

        self.logger, self.start = self.start_logging(path, current_yr)

        self.data     = data.Data(self, clear_old, get_from_sql, current_yr, backfill)
        self.process  = process.Process(self)
        self.validate = validate.Validate(self, tolerance, do_validation, partial_validation)
        self.write    = write.Write(self, output_full)

    def start_logging(self, path, current_yr):
        """
        Initializes the logging stream to a log_YYYY.txt file and to stdout.
        """
        formatter = logging.Formatter('[%(funcName)s]: %(message)s')
        logger = logging.getLogger('logger')
        logger.setLevel(logging.INFO)
        ch_file = logging.FileHandler(os.path.join(path, 'log_{}.txt'.format(current_yr)), mode='w')
        ch_file.setLevel(logging.INFO)
        ch_file.setFormatter(formatter)
        ch_console = logging.StreamHandler()
        ch_console.setLevel(logging.INFO)
        ch_console.setFormatter(formatter)
        logger.addHandler(ch_file) #handler for printing to log file
        logger.addHandler(ch_console) #handler for printing to stdout

        start = datetime.datetime.now()
        logger.info('Process started at {}.'.format(start))
        logger.info('Building NCCS core files for {}.'.format(current_yr))
        return logger, start

    def end_logging(self):
        """
        Cleanly ends the logging process.
        """
        start = self.start
        logger = self.logger
        end = datetime.datetime.now()
        logger.info('Process finished at {} -- Elapsed time: {}'.format(end, end-start))
        logging.shutdown()

    def end(self):
        """
        Calls the end_logging() method, then checks to see if the program was run from an interactive prompt
        (i.e. within Python and not from a command line).  If yes, it prints to stdout a summary of useful
        debugging info maintained within the nccs class instance.
        """
        self.end_logging()

        if sys.stdin.isatty():
            interactive_note = """\nUseful information for debugging:

nccs.forms     : list of forms processed
nccs.data_dict : dictionary of {form: dataframe} where form is EZ, Full or PF, before splitting and merging into CO and PC

nccs.data.core_file_year  : int of the year processed
nccs.data.backfilled      : nested dictionary of {form: {year: list of EINs used in backfilling}}
nccs.data.crosswalks      : nested dictionary of {form: {IRS column name: NCCS column name}}
nccs.data.droplists       : dictionary of {form: list of columns to check for zero-filer status}
nccs.data.dropped_columns : dictionary of {form: list of columns dropped before writing to file}
nccs.data.missing_columns : dictionary of {form: list of columns expected but not found when writing to file}
nccs.data.numeric_columns : list of columns forced to be numeric
nccs.data.sql_cache       : dictionary of {filename: dataframe downloaded from SQL}

nccs.write.data_dict : dictionary of {form: dataframe} where form is CO, PC, PF, CO_full or PC_full.  Final versions written to file.

nccs.validate.failed_eins   : dictionary of {form: list of EINs that fail validation, if no fixes were incorporated}
nccs.validate.fixes_applied : dictionary of {form: int of number of manual fixes reincorporated into the form}
"""
            print(interactive_note)
