import os
import sys
import time
import subprocess
import webbrowser
from collections import defaultdict
import pandas as pd
import numpy as np
from numpy import floor, ceil

path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(path)
pd.set_option('display.float_format', lambda x: '%.3f' % x)

from validate_ez import *
from validate_full import *
from validate_pf import *
import data

"""
<Class>
    <Methods>   <description>
        <related methods>

Utilities
    generate_token          builds a "token" dictionary to pass between the loops with all values necessary for the current EIN
    update_df_row           extracts an updated row from a token to write back to the dataframe
    get_components          handles cross-referencing equation components (denoted by the * in the display)
    load_data               loads the dataframe at the start of the program
    load_saved              loads previously saved entries and merges them
    sort_data               sorts data by the specified criteria on program start
    build_url               builds Foundation Center URLs from the current EINs data
    pdf_opener              opens Foundation Center PDFs in default browser
    get_form_crosswalk      connects column names to IRS form 990 lines for user reference
    process_token_storage   handles the restoring of the EIN placed on hold in order to go back one

Display
    display                     main display loop
    display_static_header       program info at top between the *** lines
    display_form_header         header with info on the current form, including eins completed/remaining - also has the validation reason from the current EIN
    display_ein_header          header with info on the current row, rev/ass/exp both current and prior, plus tax period
    display_failed_equations    manages the failed equation display between the --- lines
    failure_entries             used for updating the failed equations section on the fly

UserInput
    get_explanation     asks user to explain what was done
    get_user            initial setup questions
    col_viewer          helper function for formatting output
    user_input          main menu, and methods related to it:
        ui_fixed
        ui_checked
        ui_ignore
        ui_skip
        ui_reset
        ui_quit
        ui_options
        ui_done_so_far
        ui_view
        ui_view_group
        ui_modify_row
        ui_get_fix

CoreFixer
    __init__        environmental variables
    start           base method called to begin the validation tool
    dataframe_loop  manages the loop through every row of the dataframe
    row_loop        manages the loop through a single row until fixed
    end             handles wrap-up and saving

"""

def wprint(text, chars=99, indent=True, ident=4):
    #adds auto wrapping and optional indenting to printed text
    first_line = True
    lines = []
    while len(text) > 0:
        if not first_line:
            eol = chars - ident
        else:
            eol = chars

        curr_line_rev = text[eol-1::-1]

        if '-' in curr_line_rev and '+' in curr_line_rev:
            split_pt = min(curr_line_rev.find('+'), curr_line_rev.find('-'))
        elif '-' in curr_line_rev:
            split_pt = curr_line_rev.find('-')
        elif '+' in curr_line_rev:
            split_pt = curr_line_rev.find('+')
        else:
            split_pt = 0

        if len(text) >= eol:
            line = text[:eol-split_pt]
        else:
            line = text

        text = text[len(line):].lstrip()
        if not first_line:
            line = ' '*ident + line
        else:
            first_line = False

        lines.append(line)

    for line in lines:
        print(line)

