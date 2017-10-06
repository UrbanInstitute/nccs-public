# Code by Jeff Levy (jlevy@urban.org), 2016-2017

class ValidatePF():
    """
    Methods for validating EINs from IRS form 990 PF.

    Each method called by validate_pf represents the validation of one column, and comes with the kwarg
    fixer_display=False, which when set to True will return only a string representation of the equation.
    This is for use in the validation fixer tool.

    Note that the PF data was never validated before, in the old SQL code.  These were all added based
    strictly on sums given by the IRS form itself.
    """
    def validate_pf(self):
        """
        Base method for validating certain columns for EINs from IRS form 990 PF.

        ARGUMENTS
        None

        RETURNS
        None
        """
        main = self.main

        if self.do_validation['PF']:
            pf = main.write.data_dict['PF']

            pf_failed_validation = self.validation_tracking['PF']

            pf['validate_pf_p1totrev'] = self.pf_validate_p1totrev(pf)
            pf, pf_failed_validation = self.validate(pf, pf_failed_validation, 'validate_pf_p1totrev', 'PF', 'PF')

            pf['validate_pf_p1totexp'] = self.pf_validate_p1totexp(pf)
            pf, pf_failed_validation = self.validate(pf, pf_failed_validation, 'validate_pf_p1totexp', 'PF', 'PF')

            pf['validate_pf_p1excrev'] = self.pf_validate_p1excrev(pf)
            pf, pf_failed_validation = self.validate(pf, pf_failed_validation, 'validate_pf_p1excrev', 'PF', 'PF')

            pf['validate_pf_p2tinvsc'] = self.pf_validate_p2tinvsc(pf)
            pf, pf_failed_validation = self.validate(pf, pf_failed_validation, 'validate_pf_p2tinvsc', 'PF', 'PF')

            pf['validate_pf_p14tnadj'] = self.pf_validate_p14tnadj(pf)
            pf, pf_failed_validation = self.validate(pf, pf_failed_validation, 'validate_pf_p14tnadj', 'PF', 'PF')

            pf['validate_pf_p14tqdis'] = self.pf_validate_p14tqdis(pf)
            pf, pf_failed_validation = self.validate(pf, pf_failed_validation, 'validate_pf_p14tqdis', 'PF', 'PF')

            pf['validate_pf_p14tasvl'] = self.pf_validate_p14tasvl(pf)
            pf, pf_failed_validation = self.validate(pf, pf_failed_validation, 'validate_pf_p14tasvl', 'PF', 'PF')

            pf['validate_pf_p14t4942'] = self.pf_validate_p14t4942(pf)
            pf, pf_failed_validation = self.validate(pf, pf_failed_validation, 'validate_pf_p14t4942', 'PF', 'PF')

            pf['validate_pf_p14tendw'] = self.pf_validate_p14tendw(pf)
            pf, pf_failed_validation = self.validate(pf, pf_failed_validation, 'validate_pf_p14tendw', 'PF', 'PF')

            pf['validate_pf_p14ttsup'] = self.pf_validate_p14ttsup(pf)
            pf, pf_failed_validation = self.validate(pf, pf_failed_validation, 'validate_pf_p14ttsup', 'PF', 'PF')

            pf['validate_pf_p14tpsup'] = self.pf_validate_p14tpsup(pf)
            pf, pf_failed_validation = self.validate(pf, pf_failed_validation, 'validate_pf_p14tpsup', 'PF', 'PF')

            pf['validate_pf_p14tginv'] = self.pf_validate_p14tginv(pf)
            pf, pf_failed_validation = self.validate(pf, pf_failed_validation, 'validate_pf_p14tginv', 'PF', 'PF')

            self.validation_tracking['PF'] = pf_failed_validation
            #self.validate_form(pf, 'PF', pf_failed_validation)

    def pf_validate_p1totrev(self, pf, fixer_display=False):
        if fixer_display:
            return 'P1TOTREV - (P1TCONT + P1INTREV + P1DIVID + P1GRENTS + P1NGASTS + P1GINVPF + P1OTHINC)'
        else:
            return pf['P1TOTREV'] - (pf['P1TCONT'] + pf['P1INTREV'] + pf['P1DIVID'] + pf['P1GRENTS'] + pf['P1NGASTS'] + pf['P1GINVPF'] + pf['P1OTHINC'])

    def pf_validate_p1totexp(self, pf, fixer_display=False):
        if fixer_display:
            return 'P1TOTEXP - (P1ADMEXP + P1CONTPD)'
        else:
            return pf['P1TOTEXP'] - (pf['P1ADMEXP'] + pf['P1CONTPD'])

    def pf_validate_p1excrev(self, pf, fixer_display=False):
        if fixer_display:
            return 'P1EXCREV - (P1TOTREV - P1TOTEXP)'
        else:
            return pf['P1EXCREV'] - (pf['P1TOTREV'] - pf['P1TOTEXP'])

    def pf_validate_p2tinvsc(self, pf, fixer_display=False):
        if fixer_display:
            return 'P2TINVSC - (P2GVTINV + P2CRPSTK + P2CRPBND)'
        else:
            return pf['P2TINVSC'] - (pf['P2GVTINV'] + pf['P2CRPSTK'] + pf['P2CRPBND'])

    def pf_validate_p14tnadj(self, pf, fixer_display=False):
        if fixer_display:
            return 'P14TNADJ - (P14NADJA + P14NADJB + P14NADJC + P14NADJD)'
        else:
            return pf['P14TNADJ'] - (pf['P14NADJA'] + pf['P14NADJB'] + pf['P14NADJC'] + pf['P14NADJD'])

    def pf_validate_p14tqdis(self, pf, fixer_display=False):
        if fixer_display:
            return 'P14TQDIS - (P14QDISA + P14QDISB + P14QDISC + P14QDISD)'
        else:
            return pf['P14TQDIS'] - (pf['P14QDISA'] + pf['P14QDISB'] + pf['P14QDISC'] + pf['P14QDISD'])

    def pf_validate_p14tasvl(self, pf, fixer_display=False):
        if fixer_display:
            return 'P14TASVL - (P14ASVLA + P14ASVLB + P14ASVLC + P14ASVLD)'
        else:
            return pf['P14TASVL'] - (pf['P14ASVLA'] + pf['P14ASVLB'] + pf['P14ASVLC'] + pf['P14ASVLD'])

    def pf_validate_p14t4942(self, pf, fixer_display=False):
        if fixer_display:
            return 'P14T4942 - (P14A4942 + P14B4942 + P14C4942 + P14D4942)'
        else:
            return pf['P14T4942'] - (pf['P14A4942'] + pf['P14B4942'] + pf['P14C4942'] + pf['P14D4942'])

    def pf_validate_p14tendw(self, pf, fixer_display=False):
        if fixer_display:
            return 'P14TENDW - (P14ENDWA + P14ENDWB + P14ENDWC + P14ENDWD)'
        else:
            return pf['P14TENDW'] - (pf['P14ENDWA'] + pf['P14ENDWB'] + pf['P14ENDWC'] + pf['P14ENDWD'])

    def pf_validate_p14ttsup(self, pf, fixer_display=False):
        if fixer_display:
            return 'P14TTSUP - (P14TSUPA + P14TSUPB + P14TSUPC + P14TSUPD)'
        else:
            return pf['P14TTSUP'] - (pf['P14TSUPA'] + pf['P14TSUPB'] + pf['P14TSUPC'] + pf['P14TSUPD'])

    def pf_validate_p14tpsup(self, pf, fixer_display=False):
        if fixer_display:
            return 'P14TPSUP - (P14PSUPA + P14PSUPB + P14PSUPC + P14PSUPD)'
        else:
            return pf['P14TPSUP'] - (pf['P14PSUPA'] + pf['P14PSUPB'] + pf['P14PSUPC'] + pf['P14PSUPD'])

    def pf_validate_p14tginv(self, pf, fixer_display=False):
        if fixer_display:
            return 'P14TGINV - (P14GINVA + P14GINVB + P14GINVC + P14GINVD)'
        else:
            return pf['P14TGINV'] - (pf['P14GINVA'] + pf['P14GINVB'] + pf['P14GINVC'] + pf['P14GINVD'])
