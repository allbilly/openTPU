# Repository instructions

## Current session handoff

- Read the final disposition at the top of [HANDOFF.md](HANDOFF.md) before
  continuing this bring-up. On October 22 the user abandoned the c01848
  runtime-clock effort. Do not resume its builds, qualification, packaging or
  hardware work without a new explicit instruction. Earlier plans below that
  disposition are historical.
- The c0172300 CH0/LFM regression was subsequently corrected in the combined
  JTAG/PCIe fixed-clock images c0182800 and c0182863; their recorded Mac tests
  passed. Preserve those fallback artifacts and all failed-image evidence.
  c0182301 is retired and c0172462 was rejected; neither is an active test
  candidate. The final handoff did not recheck physical card state or ownership.
  Code review and fixes do not resume hardware work or change programming scope.

## Mandatory interfaces in every bitstream

- Every new OpenTPU bitstream must include **both JTAG and PCIe runtime memory
  and control interfaces**, including baseline repairs, clock candidates,
  startup-firmware variants and experimental images.
- JTAG configuration/programming or INIT/DONE/IDCODE access does not satisfy
  this requirement. JTAG must reach DDR memory, accelerator control and the
  calibration/status registers so weights and programs can be uploaded and
  inference can run on the local JTAG-only host.
- Retain the full requested PCIe memory/control path alongside JTAG. JTAG
  runtime must work with PCIe physically absent, using the independent host
  clock and reviewed reset/abort behavior.
- Verify both interfaces in the frozen source and exact routed image. An
  image missing either interface is ineligible for packaging, programming or
  the active hardware-test plan. Do not omit an interface to simplify a repair,
  shorten a build or isolate a regression. An exception requires the user's
  explicit instruction for that exact image.
- A selected JTAG-only or Mac/Chestnut test host changes which physical tests
  can run there; it does not change the required interfaces in the image or
  introduce a local PCIe runtime gate before an authorized Mac workflow.

## Prioritize the requested hardware milestone

- Advance already authorized work without waiting for another user reminder.
  Before ending a work turn, take the next executable step for a ready task;
  a status table, recorded intention or queued design note is not execution.
- When artifact/CDC evidence collection finishes, start the exact image's final
  disposition immediately. Do not leave it marked "manual review pending"
  while working on unrelated preparation. Keep final review and packaging as
  explicit scheduled tasks with their own receipts and current owner.
- If final review finds a real defect, record the exact image, routed/source
  evidence and rejection. Continue with the prepared correction under its own
  build ID; do not leave the original indefinitely pending or waive the gate.
- Distinguish a requested design, source preparation, an admitted build job,
  a running implementation and a ready image. Never call a request record a
  queued Vivado build. State the missing prerequisite and work on it.
- Follow the user's current priority across builds, review, packaging and board
  work. Starting a background build does not complete the requested handoff.
- As soon as the priority image finishes implementation, start its required
  review while other builds continue. A completed baseline must not wait behind
  a slower experimental image in a serial review queue. Track build priority
  and review readiness separately.
- Prepare the matching host tools and programming commands during the build.
  Once the required review passes, continue through already authorized SRAM
  testing and temporary programming without asking for permission again.
- Fix a blocking reviewer or packaging problem before preparing unrelated
  variants. Report the actual blocker and next action promptly.

## Honor the selected test host and programming scope

- Complete preparation autonomously: source changes, tool/firmware preparation,
  builds, evidence collection, final review, packaging, runtime instructions and
  programming commands must not wait for another user approval. Finish all
  applicable preparation before presenting a permanent-flash approval request.
- Temporary SRAM configuration and the requested SRAM hardware checks are
  authorized by the ongoing FPGA task and require no separate approval. Acquire
  exclusive hardware ownership, preserve the permanent image, and satisfy the
  exact image's technical review gates before loading. A missing cable or
  technical blocker is not "pending user approval."
- Writing permanent configuration flash requires explicit user approval for
  the exact image and operation. Present its build ID, checksum, review/SRAM
  results and prepared command. An approval for one image does not authorize
  a different successor. Honor an existing approval for the same image without
  asking again; do not treat SRAM permission as permanent-flash permission.
- When the user authorizes an experimental image to be permanently flashed
  here and tested on the Mac with Chestnut, carry out that workflow. Do not
  invent a prerequisite for local PCIe DMA, matmul or LLM validation on a host
  that has only JTAG. Those runtime results remain pending for the Mac.
- Require the exact image's applicable offline review and integrity checks,
  verify the SRAM programming result, and verify flash programming and boot.
  Keep those outcomes separate from memory, inference and bandwidth results.
  Do not silently import an additional runtime gate from a different image's
  authorization. Honor the user's existing backup preference.
- Use the user's already granted programming scope. Record which instruction
  authorizes the image and any conditions that actually apply; do not ask for
  the same permission again or describe an internal technical check as pending
  user approval.
- A ready reviewed image with an authorized test path must not wait for a
  newer build merely because the newer image has additional interfaces.
  Prepare and execute the ready image's matching tools while builds continue.
- Stop temporary sibling-project hardware work and release JTAG promptly when
  the selected OpenTPU image is ready or the user requests the switch. Keep
  sibling-project results in that project's folder.
- When the user requests all Vortex work to stop at priority-build completion,
  coordinate with the other Codex session, stop its Vortex workers and release
  the shared FPGA promptly. Let any atomic programming operation finish before
  changing hardware ownership. Keep its evidence in the Vortex repository.

