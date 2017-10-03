import sys
import os
import numpy as np
from data import check_folder, clear_files
from validate_ez import *
from validate_full import *
from validate_pf import *
import datetime
import logging
import pandas as pd

# Code by Jeff Levy (jlevy@urban.org), 2016-2017

class Validate(ValidateEZ, ValidateFull, ValidatePF):
    """
    Base class for validating the data, including testing observations and flagging errors, as well as
    outputting particularly large firms for additional scrutiny.  Also then re-integrates that same
    data when it finds it in the "fixed validation" folder.
    """
    def __init__(self, main, tolerance, do_validation, partial_validation):
        self.main = main
        self.validate_folder = check_folder(main.path, os.path.join('validation', 'failures'))
        clear_files(main.path, self.validate_folder)
        self.validate_fixes  = check_folder(main.path, os.path.join('validation', 'fixes'))
        self.validation_failed = False
        self.tolerance = tolerance
        self.integrated_fixes = False
        self.manual_fix_column_name = 'MANUALLY_FIXED'
        self.validation_state_column_name = 'VALIDATION_STATE'
        self.validation_reason = 'VALIDATION_REASON'
        self.do_validation = do_validation
        self.partial_validation = partial_validation

        self.validation_tracking = dict()
        for form in ['CO', 'PC', 'PF']:
            self.validation_tracking[form] = False

        self.failed_eins = dict() #for tracking EINs written out as failures

        #values for VALIDATION_STATE column
        self.unchanged = 0
        self.fixed     = 1
        self.ignored   = 2
        self.checked   = 3

        #storage of validation failures
        self.validation_output = {'CO':{'L':None, 'C':None, 'F':None},
                                  'PC':{'L':None, 'C':None, 'F':None},
                                  'PF':{'L':None, 'C':None, 'F':None}}

        self.fixes_applied = {'CO':0, 'PC':0, 'PF':0}

    def to_file(self):
        """
        Method for writing EINs flagged for validation out to the "validation failures" folder.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main
        for form, types in self.validation_output.items():
            if all([d is None for d in types.values()]):
                continue

            df = pd.concat(types)
            assert(df.index.dtype.type is np.object_), 'First'
            grp = df.reset_index().groupby('EIN')
            df = df.merge(grp['level_0'].unique().map(lambda r: ''.join(r)).to_frame(), left_index=True, right_index=True, how='left')
            assert(df.index.dtype.type is np.object_), 'Second'
            df.rename(columns={'level_0':self.validation_reason}, inplace=True)
            assert(df.index.dtype.type is np.object_), 'Third'
            df = df.reset_index().groupby('EIN').head(1)
            assert(df['EIN'].dtype.type is np.object_), 'Fourth'
            df.drop('level_0', axis=1, inplace=True)
            df.set_index('EIN', inplace=True)
            assert(df.index.dtype.type is np.object_), 'Fifth'

            df.to_csv(os.path.join(main.path, self.validate_folder, '{}_{}_validate.csv'.format(form.lower(), main.data.core_file_year)))

        if self.validation_failed and not self.partial_validation: #catch for partial validation also?
            exit_str = 'Validation completed with unresolved failures; final output will not be written.  Check folder "{}" for files to manually audit.\n'.format(self.validate_folder)
            main.logger.info(exit_str)
            main.end_logging()
            sys.exit()

    def validate_columns(self):
        """
        Base method for entering the process to validation calucations.  Begins by integrating any fixes found
        in the validation fixes folder, then calls the validation methods for each form.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main

        #this should be redundant now, but the conditional makes it harmless to leave in
        for form in main.write.data_dict.keys():
            #adds the validation tracking columns if they are not already present
            #this is run in a separate loop at the start because the columns must
            #exist before fixes are reintegrated with those columns
            if self.validation_state_column_name not in main.write.data_dict[form].columns:
                main.write.data_dict[form][self.validation_state_column_name] = self.unchanged
                main.write.data_dict[form][self.manual_fix_column_name] = ''
                #main.write.data_dict[form][self.validation_reason] = ''

        if any(self.do_validation.values()):
            path = os.path.join(main.path, self.validate_fixes)
            if len([f for f in os.listdir(path+os.sep) if f.endswith('.csv')]) > 0:
                #if files are found in the "fixes" folder, it integreates them
                self.integrate_fixes()
            else:
                log_str = 'No validation fixes found in "{}" folder, continuing with validation...\n'.format(self.validate_fixes)
                main.logger.info(log_str)

            if 'CO' in main.write.data_dict.keys():
                main.logger.info('Beginning validation of EZ observations...')
                self.validate_ez()
                main.logger.info('Begnning validation of Full observations...')
                self.validate_full()
                for form in ['CO', 'PC']:
                    df = main.write.data_dict[form]
                    status = self.validation_tracking[form]
                    self.validate_form(df, form, status)

            if 'PF' in main.write.data_dict.keys():
                main.logger.info('Begnning validation in PF...')
                self.validate_pf()
                df = main.write.data_dict['PF']
                status = self.validation_tracking[form]
                self.validate_form(df, 'PF', status)

            # if self.validation_failed:
            #     exit_str = 'Validation completed with unresolved failures; process halted.  Check folder "{}" for files to manually audit.\n'.format(self.validate_folder)
            #     exit_str = 'Validation completed with unresolved failures; final output will not be written.  Check folder "{}" for files to manually audit.\n'.format(self.validate_folder)
            #     main.logger.info(exit_str)
            #     main.end_logging()
            #     sys.exit()
            else:
                main.logger.info('Validation completed, there were no unresolved failures.\n')
        else:
            main.logger.info('Validation skipped due to do_validate=False argument in main.py.\n')

    def extract(self, qtile=.999, pchan=.5, cutoff=10000000):
        """
        Base method for extracting the largest and most-changed firms for additional validation.

        ARGUMENTS
        qtile (float) : Quartile cutoff to define the "largest" firms
        pchan (float) : Percent change in revenue, assets or expenses that qualfies as a "big change"
        cutoff (int) : Revenue threshold below which we ignore large changes as defined by pchan

        RETURNS
        None
        """
        main = self.main

        def _extract(df, form, current, prior, qtile=qtile, pchan=pchan, cutoff=cutoff):
            rev, exp, ass = current
            revp, expp, assp = prior

            #largest .1%
            largest = df[ ((df[rev] >= df[rev].quantile(qtile)) | (df[exp] >= df[exp].quantile(qtile)) | (df[ass] >= df[ass].quantile(qtile))) & (~df['VALIDATION_STATE'].astype(int).isin([2, 3]))].copy()
            if len(largest) > 0: self.validation_failed = True
            output = 'Extracting the firms from {} in the largest {} quartile for revenue, assets or expenses for additional checks.'.format(form, qtile)
            main.logger.info(output)

            #largest[self.validation_reason] = self.largest
            #largest.to_csv(os.path.join(main.path, self.validate_folder, '{}_validate_largest.csv'.format(form.lower())))
            self.validation_output[form]['L'] = largest

            if revp != '':

                #50% changes
                changed = df[ ((abs(df[rev] - df[revp])/ df[revp] >= pchan) | (abs(df[exp] - df[expp])/ df[expp] >= pchan) | (abs(df[ass] - df[assp])/ df[assp] >= pchan)) & (~df['VALIDATION_STATE'].astype(int).isin([2, 3])) ].copy()
                changed = changed[ (changed[rev] >= cutoff) | (changed[revp] >= cutoff) ]
                if len(changed) > 0: self.validation_failed = True
                output = 'Extracting the firms from {} with >{}% change in revenue, expenses or assets and >{} in revenue this year or last.'.format(form, 100*pchan, cutoff)
                main.logger.info(output)

                #changed[self.validation_reason] = self.changed
                #changed.to_csv(os.path.join(main.path, self.validate_folder, '{}_validate_bigchanges.csv'.format(form.lower())))
                self.validation_output[form]['C'] = changed

        if 'EZ' in main.forms:
            for form in ['CO', 'PC']:
                current = ('TOTREV2', 'EXPS', 'ASS_EOY')
                prior   = ('TOTREVP', 'EXPSP', 'ASS_BOY')
                df = main.write.data_dict[form]
                _extract(df, form, current, prior)
        if 'PF' in main.forms:
            current = ('P1TOTREV', 'P1TOTEXP', 'P2TOTAST')
            prior   = ('', '', '')
            df = main.write.data_dict['PF']
            _extract(df, 'PF', current, prior)

        main.logger.info('Finished extracting additional validation data.\n')

    def validate(self, df, failed_validation, col_name, form, sub_form):
        """
        Method used on a per-column basis to see if there are any validation failures.  This is called from
        within each of the form-specific validation classes (e.g. validate_full.py) after the calculation
        has been done.

        ARGUMENTS
        df (DataFrame) : The entire dataframe for the form being validated
        failed_validation (bool) : The current status of the form
        col_name (str) : The name of the column being validated, e.g. validate_fu_netgnls
        form (str) : The current form, along the release axis of CO, PC or PF
        sub_form (str) : The source form, along the IRS axis of EZ, Full or PF (for logging purposes)

        RETURNS
        DataFrame
        Bool
        """
        tolerance = self.tolerance
        name = col_name[12:].upper() #strips off the leading "validate_" part of the column name

        col = df[df['VALIDATION_STATE'].astype('int') != self.ignored][col_name] #pulls the series but only for entries that aren't flagged "ignore"
        vcs = col.value_counts()

        val_fail = sum([vcs[i] for i in vcs.keys() if i > tolerance or i < -tolerance]) #number of observations that FAIL validation
        col_len = len(col)

        log_str = 'Column {} in form {} (subform {}) has {} validation failures ({}% of observations)'.format(name, form, sub_form, val_fail, round(100*val_fail/col_len, 1))
        self.main.logger.info(log_str)

        if val_fail == 0:
            pass #originally only validation columns with failures were kept, but for use with the validation fixer tool, all are now kept
            #df.drop(col_name, axis=1, inplace=True)
        else:
            failed_validation = True

        return df, failed_validation

    def validate_form(self, df, form, failed_validation):
        """
        Summarizes the validation status of a given form, once all columns have been analyzed.  It then handles
        logging, and setting up the validation output for the to_file method.

        ARGUMENTS
        df (DataFrame) : The form being summarized
        form (str) : Name of the form
        failed_validation (bool) : The flag from the validate method indicating whether there were any
                                   failures for this form

        RETURNS
        None
        """
        main = self.main
        tolerance = self.tolerance
        partial_validation = self.partial_validation

        if failed_validation and (not partial_validation or self.fixes_applied[form] == 0):
            val_cols = [c for c in df.columns if c.startswith('validate_')]
            df = df[(df[val_cols].abs() > tolerance).any(axis=1)] #limits output to only observations with a validation failure
            df = df[df['VALIDATION_STATE'] != self.ignored].copy() #ignores validation failures that have been flagged as "ignore"
            #df[self.validation_reason] = self.failed
            #df.to_csv(os.path.join(main.path, self.validate_folder, '{}_validate_failures.csv'.format(form.lower())))
            self.validation_output[form]['F'] = df
            self.failed_eins[form] = df.index
            log_str = 'Form {} validation failures outputted to folder "{}"'.format(form, self.validate_folder)
            self.validation_failed = True
        elif failed_validation and partial_validation and self.fixes_applied[form] > 0:
            log_str = 'Form {} has failures remaining, but all will be ignored because partial_validation=True and the number of fixes integrated is greater than zero.'.format(form)
            self.failed_eins[form] = []
        else:
            log_str = 'Form {} passed all validations.'.format(form)
            self.failed_eins[form] = []
        main.logger.info(log_str)

    def integrate_fixes(self):
        """
        Method for handling the incorporation of fixed validation errors back into the data.  If the
        validation fixer has been used to generate fixes, they will automatically be in the right place
        and in the right configuration for this method to find and use.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main

        path = os.path.join(main.path, self.validate_fixes)

        for form in main.write.data_dict.keys():
            try:
                fixes_df = pd.read_csv(os.path.join(path, '{}_{}_validate.csv'.format(form.lower(), main.data.core_file_year)), dtype='str')
                number_of_fixes = len(fixes_df[fixes_df['VALIDATION_STATE'] != 0])
                self.fixes_applied[form] = number_of_fixes
                log_str = 'Found {} validation fixes or checks to merge into form {}'.format(number_of_fixes, form)
                main.logger.info(log_str)
            except FileNotFoundError:
                log_str = 'No validation fixes found for form {}.'.format(form)
                main.logger.info(log_str)
                continue

            # fixes_df = fixes_df[~fixes_df['SOURCE'].isin(['14eofinextract990.zip', '13eofinextract990.zip', '15eofinextract990.dat.dat'])] #TEMP FOR 2014/2015 due to backfill process change
            fixes_df.set_index('EIN', inplace=True)
            #recast required str columns in fixed dataframe as numeric
            num_cols = [c for c in main.data.numeric_columns if c in fixes_df.columns]
            for col in num_cols:
                fixes_df[col] = pd.to_numeric(fixes_df[col], errors='coerce')

            drop_cols = [c for c in fixes_df.columns if c.startswith('validate_')]#+[self.manual_fix_column_name]
            fixes_df.drop(drop_cols, axis=1, inplace=True) #separates the manual fixes column from the data
            fixes_df = fixes_df.loc[[i for i in fixes_df.index if i in main.write.data_dict[form].index]] #make sure only EINs that are in both dfs are merged - should be redundant
            main.write.data_dict[form].loc[fixes_df.index] = fixes_df

            log_str = 'Integrated {} rows of manually fixed EINs from "{}" folder into form {}'.format(len(fixes_df),self.validate_fixes, form)
            main.logger.info(log_str)

        self.integrated_fixes = True
        main.logger.info('Integration of manual fixes completed, continuing with validation...\n')
