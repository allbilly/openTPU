#!/usr/bin/env python3
"""Row RMS normalization with a learned scale, using VPU reductions and RSQRT."""
from _common import Input, Output, bounded, execute, np, ol, parser, positive
from opentpu.kernels.lib import rmsnorm as normalize


@ol.jit
def rmsnorm(x, gamma, out, eps):
    ol.store(out, normalize(ol.load(x), ol.load(gamma), eps))


def main():
    p = parser(__doc__)
    p.add_argument('--rows', type=positive, default=4)
    p.add_argument('--cols', type=positive, default=128)
    args = p.parse_args()
    bounded(p, (args.rows, args.cols))
    rng = np.random.default_rng(args.seed)
    x = rng.standard_normal((args.rows, args.cols)).astype(np.float32)
    gamma = rng.uniform(0.5, 1.5, args.cols).astype(np.float32)
    reference = x.astype(np.float64) / np.sqrt(np.mean(x.astype(np.float64) ** 2, axis=1, keepdims=True) + 1e-6)
    reference *= gamma
    execute('rmsnorm', p, args, rmsnorm,
            dict(x=Input(x), gamma=Input(gamma), out=Output(x.shape), eps=1e-6),
            dict(out=reference), rtol=2e-5, atol=1e-6)


if __name__ == '__main__':
    main()
