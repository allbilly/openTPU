#!/usr/bin/env python3
"""Load two vectors, add on the VPU, and store the result."""
from _common import Input, Output, bounded, execute, np, ol, parser, positive


@ol.jit
def add(a, b, out):
    ol.store(out, ol.load(a) + ol.load(b))


def main():
    p = parser(__doc__)
    p.add_argument('--size', type=positive, default=32)
    args = p.parse_args()
    bounded(p, (args.size,))
    rng = np.random.default_rng(args.seed)
    a = rng.integers(-32, 33, args.size).astype(np.float32) / 4
    b = rng.integers(-32, 33, args.size).astype(np.float32) / 4
    execute('simple_add', p, args, add, dict(a=Input(a), b=Input(b), out=Output(a.shape)),
            dict(out=a + b), rtol=0, atol=0)


if __name__ == '__main__':
    main()
