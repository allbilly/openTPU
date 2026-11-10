#!/usr/bin/env python3
"""Elementwise add, subtract, multiply, min/max, ReLU and absolute value."""
from _common import Input, Output, bounded, execute, np, ol, parser, positive


@ol.jit
def elementwise(a, b, out, operation):
    x, y = ol.load(a), ol.load(b)
    if operation == 'add':
        z = x + y
    elif operation == 'sub':
        z = x - y
    elif operation == 'mul':
        z = x * y
    elif operation == 'max':
        z = ol.maximum(x, y)
    elif operation == 'min':
        z = ol.minimum(x, y)
    elif operation == 'relu':
        z = ol.maximum(x, 0.0)
    else:
        z = ol.abs(x)
    ol.store(out, z)


def main():
    p = parser(__doc__)
    p.add_argument('--op', choices=['add', 'sub', 'mul', 'max', 'min', 'relu', 'abs'], default='mul')
    p.add_argument('--size', type=positive, default=32)
    args = p.parse_args()
    bounded(p, (args.size,))
    rng = np.random.default_rng(args.seed)
    a = rng.integers(-32, 33, args.size).astype(np.float32) / 4
    b = rng.integers(-32, 33, args.size).astype(np.float32) / 4
    references = dict(add=lambda: a + b, sub=lambda: a - b, mul=lambda: a * b,
                      max=lambda: np.maximum(a, b), min=lambda: np.minimum(a, b),
                      relu=lambda: np.maximum(a, 0), abs=lambda: np.abs(a))
    execute('elementwise_' + args.op, p, args, elementwise,
            dict(a=Input(a), b=Input(b), out=Output(a.shape), operation=args.op),
            dict(out=references[args.op]()), rtol=0, atol=0)


if __name__ == '__main__':
    main()
