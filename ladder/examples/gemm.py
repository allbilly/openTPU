#!/usr/bin/env python3
"""A[M,K] @ W[N,K].T through QACT and the streamed int8 matrix unit."""
from _common import Input, Output, Weight, bounded, exact_int8_rows, execute, np, ol, parser, positive


@ol.jit
def gemm(a, weights, out):
    ol.store(out, ol.dot(ol.load(a), weights))


def main():
    p = parser(__doc__)
    p.add_argument('--m', type=positive, default=4)
    p.add_argument('--n', type=positive, default=16)
    p.add_argument('--k', type=positive, default=128)
    args = p.parse_args()
    if args.k % 128:
        p.error('--k must be a multiple of the 128-element quantization block')
    bounded(p, (args.m, args.k), (args.n, args.k), (args.m, args.n))
    rng = np.random.default_rng(args.seed)
    a = exact_int8_rows(rng, args.m, args.k)
    weights = exact_int8_rows(rng, args.n, args.k)
    reference = (a.astype(np.int64) @ weights.astype(np.int64).T).astype(np.float32)
    execute('gemm', p, args, gemm,
            dict(a=Input(a), weights=Weight(weights, fmt='int8'), out=Output((args.m, args.n))),
            dict(out=reference), rtol=0, atol=0,
            notes=['Weights are [N,K], so the operation is A @ W.T.',
                   'Integer-valued fp32 inputs contain 127 in each block, making both quantizer scales exactly one.'])


if __name__ == '__main__':
    main()
