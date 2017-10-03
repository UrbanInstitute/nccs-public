from process_pf import *
from process_ez import *
from process_full import *
import pandas as pd
from numpy import random
import logging

import dask
import dask.dataframe as dd
dask.set_options(get=dask.multiprocessing.get) #switch from default multithreading to multiprocessing

# Code by Jeff Levy (jlevy@urban.org), 2016-2017

class Deduplicate():
    """
    Class that holds the deduplicate method, which knows how to select the "best" of any given EIN that
    shows up more than once in the index.  This was originally split into its own class so it could be
    inherited in multiple places, but that is now redundant; it is only inherited and called by the Write
    class.
    """
    def deduplicate(self, source, form, dup_criteria):
        """
        Method for efficiently removing duplicate EINs based on criteria specified in functions found in
        process_co_pc and process_pf.

        Originally the process was handled by building a column of tuples to sort by, but because of the
        large apply it was very slow.  The new process works by building temporary columns in order to take
        advanrage of vectorized operations under the hood of Pandas.

        ARGUMENTS
        source (dict) : A dictionary of DataFrames
        form (str) : The current form, e.g. 'CO', 'PC'
        dup_criteria (func) : The appropriate function for deduplicating the current form

        RETURNS
        DataFrame (with unique index)
        """
        main = self.main

        #first discard any entries with FISYR that is more than two years behind the release year
        release_year = main.data.core_file_year
        df = source[form][source[form]['FISYR'] >= release_year-2]

        #split the data into one dataframe of all duplicates:
        dups = df[
                df.index.duplicated(keep=False)
                ].copy(deep=True)
        dups['rnd'] = random.random(len(dups))
        #and one dataframe of the unique eins
        df   = df[
                ~df.index.duplicated(keep=False)
                ].copy(deep=True)

        main.logger.info('Removing duplicate EINs from {}... '.format(form))

        #this old method works but is super slow due to the apply

        # #add a column where the duplicate selection criteria are in order, in a tuple
        # dups['dup_criteria'] = dup_criteria(dups)
        #
        # #take only the obs from each EIN with the max value of 'dup_criteria', which is calculated left to right
        # singled = dups.reset_index().groupby('EIN').apply(
        #                lambda dups: dups[dups['dup_criteria'] == dups['dup_criteria'].max()]
        #                ).set_index('EIN')
        # #drop the dup_criteria rand rnd columns
        # singled.drop('dup_criteria', axis=1, inplace=True)
        # singled.drop('rnd', axis=1, inplace=True)

        release_year = main.data.core_file_year #an int, e.g. 2005, when the primary FISYR should be 2005
        start_len = len(dups)
        dups, conditions = dup_criteria(dups)
        for cond in conditions:
            if cond == 'FISYR' and form != 'PF':
                #need to check FISYR for dups, to make sure we avoid the situation where, for example, the prior release was 2014 but the current release has both 2015 and
                #2016 in it.  if we just take the newest FISYR in that case, then the 2015 data will never appear in any release.  but we can't just take the 2015 data over
                #the 2016 data, because some firms may have had 2015 data in the prior release, and thus the 2016 data SHOULD be in this release.
                #
                #excludes PF because prior year data is not merged into the PF file
                dups['fisyr_max_minus'] = dups.groupby('EIN').apply(lambda g: ((g['FISYR'] == release_year) & (g['FISYRP'] == release_year-1)) | ((g['FISYR'] == release_year+1) & (g['FISYRP'].isnull()))).groupby('EIN').sum() == 2
            else:
                dups['fisyr_max_minus'] = False

            #dup_maxes = (dups.reset_index().groupby('EIN')[cond].max() - dups.groupby('EIN')['fisyr_max_minus'].max()).to_frame() #will be -0 for all non-FISYR conditions, otherwise will subtract 1 if it meets the above condition for FISYR

            #dups = dups.merge(dup_maxes, left_index=True, right_index=True, how='left', suffixes=('', '_max'))
            dups[cond+'_max'] = dups.groupby('EIN')[cond].max() - dups.groupby('EIN')['fisyr_max_minus'].max() #will be -0 for all non-FISYR conditions, otherwise will subtract 1 if it meets the above condition for FISYR
            first_len = len(dups)
            dups = dups[dups[cond] == dups[cond+'_max']]
            after_len = len(dups)
            main.logger.info('    {} EINs dropped based on {} from {}.'.format(first_len-after_len, cond, form))
        dups.drop([c+'_max' for c in conditions], axis=1, inplace=True)
        dups.drop(['val', 'rnd', 'fisyr_max_minus'], axis=1, inplace=True)

        #merge the single-fied duplicate observations back to the original data
        df = pd.concat([df, dups])#singled])

        assert(df.index.is_unique), 'Deduplication process did not result in unique EINs in {}'.format(form)
        main.logger.info('{} complete, {} total observations dropped.'.format(form, start_len-len(dups)))

        return df

