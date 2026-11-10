"""Independent Q8.8 golden model for the step-2 toy-TPU scoreboard.

Arithmetic mirrors `ladder/toy/src/fixedpoint.sv` defaults (all fxp_* instances use
WII=WIF=8, i.e. signed 16-bit Q8.8, ROUND=1):

* `fmul(a, b)`  - `fxp_mul`: 32-bit Q16.16 product, arithmetic shift right by
  8 with a +1 bump when the dropped bit 7 is set (round-half-up on the
  floored value, exact `fxp_zoom` rule), then saturate to int16.
* `fadd(a, b)`  - `fxp_add`: saturating int16 addition.
* `fsub(a, b)`  - `fxp_addsub(sub=1)`: saturating int16 subtraction.
* `leaky(x, leak)` - `leaky_relu_child`: x >= 0 ? x : fmul(x, leak).

`golden()` computes the XOR MLP forward pass, the MSE loss gradient, the
layer-1 gradient and one SGD step from the source-language constants, using
only the helpers above.  The step-2 bench compares the RTL's unified-buffer
contents against these vectors.
"""

# Source-language stimulus (same numbers as test/test_tpu.py).
X = [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]
Y = [0.0, 1.0, 1.0, 0.0]
W1 = [[0.2985, -0.5792], [0.0913, 0.4234]]
W2 = [0.5266, 0.2958]
B1 = [-0.4939, 0.189]
B2 = [0.6358]
LEARNING_RATE = 0.75
LEAK_FACTOR = 0.5


def q(v):
    """Float -> signed Q8.8 integer value (the arithmetic domain of the bench)."""
    return int(round(v * 256.0))


def u16(x):
    """Signed Q8.8 value -> 16-bit unified-buffer word."""
    return x & 0xFFFF


def s16(x):
    return x - 0x10000 if x >= 0x8000 else x


def clip16(x):
    return max(-32768, min(32767, x))


def fmul(a, b):
    prod = a * b
    r = prod >> 8
    if (prod >> 7) & 1 and (r & 0x7FFFFF) != 0x7FFFFF:
        r += 1
    return clip16(r)


def fadd(a, b):
    return clip16(a + b)


def fsub(a, b):
    return clip16(a - b)


def leaky(x, leak):
    return x if x >= 0 else fmul(x, leak)


XQ = [[q(v) for v in row] for row in X]
YQ = [q(v) for v in Y]
W1Q = [[q(v) for v in row] for row in W1]
W2Q = [q(v) for v in W2]
B1Q = [q(v) for v in B1]
B2Q = [q(v) for v in B2]
LRQ = q(LEARNING_RATE)
LEAKQ = q(LEAK_FACTOR)
INVQ = q(2.0 / len(X))

# Unified-buffer host-load layout produced by test_tpu's write channel order
# (row-major matrices, write loop stores channel 1 before channel 0):
#   [0:8) X row-major, [8:12) Y, [12:16) W1 row-major,
#   [16:18) B1, [18:20) W2, [20] B2
HOST_UB = [u16(v) for v in (XQ[0] + XQ[1] + XQ[2] + XQ[3] + YQ
                            + W1Q[0] + W1Q[1] + B1Q + W2Q + B2Q)]


def golden():
    """Bit-exact Q8.8 golden vectors for the toy XOR network."""
    h1 = []
    for s in range(4):
        row = []
        for j in range(2):
            z = fadd(fmul(XQ[s][0], W1Q[j][0]), fmul(XQ[s][1], W1Q[j][1]))
            row.append(leaky(fadd(z, B1Q[j]), LEAKQ))
        h1.append(row)

    h2, dz2, dz1 = [], [], []
    for s in range(4):
        z2 = fadd(fadd(fmul(h1[s][0], W2Q[0]), fmul(h1[s][1], W2Q[1])), B2Q[0])
        h2s = leaky(z2, LEAKQ)
        h2.append(h2s)
        g = fmul(fsub(h2s, YQ[s]), INVQ)
        g = g if h2s >= 0 else fmul(g, LEAKQ)  # leaky-ReLU derivative
        dz2.append(g)
        row = []
        for j in range(2):
            r = fmul(g, W2Q[j])
            row.append(r if h1[s][j] >= 0 else fmul(r, LEAKQ))
        dz1.append(row)

    dw1 = [[fadd(fadd(fadd(fmul(dz1[0][j], XQ[0][k]), fmul(dz1[1][j], XQ[1][k])),
                     fmul(dz1[2][j], XQ[2][k])), fmul(dz1[3][j], XQ[3][k]))
            for k in range(2)] for j in range(2)]
    dw2 = [fadd(fadd(fadd(fmul(dz2[0], h1[0][j]), fmul(dz2[1], h1[1][j])),
                     fmul(dz2[2], h1[2][j])), fmul(dz2[3], h1[3][j])) for j in range(2)]
    db1 = [fadd(fadd(fadd(dz1[0][j], dz1[1][j]), dz1[2][j]), dz1[3][j]) for j in range(2)]
    db2 = fadd(fadd(fadd(dz2[0], dz2[1]), dz2[2]), dz2[3])

    def sgd(w, g):
        return fsub(w, fmul(g, LRQ))

    return {
        "H1": h1,
        "H2": h2,
        "dZ2": dz2,
        "dZ1": dz1,
        "dW1": dw1,
        "dW2": dw2,
        "dB1": db1,
        "dB2": db2,
        "W1_new": [[sgd(W1Q[j][k], dw1[j][k]) for k in range(2)] for j in range(2)],
        "W2_new": [sgd(W2Q[j], dw2[j]) for j in range(2)],
        "B1_new": [sgd(B1Q[j], db1[j]) for j in range(2)],
        "B2_new": [sgd(B2Q[0], db2)],
    }


def flat_h1():
    return [v for row in golden()["H1"] for v in row]


def sgd_step(old, grad):
    """One SGD update used by gradient_descent.sv: old - lr*grad."""
    return fsub(old, fmul(grad, LRQ))
