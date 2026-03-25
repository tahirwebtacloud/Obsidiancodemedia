# Project Updates & Architectural Changes

This file tracks major refactoring and updates to the Obsidian LinkedIn System to provide a clear rollback path and debugging context.

## Refactoring the Mega-Prompt Pipeline (generate_assets.py)
**Date:** 2026-03-20
**Reason:** The single `generate_assets.py` script was suffering from "attention dilution". It forced one LLM call to handle creative copywriting, post scoring, image template selection, placeholder filling, and image generation routing all at once. This degraded both text quality and prompt accuracy.

### Architectural Changes:
1. **Separation of Concerns:**
   - The pipeline is split into a sequential flow: Text Post Generation -> Image Prompt Generation -> Image Asset Generation.
2. **File Renames & Creations:**
   - `execution/generate_assets.py` -> `execution/generate_text_post.py` (Handles ONLY text generation and quality scoring).
   - Created `execution/generate_image_prompt.py` (Reads the finished text post, selects an image template via tool calling, fills placeholders, applies brand colors, and calls Nano Banana Pro).
3. **Context Isolation:**
   - Brand color palettes (`color_palette.json` / user brand kits) are now ONLY passed to the Image Prompt LLM, saving thousands of tokens and improving the Text LLM's focus.
4. **Dynamic Extensibility:**
   - Image prompt libraries are now read dynamically. Adding a new library just requires dropping a JSON file into the directives folder; the LLM's tool calling automatically picks it up based on its description.

### Files Modified/Created:
- `update.md`: (Created) To track these changes.
- *Pending*: `execution/generate_text_post.py` (Renamed & Stripped down)
- *Pending*: `execution/generate_image_prompt.py` (Created)
- *Pending*: `orchestrator.py` (Updated to run sequentially)
- *Pending*: `server.py` (Updated to handle SSE logs from both scripts)