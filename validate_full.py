# Code by Jeff Levy (jlevy@urban.org), 2016-2017

class ValidateFull():
    """
    Methods for validating EINs from IRS form 990 Full.

    Each method called by validate_full represents the validation of one column, and comes with the kwarg
    fixer_display=False, which when set to True will return only a string representation of the equation.
    This is for use in the validation fixer tool.
    """
    def validate_full(self):
        """
        Base method for validating certain columns for EINs from IRS form 990 Full.  Note that there's are
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
        sub_form = 'Full'

        for form in ['CO', 'PC']:
            if self.do_validation[form]:
                df = main.write.data_dict[form]
                fullonly = df[(df['SOURCE'].str.split('.').apply(lambda r: r[0]).str.endswith('990'))]

                full_failed_validation = self.validation_tracking[form]

                # df['validate_fu_exps'] = self.full_validate_exps(df).ix[fullonly.index]
                # df, full_failed_validation = self.validate(df, full_failed_validation, 'validate_fu_exps', form, sub_form)

                df['validate_fu_netrent'] = self.full_validate_netrent(df).loc[fullonly.index]
                df, full_failed_validation = self.validate(df, full_failed_validation, 'validate_fu_netrent', form, sub_form)

                df['validate_fu_netgnls'] = self.full_validate_netgnls(df).loc[fullonly.index]
                df, full_failed_validation = self.validate(df, full_failed_validation, 'validate_fu_netgnls', form, sub_form)

                df['validate_fu_netincfndrsng'] = self.full_validate_netincfndrsng(df).loc[fullonly.index]
                df, full_failed_validation = self.validate(df, full_failed_validation, 'validate_fu_netincfndrsng', form, sub_form)

                df['validate_fu_netincgaming'] = self.full_validate_netincgaming(df).loc[fullonly.index]
                df, full_failed_validation = self.validate(df, full_failed_validation, 'validate_fu_netincgaming', form, sub_form)

                df['validate_fu_grprof'] = self.full_validate_grprof(df).loc[fullonly.index]
                df, full_failed_validation = self.validate(df, full_failed_validation, 'validate_fu_grprof', form, sub_form)

                # df['validate_fu_othinc'] = self.full_validate_othinc(df).ix[fullonly.index]
                # df, full_failed_validation = self.validate(df, full_failed_validation, 'validate_fu_othinc', form, sub_form)

                df['validate_fu_totrev2'] = self.full_validate_totrev2(df).loc[fullonly.index]
                df, full_failed_validation = self.validate(df, full_failed_validation, 'validate_fu_totrev2', form, sub_form)

                # df['validate_fu_progrev'] = self.full_validate_progrev(df).ix[fullonly.index]
                # df, full_failed_validation = self.validate(df, full_failed_validation, 'validate_fu_progrev', form, sub_form)

                df['validate_fu_fundbal'] = self.full_validate_fundbal(df).loc[fullonly.index]
                df, full_failed_validation = self.validate(df, full_failed_validation, 'validate_fu_fundbal', form, sub_form)

                # df['validate_fu_ass_eoy'] = self.full_validate_ass_eoy(df).ix[fullonly.index]
                # df, full_failed_validation = self.validate(df, full_failed_validation, 'validate_fu_ass_eoy', form, sub_form)

                # df['validate_fu_liab_eoy'] = self.full_validate_liab_eoy(df).ix[fullonly.index]
                # df, full_failed_validation = self.validate(df, full_failed_validation, 'validate_fu_liab_eoy', form, sub_form)

                # df['validate_fu_totnetliabastend'] = self.full_validate_totnetliabastend(df).ix[fullonly.index]
                # df, full_failed_validation = self.validate(df, full_failed_validation, 'validate_fu_totnetliabastend', form, sub_form)

                self.validation_tracking[form] = full_failed_validation

    def full_validate_exps(self, df, fixer_display=False):
        if fixer_display:
            return 'EXPS - (GRNTSTOGOVT + GRNSTTOINDIV + GRNTSTOFRGNGOVT + BENIFITSMEMBRS + COMPENS + COMPNSATNANDOTHR + OTHSAL + PENSIONPLANCONTRB + OTHREMPLYEEBENEF + PAYTAX + FEESFORSRVCMGMT + LEGALFEES + ACCNTINGFEES + FEESFORSRVCLOBBY + FUNDFEES + FEESFORSRVCINVSTMGMT + FEESFORSRVCOTHR + ADVRTPROMO + OFFICEXPNS + INFOTECH + ROYALTSEXPNS + OCCUPANCY + TRAVEL + TRAVELOFPUBLICOFFCL + CONVERCONVENTMTNG + INTERESTAMT + PYMTOAFFILIATES + DEPRCATNDEPLETN + INSURANCE + OTHREXPNSA + OTHREXPNSB + OTHREXPNSC + OTHREXPNSD + OTHREXPNSE + OTHREXPNSF)'
        else:
            return df['EXPS'] - (df['GRNTSTOGOVT'] + df['GRNSTTOINDIV'] + df['GRNTSTOFRGNGOVT'] + df['BENIFITSMEMBRS'] +
            df['COMPENS'] + df['COMPNSATNANDOTHR'] + df['OTHSAL'] + df['PENSIONPLANCONTRB'] +
            df['OTHREMPLYEEBENEF'] + df['PAYTAX'] + df['FEESFORSRVCMGMT'] + df['LEGALFEES'] +
            df['ACCNTINGFEES'] + df['FEESFORSRVCLOBBY'] + df['FUNDFEES'] + df['FEESFORSRVCINVSTMGMT'] +
            df['FEESFORSRVCOTHR'] + df['ADVRTPROMO'] + df['OFFICEXPNS'] + df['INFOTECH'] + df['ROYALTSEXPNS'] +
            df['OCCUPANCY'] + df['TRAVEL'] + df['TRAVELOFPUBLICOFFCL'] + df['CONVERCONVENTMTNG'] +
            df['INTERESTAMT'] + df['PYMTOAFFILIATES'] + df['DEPRCATNDEPLETN'] + df['INSURANCE'] +
            df['OTHREXPNSA'] + df['OTHREXPNSB'] + df['OTHREXPNSC'] + df['OTHREXPNSD'] + df['OTHREXPNSE'] +
            df['OTHREXPNSF'])

    def full_validate_netrent(self, df, fixer_display=False):
        if fixer_display:
            return 'NETRENT - (RNTLINCREAL + RNTLINCPRSNL)'
        else:
            return df['NETRENT'] - (df['RNTLINCREAL'] + df['RNTLINCPRSNL'])

    def full_validate_netgnls(self, df, fixer_display=False):
        if fixer_display:
            return 'NETGNLS - (SALESECN + SALEOTHN)'
        else:
            return df['NETGNLS'] - (df['SALESECN'] + df['SALEOTHN'])

    def full_validate_netincfndrsng(self, df, fixer_display=False):
        if fixer_display:
            return 'NETINCFNDRSNG - (GRSINCFNDRSNG - LESSDIRFNDRSNG)'
        else:
            return df['NETINCFNDRSNG'] - (df['GRSINCFNDRSNG'] - df['LESSDIRFNDRSNG'])

    def full_validate_netincgaming(self, df, fixer_display=False):
        if fixer_display:
            return 'NETINCGAMING - (GRSINCGAMING - LESSDIRGAMING)'
        else:
            return df['NETINCGAMING'] - (df['GRSINCGAMING'] - df['LESSDIRGAMING'])

    def full_validate_grprof(self, df, fixer_display=False):
        if fixer_display:
            return 'GRPROF - (INVENTG - GOODS)'
        else:
            return df['GRPROF'] - (df['INVENTG'] - df['GOODS'])

    def full_validate_othinc(self, df, fixer_display=False):
        if fixer_display:
            return 'OTHINC - (MISCREVTOTA + MISCREVTOT11B + MISCREVTOT11C + MISCREVTOT11D)'
        else:
            return df['OTHINC'] - (df['MISCREVTOTA'] + df['MISCREVTOT11B'] + df['MISCREVTOT11C'] + df['MISCREVTOT11D'])

    def full_validate_totrev2(self, df, fixer_display=False):
        if fixer_display:
            return 'TOTREV2 - (CONT + PROGREV + INVINC + TXEXMPTBNDSPROCEEDS + ROYALTSINC + NETRENT + NETGNLS + NETINCFNDRSNG + NETINCGAMING + GRPROF + OTHINC)'
        else:
            return df['TOTREV2'] - (df['CONT'] + df['PROGREV'] + df['INVINC'] + df['TXEXMPTBNDSPROCEEDS'] +
            df['ROYALTSINC'] + df['NETRENT'] + df['NETGNLS'] + df['NETINCFNDRSNG'] + df['NETINCGAMING'] +
            df['GRPROF'] + df['OTHINC'])

    def full_validate_progrev(self, df, fixer_display=False):
        if fixer_display:
            return 'PROGREV - (TOTREV2ACOLA + TOTREV2BCOLA + TOTREV2CCOLA + TOTREV2DCOLA + TOTREV2ECOLA + TOTREV2FCOLA)'
        else:
            return df['PROGREV'] - (df['TOTREV2ACOLA'] + df['TOTREV2BCOLA'] + df['TOTREV2CCOLA'] +
            df['TOTREV2DCOLA'] + df['TOTREV2ECOLA'] + df['TOTREV2FCOLA'])

    def full_validate_fundbal(self, df, fixer_display=False):
        if fixer_display:
            return 'FUNDBAL - (ASS_EOY - LIAB_EOY'
        else:
            return df['FUNDBAL'] - (df['ASS_EOY'] - df['LIAB_EOY'])

    def full_validate_ass_eoy(self, df, fixer_display=False):
        if fixer_display:
            return 'ASS_EOY - (NONINTCASHEND + SVNGSTEMPINVEND + PLDGEGRNTRCVBLEND + ACCNTSRCVBLEND + CURRFRMRCVBLEND + RCVBLDISQUALEND + NOTESLOANSRCVBLEND + INVNTRIESALESEND + PREPAIDEXPNSEND + LNDBLDGSEQUIPEND + INVSTMNTSEND + INVSTMNTSOTHREND + INVSTMNTSPRGMEND + INTANGIBLEASSETSEND + OTHRASSETSEND)'
        else:
            return df['ASS_EOY'] - (df['NONINTCASHEND'] + df['SVNGSTEMPINVEND'] + df['PLDGEGRNTRCVBLEND'] +
            df['ACCNTSRCVBLEND'] + df['CURRFRMRCVBLEND'] + df['RCVBLDISQUALEND'] + df['NOTESLOANSRCVBLEND'] +
            df['INVNTRIESALESEND'] + df['PREPAIDEXPNSEND'] + df['LNDBLDGSEQUIPEND'] + df['INVSTMNTSEND'] +
            df['INVSTMNTSOTHREND'] + df['INVSTMNTSPRGMEND'] + df['INTANGIBLEASSETSEND'] + df['OTHRASSETSEND'])

    def full_validate_liab_eoy(self, df, fixer_display=False):
        if fixer_display:
            return 'LIAB_EOY - (ACCNTSPAYABLEEND + GRNTSPAYABLEEND + DEFEREDREVNUEND + BOND_EOY + ESCRWACCNTLIABEND + PAYBLETOFFCRSEND + MRTG_EOY + UNSECUREDNOTESEND + OTHRLIABEND)'
        else:
            return df['LIAB_EOY'] - (df['ACCNTSPAYABLEEND'] + df['GRNTSPAYABLEEND'] + df['DEFEREDREVNUEND'] +
            df['BOND_EOY'] + df['ESCRWACCNTLIABEND'] + df['PAYBLETOFFCRSEND'] + df['MRTG_EOY'] + df['UNSECUREDNOTESEND'] +
            df['OTHRLIABEND'])

    def full_validate_totnetliabastend(self, df, fixer_display=False):
        if fixer_display:
            return 'TOTNETLIABASTEND - (LIAB_EOY + FUNDBAL)'
        else:
            return df['TOTNETLIABASTEND'] - (df['LIAB_EOY'] + df['FUNDBAL'])
