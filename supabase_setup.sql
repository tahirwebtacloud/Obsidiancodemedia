-- ============================================
-- Supabase Schema for LinkedIn Post Generator
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor)
-- ============================================

-- 1. History table (stores all generation runs per user)
CREATE TABLE IF NOT EXISTS history (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    timestamp BIGINT NOT NULL,
    type TEXT DEFAULT 'generate',
    status TEXT DEFAULT 'success',
    input_summary TEXT,
    topic TEXT,
    purpose TEXT,
    style TEXT,
    params JSONB DEFAULT '{}',
    caption TEXT DEFAULT '',
    full_caption TEXT DEFAULT '',
    asset_url TEXT DEFAULT '',
    final_image_prompt TEXT DEFAULT '',
    full_results JSONB,
    error_message TEXT,
    costs JSONB DEFAULT '[]',
    total_cost FLOAT DEFAULT 0.0,
    duration_ms INT DEFAULT 0,
    approved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast per-user queries ordered by timestamp
CREATE INDEX IF NOT EXISTS idx_history_user_timestamp ON history (user_id, timestamp DESC);

-- 2. User settings table
CREATE TABLE IF NOT EXISTS user_settings (
    user_id TEXT PRIMARY KEY,
    tracked_profile_url TEXT DEFAULT '',
    settings JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. User brand table
CREATE TABLE IF NOT EXISTS user_brands (
    user_id TEXT PRIMARY KEY,
    brand_name TEXT DEFAULT '',
    primary_color TEXT DEFAULT '#F9C74F',
    secondary_color TEXT DEFAULT '#0E0E0E',
    accent_color TEXT DEFAULT '#FCF0D5',
    font_family TEXT DEFAULT 'Inter',
    logo_url TEXT DEFAULT '',
    visual_style TEXT DEFAULT '',
    tone_of_voice TEXT DEFAULT '',
    tagline TEXT DEFAULT '',
    description TEXT DEFAULT '',
    products_services JSONB DEFAULT '[]'::jsonb,
    ui_theme JSONB DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. User profiles table (persona, LinkedIn processing status, counts)
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,
    profile_data JSONB DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read own profile" ON user_profiles;
DROP POLICY IF EXISTS "Users can upsert own profile" ON user_profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON user_profiles;

CREATE POLICY "Users can read own profile" ON user_profiles FOR SELECT TO authenticated
USING ((SELECT auth.uid())::text = user_id);
CREATE POLICY "Users can upsert own profile" ON user_profiles FOR INSERT TO authenticated
WITH CHECK ((SELECT auth.uid())::text = user_id);
CREATE POLICY "Users can update own profile" ON user_profiles FOR UPDATE TO authenticated
USING ((SELECT auth.uid())::text = user_id)
WITH CHECK ((SELECT auth.uid())::text = user_id);

-- 5. Voice chunks table (RAG storage)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS voice_chunks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    source_type TEXT DEFAULT 'custom',
    metadata JSONB DEFAULT '{}'::jsonb,
    embedding VECTOR,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_voice_chunks_user_created ON voice_chunks (user_id, created_at DESC);

-- 5. CRM contacts table (Phase 1-4 + History)
-- Base table (if doesn't exist)
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    conversation_id TEXT,
    linkedin_url TEXT DEFAULT '',
    full_name TEXT DEFAULT '',
    company TEXT DEFAULT '',
    position TEXT DEFAULT '',
    behavioral_tag TEXT DEFAULT 'cold_pitch',
    intent_summary TEXT DEFAULT '',
    warmth_score INT DEFAULT 0,
    recommended_action TEXT DEFAULT '',
    last_message_date TEXT DEFAULT '',
    message_count INT DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add Phase 1-4 columns if they don't exist (idempotent migration)
ALTER TABLE crm_contacts
  ADD COLUMN IF NOT EXISTS title_source TEXT DEFAULT 'unknown',
  ADD COLUMN IF NOT EXISTS title_confidence TEXT DEFAULT 'low',
  ADD COLUMN IF NOT EXISTS reason_summary TEXT DEFAULT '',
  ADD COLUMN IF NOT EXISTS evidence JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS buyer_stage TEXT DEFAULT '',
  ADD COLUMN IF NOT EXISTS urgency_score INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS fit_score INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS cold_outreacher_flag BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS confidence TEXT DEFAULT 'medium',
  ADD COLUMN IF NOT EXISTS inferred_title TEXT DEFAULT '',
  ADD COLUMN IF NOT EXISTS inferred_company TEXT DEFAULT '',
  ADD COLUMN IF NOT EXISTS inferred_title_confidence TEXT DEFAULT 'low',
  ADD COLUMN IF NOT EXISTS draft TEXT DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_crm_contacts_user_warmth ON crm_contacts (user_id, warmth_score DESC);
CREATE INDEX IF NOT EXISTS idx_crm_contacts_user_tag ON crm_contacts (user_id, behavioral_tag);
CREATE INDEX IF NOT EXISTS idx_crm_contacts_user_buyer_stage ON crm_contacts (user_id, buyer_stage);

-- 6. RPC function for vector similarity search
CREATE OR REPLACE FUNCTION public.match_voice_chunks(
    query_embedding VECTOR,
    match_threshold FLOAT,
    match_count INT,
    user_id_filter TEXT
)
RETURNS TABLE (
    id BIGINT,
    user_id TEXT,
    content TEXT,
    source_type TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, extensions, pg_temp
AS $$
    SELECT
        vc.id,
        vc.user_id,
        vc.content,
        vc.source_type,
        vc.metadata,
        1 - (vc.embedding <=> query_embedding) AS similarity
    FROM public.voice_chunks vc
    WHERE vc.user_id = user_id_filter
      AND 1 - (vc.embedding <=> query_embedding) > match_threshold
    ORDER BY vc.embedding <=> query_embedding
    LIMIT match_count;
$$;

-- 7. Enable Row Level Security
ALTER TABLE history ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_brands ENABLE ROW LEVEL SECURITY;
ALTER TABLE voice_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE crm_contacts ENABLE ROW LEVEL SECURITY;

-- 8. RLS Policies (idempotent + tenant isolated + auth-optimized)
-- For service-role key access (backend), RLS is bypassed automatically.

-- history
DROP POLICY IF EXISTS "Users can read own history" ON history;
DROP POLICY IF EXISTS "Users can insert own history" ON history;
DROP POLICY IF EXISTS "Users can update own history" ON history;

CREATE POLICY "Users can read own history" ON history FOR SELECT TO authenticated
USING ((SELECT auth.uid())::text = user_id);
CREATE POLICY "Users can insert own history" ON history FOR INSERT TO authenticated
WITH CHECK ((SELECT auth.uid())::text = user_id);
CREATE POLICY "Users can update own history" ON history FOR UPDATE TO authenticated
USING ((SELECT auth.uid())::text = user_id)
WITH CHECK ((SELECT auth.uid())::text = user_id);

-- user_settings
DROP POLICY IF EXISTS "Users can read own settings" ON user_settings;
DROP POLICY IF EXISTS "Users can upsert own settings" ON user_settings;
DROP POLICY IF EXISTS "Users can update own settings" ON user_settings;

CREATE POLICY "Users can read own settings" ON user_settings FOR SELECT TO authenticated
USING ((SELECT auth.uid())::text = user_id);
CREATE POLICY "Users can upsert own settings" ON user_settings FOR INSERT TO authenticated
WITH CHECK ((SELECT auth.uid())::text = user_id);
CREATE POLICY "Users can update own settings" ON user_settings FOR UPDATE TO authenticated
USING ((SELECT auth.uid())::text = user_id)
WITH CHECK ((SELECT auth.uid())::text = user_id);

-- crm_contacts
DROP POLICY IF EXISTS "Users can read own crm contacts" ON crm_contacts;
DROP POLICY IF EXISTS "Users can insert own crm contacts" ON crm_contacts;
DROP POLICY IF EXISTS "Users can update own crm contacts" ON crm_contacts;
DROP POLICY IF EXISTS "Users can delete own crm contacts" ON crm_contacts;

CREATE POLICY "Users can read own crm contacts" ON crm_contacts FOR SELECT TO authenticated
USING ((SELECT auth.uid())::text = user_id);
CREATE POLICY "Users can insert own crm contacts" ON crm_contacts FOR INSERT TO authenticated
WITH CHECK ((SELECT auth.uid())::text = user_id);
CREATE POLICY "Users can update own crm contacts" ON crm_contacts FOR UPDATE TO authenticated
USING ((SELECT auth.uid())::text = user_id)
WITH CHECK ((SELECT auth.uid())::text = user_id);
CREATE POLICY "Users can delete own crm contacts" ON crm_contacts FOR DELETE TO authenticated
USING ((SELECT auth.uid())::text = user_id);

-- ============================================
-- 5. Drafts table (stores saved post drafts for editing, scheduling, publishing)
-- ============================================
CREATE TABLE IF NOT EXISTS drafts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    caption TEXT DEFAULT '',
    asset_url TEXT DEFAULT '',
    final_image_prompt TEXT DEFAULT '',
    type TEXT DEFAULT 'text',
    purpose TEXT DEFAULT '',
    topic TEXT DEFAULT '',
    status TEXT DEFAULT 'draft',
    scheduled_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    blotato_post_id TEXT,
    source_data JSONB DEFAULT '{}',
    carousel_layout JSONB,
    quality_score INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast per-user draft queries
CREATE INDEX IF NOT EXISTS idx_drafts_user_status ON drafts (user_id, status);
CREATE INDEX IF NOT EXISTS idx_drafts_user_created ON drafts (user_id, created_at DESC);

ALTER TABLE drafts ENABLE ROW LEVEL SECURITY;

-- drafts
DROP POLICY IF EXISTS "Users can read own drafts" ON drafts;
DROP POLICY IF EXISTS "Users can insert own drafts" ON drafts;
DROP POLICY IF EXISTS "Users can update own drafts" ON drafts;
DROP POLICY IF EXISTS "Users can delete own drafts" ON drafts;

CREATE POLICY "Users can read own drafts" ON drafts FOR SELECT TO authenticated
USING ((SELECT auth.uid())::text = user_id);
CREATE POLICY "Users can insert own drafts" ON drafts FOR INSERT TO authenticated
WITH CHECK ((SELECT auth.uid())::text = user_id);
CREATE POLICY "Users can update own drafts" ON drafts FOR UPDATE TO authenticated
USING ((SELECT auth.uid())::text = user_id)
WITH CHECK ((SELECT auth.uid())::text = user_id);
CREATE POLICY "Users can delete own drafts" ON drafts FOR DELETE TO authenticated
USING ((SELECT auth.uid())::text = user_id);

-- user_brands
DROP POLICY IF EXISTS "Users can read own brand" ON user_brands;
DROP POLICY IF EXISTS "Users can upsert own brand" ON user_brands;
DROP POLICY IF EXISTS "Users can update own brand" ON user_brands;

CREATE POLICY "Users can read own brand" ON user_brands FOR SELECT TO authenticated
USING ((SELECT auth.uid())::text = user_id);
CREATE POLICY "Users can upsert own brand" ON user_brands FOR INSERT TO authenticated
WITH CHECK ((SELECT auth.uid())::text = user_id);
CREATE POLICY "Users can update own brand" ON user_brands FOR UPDATE TO authenticated
USING ((SELECT auth.uid())::text = user_id)
WITH CHECK ((SELECT auth.uid())::text = user_id);

-- voice_chunks
DROP POLICY IF EXISTS "Users can read own voice chunks" ON voice_chunks;
DROP POLICY IF EXISTS "Users can insert own voice chunks" ON voice_chunks;
DROP POLICY IF EXISTS "Users can update own voice chunks" ON voice_chunks;
DROP POLICY IF EXISTS "Users can delete own voice chunks" ON voice_chunks;

CREATE POLICY "Users can read own voice chunks" ON voice_chunks FOR SELECT TO authenticated
USING ((SELECT auth.uid())::text = user_id);
CREATE POLICY "Users can insert own voice chunks" ON voice_chunks FOR INSERT TO authenticated
WITH CHECK ((SELECT auth.uid())::text = user_id);
CREATE POLICY "Users can update own voice chunks" ON voice_chunks FOR UPDATE TO authenticated
USING ((SELECT auth.uid())::text = user_id)
WITH CHECK ((SELECT auth.uid())::text = user_id);
CREATE POLICY "Users can delete own voice chunks" ON voice_chunks FOR DELETE TO authenticated
USING ((SELECT auth.uid())::text = user_id);

-- ============================================
-- 9. Supabase Storage — generated-assets bucket
-- ============================================
-- Create the public bucket for generated images/carousels/assets
-- This MUST exist for image persistence to work across container restarts
INSERT INTO storage.buckets (id, name, public, file_size_limit)
VALUES ('generated-assets', 'generated-assets', true, 10485760)
ON CONFLICT (id) DO NOTHING;

-- Allow anyone to READ assets (public bucket)
DROP POLICY IF EXISTS "Public read access for generated-assets" ON storage.objects;
CREATE POLICY "Public read access for generated-assets" ON storage.objects
    FOR SELECT USING (bucket_id = 'generated-assets');

-- Allow authenticated users and service role to INSERT assets
DROP POLICY IF EXISTS "Authenticated upload to generated-assets" ON storage.objects;
CREATE POLICY "Authenticated upload to generated-assets" ON storage.objects
    FOR INSERT WITH CHECK (bucket_id = 'generated-assets');

-- Allow UPDATE (upsert) for generated-assets
DROP POLICY IF EXISTS "Authenticated update in generated-assets" ON storage.objects;
CREATE POLICY "Authenticated update in generated-assets" ON storage.objects
    FOR UPDATE USING (bucket_id = 'generated-assets');
