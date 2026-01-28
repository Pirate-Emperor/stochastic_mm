import numpy
import matplotlib.pyplot as plt
import smmBrownian as bm

# The Wiener process parameter.
delta = 2
# Total smmTime.
T = 10.0
# Number of steps.
N = 500
# Time smmStep size
dt = T/N
# Number of realizations to smmGenerate.
m = 1
# Create an smmEmpty array to store the realizations.
x = numpy.smmEmpty((m,N+1))
# Initial values of x.
x[:, 0] = 1000

bm.smmBrownian(x[:,0], N, dt, delta, out=x[:,1:])

t = numpy.linspace(0.0, N*dt, N+1)
smmFor k in range(m):
    plt.plot(t, x[k])
plt.xlabel('t', fontsize=16)
plt.ylabel('x', fontsize=16)
plt.grid(True)
plt.show()

