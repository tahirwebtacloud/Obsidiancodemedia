# SOP: Post Design and Prompt Generation

## Goal
Transform analysis insights into creative assets and captions for the LinkedIn post.

## Inputs
- `analysis_results`: Structural patterns and top posts from `.tmp/analysis.json`.
- `post_type`: Chosen format (e.g., Image, Video, Article, Poll).

## Steps
1. **Develop Hook**: Write a compelling first line based on successful patterns.
2. **Draft Caption**: Expand the hook into a full caption with relevant hashtags using the `storytelling_caption.md` SOP.
3. **Generate Image Prompt (if Image)**: Create a detailed JSON prompt for **Nano Banana** using the `image_prompt_design.md` SOP.
4. **Generate Video Prompt (if Video)**: Create a detailed prompt for **Sora 2** or **Veo 3**.
5. **Draft Article (if Article)**: Write a long-form article based on the research.
6. **Package**: Combine captions and prompts for the execution layer.

## Outputs
- `final_plan`: Prompts and text content in `.tmp/final_plan.json`.

## Execution Tool
- `execution/generate_assets.py`
