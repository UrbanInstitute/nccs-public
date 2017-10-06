import numpy as np
import logging

# Code by Jeff Levy (jlevy@urban.org), 2016-2017

def pf_dup_criteria(dups):
    dups['p2tasfmv_abs'] = dups['P2TASFMV'].abs()
    dups['p2ttotast_abs'] = dups['P2TOTAST'].abs()
    dups['val'] = dups['P1TOTREV'].abs() + dups['P1TOTEXP'].abs() + dups[['p2tasfmv_abs', 'p2ttotast_abs']].max(axis=1)
    dups.drop(['p2tasfmv_abs', 'p2ttotast_abs'], axis=1, inplace=True)
    return dups, ['FISYR', 'val', 'STYEAR', 'rnd']

class ProcessPF():
    """
    The methods used to process the PF data.  Everything here is inhereted by the main "process" class.
    """
    def pf_calculate(self):
        """
        Base method for calling all of the methods to calculate the columns for the 990 PF form.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main
        pf = main.data_dict['PF']

        main.logger.info('Calculating new columns for PF.')

        pf['P6TXRFD']  = self.pf_p6txrfd(pf)
        pf['P1NGASTS'] = self.pf_p1ngasts(pf)
        pf['TFLD']     = self.pf_tfld(pf)
        pf['FILENAME'] = self.pf_filename(pf)

    def pf_tfld(self, pf):
        """
        Calculates the TFLD column.

        ARGUMENTS
        pf (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        return pf['TAXDUE'] - pf['OVERPAY']

    def pf_p1ngasts(self, pf):
        """
        Calculates the P1NGASTS column.

        ARGUMENTS
        pf (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        assert(pf['TOTEXCAPLS'].dtype.type in [np.int64, np.float64])
        assert(pf['TOTEXCAPGN'].dtype.type in [np.int64, np.float64])
        return pf['TOTEXCAPLS'] + pf['TOTEXCAPGN']

    def pf_p6txrfd(self, pf):
        """
        Calculates the P6TXRFD column.

        ARGUMENTS
        pf (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        return np.maximum(pf['P6ESTTX']+pf['P6TXWTH']+pf['P6TXINV']+pf['P6TXWERR']-
                          pf['P6TEXCTX']+pf['P6TXPNLT'], 0)

    def pf_balduopt(self, pf):
        """
        Calculates the BALDUOPT column.  This column was used in 2012 and earlier, but is now unused.

        ARGUMENTS
        pf (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        def op_vs_td(r):
            if r['OVERPAY'] > r['TAXDUE']:
                return r['OVERPAY']
            else:
                return -r['TAXDUE']

        if 'BALDUOPT' not in pf.columns.values:
            #When there is NO data used from 2012 or earlier, the entire column simply needs to be calculated
            assert(all(pf[['OVERPAY', 'TAXDUE']].min(axis=1) == 0)), "Expected min(df[['OVERPAY', 'TAXDUE']] == 0) for all observations."
            return pf[['OVERPAY', 'TAXDUE']].apply(lambda r: op_vs_td(r), axis=1)

        else:
            #When there IS data from 2012 or earlier, some of the column is already included and others will need
            #to be calculated and have the null values filled
            assert(all(pf[pf['BALDUOPT'].isnull()][['OVERPAY', 'TAXDUE']].min(axis=1) == 0)), "Expected min(df[['OVERPAY', 'TAXDUE']] == 0) for all observations from 2013 and onward."
            balduopt_fill = pf[['OVERPAY', 'TAXDUE']].apply(lambda r: op_vs_td(r), axis=1)
            return pf['BALDUOPT'].fillna(balduopt_fill)

    def pf_filename(self, pf):
        """
        Assembles the FILENAME column from the EIN and TAXPER columns, which is used to build the URL to
        the PDF of the 990 filing on the Foundation Center's website.  The full construction is:

        http://990s.foundationcenter.org/990_pdf_archive/<FIRST THREE DIGITS OF EIN>/<FULL EIN>/<FILENAME>.pdf

        for 990 Full or EZ filings, or

        http://990s.foundationcenter.org/990pf_pdf_archive/<FIRST THREE DIGITS OF EIN>/<FULL EIN>/<FILENAME>.pdf

        for 990 PF filings.

        ARGUMENTS
        pf (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        return pf.index + '_' + pf['TAXPER'] + '_990PF'

    def pf_manual(self):
        """
        Applies any manual, one-time fixes to the PF data.  This is usually defined as a change to a single
        EIN from a single year, in a non-generalizable way, e.g. a mistyped EIN in the raw IRS data.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main
        pf = main.data_dict['PF']

        #per this note: http://nccsweb.urban.org/knowledgebase/detail.php?linkID=4207&category=40023&xrefID=7226&close=0
        try:
            pf = pf.drop('954585397', axis=0)
        except ValueError:
            print('Tried to drop EIN 954585397 from PF, but it was not present.  Please review the pf_manual method.')

        main.data_dict['PF'] = pf