## Make review tools understand real Vivado output

- Before relying on a review queue, check its parsers against actual reports
  and saved constraints from a representative completed implementation, within
  the verification scope requested by the user.
- CDC readers must handle all row numbers, including 100 and 1000 or greater.
  Reconcile detailed Critical and Warning rows with the report summary. An
  incomplete inventory must fail review rather than silently omit crossings.
- Saved constraints can use `_xlnx_shared_iN` collection aliases. Resolve their
  definitions within the correct scope before checking endpoints and bounds.
  Reject unresolved or unsupported forms; do not execute arbitrary report text.
- A parser rejecting valid report syntax is a review-tool failure, not evidence
  that the FPGA implementation failed. Preserve the failed receipt and explain
  the distinction before rerunning the corrected review.
- Parser fixes must retain the original numerical limits, endpoint checks and
  package gates. A real timing or CDC finding still needs an explicit technical
  disposition or a new implementation containing the fix.

## Keep evidence and active jobs consistent

- Inspect the live service, process identity, invocation and latest receipt
  before declaring a job running, finished, stalled or safe to replace. Stale
  manifest fields and a child process exiting are insufficient evidence.
- Treat frozen source trees and tools hashed by active workers as immutable.
  Put corrections in a fresh preparation, preserve prior evidence and identify
  the superseded worker. Do not restart implementation for a parser-only fix.
- When replacing a worker, update the canonical progress manifest, refresh
  helper and documentation together so a later refresh cannot restore stale
  job handles. Avoid duplicate audits and unrelated process termination.
- Identify each image by build ID, bitstream hash, compute clock, DDR data rate,
  capacity, physical lane mapping, ECC mode, calibration method and interfaces.
  Do not transfer qualification between images with different configurations.

## Report readiness precisely

- Distinguish source preparation, implementation, independent review,
  packaging, SRAM execution, permanent programming and workload qualification.
  A generated `.bit` file alone is not ready to flash.
- Report build percentages as completed milestones, with the calculation or
  milestone scale stated. They are not remaining-time estimates. Report review
  and physical-test status separately, and highlight the current task.
- Include a "What changed" column in the main progress table: identify each
  variant's interfaces, clock changes, read pipeline, reset correction or
  calibration change. An image ID alone does not explain its purpose.
- When the user replaces or retires an image, remove it from the active test
  and progress lists and update the refresh helper so it cannot reappear.
  Preserve dependency files and historical evidence required by the successor.
- A successful terminal build is finished, not stopped. Check its exact
  completion receipt and review worker before offering to resume or restart it.
- For delays, state the last completed milestone, current operation, elapsed
  time and actual blocker. Give an ETA only when supported by measured runs.
- Keep programming authorization tied to the approved image and scope. Preserve
  the user's existing backup preference and do not repeat approval requests.
  Require the applicable image checks and SRAM checks before permanent flash.
- A successful load does not establish memory correctness, inference
  correctness, improved bandwidth or successful boot from permanent storage.
  State which outcome was observed and link its evidence.

## Current DDR bring-up priorities

- Prioritize usable 4 GiB spare-lane OpenTPU integration, the CH0 bandwidth
  correction, combined JTAG/PCIe access and the requested clock candidates.
  Original lane-6 diagnosis and restoration of CH0 ECC come last unless the
  user changes priorities.
- Full-capacity testing has already been demonstrated. Do not start additional
  standalone RAM soaks merely to keep the FPGA occupied. Run the authorized
  integration, numerical and performance checks that advance the milestone.
- Keep a working fallback available. Do not change clocks, lane mapping, ECC
  mode or startup firmware under an existing image identity.

## Workspace and handoffs

- Preserve unrelated staged, modified and untracked files. Scope changes to the
  requested work; do not stage, commit or push without authorization.
- Use checkout-relative paths, discovery and explicit overrides in public
  scripts and documentation. Avoid developer-specific home paths and host
  distribution assumptions.
- Deliver Mac handoffs through the GitHub repository: ordinary source files,
  scoped commits, an authorized push, and `git pull` on the Mac. Do not create,
  commit or recommend tar, tgz, zip or other archive bundles for handoffs.
- Do not commit large generated files, including FPGA bitstreams, routed
  checkpoints, generated netlists, model weights, build caches or large logs.
  Keep those artifacts local and record their build IDs, checksums and rebuild
  instructions in small version-controlled metadata files. Do not use an
  archive to hide large files inside a commit.
- For Mac inference on an already flashed card, commit the matching host
  scripts, small required calibration/configuration files, image identity and
  review metadata, and runnable instructions. Do not make transferring the
  large bitstream or Vivado build outputs a prerequisite for runtime use.
- Inspect the proposed commit's file list and sizes before committing. Preserve
  unrelated staged work. Distinguish local files, a local commit and a published
  remote commit; a Mac `git pull` cannot retrieve unpublished local work.

## Honor deferred pause requests

- If the user requests a pause after the next context compaction, save the exact
  request and a concrete resume handoff before compaction. Keep the condition
  attached to the current thread rather than applying it to unrelated work.
- On the first continuation after that compaction, finish saving the compacted
  handoff, call `update_goal(status="paused")`, report the returned state and
  stop goal work. Do not resume automatically because an older goal was active.
- Record background job handles and whether they were left running. Pausing
  agent work does not authorize killing another session's jobs or abandoning
  a programming operation halfway through; finish any active atomic hardware
  operation and leave the board in a documented state.
