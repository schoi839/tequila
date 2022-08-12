import tequila as tq

H = tq.paulis.Z(0) + tq.paulis.Z([0,1]) + tq.paulis.X(1) + tq.paulis.X([0,1]) # should be 2 groups
U = tq.gates.H([0,1]) + tq.gates.Ry(angle="a", target=0)

E = tq.ExpectationValue(H=H, U=U, optimize_measurements=True, suggested_samples=samples)

print("non optimized expectation value")
tmp = tq.ExpectationValue(H=H, U=U)
print(tmp)
print("optimized expectation value")

# this should tell us, that we have 2 individual expectation values (the two groups)
print(E)

# define what values the variable "a" should actually take
variables = {"a":1.0}

# evaluate the optimized expectation value
compiled = tq.compile(E) # options: e.g. backend="cirq","qulacs","qiskit" ... 
evaluated = compiled(variables, samples=None) # set samples to an integer for shot based simulation otherwise it simulates the expectation vaue exactly
print("value is = ", evaluated)

# evaluate the groups individually
values = []
for expval in E.get_expectationvalues():
    # need to make an objective out of this
    expval = tq.Objective(args=[expval])
    f = tq.compile(expval)
    value = f(variables, samples=1000) # just an example
    values.append(value)

print("individual values are: ", values)
print("summed = ", sum(values))
