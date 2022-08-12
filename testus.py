import tequila as tq

H = tq.QubitHamiltonian("1.0*X(0)X(1) + 1.0*Y(0)Y(1) +  1.0*X(0)")
U = tq.gates.H([0,1])
E = tq.ExpectationValue(H=H , U=U)
E = tq.ExpectationValue(H=H , U=U, optimize_measurements=True)
# method = ["rls","largest_first", "sorted_insertion", "overlapping_sorted_insertion"]
# covariance_dictionary = [None, dict]
# number_of_iterations = [None, integer]
E = tq.ExpectationValue(H=H , U=U, optimize_measurements={"asd":"asd", "other":1})