class Process(ProcessPF, ProcessEZ, ProcessFull, Deduplicate):
    """
    Base class for the calculation of all new columns in the core files.  It holds the methods to create
    any columns that appear in all three 990 forms (calculated at the initial Full-EZ-PF level, not the
    final CO-PC-PF level), while it inherits the methods used by only one or two of the forms from the
    ProcessPF, ProcessEZ and ProcessFull classes.
    """
    def __init__(self, main, parallelize=False):
        self.main = main
        self.parallelize = parallelize
        self.chunksize = 100000

    def manual_fixes(self):
        """
        Base method for applying any manual, one-time fixes to the data.  This is usually defined as a change
        to a single EIN from a single year, in a non-generalizable way, e.g. a mistyped EIN in the raw IRS data.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main

        if 'PF' in main.forms:
            self.pf_manual()
        if 'EZ' in main.forms:
            self.ez_manual()
        if 'Full' in main.forms:
            self.full_manual()

    def calculate_columns(self):
        """
        Base method for creating all new, calculated columns in the core files.  The option to parallelize
        the calculations using Dask was added here, but was not found to speed the apply process up, so
        its use is not recommended.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main

        #process columns common to all forms:
        main.logger.info('Calculating new columns common to all dataframes.')
        for form in main.forms:
            df = main.data_dict[form]
            assert(df.index.name == 'EIN')

            df['FISYR'] = self.all_fisyr(df)
            df['ACCPER'] = self.all_accper(df)
            df['NCCSKEY'], df['NCCSKEY2'] = self.all_nccskey(df)
            df['RANDNUM'] = self.all_randnum(df)

            df['NTEECC'] = self.all_nteecc(df)
            df['NTEE1'] = self.all_ntee1(df)
            df['NTEEFINAL1'] = self.all_nteefinal1(df)
            df['LEVEL4'] = self.all_level4(df)

            if self.parallelize:
                df = dd.from_pandas(df, chunksize=self.chunksize)
                df = self.all_level1(df)
                df = df.rename(columns={'dask_result':'LEVEL1'})
                df = self.all_ntmaj10(df)
                df = df.rename(columns={'dask_result':'NTMAJ10'})
                df = self.all_majgrpb(df)
                df = df.rename(columns={'dask_result':'MAJGRPB'})
                df = self.all_level3(df)
                df = df.rename(columns={'dask_result':'LEVEL3'})
                df = self.all_level2(df)
                df = df.rename(columns={'dask_result':'LEVEL2'})
                df = self.all_ntmaj12(df)
                df = df.rename(columns={'dask_result':'NTMAJ12'})
                df = self.all_ntmaj5(df)
                df = df.rename(columns={'dask_result':'NTMAJ5'})
                df = df.compute()
            else:
                df['LEVEL1'] = self.all_level1(df)
                df['NTMAJ10'] = self.all_ntmaj10(df)
                df['MAJGRPB'] = self.all_majgrpb(df)
                df['LEVEL3'] = self.all_level3(df)
                df['LEVEL2'] = self.all_level2(df)
                df['NTMAJ12'] = self.all_ntmaj12(df)
                df['NTMAJ5'] = self.all_ntmaj5(df)

        if 'PF' in main.forms:
            self.pf_calculate()
        if 'EZ' in main.forms:
            self.ez_calculate()
        if 'Full' in main.forms:
            self.full_calculate()

        main.logger.info('All columns calculated.\n')

    # def handle_duplicates(self):
    #     #Redundant method: deduplication moved to Write class.
    #     main = self.main
    #
    #     from process_full import full_dup_criteria
    #     from process_ez   import   ez_dup_criteria
    #     from process_pf   import   pf_dup_criteria
    #     dup_crit_fns = {'EZ':ez_dup_criteria, 'Full':full_dup_criteria, 'PF':pf_dup_criteria}
    #
    #     for form in main.forms:
    #         dup_criteria = dup_crit_fns[form]
    #         main.data_dict[form] = self.deduplicate(main.data_dict, form, dup_criteria)
    #
    #     main.logger.info('All duplicate EINs removed.\n')

    def parallel_apply(self, df, func):
        """
        Experimental.

        ARGUMENTS
        df (dask.core.DataFrame) : A Dask dataframe
        func (func) : The function that needs to be applied in parallel

        RETURNS
        dask.core.DataFrame
        """
        assert(isinstance(df, dd.core.DataFrame)), 'A non-Dask dataframe was sent to the parallel_apply method.'
        # df = df.assign(dask_result=df.apply(lambda r: func(r), axis=1, meta=str))
        # df = df.assign(dask_result=df.map_partitions(func, columns=[c for c in ['SUBSECCD', 'FNDNCD', 'NTEEFINAL', 'LEVEL3', 'NTMAJ10'] if c in df.columns]))
        df = df.assign(dask_result=df.map_partitions(func, meta=str))
        return df
        # out_string = 'Handling parallely apply for {}'.format(func)
        # self.main.logger.info(out_string)
        # nprocs = self.nprocs #number of pieces to split the df into
        # split_size = int(np.ceil(len(df) / nprocs)) #number of rows in each split
        #
        # def parallel_func(args):
        #     func, df = args
        #     return df.apply(lambda r: func(r), axis=1)
        #
        # split_df = [df.iloc[i*split_size:(i+1)*split_size] if (i+1)*split_size <= len(df) else df.iloc[i*split_size:len(df)] for i in range(nprocs)]
        #
        # param_set = zip([func]*len(split_df), split_df)
        # with closing(mp.Pool(nprocs)) as pool:
        #     recombine = []
        #     for series in pool.imap_unordered(parallel_func, param_set):
        #         recombine.append(series)
        # return pd.concat(recombine)

    def all_randnum(self, df):
        """
        Generates a NumPy array of random numbers, the same length as the core file dataframe.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Array
        """
        return random.random(len(df))

    def all_nccskey(self, df):
        """
        Generates two new string columns, one in the form EIN+TAXPER, the other EIN+FISYR.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Two Series
        """
        main = self.main

        temp_df = df.reset_index() #pulls EIN out of the index

        #Joins the columns as strings.  Note, TAXPER is tax_prd in IRS original
        new_col1 = temp_df['EIN'] + temp_df['TAXPER']
        new_col2 = temp_df['EIN'] + temp_df['FISYR'].astype(str)

        #resets the indices back to EIN
        new_col1.index = df.index
        new_col2.index = df.index

        return new_col1, new_col2

    def all_fisyr(self, df):
        """
        Generates a Series as just the year portion of the TAXPER column.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        return df['TAXPER'].str.slice(0,4).astype(int)

    def all_accper(self, df):
        """
        Generates a Series as just the non-year portion (accounting period) of the TAXPER column.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        return df['TAXPER'].str.slice(4,6)

    def all_nteecc(self, df):
        """
        Generates a Series as a suibset of the NTEEFINAL columns.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        return df['NTEEFINAL'].str.slice(0, 4)

    def all_ntee1(self, df):
        """
        Generates a Series as a suibset of the NTEEFINAL columns.  Identical to NTEEFINAL1 and LEVEL4

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        return df['NTEEFINAL'].str.slice(0, 1)

    def all_nteefinal1(self, df):
        """
        Generates a Series as a suibset of the NTEEFINAL columns.  Identical to NTEE1 and LEVEL4.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        return df['NTEEFINAL'].str.slice(0, 1)

    def all_level4(self, df):
        """
        Generates a Series as a suibset of the NTEEFINAL columns.  Identical to NTEE1 and NTEEFINAL1.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Series
        """
        return df['NTEEFINAL'].str.slice(0, 1)

    def all_level1(self, df):
        """
        Generates a piecewise value based on SUBSECCD and FNDNCD.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Series or dask.core.DataFrame
        """
        def level1(row):
            sbcd = float(row['SUBSECCD'])
            fndc = float(row['FNDNCD'])

            if sbcd > 3 or sbcd == 1 or sbcd == 2:
                return 'O'
            elif sbcd == 3 and (fndc in [2, 3, 4]):
                return 'PF'
            elif sbcd == 3 and (fndc not in [2, 3, 4]):
                return 'PC'
            elif (sbcd not in [0, 3, np.NaN]) and (fndc in [0, np.NaN]):
                return 'O'
            elif (sbcd in [0, np.NaN]) and (fndc not in [0, 2, 3, 4, 9, np.NaN]):
                return 'PC'
            elif (sbcd in [0, np.NaN]) and (fndc in [2, 3, 4]):
                return 'PF'
            else:
                return 'U'

        if self.parallelize:
            return self.parallel_apply(df, level1)
        else:
            return df.apply(lambda r: level1(r), axis=1)

    def all_ntmaj10(self, df):
        """
        Generates a piecewise value based on NTEEFINAL.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Series or dask.core.DataFrame
        """
        def ntmaj10(row):
            ntf = row['NTEEFINAL']

            if ntf is np.NaN or ntf[0] in ['Z', '', ' ']:
                return 'UN'
            elif ntf[0] == 'A':
                return 'AR'
            elif ntf[0] == 'B':
                return 'ED'
            elif ntf[0] in ['C', 'D']:
                return 'EN'
            elif ntf[0] in ['E', 'F', 'G', 'H']:
                return 'HE'
            elif ntf[0] in ['I', 'J', 'K', 'L', 'M', 'N', 'O', 'P']:
                return 'HU'
            elif ntf[0] == 'Q':
                return 'IN'
            elif ntf[0] in ['R', 'S', 'T', 'U', 'V', 'W']:
                return 'PU'
            elif ntf[0] == 'X':
                return 'RE'
            elif ntf[0] == 'Y':
                return 'MU'
            else:
                return 'UN'

        if self.parallelize:
            return self.parallel_apply(df, ntmaj10)
        else:
            return df.apply(lambda r: ntmaj10(r), axis=1)

    def all_majgrpb(self, df):
        """
        Generates a piecewise value based on NTEEFINAL.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Series or dask.core.DataFrame
        """
        def majgrpb(row):
            ntf = row['NTEEFINAL']

            if ntf is np.NaN or ntf == '':
                return ntf
            elif ntf[:2] in ['B4', 'B5']:
                return 'BH'
            elif ntf[:2] == 'E2':
                return 'EH'
            else:
                return ntf[0]

        if self.parallelize:
            return self.parallel_apply(df, majgrpb)
        else:
            return df.apply(lambda r: majgrpb(r), axis=1)

    def all_level3(self, df):
        """
        Generates a piecewise value based on NTEEFINAL.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Series or dask.core.DataFrame
        """
        def level3(row):
            ntf = row['NTEEFINAL']

            if ntf is np.NaN or ntf == '':
                return '-'
            elif ntf[:2] != 'B8' and ntf[1:3] == '11':
                return 'ZA'
            elif ntf[:2] != 'B8' and ntf[1:3] == '12':
                return 'ZB'
            elif ntf[0] == 'T' and ntf[1] == '2':
                return 'ZC'
            elif ntf[0] == 'T' and ntf[1] == '3':
                return 'ZD'
            elif ntf[0] == 'T' and ntf[1] == '7':
                return 'ZE'
            elif ntf[0] == 'T' and ntf[1:3] in ['90', '99']:
                return 'ZF'
            elif ntf[0] == 'T' and ntf[1] == '6':
                return 'ZF'
            elif ntf[:3] == 'Y30':
                return 'MR'
            elif ntf[0] == 'Y' and ntf[1:3] != '30':
                return 'MO'
            elif ntf[0] == 'A':
                return 'AR'
            elif ntf[0] == 'B':
                return 'ED'
            elif ntf[0] in ['C', 'D']:
                return 'EN'
            elif ntf[0] in ['E', 'F', 'G', 'H']:
                return 'HE'
            elif ntf[0] in ['I', 'J', 'K', 'L', 'M', 'N', 'O', 'P']:
                return 'HS'
            elif ntf[0] == 'Q':
                return 'IN'
            elif ntf[0] in ['R', 'S', 'T', 'U', 'V', 'W']:
                return 'PB'
            elif ntf[0] == 'X':
                return 'RE'
            elif ntf[0] == 'Z':
                return 'UN'
            else:
                return '-'

        if self.parallelize:
            return self.parallel_apply(df, level3)
        else:
            return df.apply(lambda r: level3(r), axis=1)

    def all_level2(self, df):
        """
        Generates a piecewise value based on SUBSECCD, FNDNCD, LEVEL3 and NTEEFINAL.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Series or dask.core.DataFrame
        """
        def level2(row):
            sbcd = float(row['SUBSECCD'])
            fndc = float(row['FNDNCD'])
            lvl3 = row['LEVEL3']
            ntf = row['NTEEFINAL']

            if sbcd == 3 and fndc == 4:
                return 'S'
            elif sbcd == 3 and fndc == 17:
                return 'S'
            elif lvl3 is not np.NaN and lvl3 is not '' and lvl3[0] == 'Z':
                return 'S'
            elif ntf is not np.NaN and ntf is not '' and ntf[0] == 'Y':
                return 'M'
            else:
                return 'O'

        if self.parallelize:
            return self.parallel_apply(df, level2)
        else:
            return df.apply(lambda r: level2(r), axis=1)

    def all_ntmaj12(self, df):
        """
        Generates a piecewise value based on NTEEFINAL.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Series or dask.core.DataFrame
        """
        def ntmaj12(row):
            ntf = row['NTEEFINAL']

            if ntf is not np.NaN and ntf[:2] in ['B4', 'B5']:
                return 'BH'
            elif ntf is not np.NaN and ntf[:2] == 'E2':
                return 'EH'
            else:
                return row['NTMAJ10']

        if self.parallelize:
            return self.parallel_apply(df, ntmaj12)
        else:
            return df.apply(lambda r: ntmaj12(r), axis=1)

    def all_ntmaj5(self, df):
        """
        Generates a piecewise value based on NATMAJ10, which is in turn calculated from NTEEFINAL.

        ARGUMENTS
        df (DataFrame) : Core file dataframe

        RETURNS
        Series or dask.core.DataFrame
        """
        def ntmaj5(row):
            if row['NTMAJ10'] in ['IN', 'EN', 'PU', 'RE', 'MU', 'UN']:
                return 'OT'
            else:
                return row['NTMAJ10']

        if self.parallelize:
            return self.parallel_apply(df, ntmaj5)
        else:
            return df.apply(lambda r: ntmaj5(r), axis=1)
