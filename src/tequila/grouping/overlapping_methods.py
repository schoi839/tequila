import numpy as np
from tequila.grouping.binary_utils import sorted_insertion_grouping, term_commutes_with_group
from copy import deepcopy

class OverlappingHelp:
    '''
    Class required for passing cov_dict and number of iterations to
    OverlappingGroups. Eventually, this may also be used for building cov_dict from
    approximate wavefunction if the user provides only the latter.
    '''
    def __init__(self, cov_dict, n_iter=5):
        self.cov_dict = cov_dict
        self.n_iter = n_iter

class OverlappingGroups_wo_fixed:
    '''
    Class required for mapping OverlappingGroups onto a vector of overlapping coefficients.
    Same as OverlappingGroups, but Pauli products corresponding to fixed coefficients are removed.
    '''
    def __init__(self, o_groups, o_terms, term_exists_in):
        def exclude_fixed_coeffs(o_groups, o_terms, term_exists_in):
            '''
            Remove fixed coefficients from o_groups and term_exists_in.
            These fixed coefficients are determined from other Pauli coefficients in order that
            the condition sum_alpha c^{alpha} = 0 is satisfied.
            '''
            fixed_grp = []
            o_groups_wo_fixed = deepcopy(o_groups)
            term_exists_in_wo_fixed = deepcopy(term_exists_in)
            for term_idx, term in enumerate(o_terms):
                fixed_grp.append(term_exists_in[term_idx][-1])
                o_groups_wo_fixed[fixed_grp[term_idx]].remove(term)
                term_exists_in_wo_fixed[term_idx].remove(fixed_grp[term_idx])
            Ncoeff_grp = np.array([len(lst) for lst in o_groups_wo_fixed])
            init_idx = [sum(Ncoeff_grp[:i]) for i in range(len(o_groups_wo_fixed))]
            return fixed_grp, o_groups_wo_fixed, term_exists_in_wo_fixed, Ncoeff_grp, init_idx

        def get_term_idxs(o_terms, o_groups_wo_fixed, term_exists_in_wo_fixed, init_idx):
            '''
            Obtain a dictionary (over i) of dictionaries (over alpha) containing
            the index corresponding to a Pauli coefficient c_{i}^{alpha}.
            '''
            term_idxs = {}
            for term_idx, term in enumerate(o_terms):
                cur_idxs = {}
                for grp_idx in term_exists_in_wo_fixed[term_idx]:
                    cur_idxs[grp_idx] = init_idx[grp_idx] + o_groups_wo_fixed[grp_idx].index(term)
                term_idxs[term.binary_tuple()] = cur_idxs
            return term_idxs

        self.fixed_grp, self.o_groups, self.term_exists_in, self.Ncoeff_grp, self.init_idx \
                                                            = exclude_fixed_coeffs(o_groups, o_terms, term_exists_in)
        self.term_idxs = get_term_idxs(o_terms, self.o_groups, self.term_exists_in, self.init_idx)
        return None

def get_cov(term1, term2, cov_dict):
    '''
    Return the covariance between Pauli string term 1 and 2 from a dictionary.
    '''
    if (term1.binary_tuple(), term2.binary_tuple()) in cov_dict:
        return cov_dict[(term1.binary_tuple(), term2.binary_tuple())]
    if (term2.binary_tuple(), term1.binary_tuple()) in cov_dict:
        return cov_dict[(term2.binary_tuple(), term1.binary_tuple())]

def cov_term_w_group(term, group, cov_dict):
    '''
    Compute covariance between a Pauli string term and a group of Pauli strings.
    '''
    cov = 0.0
    for grp_term in group:
        cov += grp_term.get_coeff() * get_cov(term, grp_term, cov_dict)
    return cov

def get_opt_sample_size(groups, cov_dict):
    '''
    Allocate sample_size optimally based on variance.
    '''
    weights = np.zeros(len(groups))
    for idx, group in enumerate(groups):
        cur_var = 0.
        for term1 in group:
            for term2 in group:
                cur_var += term1.coeff * term2.coeff * get_cov(term1, term2, cov_dict)
        weights[idx] = np.sqrt(np.real(cur_var))
    return weights / np.sum(weights)

