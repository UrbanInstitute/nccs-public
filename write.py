from data import check_folder, clear_files
from process import Deduplicate
import pandas as pd
import numpy as np
import os
import logging
from process_co_pc import pc_dup_criteria, co_dup_criteria

# Code by Jeff Levy (jlevy@urban.org), 2016-2017

class Write(Deduplicate):
    """
    This class handles writing the final dataframes out for release.  It can tell which files to create
    by which dataframes it currently knows, aside from the "_full990" files, which are set by flag at
    startup.

    Inherits the Deduplicate class from the process.py file; this is now an unnecessary inheritance because
    all deduplication happens here.  Originally deduplication happened in the process stage AND in the
    write stage.
    """
    def __init__(self, main, output_full):
        self.main = main
        self.data_dict = {}
        self.output_folder = os.path.join(main.path, check_folder(main.path, 'final output'))
        self.output_full = output_full
        clear_files(main.path, self.output_folder)

    def build_output(self):
        """
        This method goes through the dataframes that come out of the data and process classes, split along
        the initial axis of Full, EZ or PF, then splits and recombines them into the CO, PC and PF files.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main
        forms = main.forms

        if 'PF' in forms:
            # If PF is found in the forms, then it creates the PF file - currently this is just a
            # pointer, because there is no additional merging or processing.
            pf = main.data_dict['PF']

            main.logger.info('Building PF file from PF source.')
            self.data_dict['PF'] = main.data_dict['PF'].copy()
            assert(self.data_dict['PF'].index.name == 'EIN')

        if 'EZ' in forms and 'Full' in forms:
            # If both EZ and Full are present, it will split them apart based on the SUBSECCD column,
            # then merge the split sections together to form the CO and PC files.  It then has to
            # de-duplicate them again, because sometimes the same EIN exists in both the EZ and Full
            # sources, which to this point have been processed separately.
            ez   = main.data_dict['EZ']
            full = main.data_dict['Full']

            def _na_fill(df):
                #for fixing NaNs created by concatenting EZ entries with Full
                num_cols = df.select_dtypes(include=[np.number]).columns.values
                str_cols = df.select_dtypes(include=[np.object_]).columns.values
                df.loc[:, num_cols] = df.loc[:, num_cols].fillna(0)
                df.loc[:, str_cols] = df.loc[:, str_cols].fillna('')
                return df

            main.logger.info('Building PC file from Full and EZ source.')
            ezpc = ez[ez['SUBSECCD'] == '03']
            fullpc = full[full['SUBSECCD'] == '03']
            pc = pd.concat([ezpc, fullpc])
            pc = _na_fill(pc)

            self.data_dict['PC'] = pc

            main.logger.info('Building CO file from Full and EZ source.')
            ezco = ez[ez['SUBSECCD'] != '03']
            fullco = full[full['SUBSECCD'] != '03']
            co = pd.concat([ezco, fullco])
            co = _na_fill(co)

            self.data_dict['CO'] = co

        if 'EZ' in forms and 'Full' not in forms:
            raise Exception('Including IRS form 990EZ, but not IRS form 990 full, is not enough to create either the CO or PC files.')

        main.logger.info('Finished building final output.\n')

    def handle_duplicates(self):
        """
        The raw data, the data from backfilling, and the data from merging and splitting into CO/PC, may all
        result in non-unique EINs in the index.  The method loads the criteria to select the "best" instance
        of a given EIN from the process_co_pc and process_pf classes, then applies them to all the dataframes
        in memory.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main

        from process_co_pc import pc_dup_criteria, co_dup_criteria
        from process_pf import pf_dup_criteria

        dup_crit_fns = {'CO':co_dup_criteria, 'PC':pc_dup_criteria, 'PF':pf_dup_criteria}
        dup_crit_fns['CO_Full'] = dup_crit_fns['CO']
        dup_crit_fns['PC_Full'] = dup_crit_fns['PC']
        dup_crit_fns['CO_full'] = dup_crit_fns['CO']
        dup_crit_fns['PC_full'] = dup_crit_fns['PC']

        for form in self.data_dict.keys():
            dup_criteria = dup_crit_fns[form]
            self.data_dict[form] = self.deduplicate(self.data_dict, form, dup_criteria)

        main.logger.info('All duplicate EINs removed.\n')

    def to_file(self):
        """
        Writes the final releases to file, in the "final output" folder.

        ARGUMENTS
        None

        RETURNS
        NONE
        """
        main = self.main
        if not main.validate.validation_failed or main.validate.integrated_fixes:
            main.logger.info('Writing final output to file...')
            for form in self.data_dict.keys():
                y = main.data.core_file_year
                if form.lower().endswith('_full'):
                    name = form.lower() + '990'
                else:
                    name = form.lower()
                self.data_dict[form].to_csv(os.path.join(self.output_folder, 'core{}{}.csv'.format(y, name)))
                main.logger.info('Completed form {} written to {}'.format(form, self.output_folder + os.sep))
            main.logger.info('All dataframes written to file.\n')
        else:
            main.logger.info('Process halted before final output; validation errors must be addressed.')
