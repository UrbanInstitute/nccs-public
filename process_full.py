from process_co_pc import *
import logging
import numpy as np

# Code by Jeff Levy (jlevy@urban.org), 2016-2017

def full_dup_criteria(dups):
    dups['val'] = dups['TOTREV'].abs() + dups['ASS_EOY'].abs() + dups['EXPS'].abs()
    return dups, ['FISYR', 'val', 'STYEAR', 'rnd']

class ProcessFull(ProcessCOPC):
    """Creates columns found only in the Full dataframe.
    """
    def full_calculate(self):
        """Base method for calling all of the methods to calculate the columns for the Full 990 form.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main
        full = main.data_dict['Full']

        main.logger.info('Calculating new columns for Full.')

        full['RENTINC'] = self.full_rentinc(full)
        full['RENTEXP'] = self.full_rentexp(full)
        full['SPEVTG']  = self.full_spevtg(full)
        full['DIREXP']  = self.full_direxp(full)
        full['FUNDINC'] = self.full_fundinc(full)
        full['NETINC']  = self.full_netinc(full)
        full['TOTREV'] = self.full_totrev(full)
        full['GRREC']   = self.full_grrec(full)
        full['FILENAME'] = self.full_filename(full)

        full['EPOSTCARD'] = self.copc_epostcard(full)
        full['STYEAR'] = self.copc_styear(full)
        full['SOIYR'] = self.copc_soiyr(full)
        full['SUBCD'] = self.copc_subcd(full)

    def full_grrec(self, full):
        """Calculates the GRREC column.  Note that the same column has a different calculation for EINs from
        the Full 990 and EINS from the 990 EZ.

        ARGUMENTS
        full (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        assert(full['TOTREV'].dtype.type in [np.int64, np.float64])
        assert(full['RNTLEXPNSREAL'].dtype.type in [np.int64, np.float64])
        assert(full['RNTLEXPNSPRSNL'].dtype.type in [np.int64, np.float64])
        assert(full['SALESEXP'].dtype.type in [np.int64, np.float64])
        assert(full['SALEOTHE'].dtype.type in [np.int64, np.float64])
        assert(full['LESSDIRFNDRSNG'].dtype.type in [np.int64, np.float64])
        assert(full['LESSDIRGAMING'].dtype.type in [np.int64, np.float64])
        assert(full['GOODS'].dtype.type in [np.int64, np.float64])

        return full['TOTREV'] + full['RNTLEXPNSREAL'] + full['RNTLEXPNSPRSNL'] + full['SALESEXP'] +\
               full['SALEOTHE'] + full['LESSDIRFNDRSNG'] + full['LESSDIRGAMING'] + full['GOODS']

    def full_rentinc(self, full):
        """Calculates the RENTINC column.

        ARGUMENTS
        full (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        assert(full['GRSRNTSREAL'].dtype.type in [np.int64, np.float64])
        assert(full['GRSRNTSPRSNL'].dtype.type in [np.int64, np.float64])

        return full['GRSRNTSREAL'] + full['GRSRNTSPRSNL']

    def full_rentexp(self, full):
        """Calculates the RENTEXP column.

        ARGUMENTS
        full (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        assert(full['RNTLEXPNSREAL'].dtype.type in [np.int64, np.float64])
        assert(full['RNTLEXPNSPRSNL'].dtype.type in [np.int64, np.float64])

        return full['RNTLEXPNSREAL'] + full['RNTLEXPNSPRSNL']

    def full_spevtg(self, full):
        """Calculates the SPEVTG column.

        ARGUMENTS
        full (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        assert(full['GRSINCFNDRSNG'].dtype.type in [np.int64, np.float64])
        assert(full['GRSINCGAMING'].dtype.type in [np.int64, np.float64])

        return full['GRSINCFNDRSNG'] + full['GRSINCGAMING']

    def full_direxp(self, full):
        """Calculates the DIREXP column.

        ARGUMENTS
        full (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        assert(full['LESSDIRFNDRSNG'].dtype.type in [np.int64, np.float64])
        assert(full['LESSDIRGAMING'].dtype.type in [np.int64, np.float64])

        return full['LESSDIRFNDRSNG'] + full['LESSDIRGAMING']

    def full_fundinc(self, full):
        """Calculates the FUNDINC column.

        ARGUMENTS
        full (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        assert(full['NETINCFNDRSNG'].dtype.type in [np.int64, np.float64])
        assert(full['NETINCGAMING'].dtype.type in [np.int64, np.float64])

        return full['NETINCFNDRSNG'] + full['NETINCGAMING']

    def full_netinc(self, full):
        """Calculates the NETINC column.

        ARGUMENTS
        full (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        return full['TOTREV2'] - full['EXPS']

    def full_totrev(self, full):
        """Calculates the TOTREC column.  Note that TOTREV2 is taken from 990 part VIII, 12A, while TOTREV
        is calculated from the expense and income subtotals.  This is the only column like this, and usually
        any discrepencies between stated and calculated values are tested in the validation steps.  However,
        it was always done this way before, so it continues.

        ARGUMENTS
        full (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        return full['EXPS'] + full['NETINC']

    def full_filename(self, full):
        """Assembles the FILENAME column from the EIN and TAXPER columns, which is used to build the URL to
        the PDF of the 990 filing on the Foundation Center's website.  The full construction is:

        http://990s.foundationcenter.org/990_pdf_archive/<FIRST THREE DIGITS OF EIN>/<FULL EIN>/<FILENAME>.pdf

        for 990 Full or EZ filings, or

        http://990s.foundationcenter.org/990pf_pdf_archive/<FIRST THREE DIGITS OF EIN>/<FULL EIN>/<FILENAME>.pdf

        for 990 PF filings.

        ARGUMENTS
        full (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        return full.index + '_' + full['TAXPER'] + '_990O'

    def full_manual(self):
        """Applies any manual, one-time fixes to the Full data.  This is usually defined as a change to a single
        EIN from a single year, in a non-generalizable way, e.g. a mistyped EIN in the raw IRS data.

        ARGUMENTS
        None

        RETURNS
        None
        """
        df = self.main.data_dict['Full']

        #The EIN for this organization(Flying Crown Land Group) is wrong in the validation program; EIN SHOULD BE 453208250
        #-note from Jenny Lee's validation fixing, summer 2017
        if '453208450' in df.index and df.loc['453208450', 'NAME'] == 'FLYING CROWN LAND GROUP':
            i = df.index.tolist().index('453208450')
            # new_index = np.append(df.index.values[:i], [['453208250'], df.index.values[i+1:]])
            new_index = list(df.index.values[:i]) + ['453208250'] + list(df.index.values[i+1:])
            assert(len(new_index) == len(df.index))
            assert(sum(new_index != df.index) == 1)
            self.main.data_dict['Full'].index = new_index
            self.main.data_dict['Full'].index.name = 'EIN'