class OverlappingGroups:
    '''
    Class required for performing overlapping grouping techniques:
    coefficient splitting (implemented), ghost paulis (todo), and iterative 
    measurement allocation (todo).
    '''
    def __init__(self, no_groups, o_terms, term_exists_in):
        self.no_groups = no_groups #Non-overlapping groups: required as a starting point.
        self.o_terms = o_terms #List of Pauli products that are compatible in multiple groups.
        self.term_exists_in = term_exists_in #List of indices indicating where overlapping Pauli products appear.
        self.o_groups = [[] for i in range(len(no_groups))]
        for idx, term in enumerate(o_terms):
            for grup_idx in term_exists_in[idx]:
                self.o_groups[grup_idx].append(term)
        self.wo_fixed = OverlappingGroups_wo_fixed(self.o_groups, self.o_terms, self.term_exists_in)
        return None

    @classmethod
    def init_from_binary_terms(cls, terms, condition='fc'):
        '''
        Obtain a list of Pauli operators that are compatible in more than one group
        by using the overlapping version of the sorted insertion algorithm.
        '''
        nonoverlapping_groups = sorted_insertion_grouping(terms, condition=condition)
        sorted_terms = sorted(terms, key=lambda x: np.abs(x.coeff), reverse=True)
        overlapping_terms = []
        term_exists_in = [] #List of group indices where overlapping terms are present.
        for term in sorted_terms:
            grup_idxs = []
            for idx, group in enumerate(nonoverlapping_groups):
                commute = term_commutes_with_group(term, group, condition)
                if commute: grup_idxs.append(idx)
            if len(grup_idxs) > 1:
                overlapping_terms.append(term.term_w_coeff(0.0))
                term_exists_in.append(grup_idxs)
        group = cls(nonoverlapping_groups, overlapping_terms, term_exists_in)
        return group

    def optimize_pauli_coefficients(self, cov_dict, sample_size):
        '''
        Build the equation matrix @ x = b and solve it in order to obtain the
        optimal overlapping coefficients for the measurable fragments 
        [see Eq. (14) on arXiv:2201.01471].
        '''
        def prep_mat_single_row(term, group_index):
            '''
            Build the matrix row corresponding to Pauli term. 
            '''
            mat_single = np.zeros(np.sum(self.wo_fixed.Ncoeff_grp))
            for term2_idx, term2 in enumerate(self.o_groups[group_index]):
                term2_idx_dict = self.wo_fixed.term_idxs[term2.binary_tuple()]
                cov = np.real_if_close(get_cov(term, term2, cov_dict))
                if term2 in self.wo_fixed.o_groups[group_index]:
                    mat_single[term2_idx_dict[group_index]] -= cov/sample_size[group_index]
                else:
                    for idx in term2_idx_dict.values():
                        mat_single[idx] += cov/sample_size[group_index]
            return mat_single

        def prep_b_single_row(term, group_index):
            '''
            Build b row corresponding to Pauli term. 
            '''
            return np.real_if_close(cov_term_w_group(term, self.no_groups[group_index], cov_dict) / sample_size[group_index])

        mat_size = np.sum(self.wo_fixed.Ncoeff_grp)
        matrix = np.zeros((mat_size, mat_size))
        b = np.zeros((1, mat_size))
        row_idx = 0
        for grp_idx, grp in enumerate(self.wo_fixed.o_groups):
            for term1 in grp:
                matrix[row_idx] += prep_mat_single_row(term1, grp_idx)
                b[0, row_idx] += prep_b_single_row(term1, grp_idx)

                fixed_group_index = self.wo_fixed.fixed_grp[self.o_terms.index(term1)]
                matrix[row_idx] -= prep_mat_single_row(term1, fixed_group_index)
                b[0, row_idx] -= prep_b_single_row(term1, fixed_group_index)
                row_idx += 1
        sol = np.linalg.lstsq(matrix, b.T, rcond=None)[0]
        return sol.T[0]

    def overlapping_groups_from_coeff(self, coeff):
        '''
        Find fixed coefficients from the optimal coefficients and
        return the optimal overlapping groups to be measured.
        '''
        def add_coeff_times_term(coeff, term, group_index):
            added = False
            for igrp, group_term in enumerate(final_overlapping_groups[group_index]):
                if group_term.binary_tuple() == term.binary_tuple():
                    final_overlapping_groups[group_index][igrp].set_coeff( coeff + group_term.get_coeff() )
                    added = True
            if not(added): final_overlapping_groups[group_index].append( term.term_w_coeff(coeff) )
            return None

        final_overlapping_groups = deepcopy(self.no_groups)
        for term_idx, term in enumerate(self.o_terms):
            fixed_grp_coefficient = 0.0
            for grp_idx in self.wo_fixed.term_exists_in[term_idx]:
                cur_coeff = coeff[self.wo_fixed.init_idx[grp_idx] + self.wo_fixed.o_groups[grp_idx].index(term)]
                fixed_grp_coefficient -= cur_coeff
                add_coeff_times_term(cur_coeff, term, grp_idx)

            fixed_idx = self.wo_fixed.fixed_grp[term_idx]
            add_coeff_times_term(fixed_grp_coefficient, term, fixed_idx)
        return final_overlapping_groups

    def optimal_overlapping_groups(self, overlap_help):
        '''
        Find a set of overlapping groups with optimized coefficients.
        '''
        cur_groups = self.no_groups
        for i in range(overlap_help.n_iter):
            cur_sample_size = get_opt_sample_size(cur_groups, overlap_help.cov_dict)
            coeff = self.optimize_pauli_coefficients(overlap_help.cov_dict, cur_sample_size)
            cur_groups = self.overlapping_groups_from_coeff(coeff)
        return cur_groups, cur_sample_size
