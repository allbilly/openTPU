#!/usr/bin/env python3
"""Stable row softmax using VPU max, EXP2, sum and reciprocal."""
from _common import Input, Output, bounded, execute, np, ol, parser, positive


@ol.jit
def softmax(x, out):
    values = ol.load(x)
    maximum = ol.max(values, axis=1)
    exponentials = ol.exp2((values - maximum[:, None]) * ol.LOG2E)
    totals = ol.sum(exponentials, axis=1)
    ol.store(out, exponentials / totals[:, None])


def main():
    p = parser(__doc__)
    p.add_argument('--rows', type=positive, default=4)
    p.add_argument('--cols', type=positive, default=32)
    args = p.parse_args()
    bounded(p, (args.rows, args.cols))
    x = np.random.default_rng(args.seed).uniform(-4, 4, (args.rows, args.cols)).astype(np.float32)
    shifted = x.astype(np.float64) - x.max(axis=1, keepdims=True)
    exponentials = np.exp(shifted)
    reference = exponentials / exponentials.sum(axis=1, keepdims=True)
    execute('softmax', p, args, softmax, dict(x=Input(x), out=Output(x.shape)),
            dict(out=reference), rtol=2e-5, atol=1e-6)


if __name__ == '__main__':
    main()
