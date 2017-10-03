import numpy as np
import logging
import os

# Code by Jeff Levy (jlevy@urban.org), 2016-2017

def pc_dup_criteria(dups):
    dups['val'] = dups['TOTREV'].abs() + dups['ASS_EOY'].abs() + dups['EXPS'].abs()
    return dups, ['FISYR', 'val', 'STYEAR', 'rnd']

def co_dup_criteria(dups):
    dups['val'] = dups['TOTREV'].abs() + dups['ASS_EOY'].abs() + dups['EXPS'].abs()
    return dups, ['FISYR', 'val', 'STYEAR', 'rnd']

class ProcessCOPC():
    """
    Contains the methods to create columns that appear only in the CO and PC files, and not in the PF.
    """
    def copc_epostcard(self, df):
        """
        Generates a piecewise value based on FISYR and EPOSTCARD.  This replaces the existing EPOSTCARD
        value, which is a datetime object, with a 1 or a 0.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        def epostcard(row):
            fisyr = row['FISYR']
            epost = row['EPOSTCARD']

            if fisyr == epost:
                return '1'
            else:
                return '0'

        return df.apply(lambda r: epostcard(r), axis=1)

    def copc_styear(self, df):
        """
        Slices the month off the end of TAXPER.  Returns the month-1 if month is not 12.  This is a holdover
        from the original SQL code.  Also catches month=1, so that it never returns a month of 0.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        def styear(row):
            taxper = row['TAXPER']
            if taxper[5:] in [1, '1', 12, '12']:
                return int(taxper[:5])
            else:
                return int(taxper[:5]) - 1

        return df.apply(lambda r: styear(r), axis=1)

    def copc_soiyr(self, df):
        """
        Slices the month off the end of TAXPER.  Returns the month-1 if month is not 12.  This is a holdover
        from the original SQL code.  Also catches month=1, so that it never returns a month of 0.  Identical
        to STYEAR.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        def soiyr(row):
            taxper = row['TAXPER']
            if taxper[5:] in [1, '1', 12, '12']:
                return taxper[:5]
            else:
                return str(float(taxper[:5]) - 1)

        return df.apply(lambda r: soiyr(r), axis=1)

    def copc_subcd(self, df):
        """
        Simply returns the value from SUBSECCD.  Holdover from the original SQL code.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        return df['SUBSECCD']
