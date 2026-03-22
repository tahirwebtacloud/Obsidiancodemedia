import { z } from "zod";

export const GeneratePostSchema = z.object({
  action: z.string().default("develop_post"),
  topic: z.string().default(""),
  auto_topic: z.boolean().default(false),
  include_lead_magnet: z.boolean().default(false),
  source: z.string().default("topic"),
  type: z.string().default("text"),
  purpose: z.string().default("educational"),
  visual_style: z.string().default("minimal"),
  aspect_ratio: z.string().default("16:9"),
  visual_aspect: z.string().default("none"),
  style_type: z.string().nullable().optional(),
  color_palette: z.string().default("brand_kit"),
  url: z.string().nullable().optional(),
  reference_image: z.string().nullable().optional(),
  deep_research: z.boolean().default(false),
  time_range: z.string().nullable().optional(),
  brand_kit_palette: z.record(z.string(), z.any()).nullable().optional(),
  source_content: z.string().nullable().optional(),
  source_post_type: z.string().nullable().optional(),
  source_image_urls: z.array(z.string()).nullable().optional(),
});
