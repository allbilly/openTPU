#!/usr/bin/env python3
"""Valid NHWC max/average pooling through accelerator row reductions."""
from _common import Input, Output, bounded, execute, np, ol, parser, positive


@ol.jit
def pooling(windows, out, operation, count):
    values = ol.load(windows)
    result = ol.max(values, axis=1) if operation == 'max' else ol.sum(values, axis=1) * (1.0 / count)
    ol.store(out, result)


def main():
    p = parser(__doc__)
    p.add_argument('--op', choices=['max', 'avg'], default='max')
    p.add_argument('--height', type=positive, default=4)
    p.add_argument('--width', type=positive, default=4)
    p.add_argument('--channels', type=positive, default=2)
    p.add_argument('--kernel', type=positive, default=2)
    p.add_argument('--stride', type=positive, default=2)
    args = p.parse_args()
    h, w, c, k, stride = args.height, args.width, args.channels, args.kernel, args.stride
    if min(h, w) < k:
        p.error('kernel must fit inside both image dimensions')
    oh, ow = (h - k) // stride + 1, (w - k) // stride + 1
    bounded(p, (h, w, c), (oh * ow * c, k * k))
    rng = np.random.default_rng(args.seed)
    image = rng.integers(-32, 33, (h, w, c)).astype(np.float32) / 4
    windows = np.empty((oh * ow * c, k * k), dtype=np.float32)
    reference = np.empty((oh, ow, c), dtype=np.float32)
    for y in range(oh):
        for x in range(ow):
            window = image[y * stride:y * stride + k, x * stride:x * stride + k]
            windows[(y * ow + x) * c:(y * ow + x + 1) * c] = window.reshape(-1, c).T
            reference[y, x] = (np.max(window, axis=(0, 1)) if args.op == 'max'
                               else np.mean(window.astype(np.float64), axis=(0, 1)))
    execute('pooling_' + args.op, p, args, pooling,
            dict(windows=Input(windows), out=Output((oh * ow * c,)),
                 operation=args.op, count=k * k), dict(out=reference.reshape(-1)),
            rtol=1e-6, atol=1e-6,
            notes=[f'Valid NHWC pooling; output reshapes to [{oh},{ow},{c}].',
                   'Host extracts windows; accelerator executes max/sum reductions.'])


if __name__ == '__main__':
    main()
