# Provenance of the imported tiny-tpu baseline (ladder step 0)

The `src/`, `test/`, `Makefile`, `README.md` and Python project files at the
root of this branch are an import of the tiny-tpu project:

- Upstream: https://github.com/tiny-tpu-v2/tiny-tpu
- Local source tree: `/home/fedora/tiny-tpu`
- Imported commit family: `main` @ `5c55aaec94818a0a42b6137def5bfb86d77e846e`
  ("Document portable YPCB workflows and checkpoint requirements")
- The import is the *working-tree snapshot* of that checkout, because the
  following local fixes were uncommitted and are needed for the baseline test
  suite to be green (see `PROVENANCE.md` for the file hashes):
  - `Makefile`: cocotb 2.x / portable cocotb-config handling, corpora
    variables, results.xml checking;
  - `test/test_tpu.py`: `wait_vpu_output_done()` (dual-lane wait fix);
  - `src/gradient_descent.sv`, `src/unified_buffer.sv`: two `default:` cases
    that remove inferred latches.
- The upstream repo ships **no LICENSE file and no SPDX/copyright headers** in
  its RTL or tests. This import was requested explicitly for the ladder work.
  A licensing decision for redistributing this code inside the Apache-2.0
  openTPU repository is still required from the repository owner; until then
  this directory is a reference/intermediate artifact of the ladder branch and
  is removed when the branch converges on the production openTPU tree.
- Authors recorded by the upstream git history include (alphabetically)
  Evan Lin, Kenny Guo, Surya Sure, Xander Chin and other contributors; the
  `fixedpoint.sv` library has no author/license header in the upstream repo.
