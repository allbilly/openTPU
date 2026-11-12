"""otpu-train: fine-tune the small model `opentpu/train` trains, on the simulator or a card.

A training step is the device's matmuls plus the host's optimizer (`docs/train.md`): the forward
pass and the backward pass run as instructions on the ISA simulator, the RTL model or the card
(`--backend`), and AdamW and the loss stay on the host. What this tool trains is the model in
`opentpu/train/params.py`: a SwiGLU block with an RMSNorm and a tied output head, on a byte-sized
vocabulary -- the shape the inference kernels already have, at a size one program fits. It is the
first rung of `docs/train.md` 8's plan, not a 7B fine-tune.

    otpu-train                                    the default task: learn to predict a target
                                                  token for each of a fixed batch's rows
    otpu-train --steps 200                        longer
    otpu-train --backend rtl                      on the SystemVerilog RTL (Verilator)
    otpu-train --backend board                    on the card (needs `otpu-lock`)
    otpu-train --checkpoint run.npz               save the master weights every --save-every steps
    otpu-train --resume run.npz                   continue from a checkpoint
    otpu-train --tokenize                         train on text: the batch is a window of a
                                                  token stream, the target the next token
                                                  (a byte-level model: the vocabulary is the 256
                                                  bytes, padded to D)

The task is deliberately simple and its optimum is reachable: the loss must fall, and the tool
prints it. A run that does not fall is a broken step, not a hard problem -- that is the point of
the first target in the plan (`docs/train.md` 7, 8).

How the batch is made. `--tokenize` with `--text FILE` reads the file and trains on windows of
`--seq` bytes: row t of the batch is bytes [t * seq, (t + 1) * seq) of a sliding window, and the
target is the byte after each window -- a next-byte prediction, which the block can learn. Without
`--text`, the batch is random and the targets are `--targets`, so the run is a synthetic task whose
loss falls to zero: a smoke test of the whole loop, and one whose exact optimum is known.

The checkpoint is the fp32 master copies (`opentpu/train/params.py: Params.named`), the optimizer's
moments and the shapes, in one `.npz`: `docs/train.md` 6 says why the master copy -- not the
quantized image -- is what a checkpoint saves.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

from .params import AdamW, Params, Shapes, softmax_xent
from .loop import Trainer


def make_batch(args, shapes: Shapes) -> tuple[np.ndarray, np.ndarray]:
    """The batch a run trains on: (x [B, H], targets [B]).

    Without `--text`, a deterministic random batch and `--targets`; with it, a window of the
    text's bytes as the inputs and the byte after each window as the target. The token id is a
    byte plus one (0 stays the padding), and the vocabulary is padded to the configuration's D
    (`Shapes.check`: the backward pass streams its transpose, so it must be a multiple of D).
    """
    if args.text:
        text = Path(args.text).read_bytes()
        if len(text) < shapes.batch * args.seq + 1:
            raise ValueError(f"{args.text} has {len(text)} bytes; a batch of "
                             f"{shapes.batch} x {args.seq} needs more")
        start = args.offset
        rows = np.zeros((shapes.batch, shapes.hidden), np.float32)
        targets = np.zeros(shapes.batch, np.int64)
        for b in range(shapes.batch):
            window = text[start + b * args.seq: start + (b + 1) * args.seq]
            # one byte a row: the block's residual stream is H wide, the first `seq` H words carry
            # the window's bytes (a byte-level model: vectors of bytes, as makemore's does)
            rows[b, :len(window)] = np.frombuffer(window, np.uint8).astype(np.float32) / 255.0
            targets[b] = int(text[start + (b + 1) * args.seq]) + 1   # 0 stays padding
        return rows, targets
    rng = np.random.default_rng(args.seed)
    x = (rng.standard_normal((shapes.batch, shapes.hidden)) * 0.5).astype(np.float32)
    targets = args.targets[:shapes.batch] if args.targets else \
        rng.integers(0, shapes.vocab, shapes.batch)
    return x, np.asarray(targets, np.int64)


def vocab_for(shapes: Shapes, cfg) -> Shapes:
    """`shapes` with the vocabulary padded to the configuration's D (the backward pass streams
    the head's transpose, whose reduction dim the vocabulary becomes)."""
    v = -(-shapes.vocab // cfg.D) * cfg.D
    return Shapes(**{**shapes.__dict__, "vocab": v})


def save(path: str, tr: Trainer, args) -> None:
    """Write the master weights, gamma, the optimizer's moments and the shapes."""
    # Params.named() keys are the names a resume reads: w_gate, not w_w_gate
    d = {n: a for n, a in tr.params.named().items()}
    d.update({f"m_{n}": a for n, a in tr.optimizer.m.items()})
    d.update({f"v_{n}": a for n, a in tr.optimizer.v.items()})
    d["shapes"] = np.asarray(list(vars(tr.shapes).values()), np.int64)
    d["step"] = np.asarray([tr.optimizer.step], np.int64)
    np.savez(path, **d)


def load(path: str, tr: Trainer) -> None:
    """Read a checkpoint into the trainer's master copies and optimizer state."""
    z = np.load(path)
    for n, a in tr.params.named().items():
        a[...] = z[n]
    for n in tr.optimizer.m:
        tr.optimizer.m[n][...] = z[f"m_{n}"]
        tr.optimizer.v[n][...] = z[f"v_{n}"]
    tr.optimizer.step = int(z["step"][0])
    tr.params.quantized()


def _run_lora(args, cfg, shapes) -> int:
    """The LoRA rung: a frozen random base and a `--lora`-rank adapter, trained on the same
    synthetic or text batch the block's run uses.

    The base is random (this is a smoke test of the adapter path, not a fine-tune of a real
    checkpoint): what it demonstrates is that the adapter's two gradients are the only things
    that move, that the frozen base does not, and that repeated steps reduce the loss.
    """
    from .lora import Adapters, LoRA
    rank = args.lora or args.qlora
    rng = np.random.default_rng(args.seed)
    kdim, n = shapes.hidden, shapes.vocab
    w = (rng.standard_normal((n, kdim)) / np.sqrt(kdim)).astype(np.float32)   # the frozen base
    ad = Adapters.random(rank, kdim, n, cfg.D, seed=args.seed)
    base_fmt = args.base_fmt if args.qlora else "int8"
    lo = LoRA(w=w, adapters=ad, cfg=cfg, optimizer=AdamW(lr=args.lr,
                                                         weight_decay=args.weight_decay),
              batch=shapes.batch, scale=args.lora_scale, base_fmt=base_fmt)
    lo.compile()
    x, targets = make_batch(args, shapes)
    w_copy = w.copy()
    kind = "QLoRA" if args.qlora else "LoRA"
    print(f"otpu-train: {kind} rank {rank} (padded to {ad.a.shape[0]}) on a frozen "
          f"{n} x {kdim} base ({base_fmt}), {shapes.batch} rows")
    print(f"            {len(lo.progs['forward'][0])} + {len(lo.progs['backward'][0])} "
          f"instructions a step, {lo.nbytes / 1024:.1f} KiB of DRAM")
    t0 = time.perf_counter()
    losses = []
    for i in range(args.steps):
        try:
            r = lo.train_step(x, targets)
        except (RuntimeError, NotImplementedError) as e:
            print(f"otpu-train: the {args.backend} backend cannot run a step here: {e}",
                  file=sys.stderr)
            return 3
        losses.append(r["loss"])
        if args.every and (i % args.every == 0 or i == args.steps - 1):
            print(f"step {i + 1:4d}  loss {r['loss']:.6f}")
    frozen_kept = bool(np.array_equal(w, w_copy))
    print(f"loss {losses[0]:.4f} -> {losses[-1]:.4f} in {len(losses)} steps "
          f"({time.perf_counter() - t0:.2f} s, {args.backend}); frozen base "
          f"{'unchanged' if frozen_kept else 'MOVED (a bug)'}")
    return 0 if (losses and losses[-1] < losses[0] and frozen_kept) else 1


def _run_layer(args, cfg, shapes) -> int:
    """The full-training rung: a whole transformer layer -- attention, an MLP, nine trainable
    parameter groups -- on the same synthetic or text batch.

    The layer's width is `--hidden` (the model width and the head count's product), its MLP's
    inner width `--interm`. A step is 247 + 1213 instructions at the default shapes (measured),
    which is why this is a smoke test of the full-training path rather than a model.
    """
    from .layers import LayerParams, LayerTrainer
    dh, trunk = shapes.hidden, shapes.interm
    Tt = shapes.batch
    if Tt % cfg.D:
        Tt = -(-Tt // cfg.D) * cfg.D      # the sequence length is an attention reduction dim
        print(f"otpu-train: the token count padded to D: {shapes.batch} -> {Tt}")
    p = LayerParams.random(dh, trunk, cfg.D, seed=args.seed)
    tr = LayerTrainer(p, cfg, T=Tt, optimizer=AdamW(lr=args.lr,
                                                    weight_decay=args.weight_decay))
    x, targets = make_batch(args, shapes)
    x = x[:, :dh] if x.shape[1] >= dh else np.pad(x, ((0, 0), (0, dh - x.shape[1])))
    if x.shape[0] < Tt:                  # (the batch's rows are the layer's tokens)
        x = np.pad(x, ((0, Tt - x.shape[0]), (0, 0)))
    print(f"otpu-train: a whole layer, {dh} wide with a {trunk}-wide MLP, {shapes.batch} tokens")
    print(f"            {len(tr.progs['forward'][0])} + {len(tr.progs['backward'][0])} "
          f"instructions a step, {tr.lay.nbytes / 1024:.1f} KiB of DRAM")
    t0 = time.perf_counter()
    losses = []
    for i in range(args.steps):
        try:
            tg = np.asarray(targets, np.int64) % dh
            if len(tg) < Tt:
                tg = np.concatenate([tg, np.zeros(Tt - len(tg), np.int64)])
            r = tr.train_step(x, tg)
        except (RuntimeError, NotImplementedError) as e:
            print(f"otpu-train: the {args.backend} backend cannot run a step here: {e}",
                  file=sys.stderr)
            return 3
        losses.append(r["loss"])
        if args.every and (i % args.every == 0 or i == args.steps - 1):
            print(f"step {i + 1:4d}  loss {r['loss']:.6f}")
    print(f"loss {losses[0]:.4f} -> {losses[-1]:.4f} in {len(losses)} steps "
          f"({time.perf_counter() - t0:.2f} s, {args.backend})")
    return 0 if losses and losses[-1] < losses[0] else 1


def _run_stack(args, cfg, shapes) -> int:
    """A stack of `--stack` transformer layers, chained: the whole-model rung.

    One DRAM image holds every layer; a step is n forward launches, the host's loss, and n + 1
    backward launches (docs/train.md 8). The measured cost is about 140 KiB a layer at these
    shapes, so the simulator holds four comfortably.
    """
    from .stack import Stack, StackParams
    dh, trunk, vocab = shapes.hidden, shapes.interm, shapes.vocab
    Tt = shapes.batch
    if Tt % cfg.D:
        Tt = -(-Tt // cfg.D) * cfg.D      # the token count is an attention reduction dim
        print(f"otpu-train: the token count padded to D: {shapes.batch} -> {Tt}")
    p = StackParams.random(args.stack, dh, trunk, vocab, cfg.D, seed=args.seed)
    st = Stack(p, cfg, T=Tt, optimizer=AdamW(lr=args.lr, weight_decay=args.weight_decay))
    x, targets = make_batch(args, shapes)
    if x.shape[1] > dh:
        x = x[:, :dh]
    elif x.shape[1] < dh:
        x = np.pad(x, ((0, 0), (0, dh - x.shape[1])))
    if x.shape[0] < Tt:
        x = np.pad(x, ((0, Tt - x.shape[0]), (0, 0)))
    tg = np.asarray(targets, np.int64) % vocab
    if len(tg) < Tt:
        tg = np.concatenate([tg, np.zeros(Tt - len(tg), np.int64)])
    print(f"otpu-train: {args.stack} layers of {dh} (MLP {trunk}), an LM head over {vocab}, "
          f"{Tt} tokens")
    print(f"            {len(st.lts[0].progs['forward'][0])} + "
          f"{len(st.lts[0].progs['backward'][0])} instructions a layer, "
          f"{st.sl.nbytes / 1024:.1f} KiB of DRAM for the whole stack")
    t0 = time.perf_counter()
    losses = []
    for i in range(args.steps):
        try:
            r = st.train_step(x, tg)
        except (RuntimeError, NotImplementedError) as e:
            print(f"otpu-train: the {args.backend} backend cannot run a step here: {e}",
                  file=sys.stderr)
            return 3
        losses.append(r["loss"])
        if args.every and (i % args.every == 0 or i == args.steps - 1):
            print(f"step {i + 1:4d}  loss {r['loss']:.6f}")
    print(f"loss {losses[0]:.4f} -> {losses[-1]:.4f} in {len(losses)} steps "
          f"({time.perf_counter() - t0:.2f} s, {args.backend}, {args.stack} layers)")
    return 0 if losses and losses[-1] < losses[0] else 1


def main(argv=None) -> int:
    from ..isasim import Config, board_config
    ap = argparse.ArgumentParser(
        prog="otpu-train", description="Fine-tune openTPU's small SwiGLU model (docs/train.md)")
    ap.add_argument("--backend", default="isa", choices=("isa", "rtl"),
                    help="where a step runs: the ISA simulator (default) or the Verilator RTL "
                         "model, which needs a Verilator that parses the design's "
                         "SystemVerilog (5.020 does not: rtl/mxu/otpu_mxu.sv's array selects). "
                         "The card's protocol is not wired yet (docs/train.md 10)")
    ap.add_argument("--steps", type=int, default=50)
    ap.add_argument("--lr", type=float, default=0.05)
    ap.add_argument("--weight-decay", type=float, default=0.01)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--hidden", type=int, default=32)
    ap.add_argument("--interm", type=int, default=32)
    ap.add_argument("--vocab", type=int, default=32)
    ap.add_argument("--rows", type=int, default=4)
    ap.add_argument("--text", help="train on this file's bytes (a next-byte prediction)")
    ap.add_argument("--seq", type=int, default=32, help="bytes a row of the batch")
    ap.add_argument("--offset", type=int, default=0, help="the window's first byte")
    ap.add_argument("--targets", type=int, nargs="*", default=None,
                    help="the synthetic task's targets (default: random)")
    ap.add_argument("--lora", type=int, default=0, metavar="RANK",
                    help="train a LoRA adapter of this rank on a frozen weight instead of the "
                         "whole block (docs/train.md 8, rung 4): the frozen base never moves; "
                         "the rank is padded to a D-block")
    ap.add_argument("--qlora", type=int, default=0, metavar="RANK",
                    help="QLoRA: like --lora, but the frozen base streams in --base-fmt "
                         "(default nvfp4), 4.25 bits a weight instead of int8's 8.25")
    ap.add_argument("--base-fmt", default="nvfp4", choices=("int8", "int4", "fp4", "nvfp4"),
                    help="the frozen base's MX format (with --qlora; the adapters stay int8, "
                         "because the device's own quantizer QST writes int8 only)")
    ap.add_argument("--stack", type=int, default=0, metavar="N",
                    help="train a stack of N transformer layers chained end to end -- a whole "
                         "model, not one layer (docs/train.md 8): each layer's dX feeds the one "
                         "below it, and every matrix trains")
    ap.add_argument("--layer", action="store_true",
                    help="train a WHOLE transformer layer -- attention, an MLP, and every "
                         "parameter (docs/train.md 8, rung 6) -- instead of the block")
    ap.add_argument("--checkpoint", help="save the master weights here (an .npz)")
    ap.add_argument("--save-every", type=int, default=0, help="save every n steps (0: at the end)")
    ap.add_argument("--resume", help="continue from this checkpoint")
    ap.add_argument("--every", type=int, default=5, help="print the loss every n steps")
    ap.add_argument("--lora-scale", type=float, default=1.0,
                    help="the LoRA term's scale (alpha/r in the usual formulation)")
    args = ap.parse_args(argv)

    # the simulator's D=32 is the shapes the tests run; the RTL model takes the same program, so
    # it is compiled for the same configuration (the card's D=128 is a section-10 limit)
    cfg = Config(S=1, D=32, ACT_BLOCKS=64, ACT_ROWS=64, IMEM_WORDS=1 << 16)
    shapes = vocab_for(Shapes(vocab=args.vocab, hidden=args.hidden, interm=args.interm,
                              batch=args.batch, rows=args.rows), cfg)
    try:
        shapes.check(cfg)
    except ValueError as e:
        print(f"otpu-train: {e}", file=sys.stderr)
        return 2
    if shapes.vocab != args.vocab:
        print(f"otpu-train: the vocabulary padded to D: {args.vocab} -> {shapes.vocab}")

    if args.stack:
        return _run_stack(args, cfg, shapes)
    if args.layer:
        return _run_layer(args, cfg, shapes)
    if args.lora or args.qlora:
        return _run_lora(args, cfg, shapes)

    tr = Trainer(shapes=shapes, cfg=cfg, params=Params.random(shapes, args.seed),
                 optimizer=AdamW(lr=args.lr, weight_decay=args.weight_decay),
                 backend=args.backend)
    if args.resume:
        load(args.resume, tr)
        print(f"otpu-train: resumed {args.resume} at step {tr.optimizer.step}")
    x, targets = make_batch(args, shapes)

    print(f"otpu-train: {shapes.batch} rows of {shapes.hidden}, the block {shapes.hidden} -> "
          f"{shapes.interm} -> {shapes.hidden}, a {shapes.vocab}-token head")
    print(f"            {args.backend}: {len(tr.progs['forward'][0])} + "
          f"{len(tr.progs['backward'][0])} instructions a step, {tr.lay.nbytes / 1024:.1f} KiB "
          f"of DRAM")
    t0 = time.perf_counter()
    losses = []
    for i in range(args.steps):
        try:
            r = tr.step(x, targets)
        except (RuntimeError, NotImplementedError) as e:
            print(f"otpu-train: the {args.backend} backend cannot run a step here: {e}",
                  file=sys.stderr)
            return 3
        losses.append(r["loss"])
        step = tr.optimizer.step
        if args.every and (i % args.every == 0 or i == args.steps - 1):
            print(f"step {step:4d}  loss {r['loss']:.6f}"
                  + (f"  ({time.perf_counter() - t0:.2f} s)" if i == args.steps - 1 else ""))
        if args.checkpoint and args.save_every and (i + 1) % args.save_every == 0:
            save(args.checkpoint, tr, args)
    if args.checkpoint and not args.save_every:
        save(args.checkpoint, tr, args)
    if losses:
        print(f"loss {losses[0]:.4f} -> {losses[-1]:.4f} in {len(losses)} steps "
              f"({time.perf_counter() - t0:.2f} s, {args.backend})")
    return 0 if losses and losses[-1] < losses[0] else 1


if __name__ == "__main__":            # `python3 -m opentpu.train.cli`
    sys.exit(main())
