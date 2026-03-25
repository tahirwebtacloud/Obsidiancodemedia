---
status: resolved
trigger: "text-generation-freeze"
created: 2026-03-23T00:00:00Z
updated: 2026-03-23T00:00:00Z
---

## Current Focus
hypothesis: `sys.stdout` re-wrapping with `io.TextIOWrapper` caused block buffering, disabling `python -u` and making the process appear to hang.
test: modify the wrapper to include `line_buffering=True, write_through=True`
expecting: streams to immediately flush instead of waiting for the script to finish
next_action: None, resolved.

## Symptoms
expected: It should proceed to call the Gemini API and output the text stream
actual: It hangs indefinitely after printing "FAST PATH: Static analysis written"
errors: No errors
reproduction: Run standard generation from the UI or CLI
started: Started recently

## Eliminated
- It was not an infinite loop. The process was running and doing LLM calls, but the output buffer was not flushing.

## Evidence
- `orchestrator.py` passes `-u` to python.
- However, `execution/generate_text_post.py` (and others) forcefully re-wrap `sys.stdout` and `sys.stderr` using `io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")`.
- `io.TextIOWrapper` defaults to block buffering when not writing to an interactive terminal, overriding `-u`.
- Jina search did not re-wrap, so its logs streamed perfectly.

## Resolution
root_cause: `io.TextIOWrapper` re-wrapped stdout without `line_buffering=True, write_through=True`, which broke `python -u`'s unbuffered stream in `orchestrator.py`, causing the UI to see no logs during long LLM calls and appear hung indefinitely.
fix: Added `line_buffering=True, write_through=True` to all `io.TextIOWrapper` instantiations in `orchestrator.py` and `execution/*.py`.
verification: Verified manually by running the reproducer command and seeing the logs flush immediately instead of hanging.
files_changed: 
- orchestrator.py
- execution/generate_text_post.py
- execution/generate_image_prompt.py
- execution/regenerate_image.py
- execution/generate_carousel.py
- execution/regenerate_caption.py
