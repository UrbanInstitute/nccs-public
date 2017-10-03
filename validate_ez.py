# Code by Jeff Levy (jlevy@urban.org), 2016-2017

class ValidateEZ():
    """
    Methods for validating EINs from IRS form 990 Full.

    Each method called by validate_ez represents the validation of one column, and comes with the kwarg
    fixer_display=False, which when set to True will return only a string representation of the equation.
    This is for use in the validation fixer tool.
    """
    def validate_ez(self):
        """
        Base method for validating certain columns for EINs from IRS form 990 EZ.  Note that there's are
        some steps leadin to this that seem redundant/odd, but actually had to follow that order.

        The Full and EZ forms require different validations, because the components of each form are different.
        However, they need to be combined and then split again to create the CO and PC releases, and that needs
        to happen before validation because info from the prior NCCS releases are used in the validation steps
        (and the prior releases are CO/PC, not Full/EZ).

        That means we start with EZ/Full, combine and split into CO/PC, merge in prior releases, then run this
        validate_full method wherein we split each of the CO/PC files into its Full/EZ components to pick the
        correct validation equations, then recombine the results into the validation of form CO or PC.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main
        sub_form = 'EZ'

        for form in ['CO', 'PC']:
            if self.do_validation[form]:
                df = main.write.data_dict[form]
                ezonly = df[(df['SOURCE'].str.split('.').apply(lambda r: r[0]).str.endswith('EZ')) | (df['SOURCE'].str.split('.').apply(lambda r: r[0]).str.endswith('ez'))]

                ez_failed_validation = self.validation_tracking[form]

                df['validate_ez_saleothn'] = self.ez_validate_saleothn(df).loc[ezonly.index]
                df, ez_failed_validation = self.validate(df, ez_failed_validation, 'validate_ez_saleothn', form, sub_form)

                df['validate_ez_netincfndrsng'] = self.ez_validate_netincfndrsng(df).loc[ezonly.index]
                df, ez_failed_validation = self.validate(df, ez_failed_validation, 'validate_ez_netincfndrsng', form, sub_form)

                df['validate_ez_grprof'] = self.ez_validate_grprof(df).loc[ezonly.index]
                df, ez_failed_validation = self.validate(df, ez_failed_validation, 'validate_ez_grprof', form, sub_form)

                df['validate_ez_totrev'] = self.ez_validate_totrev(df).loc[ezonly.index]
                df, ez_failed_validation = self.validate(df, ez_failed_validation, 'validate_ez_totrev', form, sub_form)

                df['validate_ez_netinc'] = self.ez_validate_netinc(df).loc[ezonly.index]
                df, ez_failed_validation = self.validate(df, ez_failed_validation, 'validate_ez_netinc', form, sub_form)

                df['validate_ez_ass_eoy'] = self.ez_validate_ass_eoy(df).loc[ezonly.index]
                df, ez_failed_validation = self.validate(df, ez_failed_validation, 'validate_ez_ass_eoy', form, sub_form)

                self.validation_tracking[form] = ez_failed_validation
        #self.validate_form(ez, 'EZ', ez_failed_validation)

    def ez_validate_saleothn(self, ez, fixer_display=False):
        if fixer_display:
            return 'SALEOTHN - (SALEOTHG - SALEOTHE)'
        else:
            return ez['SALEOTHN'] - (ez['SALEOTHG'] - ez['SALEOTHE'])

    def ez_validate_netincfndrsng(self, ez, fixer_display=False):
        if fixer_display:
            return 'NETINCFNDRSNG - (GRSINCGAMING + GRSINCFNDRSNG - DIREXP)'
        else:
            return ez['NETINCFNDRSNG'] - (ez['GRSINCGAMING'] + ez['GRSINCFNDRSNG'] - ez['DIREXP'])

    def ez_validate_grprof(self, ez, fixer_display=False):
        if fixer_display:
            return 'GRPROF - (INVENTG - GOODS)'
        else:
            return ez['GRPROF'] - (ez['INVENTG'] - ez['GOODS'])

    def ez_validate_totrev(self, ez, fixer_display=False):
        if fixer_display:
            return 'TOTREV - (CONT + PRGMSERVREV + DUESASSESMNTS + INVINC + SALEOTHN + NETINCFNDRSNG + GRPROF + OTHINC)'
        else:
            return ez['TOTREV'] - (ez['CONT'] + ez['PRGMSERVREV'] + ez['DUESASSESMNTS'] + ez['INVINC'] + ez['SALEOTHN'] + ez['NETINCFNDRSNG'] + ez['GRPROF'] + ez['OTHINC'])

    def ez_validate_netinc(self, ez, fixer_display=False):
        if fixer_display:
            return 'NETINC - (TOTREV - EXPS)'
        else:
            return ez['NETINC'] - (ez['TOTREV'] - ez['EXPS'])

    def ez_validate_ass_eoy(self, ez, fixer_display=False):
        if fixer_display:
            return 'ASS_EOY - (LIAB_EOY + FUNDBAL)'
        else:
            return ez['ASS_EOY'] - (ez['LIAB_EOY'] + ez['FUNDBAL'])
