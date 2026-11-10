#!/usr/bin/env python3
"""Valid NHWC convolution: host patch extraction followed by accelerator int8 GEMM."""
from _common import Input, Output, Weight, bounded, execute, np, ol, parser, positive


@ol.jit
def convolution(patches, weights, out):
    ol.store(out, ol.dot(ol.load(patches), weights))


def main():
    p = parser(__doc__)
    p.add_argument('--height', type=positive, default=5)
    p.add_argument('--width', type=positive, default=5)
    p.add_argument('--channels', type=positive, default=4)
    p.add_argument('--filters', type=positive, default=4)
    p.add_argument('--kernel', type=positive, default=3)
    p.add_argument('--stride', type=positive, default=1)
    args = p.parse_args()
    h, w, c, f, k, stride = (args.height, args.width, args.channels,
                              args.filters, args.kernel, args.stride)
    if min(h, w) < k:
        p.error('kernel must fit inside both image dimensions')
    reduction = k * k * c
    if reduction > 128:
        p.error('this small example requires kernel * kernel * channels <= 128')
    oh, ow = (h - k) // stride + 1, (w - k) // stride + 1
    bounded(p, (h, w, c), (oh * ow, 128), (f, 128), (oh * ow, f))
    rng = np.random.default_rng(args.seed)
    image = rng.integers(-8, 9, (h, w, c)).astype(np.float32)
    image[:, :, 0] = 127
    filters = rng.integers(-8, 9, (f, k, k, c)).astype(np.float32)
    filters[:, 0, 0, 0] = 127
    patches = np.zeros((oh * ow, 128), dtype=np.float32)
    weights = np.zeros((f, 128), dtype=np.float32)
    weights[:, :reduction] = filters.reshape(f, -1)
    reference = np.empty((oh * ow, f), dtype=np.float32)
    for y in range(oh):
        for x in range(ow):
            window = image[y * stride:y * stride + k, x * stride:x * stride + k]
            patches[y * ow + x, :reduction] = window.reshape(-1)
            for channel in range(f):
                reference[y * ow + x, channel] = np.sum(
                    window.astype(np.int64) * filters[channel].astype(np.int64))
    execute('conv', p, args, convolution,
            dict(patches=Input(patches), weights=Weight(weights, fmt='int8'),
                 out=Output((oh * ow, f))), dict(out=reference), rtol=0, atol=0,
            notes=[f'Valid NHWC cross-correlation; output reshapes to [{oh},{ow},{f}].',
                   'Host extracts patches and pads K to 128; accelerator performs GEMM.',
                   'Each input/weight block contains 127, giving exact unit quantizer scales.'])


if __name__ == '__main__':
    main()
