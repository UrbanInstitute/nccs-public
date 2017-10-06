from process_co_pc import *
import logging

# Code by Jeff Levy (jlevy@urban.org), 2016-2017

def ez_dup_criteria(dups):
    dups['val'] = dups['TOTREV'].abs() + dups['ASS_EOY'].abs() + dups['EXPS'].abs()
    return dups, ['FISYR', 'val', 'STYEAR', 'rnd']

class ProcessEZ(ProcessCOPC):
    """
    Creates columns found only in the EZ dataframe
    """
    def ez_calculate(self):
        """
        Base method for calling all of the methods to calculate the columns for the 990 EZ form.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main
        ez = main.data_dict['EZ']

        main.logger.info('Calculating new columns for EZ.')

        ez['TOTREV'] = self.ez_totrev(ez)
        ez['GRREC']   = self.ez_grrec(ez)
        ez['PROGREV'] = self.ez_progrev(ez)
        ez['SPEVTG']  = self.ez_spevtg(ez)
        ez['NETGNLS'] = self.ez_netgnls(ez)
        ez['FILENAME'] = self.ez_filename(ez)

        ez['EPOSTCARD'] = self.copc_epostcard(ez)
        ez['STYEAR'] = self.copc_styear(ez)
        ez['SOIYR'] = self.copc_soiyr(ez)
        ez['SUBCD'] = self.copc_subcd(ez)

    def ez_grrec(self, ez):
        """
        Calculates the GRREC column.  Note that the same column has a different calculation for EINs from
        the Full 990 and EINS from the 990 EZ.

        ARGUMENTS
        ez (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        assert(ez['TOTREV'].dtype.type in [np.int64, np.float64])
        assert(ez['SALEOTHG'].dtype.type in [np.int64, np.float64])
        assert(ez['DIREXP'].dtype.type in [np.int64, np.float64])
        assert(ez['GOODS'].dtype.type in [np.int64, np.float64])

        return ez['TOTREV'] + ez['SALEOTHG'] + ez['DIREXP'] + ez['GOODS']

    def ez_progrev(self, ez):
        """
        Calculates the PROGREV column.

        ARGUMENTS
        ez (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        assert(ez['DUESASSESMNTS'].dtype.type in [np.int64, np.float64])
        assert(ez['PRGMSERVREV'].dtype.type in [np.int64, np.float64])

        return ez['DUESASSESMNTS'] + ez['PRGMSERVREV']

    def ez_spevtg(self, ez):
        """
        Calculates the SPEVTG column.

        ARGUMENTS
        ez (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        assert(ez['GRSINCFNDRSNG'].dtype.type in [np.int64, np.float64])
        assert(ez['GRSINCGAMING'].dtype.type in [np.int64, np.float64])

        return ez['GRSINCFNDRSNG'] + ez['GRSINCGAMING']

    def ez_totrev(self, ez):
        """
        Calculates the PROGREV column.  Note that TOTREV2 is taken from 990EZ part I, 9, while TOTREV
        is calculated from the expense and income subtotals.  This is the only column like this, and usually
        any discrepencies between stated and calculated values are tested in the validation steps.  However,
        it was always done this way before, so it continues.

        ARGUMENTS
        ez (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        return ez['EXPS'] + ez['NETINC']

    def ez_netgnls(self, ez):
        """
        Returns the SALEOTHN column exactly.  Redundant holdover from the old SQL process.

        ARGUMENTS
        ez (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        return ez['SALEOTHN']

    def ez_filename(self, ez):
        """
        Assembles the FILENAME column from the EIN and TAXPER columns, which is used to build the URL to
        the PDF of the 990 filing on the Foundation Center's website.  The full construction is:

        http://990s.foundationcenter.org/990_pdf_archive/<FIRST THREE DIGITS OF EIN>/<FULL EIN>/<FILENAME>.pdf

        for 990 Full or EZ filings, or

        http://990s.foundationcenter.org/990pf_pdf_archive/<FIRST THREE DIGITS OF EIN>/<FULL EIN>/<FILENAME>.pdf

        for 990 PF filings.

        ARGUMENTS
        ez (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        return ez.index + '_' + ez['TAXPER'] + '_990EZ'

    def ez_manual(self):
        """
        Applies any manual, one-time fixes to the EZ data.  This is usually defined as a change to a single
        EIN from a single year, in a non-generalizable way, e.g. a mistyped EIN in the raw IRS data.

        ARGUMENTS
        None

        RETURNS
        None
        """
        try:
            entry = self.main.data_dict['EZ'].loc['580623603']
            if entry['SOURCE'] == '16eofinextractez.dat' and entry['NAME'] == 'UNITED WAY OF THE COASTAL EMPIRE INC':
                self.main.data_dict['EZ'].drop('580623603', inplace=True)
        except KeyError:
            pass