class Utilities():
    def generate_token(self, ein, row):
        if row['SOURCE'].split('.')[0].upper().endswith('EZ'):
            source = 'EZ'
        elif row['SOURCE'].split('.')[0].upper().endswith('990'):
            source = 'Full'
        elif row['SOURCE'].split('.')[0].upper().endswith('PF'):
            source = 'PF'
        else:
            source = ''

        token = {'current_ein':  ein,
                 'irs_source' :  source,
                 'original_row': row,
                 'modified_row': row.copy(),
                 'exit':  False,
                 'write': None,
                 'changes':{}}
        return token

    def update_df_row(self, token):
        self.df.loc[token['current_ein']] = token['modified_row'] #write result back to original

    def get_components(self):
        """
        Loads the methods for validation calculations from Core, then builds the cross references
        needed to track relations between equations (e.g. one equation that fails has TOTREV2 in it,
        so the program finds all equations with TOTREV2 and displays those also)
        """

        #creates an instance of the validation code from the main program
        validator = {'EZ':ValidateEZ(),
                     'Full':ValidateFull(),
                     'PF':ValidatePF()}

        components = {}
        validators = {}
        equations = {}

        validators['EZ'] = {'validate_ez_totrev': validator['EZ'].ez_validate_totrev,
                      'validate_ez_netinc': validator['EZ'].ez_validate_netinc,
                      'validate_ez_ass_eoy': validator['EZ'].ez_validate_ass_eoy,
                      'validate_ez_saleothn': validator['EZ'].ez_validate_saleothn,
                      'validate_ez_netincfndrsng': validator['EZ'].ez_validate_netincfndrsng,
                      'validate_ez_grprof': validator['EZ'].ez_validate_grprof
                      }

        validators['Full'] = {'validate_fu_netrent':validator['Full'].full_validate_netrent,
                      'validate_fu_netgnls':validator['Full'].full_validate_netgnls,
                      'validate_fu_netincfndrsng':validator['Full'].full_validate_netincfndrsng,
                      'validate_fu_netincgaming':validator['Full'].full_validate_netincgaming,
                      'validate_fu_grprof':validator['Full'].full_validate_grprof,
                      'validate_fu_totrev2':validator['Full'].full_validate_totrev2,
                      'validate_fu_fundbal':validator['Full'].full_validate_fundbal
                      }

        validators['PF'] = {'validate_pf_p1totrev':validator['PF'].pf_validate_p1totrev,
                            'validate_pf_p1totexp':validator['PF'].pf_validate_p1totexp,
                            'validate_pf_p1excrev':validator['PF'].pf_validate_p1excrev,
                            'validate_pf_p2tinvsc':validator['PF'].pf_validate_p2tinvsc,
                            'validate_pf_p14tnadj':validator['PF'].pf_validate_p14tnadj,
                            'validate_pf_p14tqdis':validator['PF'].pf_validate_p14tqdis,
                            'validate_pf_p14tasvl':validator['PF'].pf_validate_p14tasvl,
                            'validate_pf_p14t4942':validator['PF'].pf_validate_p14t4942,
                            'validate_pf_p14tendw':validator['PF'].pf_validate_p14tendw,
                            'validate_pf_p14ttsup':validator['PF'].pf_validate_p14ttsup,
                            'validate_pf_p14tpsup':validator['PF'].pf_validate_p14tpsup,
                            'validate_pf_p14tginv':validator['PF'].pf_validate_p14tginv
                            }

        for form in ['EZ', 'Full', 'PF']:
            equations[form] = {'_'.join(k.split('_')[2:]).upper(): v(None, fixer_display=True) for k, v in validators[form].items()}
            components[form] = {k: v.translate(str.maketrans({kk: None for kk in '+-=()'})).split() for k, v in equations[form].items()}

        all_cols = {}
        multiples = {}
        cross_components_dict = {}
        for form in ['EZ', 'Full', 'PF']:
            all_cols[form] = [col for cols in components[form].values() for col in cols] #all_cols[form] = ['col1', 'col2', 'col3'...]

            multiples[form] = []

            uniques = list(set(all_cols[form])) #unique list of every column in components keys or values
            for col in uniques:
                if all_cols[form].count(col) > 1:
                    multiples[form].append(col)

        #reverse the components dict, so every name that shows up more than once is a key, while the key it shows up in in components is a value
            cross_components_dict[form] = defaultdict(lambda: [])
            for m in multiples[form]:
                for k, v in components[form].items():
                    if m in v:
                        cross_components_dict[form][m].append(k)
            cross_components_dict[form] = dict(cross_components_dict[form])

        #pointers for ease of reference later
        components['FU'] = components['Full']
        cross_components_dict['FU'] = cross_components_dict['Full']
        multiples['FU'] = multiples['Full']
        validators['FU'] = validators['Full']
        equations['FU'] = equations['Full']

        return components, cross_components_dict, multiples, equations, validators

    def load_data(self):
        df = pd.read_csv(os.path.join(self.path, 'validation', 'failures', '{}_{}_validate.csv'.format(self.form.lower(), self.year)), dtype=self.make_strings)
        df.set_index('EIN', inplace=True)

        num_cols = df.select_dtypes(include=[np.number]).columns

        for c in num_cols:
            df[c.lower()+'_adjusted_by'] = 0 #initialize empty adjustment tracking columns
        df['validated_by'] = ''
        df['EXPLANATION'] = ''

        if self.load_df is not None:
            try:
                df.loc[self.load_df.index] = self.load_df
            except KeyError:
                #if the main process has been rerun and new validation output is present, but the fixes already applied haven't been deleted from the folder, they will fail to assign
                print('\nWARNING: It appears the existing fixes have already been integrated into the main process, as some of the EINs in the saved fix content are no longer marked for validating.')
                _ = input('Press any key to continue WITHOUT loading the fixes.  They will be OVERWRITTEN the next time you save.  Otherwise please exit the program to resolve the conflict.')

        failures = [c for c in df.columns if c.startswith('validate_') and 'adjusted' not in c]
        df.loc[:,failures] = df[failures].fillna(0)

        #filters out any entries that have already been solved (does not filter any entries if there is no loaded content)
        #stopped filtering this way to avoid overwriting content on save changes only, now just used to calculate start length.
        df['INCLUDE'] = ((df['VALIDATION_STATE'] != 2) & ((abs(df[failures]) >= self.threshold).any(1) | (df['VALIDATION_REASON'].isin(self.sort_criteria) & ~df['VALIDATION_STATE'].isin([1,3]))))
        # df = df[df['INCLUDE']]
        start_len = len(df[df['INCLUDE']])
        del df['INCLUDE']

        df['VALIDATION_REASON'] = pd.Categorical(df['VALIDATION_REASON'], self.sort_criteria, ordered=True)

        self.df = df
        self.num_cols = num_cols
        self.failures = failures
        self.start_len = start_len

    def load_saved(self, form):
        #form: (str) co, pc, pf
        load_df = pd.read_csv(os.path.join(path, 'validation', 'fixes', '{}_{}_validate.csv'.format(form.lower(), self.year)), dtype=self.make_strings)
        load_df.set_index('EIN', inplace=True)

        tracking_df = pd.read_csv(os.path.join(path, 'final output', '{}_change_tracker.csv'.format(form.lower())), dtype={'EIN':'str'})
        tracking_df.set_index('EIN', inplace=True)

        load_df = load_df.merge(tracking_df, how='outer', left_index=True, right_index=True, indicator=True)

        assert((load_df['_merge'] == 'both').all(axis=0)), 'Warning, EINs do not line up when merging existing changes with change tracking.'
        load_df.drop('_merge', axis=1, inplace=True)

        load_df['VALIDATION_REASON'] = pd.Categorical(load_df['VALIDATION_REASON'], self.sort_criteria, ordered=True)

        print('{} previously completed rows loaded.'.format(len(load_df)))
        return load_df

    def sort_data(self):
        df = self.df
        form = self.form
        if form == 'PF':
            rev = 'P1TOTREV'
        else:
            rev = 'TOTREV2'
        self.df = self.df.sort_values(['VALIDATION_REASON', rev], ascending=[True, False])

    def build_url(self, filename, taxperp):
        if self.form == 'PF':
            pf = 'pf'
        else:
            pf = ''

        if not taxperp:
            return 'http://990s.foundationcenter.org/990{}_pdf_archive/{}/{}/{}.pdf'.format(pf, filename[:3], filename.split('_')[0], filename)
        else:
            fn_split = filename.split('_')
            pfn = '_'.join([ fn_split[0], str(taxperp).rstrip('.0'), fn_split[2] ])
            return 'http://990s.foundationcenter.org/990{}_pdf_archive/{}/{}/{}.pdf'.format(pf, filename[:3], filename.split('_')[0], pfn)

    def pdf_opener(self, filename, taxperp=None, url=None):
        if not url:
            url = self.build_url(filename, taxperp)
        webbrowser.open_new_tab(url)

    def get_form_crosswalk(self):
        """
        For connecting column names to 990 form locations
        """
        return {'FULL': pd.Series(['Part VIII Line 1h', 'Part VIII Line 2g (A)', 'Part VIII Line 3A', 'Part VIII Line 4A', 'Part VIII Line 5A', 'Part VIII Line 6a (i)',
                                   'Part VIII Line 6a (ii)', 'Sum of Part VIII Line 6a (i) and (ii)', 'Part VIII Line 6b (i)', 'Part VIII Line 6b (ii)',
                                           'Sum of Part VIII Line 6b (i) and (ii)', 'Part VIII Line 6c (i)', 'Part VIII Line 6c (ii)', 'Part VIII Line 6d (A)',
                                           'Part VIII Line 7a (i)', 'Part VIII Line 7b (i)', 'Part VIII Line 7c (i)', 'Part VIII Line 7a (ii)', 'Part VIII Line 7b (ii)',
                                           'Part VIII Line 7c (ii)', 'Part VIII Line 7d', 'Part VIII Line 8a', 'Part VIII Line 8b', 'Part VIII Line 8c', 'Part VIII Line 9a',
                                           'Part VIII Line 9b', 'Part VIII Line 9c', 'Sum of Part VIII Line 8a and 9a', 'Sum of Part VIII Line 8b and 9b',
                                           'Sum of Part VIII Line 8c (A) and 9c (A)', 'Part VIII Line 10a', 'Part VIII Line 10b', 'Part VIII Line 10c (A)',
                                           'Part VIII Line 11e (A)', 'Part VIII Line 12 (A)', 'Part IX Line 5 (A)', 'Part IX Line 7 (A)', 'Part IX Line 10 (A)',
                                           'Part IX Line 11e (A)', 'Part IX Line 25 (A)', 'Part X Line 16 (A)', 'Part X Line 16 (B)', 'Part X Line 20 (B)', 'Part X Line 23 (B)',
                                           'Part X Line 24 (B)', 'Part X Line 26 (A)', 'Part X Line 26 (B)', 'Part X Line 32 (B)', 'Part X Line 33 (B)'],
                                           index=['CONT', 'PROGREV', 'INVINC', 'TXEXMPTBNDSPROCEEDS', 'ROYALTSINC', 'GRSRNTSREAL', 'GRSRNTSPRSNL', 'RENTINC', 'RNTLEXPNSREAL', 'RNTLEXPNSPRSNL',
                                                  'RENTEXP', 'RNTLINCREAL', 'RNTLINCPRSNL', 'NETRENT', 'SECUR', 'SALESEXP', 'SALESECN', 'SALEOTHG', 'SALEOTHE', 'SALEOTHN', 'NETGNLS',
                                                  'GRSINCFNDRSNG', 'LESSDIRFNDRSNG', 'NETINCFNDRSNG', 'GRSINCGAMING', 'LESSDIRGAMING', 'NETINCGAMING', 'SPEVTG', 'DIREXP', 'FUNDINC',
                                                  'INVENTG', 'GOODS', 'GRPROF', 'OTHINC', 'TOTREV2', 'COMPENS', 'OTHSAL', 'PAYTAX', 'FUNDFEES', 'EXPS', 'ASS_BOY', 'ASS_EOY', 'BOND_EOY',
                                                  'MRTG_EOY', 'UNSECUREDNOTESEND', 'LIAB_BOY', 'LIAB_EOY', 'RETEARN', 'FUNDBAL'],
                                           ),
                'EZ':   None,
                'PF':   None}

    def process_token_storage(self, token):
        """
        Method for when the user has gone back to the previous token and then finished it and needs to restore the delayed one.
        """
        self.update_df_row(token)         #update the df with the prior token
        token = self.token_storage['on_hold']   #extract the token that was placed on hold
        self.token_storage['on_hold'] = None    #empty the token storage
        return token                            #return the token that was placed on hold and make it the current token

