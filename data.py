import os
import re
from operator import xor
import numpy as np
import pandas as pd
import logging
import pymysql
import getpass

from load_data import *

# Code by Jeff Levy (jlevy@urban.org), 2016-2017

def check_folder(path, folder):
    """Checks the given path for the specified folder then returns the folder name.  If the folder does
    not exist at this path, the folder is created first.

    ARGUMENTS
    path (str) : Base path on local system
    folder (str) : Folder name to check for in the base path

    RETURNS
    str: Folder
    """
    import os
    full_path = os.path.join(path, folder)
    if not os.path.exists(full_path):
        os.mkdir(full_path)
    return folder

def clear_files(path, folder):
    """Removes all existing .csv files from the specified path.

    ARGUMENTS
    path (str) : Base path on local system
    folder (str) : Folder name to check for in the base path

    RETURNS
    None
    """
    import os
    files = [f for f in os.listdir(path+os.sep) if f.lower().endswith('.csv')]
    for f in files:
        os.remove(os.path.join(path, folder, f))

class BMFShare():
    """This class holds methods that are used by both the NCCS core file process, and the NCCS BMF process.
    They are separated from the Data class solely for the purposes of inheritance.
    """
    def bmf(self):
        """Downloads the raw BMF data from the IRS, rearranges a few columns (splitting, combining, cleaning),
        then passes the data and lists of the columns to the bmf_create method.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main

        all_cols = ['ORGANIZATION', 'ZIP', 'ACTIVITY', 'AFFILIATION', 'DEDUCTIBILITY', 'ICO', 'SORT_NAME', 'FILING_REQ_CD', 'PF_FILING_REQ_CD']
        pf_cols = ['ASSET_CD', 'INCOME_CD']
        copc_cols = ['STATUS']

        bmf = self.download_bmf()

        #bmf = bmf[all_cols+pf_cols+copc_cols]#.copy(deep=True) #moved to bmf_create method

        bmf.rename(columns={'ORGANIZATION':'ORGCD', 'AFFILIATION':'AFCD', 'DEDUCTIBILITY':'DEDUCTCD',
                           'ICO':'CONTACT', 'SORT_NAME':'SEC_NAME', 'ASSET_CD':'ASS_CODE',
                           'INCOME_CD':'INC_CODE', 'STATUS':'EOSTATUS'}, inplace=True)
        bmf['CONTACT'] = bmf['CONTACT'].str.lstrip('%').str.lstrip()
        bmf['FRCD'] = bmf['FILING_REQ_CD'] + bmf['PF_FILING_REQ_CD']
        bmf['ACTIV1'] = bmf['ACTIVITY'].str.slice(0,3)
        bmf['ACTIV2'] = bmf['ACTIVITY'].str.slice(3,6)
        bmf['ACTIV3'] = bmf['ACTIVITY'].str.slice(6,9)

        all_cols = ['ORGCD', 'ZIP', 'AFCD', 'DEDUCTCD', 'CONTACT', 'SEC_NAME', 'FRCD', 'ACTIV1', 'ACTIV2', 'ACTIV3']
        pf_cols = ['ASS_CODE', 'INC_CODE']
        copc_cols = ['EOSTATUS']

        bmf_cols = [all_cols, copc_cols, pf_cols]

        self.bmf_create(bmf, bmf_cols)

    def bmf_create(self, bmf, bmf_cols):
        """This is split from the main bmf method because this portion is used in the Core file creation but
        overridden in the BMF process.  It subsets the BMF data by the column lists it receives from the bmf
        method, then merges it into the main core file data by EIN.

        ARGUMENTS
        bmf (DataFrame) : The BMF data
        bmf_cols (list) : The desired columns of the BMF data

        RETURNS
        None
        """
        main = self.main
        all_cols, copc_cols, pf_cols = bmf_cols
        bmf = bmf[all_cols+pf_cols+copc_cols]

        if 'Full' in main.forms:
            main.data_dict['Full'] = main.data_dict['Full'].merge(bmf[all_cols+copc_cols], how='left', left_index=True, right_index=True)
            main.logger.info('Merged BMF data with Full.')
        if 'EZ' in main.forms:
            main.data_dict['EZ'] = main.data_dict['EZ'].merge(bmf[all_cols+copc_cols], how='left', left_index=True, right_index=True)
            main.logger.info('Merged BMF data with EZ.')
        if 'PF' in main.forms:
            main.data_dict['PF'] = main.data_dict['PF'].merge(bmf[all_cols+pf_cols], how='left', left_index=True, right_index=True)
            main.logger.info('Merged BMF data with PF.')

        main.logger.info('Finished merging BMF data with all forms.\n')

    def fipsmsa(self):
        """Load the lu_fipsmsa data from SQL (or from file if it is already downloaded), then passes the data
        into the fipsmsa_create method for merging.  Must be run after the NTEE data is merged in, because
        that's where the FIPS column comes from that this method merges on.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main

        cols = ['FIPS', 'PMSA', 'MSA_NECH']

        main.logger.info('Loading FIPSMSA data from NCCS MySQL server...')
        fipsmsa = self.get_sql('lu_fipsmsa', 'nccs', cols=cols, index_col=None)

        main.logger.info('    done.')

        self.fipsmsa_create(fipsmsa, cols)

    def fipsmsa_create(self, fipsmsa, fipsmsa_cols):
        """This is split from the main fipsmsa method because this portion is used in the Core file creation but
        overridden in the BMF process.  It handles merging the fipsmsa data into the main core file data,
        by the FIPS column.

        ARGUMENTS
        fispmsa (DataFrame) : The fipsmsa data
        fipsmsa_cols (list) : Subset of columns to take from the fipsmsa data

        RETURNS
        None
        """
        main = self.main
        for form in main.forms:
            main.data_dict[form] = main.data_dict[form].reset_index().merge(fipsmsa, on='FIPS', how='left').set_index('EIN')
            main.logger.info('Merged FIPSMSA columns into {}.'.format(form))

        main.logger.info('Completed merging in FIPSMSA documention.\n')

    def ntee(self):
        """Load the nteedocAllEins data from SQL (or file if it's already downloaded), specifying only a subset
        of colunns to be part of the SQL SELECT statement due to the size of the entire ntee file (over 1.5g),
        cleans hyphens out of the EIN column, then passes the data into the ntee_create method.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main

        #removed Activ1 due to now coming from BMF downloads
        cols = ['EIN', 'OutNccs', 'OutReas', 'NteeFinal', 'Fips', 'NteeCC', 'NteeSrc',
                'NteeConf', 'FndnCd', 'NAICS', 'LONGITUDE', 'LATITUDE', 'zip5', 'Name',
                'Address', 'City', 'State', 'NteeIrs', 'RuleDate', 'ClassCd',
                'censusTract', 'block']

        main.logger.info('Loading master NTEE data from NCCS MySQL server...')
        ntee = self.get_sql('nteedocAllEins', 'nccs', cols=cols, force_sql_cols=True)

        ntee.index = ntee.index.str.replace('-', '') #EIN column has some hyphens
        # ntee.set_index('EIN', inplace=True)
        # ntee.columns = [col.upper() for col in ntee.columns.values] #make all columns upper case
        main.logger.info('    done.')

        self.ntee_create(ntee)

    def ntee_create(self, ntee):
        """This is split from the main ntee method because this portion is used in the Core file creation but
        overridden in the BMF process.  It handles merging the ntee data into the main core files.

        ARGUMENTS
        ntee (DataFrame) : The nteedocAllEins data.

        RETURNS
        None
        """
        main = self.main
        for form in main.forms:
            main.data_dict[form] = main.data_dict[form].merge(
                        ntee, how='left', left_index=True, right_index=True)
            main.logger.info('Merged NTEE columns into {}.'.format(form))

        main.logger.info('Completed merging in master NTEE documention.\n')

class Data(LoadData, BMFShare):
    """This class holds methods intended to handle the first data steps, including loading, merging, crosswalking, and
    dropping.  It does not handle the calculation of any new columns (Process), validation (Validate), or creation
    of final output (Write).  Note that there are a few exceptions to the column creation exclusion, where handling
    it here is far easier than later, e.g. setting the INPRIOR flag in the same place that prior year data is
    merged in.  For the sake of maintainability these exceptions should be fixed, and it has been added to
    the github issues list.

    Its methods are split into three classes, the last two of which are inherited by this one.  The BMFShare class
    holds Data methods that are needed for inheritance into both this class and the NCCS BMF creation process, and
    the LoadData class holds methods that specifically involve loading data from the internet, SQL or from file.
    """
    def __init__(self, main, clear_old, get_from_sql, current_yr, backfill):
        self.main = main
        if main is not None: #small exception so the validation fixer tool can create a temp instance to get at the numeric_columns values
            self.irs_download_folder = check_folder(main.path, os.path.join('downloads', 'IRS'))
            self.nccs_download_folder = check_folder(main.path, os.path.join('downloads', 'NCCS'))
        self.headers = {'user-agent': 'National Center for Charitable Statistics, Data Retrieval Tool (jlevy@urban.org)'}
        self.irs_delim = ' '
        self.epostcard_delim = '|'
        self.bmf_delim = ','
        self.clear_old = clear_old #if True, deletes old dataframes from memory after backfill

        self.get_from_sql = get_from_sql #if True, will attempt to connect to the NCCS data store and download ntee and fipsmsa
        self.sql_server_name = 'uiresearchrds.urban.org'
        self.sql_connection = None
        self.sql_cache = {} #stores dataframes retrieved from sql

        self.data_dict  = {}
        self.prior_year_df = {}
        self.droplists  = {}
        self.crosswalks = {}
        self.backfilled = {}
        self.not_crosswalked = {}
        self.dropped_columns = {}
        self.missing_columns = {}
        self.core_file_year = current_yr
        self.backfill_yrs = backfill

        self.numeric_columns = ['ACCNTINGFEES','ACCNTSPAYABLEEND','ACCNTSRCVBLEND','ADVRTPROMO','ASS_EOY','BENIFITSMEMBRS','BOND_EOY',
            'COMPENS','COMPNSATNANDOTHR','CONT','CONVERCONVENTMTNG','CURRFRMRCVBLEND','DEFEREDREVNUEND','DEPRCATNDEPLETN','DIREXP',
            'DUESASSESMNTS','ESCRWACCNTLIABEND','EXPS','FEESFORSRVCLOBBY','FEESFORSRVCMGMT','FEESFORSRVCINVSTMGMT','FEESFORSRVCOTHR','FISYR','FUNDBAL',
            'FUNDFEES','GOODS','GRNSTTOINDIV','GRNTSPAYABLEEND','GRNTSTOFRGNGOVT','GRNTSTOGOVT','GRPROF','GRSINCFNDRSNG','GRSINCGAMING',
            'GRSRNTSPRSNL','GRSRNTSREAL','INFOTECH','INSURANCE','INTANGIBLEASSETSEND','INTERESTAMT','INVENTG','INVINC','INVNTRIESALESEND',
            'INVSTMNTSEND','INVSTMNTSOTHREND','INVSTMNTSPRGMEND','LEGALFEES','LESSDIRFNDRSNG','LESSDIRGAMING','LIAB_EOY','LNDBLDGSEQUIPEND',
            'MISCREVTOTA','MISCREVTOT11B','MISCREVTOT11C','MISCREVTOT11D','MRTG_EOY','NETGNLS','NETINC','NETINCFNDRSNG','NETINCGAMING',
            'NETRENT','NONINTCASHEND','NOTESLOANSRCVBLEND','OCCUPANCY','OFFICEXPNS','OTHINC','OTHRASSETSEND','OTHREMPLYEEBENEF',
            'OTHREXPNSA','OTHREXPNSB','OTHREXPNSC','OTHREXPNSD','OTHREXPNSE','OTHREXPNSF','OTHRLIABEND','OTHSAL','OVERPAY','P1TOTEXP',
            'P1TOTREV','P2TASFMV','P2TOTAST','P6ESTTX','P6TEXCTX','P6TXINV','P6TXPNLT','P6TXWERR','P6TXWTH','PAYBLETOFFCRSEND','PAYTAX',
            'PENSIONPLANCONTRB','PLDGEGRNTRCVBLEND','PREPAIDEXPNSEND','PRGMSERVREV','PROGREV','PYMTOAFFILIATES','RCVBLDISQUALEND','RNTLEXPNSPRSNL',
            'RNTLEXPNSREAL','RNTLINCREAL','RNTLINCPRSNL','ROYALTSEXPNS','ROYALTSINC','SALEOTHE','SALEOTHG','SALEOTHN','SALESECN',
            'SALESEXP','STYEAR','SVNGSTEMPINVEND','TAXDUE','TOTEXCAPGN','TOTEXCAPLS','TOTNETLIABASTEND','TOTREV','TOTREV2',
            'TOTREV2ACOLA', 'TOTREV2BCOLA', 'TOTREV2CCOLA', 'TOTREV2DCOLA', 'TOTREV2ECOLA','TOTREV2FCOLA','TRAVEL','TRAVELOFPUBLICOFFCL',
            'TXEXMPTBNDSPROCEEDS','UNSECUREDNOTESEND','P1TOTREV','P1TCONT','P1INTREV','P1DIVID','P1GRENTS','P1NGASTS','P1GINVPF','P1OTHINC','P1TOTEXP',
            'P1ADMEXP','P1CONTPD','P1EXCREV','P1TOTREV','P1TOTEXP','P14TNADJ','P14NADJA','P14NADJB','P14NADJC','P14NADJD','P14TQDIS','P14QDISA',
            'P14QDISB','P14QDISC','P14QDISD','P14TASVL','P14ASVLA','P14ASVLB','P14ASVLC','P14ASVLD','P14T4942','P14A4942','P14B4942','P14C4942',
            'P14D4942','P14TENDW','P14ENDWA','P14ENDWB','P14ENDWC','P14ENDWD','P14TTSUP','P14TSUPA','P14TSUPB','P14TSUPC','P14TSUPD','P14TPSUP',
            'P14PSUPA','P14PSUPB','P14PSUPC','P14PSUPD','P14TGINV','P14GINVA','P14GINVB','P14GINVC','P14GINVD','P2TINVSC','P2GVTINV','P2CRPSTK','P2CRPBND',
            'TOTREVP', 'EXPSP', 'ASS_BOY']

    def apply_crosswalk(self):
        """Crosswalks the IRS data with the NCCS variable names.  The crosswalks are retrieved from the "settings/crosswalk" folder.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main
        xwalks = self.crosswalks
        data_dict = self.data_dict

        for form in main.forms:
            self.not_crosswalked[form] = {}

            header_file = os.path.join(main.path, 'settings', 'crosswalk', '{}.txt'.format(form.lower()))
            xwalks[form] = {}

            with open(header_file, 'r') as f:
                _ = f.readline() #discard headers
                for line in f:
                    nccs, irs = line.split(',')
                    irs = irs.strip().upper()
                    nccs = nccs.strip()
                    xwalks[form][irs] = nccs
                if 'EIN' in xwalks[form].keys():
                    del xwalks[form]['EIN'] #EIN is set as the index, and thus not treated as a column

            df = data_dict[form]

            #Test that there is one value to crosswalk to taxper.  Note: Python bools have int values, True=1, False=0
            cols = df.columns
            val = ('TAX_PRD' in cols) + ('TAX_PD' in cols) + ('A_TAX_PRD' in cols) + ('TAXPRD' in cols) +\
                  ('tax_prd' in cols) + ('tax_pd' in cols) + ('a_tax_prd' in cols) + ('taxprd' in cols)
            assert(val < 2), 'Found more than one value for the crosswalk to TAXPER in {} {}'.format(form, self.core_file_year)
            assert(val > 0),  'Expected to find one of TAX_PRD, TAX_PD or A_TAX_PRD to crosswalk to TAXPER in {} {}; if there is a new one it must be added to the checks in the apply_crosswalks() method.'.format(form, self.core_file_year)

            #converts all columns headers to upper case, to avoid case mismatches
            old_vals = df.columns.values
            old_vals = [v.upper() for v in old_vals]
            df.columns = old_vals

            df.rename(columns=xwalks[form], inplace=True)
            changes = len(set(old_vals).difference(df.columns.values))
            main.logger.info('Crosswalk applied to {} {}.  There were {} changes out of {} columns.'.
                  format(form, self.core_file_year, changes, len(old_vals)))

            missing = [c for c in xwalks[form].values() if c not in df.columns]
            self.not_crosswalked[form][self.core_file_year] = missing
            if len(missing) > 0:
                main.logger.info('WARNING: {} columns failed to crosswalk; see nccs.data.not_crosswalked["{}"]["{}"] for details.'.format(len(missing), form, self.core_file_year))

        main.logger.info('All crosswalks applied.\n')

    def drop_missing(self):
        """Drops "zero filers" when ALL of the values for a given EIN over the columns specified in the "drop if missing"
        folder are 0 or N.  The columns to consider are stored in the "settings/drop if missing" folder.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main
        data_dict = self.data_dict
        xwalks = self.crosswalks

        drop_criteria = ['N','0', 0]

        for form in main.forms:
            drop_list = []
            drop_file = os.path.join(main.path, 'settings', 'drop if missing', '{}.txt'.format(form.lower()))
            with open(drop_file, 'r') as f:
                _ = f.readline() #drop the line of instructions at the top

                #tries to crosswalk the entry from the droplist, but if it's not in the crosswalk then it is appended as-is
                for line in f:
                    try:
                        drop_list.append(xwalks[form][line.strip().upper()])
                    except KeyError:
                        drop_list.append(line.strip().upper())

            self.droplists[form] = drop_list

            df = data_dict[form]
            start_obs = len(df)
            if len(self.droplists[form]) > 0: #if no columns are specified in the text file, prevents dropping all obs
                data_dict[form] = df[~df[drop_list].isin(drop_criteria).all(axis=1)]
            end_obs = len(data_dict[form])
            main.logger.info('{} observations dropped from {} {} due to missing all values from droplist.'.
                  format(start_obs-end_obs, form, self.core_file_year, form))
        main.logger.info('Observations missing all values from "drop if missing" dropped.\n')

    def drop_on_values(self):
        """Method for dropping only specific values of the data.  Currently only used to remove SUBSECCD != 92
        from the PF data.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main
        data_dict = self.data_dict

        for form in main.forms:
            df = data_dict[form]
            if form == 'PF':
                df = df[df['SUBSECCD'] != '92']
            elif form == 'EZ':
                pass
            elif form == 'Full':
                pass
            data_dict[form] = df

    def backfill(self):
        """Accesses the main dataset at the top level (from init_final()), then fills in missing EINs
        from one year previous.  Then repeats the step on the newly expanded data from two years
        previous, out to as many periods as are specified.

        The data for backfilling is retrieved from SQL (or from file if it is already downloaded).

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main
        backfill = self.backfill_yrs #int, 0, 1, 2, 3
        current_yr = self.core_file_year #int, 2014, 2015
        backfill_years = [current_yr - y for y in range(1, backfill+1)] #list, [2014, 2013, 2012] if current_yr = 2015

        for form in main.write.data_dict.keys():
            self.backfilled[form] = {}

            if form == 'CO':
                dbase = 'coreco'
            else:
                dbase = 'nccs'

            for year in backfill_years:
                fname = 'core{}{}'.format(year, form.lower())
                main.logger.info('Loading prior release {} from MySQL...'.format(fname))
                old = self.get_sql(fname, dbase, match_dtypes=main.write.data_dict[form])
                main.logger.info('    success.')

                old['SOURCE'] = fname

                old = old.loc[:, [c for c in old.columns if c in main.write.data_dict[form].columns]]

                #turn some of the prior year columns into numbers
                if form != 'PF':
                    for c in ['TOTREVP', 'EXPSP', 'ASS_BOY']:
                        old[c] = pd.to_numeric(old[c], errors='coerce').fillna(0)

                current_eins = main.write.data_dict[form].index
                prev_yr_eins = old.index
                eins_to_backfill = list( set(prev_yr_eins).difference(current_eins) )
                self.backfilled[form][year] = eins_to_backfill

                backfill_obs = old.loc[eins_to_backfill]
                main.write.data_dict[form] = pd.concat([main.write.data_dict[form], backfill_obs])

                #since the older builds from the SQL days don't have these columns, their NaNs must be filled with the proper starting state
                #this should no longer matter once 2013 and earlier releases are out of rotation
                main.write.data_dict[form][main.validate.validation_state_column_name] = main.write.data_dict[form][main.validate.validation_state_column_name].fillna(main.validate.unchanged)
                main.write.data_dict[form][main.validate.manual_fix_column_name] = main.write.data_dict[form][main.validate.manual_fix_column_name].fillna('')

                main.logger.info('Backfilled {} observations into {} from {}.'.format(len(backfill_obs), form, year))

        main.logger.info('All missing EINs backfilled from previous releases.\n')

    def init_final(self):
        """This method copies the final EZ, Full and PF data from the nccs.data level to the nccs base level,
        before it is combined and split into the CO, PC and PF files.

        Note that this step is mainly redundant after changes to backfilling and prior data handling, but it
        was nearly costless to leave in and quite a pain to remove.  The only relevant part is the adding of
        the validation tracking columns at the end, but that could easily be moved to the backfilling
        method.  Removing this method has been added to the github issues list.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main
        main.data_dict = {}

        for form in main.forms:
            assert(self.data_dict[form].index.name == 'EIN')
            main.data_dict[form] = self.data_dict[form].copy(deep=True) #initialize the final product dataset
            assert(main.data_dict[form].index.name == 'EIN')
            if self.clear_old:
                self.data_dict[form] = None

            #add the validation tracking columns here, because they may exist in the backfilling data
            main.data_dict[form][main.validate.validation_state_column_name] = main.validate.unchanged
            main.data_dict[form][main.validate.manual_fix_column_name] = ''

    def epostcard(self):
        """Downloads the IRS epostcard (990N) data, then merges in the YEAR column on EIN for the Full and EZ files.
        Later, in the Process stage, this columns is checked against the FISYR column to turn it into a yes/no entry
        for whether a firm filed a 990N in the same year as an EZ or Full 990.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main
        if 'EZ' in main.forms or 'Full' in main.forms:
            df_epost = self.download_epostcard()

            if 'Full' in main.forms:
                main.data_dict['Full'] = main.data_dict['Full'].merge(df_epost, how='left', left_index=True, right_index=True)
                main.logger.info('Merged EPOSTCARD data with Full.')
            if 'EZ' in main.forms:
                main.data_dict['EZ'] = main.data_dict['EZ'].merge(df_epost, how='left', left_index=True, right_index=True)
                main.logger.info('Merged EPOSTCARD data with EZ.')

            main.logger.info('Finished merging EPOSTCARD data for 990n indicator.\n')

    def prior_year(self):
        """Merges selected prior year variables into current data, appending 'P' to the end OR changing 'EOY' to 'BOY'
        (end of prior year value becomes beginning of current year value).

        It then tests that the FISYR for the prior year data (renamed FISYRP) is the year before the current
        FISYR (i.e. FISYRP = FISYR - 1), then nulls all the merged data where this is not true.  It uses this
        same criteria to fill in the INPIOR column with 1 where FISYRP = FISYR - 1 and 0 otherwise.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main
        cols = ['EIN', 'ASS_EOY', 'BOND_EOY', 'MRTG_EOY', 'LIAB_EOY', 'TAXPER', 'FISYR', 'PROGREV',
                'INVINC', 'NETRENT', 'SALESECN', 'SALEOTHN', 'FUNDINC', 'GRPROF', 'OTHINC',
                'TOTREV', 'EXPS', 'NETINC', 'COMPENS', 'OTHSAL', 'PAYTAX', 'FUNDFEES',
                'CONT', 'RETEARN', 'FUNDBAL', 'SOURCE']# 'DocCD', 'DUES']
        ocols = [(c+'P').replace('EOYP', 'BOY')\
                        .replace('RETEARNP', 'RETE_BOY')\
                        .replace('FUNDBALP', 'NETA_BOY')\
                        .replace('SOURCEP', 'INPRIORSRC').upper() for c in cols]
        ocols = ocols[1:] #cut off EINP
        rename_dict = dict(zip(cols[1:], ocols))

        def _prior_year(df, form):

            year = self.core_file_year - 1
            fname = 'core{}{}'.format(year, form.lower())
            main.logger.info('Loading prior release {} from MySQL...'.format(fname))

            if form == 'CO':
                dbase = 'coreco'
            else:
                dbase = 'nccs'
            old = self.get_sql(fname, dbase, cols=cols, match_dtypes=df)
            main.logger.info('    success.')

            # old = old[cols]
            old.rename(columns=rename_dict, inplace=True)

            merged = df.merge(old, how='left', left_index=True, right_index=True)
            #finds the indexes where the past FISYR (FISYRP) is not equal to the current FISYR - 1
            #note that this includes any entry where FISYR or FISYRP are NaN
            merged['bad_fisyr'] = ~merged.apply(lambda r: float(r.FISYR) == float(r.FISYRP) + 1, axis=1)

            #replaces the newly-merged values with NaN if FISYRP != FISYR - 1
            bad_ilocs = merged.reset_index()[merged.reset_index()['bad_fisyr']].index
            merged.iloc[bad_ilocs, [merged.columns.get_loc(l) for l in ocols]] = np.NaN
            assert(merged.index.name == 'EIN')

            #assign all columns to INRPIOR=yes, then go back and reassign INPRIOR=no where necessary
            merged['INPRIOR'] = '1'
            merged.iloc[bad_ilocs, merged.columns.get_loc('INPRIOR')] = '0'
            del merged['bad_fisyr']
            assert(merged.index.name == 'EIN')

            #turn some of the prior year columns into numbers
            for c in ['TOTREVP', 'EXPSP', 'ASS_BOY']:
                merged[c] = pd.to_numeric(merged[c], errors='coerce')

            main.logger.info('    merged into {} successfully.'.format(form))
            return merged

        if 'EZ' in main.forms:
            main.logger.info('Loading prior year NCCS release data...')
            for form in ['CO', 'PC']:
                main.write.data_dict[form] = _prior_year(main.write.data_dict[form], form)

            main.logger.info('All past data loaded.\n')

    def check_columns(self):
        """Checks the columns in the final ouput against the columns expected to be present in the final
        output.  Drops extra columns and logs any missing ones.

        The expected columns are retrieved from "settings/final variable list" folder.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main

        main.logger.info('Validating final columns based on contents of "final variable lists" folder...')

        if main.write.output_full:
            for form in ['CO', 'PC']:
                df = main.write.data_dict[form]
                df = df[(df['SOURCE'].str.split('.').apply(lambda r: r[0]).str.endswith('990'))].copy() #split out only the entries from CO or PC that come from the Full 990
                main.write.data_dict[form+'_full'] = df
                assert(main.write.data_dict[form+'_full'].index.name == 'EIN')

        for form in main.write.data_dict.keys(): #PF, CO, PC, CO_full, PC_full
            path = os.path.join(main.path, 'settings', 'final variable lists', form.lower()+'.txt')
            with open(path, 'r') as f:
                desired_cols = [c.rstrip('\n') for c in f]
            desired_cols += ['VALIDATION_STATE', 'MANUALLY_FIXED']

            df = main.write.data_dict[form]

            drops = []
            for col in df.columns:
                if col not in desired_cols:
                    drops.append(col)
            df = df.drop(drops, axis=1)
            self.dropped_columns[form] = drops
            main.logger.info('   dropped {} columns from {}.'.format(len(drops), form))

            missing = []
            for col in desired_cols:
                if col not in df.columns:
                    missing.append(col)
            self.missing_columns[form] = missing
            main.logger.info('    found {} missing columns from {}.'.format(len(missing), form))

            main.write.data_dict[form] = df
        main.logger.info('Finished validating columns.  See the dicts at nccs.data.dropped_columns and nccs.data.missing_columns for details.\n')

    def make_numeric(self):
        """Handles converting the dtypes for columns that are used in mathematical operations later into floats, from the default strings.

        This method should be generalized, or, better yet, dtypes should be made explicit from the beginning.  This is raised as a
        github issue.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main

        for form in main.forms:
            num_cols = [c for c in self.numeric_columns if c in main.data_dict[form].columns]
            for col in num_cols:
                main.data_dict[form][col] = pd.to_numeric(main.data_dict[form][col], errors='coerce').fillna(0) #recast the str columns to float64 or int64
            main.logger.info('Recast {} columns as numeric for form {}.'.format(len(num_cols), form))
        main.logger.info('Finished initializing final dataframes.  Check nccs.data.numeric_columns dictionary for details.\n')