class Display():
    def display(self, token):
        self.display_static_header()
        self.display_form_header(token)
        self.display_ein_header(token)
        self.display_failed_equations(token)

    def display_static_header(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        line0 = '****************************************'
        line1 = 'NCCS Core File Validation Tool v7.2017'
        line2 = 'Created by Jeff Levy (jlevy@urban.org)'
        line_list = [line0, line1, line2, line0, '']
        for line in line_list:
            print(line.center(self.terminal_width))

    def display_form_header(self, token):
        form = self.form
        num_fixed = self.num_fixed
        remaining = self.start_len - num_fixed

        ein       = token['current_ein']
        firm_name = str(token['modified_row']['NAME'])
        reason    = token['modified_row']['VALIDATION_REASON']

        lcol = int(floor(self.terminal_width / 2))
        rcol = int(self.terminal_width - lcol)

        sides = int(floor(self.terminal_width / 3))
        cent  = int(self.terminal_width - 2*sides)

        line4a = 'Form: {}'.format(form).ljust(sides)
        line4c = 'Validation Reasons: {}'.format(', '.join(list(reason))).center(cent)
        line4b = 'EINs Completed: {}'.format(num_fixed).rjust(sides)
        line5a = 'EIN:  {}'.format(ein).ljust(lcol)
        line5b = 'EINs Remaining: {}'.format(remaining).rjust(rcol)
        line6  = firm_name.center(self.terminal_width)
        line7  = '-'*len(firm_name) + '--'
        print(line4a+line4c+line4b)
        print(line5a+line5b)
        print(line6)
        print(line7.center(self.terminal_width))

    def display_ein_header(self, token):
        row = token['modified_row']
        source = token['irs_source']

        sides = int(floor(self.terminal_width / 3))
        cent  = int(self.terminal_width - 2*sides)

        if source in ['EZ', 'Full']:
            current = (float(row['TOTREV2']),float(row['EXPS']), float(row['ASS_EOY']))
            prior   = (float(row['TOTREVP']), float(row['EXPSP']), float(row['ASS_BOY']))
        elif source == 'PF':
            current = (float(row['P1TOTREV']), float(row['P1TOTEXP']), float(row['P2TOTAST']))
            prior   = None
        else:
            current, prior = None, None

        taxper = 'TAX PERIOD: '+row['TAXPER'][:4]+'-'+row['TAXPER'][4:]
        print(taxper.center(self.terminal_width))
        print('')

        if current:
            line1 = 'CURRENT: Revenue: {:,.0f}'.format(current[0]).center(sides) + 'Expenses: {:,.0f}'.format(current[1]).center(cent) + 'Assets: {:,.0f}'.format(current[2]).center(sides)
            print(line1)
        if prior:
            line2 = 'PRIOR:   Revenue: {:,.0f}'.format(prior[0]).center(sides) + 'Expenses: {:,.0f}'.format(prior[1]).center(cent) + 'Assets: {:,.0f}'.format(prior[2]).center(sides)
            print(line2)

        if current or prior:
            print('')
            print(' ' + '-'*int((ceil(self.terminal_width))-2))
            print('')

    def display_failed_equations(self, token):
        row = token['modified_row']
        failures = self.failure_entries(token)

        for fail in failures.index:

            eq = self.equations[fail[9:11].upper()][fail[12:].upper()]
            cols = self.components[fail[9:11].upper()][fail[12:].upper()]

            for col in cols:
                eq = eq.replace(col, col+' [{:,.0f}]'.format(row[col]))

            entries = '${:,.0f} = '.format(int(row[fail])) + eq
            for multiple in self.multiples[fail[9:11].upper()]:
                entries = entries.replace(multiple, multiple+'*')

            ident = len(fail[12:])+6
            if row[fail] < 0:
                ident += 1
            wprint(entries, ident=ident)
            print('')

        if len(failures.index) == 0:
            print('No validation failures found.\n'.center(self.terminal_width))

    def failure_entries(self, token):
        row = token['modified_row']

        failures = row.loc[self.failures]
        failures = failures[(abs(failures) >= self.threshold)] #display all failure columns

        #adds to the display any columns that passed validation, but contain columns that are parts of columns that did fail validation
        add_related = []
        for fail in failures.index: #e.g. fail='validate_ez_totrev'
            fail_components = self.components[fail[9:11].upper()][fail[12:].upper()] #e.g. fail_components=['CONT', 'PRGMSRVREV'...]
            for fail_component in fail_components:
                if fail_component in self.multiples[fail[9:11].upper()]:
                    component_sources = self.cross_components[fail[9:11].upper()][fail_component]
                    for potential in component_sources:
                        if 'validate_'+fail[9:11].lower()+'_'+potential.lower() not in failures.index:
                            add_related.append('validate_'+fail[9:11]+'_'+potential.lower())
        if len(add_related) > 0:
            failures = pd.concat([failures, row.loc[add_related]])

        return failures

class UserInput():
    def get_explanation(self, token):
        print('Enter an explanation for what was done to this row:')
        print('    1) Error on form: fields do not sum to total')
        print('    2) Error in data: fields not as represented on form')
        print('    3) Unable to fix: 990 image missing')
        print('    4) Unable to fix: fields missing')
        print('    5) Form OK, no change')
        print('    Other (type very short explanation)')
        choice = input('> ')

        token['modified_row'].loc['EXPLANATION'] = choice
        return token

    def get_user(self):
        self.display_static_header()
        print('Current threshold for a validation failure is: ${:,.0f}'.format(self.threshold))
        print('                  for a "large" firm: ${:,.0f}'.format(self.large_firm))
        print('                  for a firm with "large changes": {:.1%}'.format(self.changed))
        print('')
        while True:
            user = input('Please enter your name: ')
            if user != '':
                break
        while True:
            form = input('Which form will you be validating? [CO, PC, PF]: ')
            if form == '':
                pass
            elif form.upper() in ['CO', 'PC']:
                form = form.upper()
                break
            elif form.upper() == 'PF':
                form = form.upper()
                break
        while True:
            yr = input('    for which NCCS release year? [YYYY]: ')
            if len(yr) == 4:
                try:
                    yr_num = int(yr)
                except ValueError:
                    pass
                else:
                    self.year = yr_num
                    break
        while True:
            pdfs = input('Do you wish to automatically open each 990 original in a browser tab? [y/n]: ')
            if pdfs.lower() == 'y':
                self.open_pdfs = True
                break
            elif pdfs.lower() == 'n':
                self.open_pdfs = False
                break

        existing = '{}_change_tracker.csv'.format(form.lower()) in os.listdir(os.path.join(path,'final output')+os.sep)
        if existing:
            print('\nExisting output for this form appears to be available.  Do you wish to load it? [y/n]')
            while True:
                choice = input('> ')
                if choice.lower() == 'y':
                    load_df = self.load_saved(form)
                    break
                elif choice.lower() == 'n':
                    print('\nWarning: the program will overwrite this output when it finishes, if you leave it in the destination folders.  Press "y" to continue without loading, or any other key to cancel.')
                    print('\nNote: If you wish to keep the other files but not load them, you may move them from the "fixed validations" and "final output" folders now, then press "y" to resume.')
                    choice = input('> ')
                    if choice.lower() == 'y':
                        load_df = None
                        break
                    else:
                        sys.exit('Please handle the existing output and then run the validation fixer again.')
        else:
            load_df = None
            print('\nNo existing output found.')
        print('\nBeginning validation...')
        time.sleep(self.pause)

        self.user = user
        self.form = form
        self.load_df = load_df

    def col_viewer(self, row, choice):
        #choice should be a list of column names, e.g. ['TOTREV2', 'NETRENT']
        def format_fn(r):
            try:
                v = '{:,.0f}'.format(float(r))
                return v
            except ValueError:
                return r #if a column is a string

        parts = self.form_crosswalk['FULL'].rename('990 LOCATION')
        try:
            values = row[choice].map(lambda r: format_fn(r)).rename('VALUE')
        except KeyError:
            print('No valid columns entered.')
        else:
            df = pd.concat([values, parts], axis=1).reindex(parts.index)
            df['990 LOCATION'] = df['990 LOCATION'].fillna('')
            print(df[df['VALUE'].notnull()])

    def user_input(self, token):
        #row = the original row from the dataframe
        #new_row = the row from the dataframe with whatever modifications have been applied
        #failures = a list of column names that begin with 'validate_'
        #form = 'CO', etc

        row = token['original_row']
        new_row = token['modified_row']
        failures = self.failures

        print(' ' + '-'*int((ceil(self.terminal_width))-2))
        #print('\n* means the column shows up in other validation calculations.\n')
        # print('Enter a column name to change its value, (v)iew to see a column value, or:')
        # print('  (F)ixed, (C)hecked\n  (I)gnore, (S)kip\n  (R)eset, (Q)uit\n')
        print('\n ENTER A COLUMN NAME to change its value, or:\n')
        print('(v)  view any columns     | (f) to mark EIN as fixed       | (r) to revert this EINs values')
        print('(vr) view revenue columns | (c) to mark EIN as checked     | (d) for what has been done so far')
        print('(va) view asset columns   | (i) to ignore this EIN         | (q) to quit')
        print('(ve) view expense columns | (s) to skip this EIN for later | (o) for options\n')

        while True:
            task = input('> ')
            task = task.lower()

            #catch descriptive user input and convert to key letters
            key_dict = {'view':'v',
                        'fixed':'f',
                        'checked':'c',
                        'ignore':'i',
                        'skip':'s',
                        'revert':'r',
                        'quit':'q',
                        'options':'o',
                        'revenue':'vr',
                        'asset':'va',
                        'assets':'va',
                        'expense':'ve',
                        'expenses':'ve',
                        'done':'d'}
            if task in key_dict:
                task = key_dict[task]

            menu = {'f':self.ui_fixed,
                    'c':self.ui_checked,
                    'i':self.ui_ignore,
                    's':self.ui_skip,
                    'r':self.ui_reset,
                    'q':self.ui_quit,
                    'o':self.ui_options,
                    'd':self.ui_done_so_far,
                    'v':self.ui_view,
                    'vr':self.ui_view_group,
                    'va':self.ui_view_group,
                    've':self.ui_view_group}

            if task in menu:
                token = menu[task](token, task)
                return token
            elif task.upper() in new_row.index:
                if not isinstance(new_row[task.upper()], (np.int64, np.float64, int, float)):
                    print('Only values in numerical columns may be changed using the fixer, please make a separate note of any other necessary changes.')
                    continue
                token = self.ui_modify_row(token, task)
                return token

    def ui_fixed(self, token, task):
        row = token['original_row']
        new_row = token['modified_row']
        failures = self.failures

        no_changes_made = row.equals(new_row)
        all_validations_fixed = (new_row[failures] <= self.threshold).all()

        if no_changes_made:
            print('No changes made to this EIN, so it cannot be marked as fixed.\n')
            time.sleep(self.pause)
            done = False
        elif not all_validations_fixed:
            print('Validation failures remain at the {} threshold.  Do you want to:'.format(self.threshold))
            print('    (s)ave and let the errors be picked up by future validation')
            print('    (i)gnore the remaining errors in future validation, but save the current fixes')
            print('    (c)ontinue working on this EIN')
            while True:
                choice = input('> ')
                if choice.lower() == 's':
                    new_row.loc['VALIDATION_STATE'] = 1
                    new_row.loc['validated_by'] = self.user
                    done = True
                    break
                elif choice.lower() == 'i':
                    new_row.loc['VALIDATION_STATE'] = 2
                    new_row.loc['validated_by'] = self.user
                    done = True
                    break
                elif choice.lower() == 'c':
                    done = False
                    break
        else:
            print('This EIN has been changed.')
            new_row.loc['VALIDATION_STATE'] = 1
            done = True #for when it passes both conditionals (changes, and all errors fixed)
        token['exit'] = done
        return token

    def ui_checked(self, token, task):
        row = token['original_row']
        new_row = token['modified_row']
        failures = self.failures

        equal_cols = list(set(row.index).difference(['VALIDATION_STATE', 'EXPLANATION', 'validated_by'])) #these columns may not match do to prior token restoring, but that's okay
        no_changes_made = row[equal_cols].equals(new_row[equal_cols])

        all_validations_fixed = (new_row[failures] <= self.threshold).all()

        if not no_changes_made:
            print('Changes were made to this EIN, so it cannot be marked as checked.')
            time.sleep(self.pause)
            done = False
        elif not all_validations_fixed:
            print('This row has validation failures above the threshold, so it cannot be marked as checked.')
            time.sleep(self.pause)
            done = False
        else:
            print('Marking this row as verified correct without changes.  This will prevent marking as a "large" or "large change", but will not prevent being marked as a validation failure.  Press "c" again to confirm:')
            while True:
                choice = input('> ')
                if choice.lower() == 'c':
                    new_row.loc['VALIDATION_STATE'] = 3
                    new_row.loc['validated_by'] = self.user
                    done = True
                    break
                else:
                    done = False
                    break
        token['exit'] = done
        return token

    def ui_ignore(self, token, task):
        new_row = token['modified_row']

        while True:
            choice = input('Caution!  This will mark remaining errors or flags for this form to be ignored.  Press "i" again to proceed: ')
            if choice.lower() == 'i':
                print('Marking this EIN for ignoring in future validations.\n')
                new_row.loc['VALIDATION_STATE'] = 2
                new_row.loc['validated_by'] = self.user
                done = True
                break
            else:
                done = False
                break
        token['exit'] = done
        return token

    def ui_skip(self, token, task):
        #returns the original row and marks it as unresolved
        choice = input('Undoing any changes and leaving this EIN to be picked up in future validations.  Press "s" again to confirm: ')
        if choice.lower() == 's':
            token['modified_row'] = token['original_row'].copy()
            token['modified_row'].loc['VALIDATION_STATE'] = 0
            token['modified_row'].loc['validated_by'] = ''
            done = True
        else:
            done = False
        token['exit'] = done
        return token

    def ui_reset(self, token, task):
        #returns the original row, where it overwrites new_row and is passed back for another round
        print('All changes discarded, now displaying original values.')
        time.sleep(self.pause)
        done = False
        token['modified_row'] = token['original_row'].copy()
        token['changes'] = {}
        token['exit'] = done
        return token

    def ui_quit(self, token, task):
        print('If you quit without saving then changes made to ALL EINS from this session will be DISCARDED.')
        print('Also note that you must complete the current EIN and then quit, if you wish to save any work on it.\n')
        while True:
            choice = input('(r)esume, (s)ave first, or (q)uit without saving? [r/s/q]: ')
            if choice.lower() == 's':
                self.end(changes_only=True)
                sys.exit('Output saved.')
            elif choice.lower() == 'q':
                sys.exit('No changes saved; bye!')
            elif choice.lower() == 'r':
                done = False
                token['exit'] = done
                return token

    def ui_options(self, token, task):
        new_row = token['modified_row']

        print('Options Menu:')
        print('1. Open the PDF of the most recent 990 | 5. View the five most recently completed EINs')
        print('2. Open the PDF of the previous 990    | 6. See any previous explanations for this EIN ')
        print('3. Open the 990 PDF search page        | 7. Go back to the previous EIN and place the current')
        print('4. Toggle default PDF opening          |    on hold (changes will not be lost)')
        print('                                       |')
        print('8. Save without exiting                | 9. Cancel\n')

        while True:
            choice = input('> ')
            if choice == '1':
                self.pdf_opener(new_row['FILENAME'])
                break
            elif choice == '2':
                if 'TAXPERP' in new_row.index and new_row['TAXPERP'] is not np.NaN:
                    self.pdf_opener(new_row['FILENAME'], taxperp=new_row['TAXPERP'])
                else:
                    print('Prior tax return date not in file; please go to http://foundationcenter.org/find-funding/990-finder or select option 3.')
                    time.sleep(self.pause)
                break
            elif choice == '3':
                self.pdf_opener(None, url='http://foundationcenter.org/find-funding/990-finder')
                break
            elif choice == '4':
                self.open_pdfs = not self.open_pdfs
                break
            elif choice == '5':
                print('Most recent on the left:')
                print(self.prior_five)
                print('')
                _ = input('Press any key to continue.')
                break
            elif choice == '6':
                print('Last explanation entered for this EIN: ')
                print(new_row['EXPLANATION'])
                _ = input('Press any key to continue.')
                break
            elif choice == '7':
                if self.token_storage['prior']:
                    print('The current EIN will automatically resume where you left off when you complete the restored one.  Restoring...')
                    time.sleep(self.pause)
                    self.token_storage['on_hold'] = token
                    token = self.token_storage['prior']
                    break
                else:
                    print('No previous EIN saved.  Are you on the first one of this session?')
                    time.sleep(self.pause)
                    break
            elif choice == '8':
                self.end(save_only=True, changes_only=True)
                break
            elif choice == '9':
                break
        done = False
        token['exit'] = done
        return token

    def ui_done_so_far(self, token, task):
        if len(token['changes']) > 0:
            print(token['changes'])
        else:
            print('No changes to this EIN yet.')
        print('')
        _ = input('Press enter to continue.')
        return token

    def ui_view(self, token, task):
        new_row = token['modified_row']

        while True:
            choice = input('Enter any number of column names (upper or lower case) separated by spaces: ')
            print('Note that invalid entries will show up as nan.\n')
            choice = choice.upper().split()

            self.col_viewer(new_row, choice)
            _ = input('\nPress any key to continue.')
            done = False
            token['exit'] = done
            return token

    def ui_view_group(self, token, task):
        new_row = token['modified_row']

        cols = {'VR':['CONT', 'PROGREV', 'INVINC', 'TXEXMPTBNDSPROCEEDS', 'ROYALTSINC', 'GRSRNTSREAL', 'GRSRNTSPRSNL', 'RENTINC', 'RNTLEXPNSREAL', 'RNTLEXPNSPRSNL', 'RENTEXP', 'RNTLINCREAL', 'RNTLINCPRSNL', 'NETRENT', 'SECUR', 'SALESEXP', 'SALESECN', 'SALEOTHG', 'SALEOTHE', 'SALEOTHN', 'NETGNLS', 'GRSINCFNDRSNG', 'LESSDIRFNDRSNG', 'NETINCFNDRSNG', 'GRSINCGAMING', 'LESSDIRGAMING', 'NETINCGAMING', 'SPEVTG', 'DIREXP', 'FUNDINC', 'INVENTG', 'GOODS', 'GRPROF', 'OTHINC', 'TOTREV2'],
                'VE':['COMPENS', 'OTHSAL', 'PAYTAX', 'FUNDFEES', 'EXPS'],
                'VA':['ASS_BOY', 'ASS_EOY', 'BOND_EOY', 'MRTG_EOY', 'UNSECUREDNOTESEND', 'LIAB_BOY', 'LIAB_EOY', 'RETEARN', 'FUNDBAL']}
        self.col_viewer(new_row, cols[task.upper()])
        _ = input('\nPress any key to continue.')
        done = False
        token['exit'] = done
        return token

    def ui_modify_row(self, token, task):
        row = token['original_row']
        new_row = token['modified_row']
        failures = self.failures

        #update entry
        if new_row.loc['MANUALLY_FIXED'] == '' or new_row.loc['MANUALLY_FIXED'] is np.NaN:
            new_row.loc['MANUALLY_FIXED'] = task.upper()
        else:
            if task.upper() not in new_row.loc['MANUALLY_FIXED']:
                new_row.loc['MANUALLY_FIXED'] = new_row.loc['MANUALLY_FIXED'] + ' ' + task.upper()
        #sets the new value in the row copy? from the dataframe
        fix = self.ui_get_fix(new_row.loc[task.upper()], task.upper(), new_row.loc[task.upper()])
        new_row.loc[task.upper()] += fix #adjusts the actual column that starts at the initial value
        new_row.loc[task.lower() + '_adjusted_by'] = float(new_row.loc[task.lower() + '_adjusted_by']) + fix #adjust the tracking column that starts at 0
        new_row.loc['validated_by'] = self.user

        #update change tracking in the token
        if task.upper() not in token['changes']:
            token['changes'][task.upper()] = fix
        else:
            token['changes'][task.upper()] += fix

        #now that the entry is updated, we go back to the validation code and recalculate the error

        #first find out if this column in this row was calculated using EZ, Full or PF code
        source = row['SOURCE'].split('.')[0].lower()
        if source.endswith('990'):
            f = 'FU'
        elif source.endswith('pf'):
            f = 'PF'
        elif source.endswith('ez'):
            f = 'EZ'

        for val_col, val_func in self.validate_method_dict[f].items():
            new_row.loc[val_col] = val_func(new_row)

        done = False
        token['exit'] = done
        return token

    def ui_get_fix(self, prev_val, col, current_val):
        # prev_val - entry value from column
        # col      - column name in upper case
        while True:
            change = input('Change {} by (or type "L" to enter a new level): '.format(col))
            if change in ['l', 'L', 'level', 'Level', 'LEVEL']:
                new_level = input('Enter a new level for {}: '.format(col))
                try:
                    change = float(new_level) - current_val
                    break
                except ValueError:
                    continue
            try:
                change = float(change)
                break
            except ValueError:
                continue
        return change

class CoreFixer(Utilities, Display, UserInput):
    def __init__(self):
        self.df = None
        self.form = None
        self.num_fixed = 0
        self.start_len = None
        self.open_pdfs = None
        self.prior_five = [None]*5

        self.path = path
        self.terminal_width = 99
        self.pause = .75

        #holding place for the ability to load the last token
        self.token_storage = {'prior':None, 'on_hold':None}

        #these must match the settings used when the core files being validated were created
        self.threshold = 1000
        self.large_firm = 10000000
        self.changed = .50

        #column dtypes are inferred automatically unless specified as strings here
        self.make_strings = {'EIN':'str', 'TAXPER':'str', 'TAXPERP':'str', 'FISYR':'str', 'FISYRP':'str', 'MANUALLY_FIXED':'str', 'NAME':'str'}
        self.form_crosswalk = self.get_form_crosswalk()

        #the order in which data is sorted in the validation_reason column
        self.sort_criteria = ['CFL', 'CLF', 'LFC', 'LCF', 'FCL', 'FLC', 'FL', 'LF', 'CF', 'FC', 'F', 'CL', 'LC', 'L', 'C']

        #these are carried as instance objects rather than local objects for debugging and exploration after the code is run.
        self.components, self.cross_components, self.multiples, self.equations, self.validate_method_dict = self.get_components()

    def start(self):
        """
        Main process called on the class instance to begin the validator
        """
        self.get_user()
        self.load_data()
        self.sort_data()
        self.dataframe_loop()
        self.end()

    def dataframe_loop(self):
        """
        Iterates through each row in the dataframe
        """
        for ein, row in self.df.iterrows():
            #only process a row that isn't marked "ignore" and that has a failure or is not marked fixed/checked
            if row['VALIDATION_STATE'] != 2 and (any(abs(row[self.failures]) >= self.threshold) or (row['VALIDATION_STATE'] not in [1,3])):
                if self.open_pdfs: self.pdf_opener(row['FILENAME'])
                token = self.generate_token(ein, row) #new token for the current row
                token = self.row_loop(token) #main loop for row processing

                self.update_df_row(token)
                self.num_fixed += 1
                self.token_storage['prior'] = token
                self.prior_five = [token['current_ein']] + self.prior_five[:4]

    def row_loop(self, token):
        """
        Continues to loop the same row through the display until it receives an exit condition
        """
        while not token['exit']:
            self.display(token)
            token = self.user_input(token)
            if token['exit'] and self.token_storage['on_hold']:
                token = self.process_token_storage(token)

        token = self.get_explanation(token)
        return token

    def end(self, changes_only=False, save_only=False):
        if not save_only:
            print('')
            wprint('Done with document, updated data written to the "fixed validations" folder.  Run the core file process again and it will incorporate your changes, then re-validate.', indent=False)
            print('')
            print('Change tracking outputted to "final output" folder.')
        df = self.df
        form = self.form

        if changes_only:
            df = df[(df['VALIDATION_STATE'] > 0) | (df['EXPLANATION'] != '')]

        val_cols = [c.lower()+'_adjusted_by' for c in self.num_cols] + ['validated_by', 'EXPLANATION']
        df[df.columns.difference(val_cols)].to_csv(os.path.join(path, 'validation', 'fixes', '{}_{}_validate.csv'.format(form.lower(), self.year)))
        df[val_cols].to_csv(os.path.join(path, 'final output', '{}_change_tracker.csv'.format(form.lower())))
        print('Changes saved.')
        time.sleep(self.pause)

if __name__ == '__main__':
    fixer = CoreFixer()
    fixer.start()
