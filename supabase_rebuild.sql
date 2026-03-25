-- ============================================
-- Voice Engine + CRM Hub Rebuild — Supabase Migration
-- Run this ONCE in Supabase SQL Editor (Dashboard → SQL Editor)
--
-- WHAT THIS DOES:
--   1. Drops old crm_contacts table (will be recreated with new schema)
--   2. Drops voice_chunks data (profiles now stored differently)
--   3. Creates linkedin_profiles table (scraped profile data + Gemini summaries)
--   4. Creates conversations table (message threads keyed by Conversation ID)
--   5. Creates new crm_contacts table (LLM-analyzed CRM records)
--   6. Sets up RLS policies for all new tables
--
-- TABLES LEFT UNTOUCHED:
--   history, user_settings, user_brands, drafts, user_profiles
-- ============================================

-- ─────────────────────────────────────────────
-- 0. Extensions (idempotent)
-- ─────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector;        -- for future embedding support

-- ─────────────────────────────────────────────
-- 1. Drop old tables that are being replaced
-- ─────────────────────────────────────────────

-- Drop old CRM contacts (will be recreated with new schema)
DROP TABLE IF EXISTS crm_contacts CASCADE;

-- Truncate voice_chunks (keep table structure for RAG, but clear data)
TRUNCATE TABLE voice_chunks;

-- ─────────────────────────────────────────────
-- 2. linkedin_profiles — scraped profile data
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS linkedin_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,

    -- LinkedIn identity
    linkedin_url TEXT NOT NULL DEFAULT '',
    first_name TEXT DEFAULT '',
    last_name TEXT DEFAULT '',
    title TEXT DEFAULT '',
    company TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    location TEXT DEFAULT '',
    headline TEXT DEFAULT '',
    profile_pic_url TEXT DEFAULT '',

    -- Raw Apify scrape response (full JSON)
    raw_json JSONB DEFAULT '{}'::jsonb,

    -- Gemini structured summary
    -- Schema: {executive_summary, key_points[], experiences[], action_items[]}
    summary JSONB DEFAULT '{}'::jsonb,

    -- Is this the authenticated user's own profile?
    is_owner BOOLEAN DEFAULT FALSE,

    -- Years of experience (extracted from profile)
    years_of_experience INT DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Unique constraint: one profile per URL per user
CREATE UNIQUE INDEX IF NOT EXISTS idx_linkedin_profiles_user_url
    ON linkedin_profiles (user_id, linkedin_url);

-- Fast lookup by user
CREATE INDEX IF NOT EXISTS idx_linkedin_profiles_user_id
    ON linkedin_profiles (user_id);

-- Fast lookup for owner profile
CREATE INDEX IF NOT EXISTS idx_linkedin_profiles_owner
    ON linkedin_profiles (user_id, is_owner) WHERE is_owner = TRUE;

-- RLS
ALTER TABLE linkedin_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read own profiles" ON linkedin_profiles;
DROP POLICY IF EXISTS "Users can insert own profiles" ON linkedin_profiles;
DROP POLICY IF EXISTS "Users can update own profiles" ON linkedin_profiles;
DROP POLICY IF EXISTS "Users can delete own profiles" ON linkedin_profiles;

CREATE POLICY "Users can read own profiles" ON linkedin_profiles
    FOR SELECT TO authenticated
    USING ((SELECT auth.uid())::text = user_id);

CREATE POLICY "Users can insert own profiles" ON linkedin_profiles
    FOR INSERT TO authenticated
    WITH CHECK ((SELECT auth.uid())::text = user_id);

CREATE POLICY "Users can update own profiles" ON linkedin_profiles
    FOR UPDATE TO authenticated
    USING ((SELECT auth.uid())::text = user_id)
    WITH CHECK ((SELECT auth.uid())::text = user_id);

CREATE POLICY "Users can delete own profiles" ON linkedin_profiles
    FOR DELETE TO authenticated
    USING ((SELECT auth.uid())::text = user_id);


-- ─────────────────────────────────────────────
-- 3. conversations — message threads
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,

    -- LinkedIn's original Conversation ID from messages.csv
    conversation_id TEXT NOT NULL DEFAULT '',

    -- FK to the OTHER person's profile (not the user)
    contact_profile_id UUID REFERENCES linkedin_profiles(id) ON DELETE SET NULL,

    -- Full thread as JSONB array:
    -- [{from, from_url, to, to_url, date, content, is_draft}, ...]
    thread JSONB DEFAULT '[]'::jsonb,

    -- Computed stats
    message_count INT DEFAULT 0,
    first_message_date TIMESTAMPTZ,
    last_message_date TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Unique constraint: one conversation per Conversation ID per user
CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_user_convid
    ON conversations (user_id, conversation_id);

-- Fast lookup by user
CREATE INDEX IF NOT EXISTS idx_conversations_user_id
    ON conversations (user_id);

-- Fast lookup by contact profile
CREATE INDEX IF NOT EXISTS idx_conversations_contact
    ON conversations (contact_profile_id);

-- RLS
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read own conversations" ON conversations;
DROP POLICY IF EXISTS "Users can insert own conversations" ON conversations;
DROP POLICY IF EXISTS "Users can update own conversations" ON conversations;
DROP POLICY IF EXISTS "Users can delete own conversations" ON conversations;

CREATE POLICY "Users can read own conversations" ON conversations
    FOR SELECT TO authenticated
    USING ((SELECT auth.uid())::text = user_id);

CREATE POLICY "Users can insert own conversations" ON conversations
    FOR INSERT TO authenticated
    WITH CHECK ((SELECT auth.uid())::text = user_id);

CREATE POLICY "Users can update own conversations" ON conversations
    FOR UPDATE TO authenticated
    USING ((SELECT auth.uid())::text = user_id)
    WITH CHECK ((SELECT auth.uid())::text = user_id);

CREATE POLICY "Users can delete own conversations" ON conversations
    FOR DELETE TO authenticated
    USING ((SELECT auth.uid())::text = user_id);


-- ─────────────────────────────────────────────
-- 4. crm_contacts — LLM-analyzed CRM records
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS crm_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,

    -- FK references
    profile_id UUID REFERENCES linkedin_profiles(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,

    -- Person info (denormalized from profile for fast reads)
    first_name TEXT DEFAULT '',
    last_name TEXT DEFAULT '',
    title TEXT DEFAULT '',
    company TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    years_of_experience INT DEFAULT 0,

    -- LLM analysis results
    intent_points JSONB DEFAULT '[]'::jsonb,   -- 3 bullet points
    score INT DEFAULT 0,                        -- 0-100 likelihood to buy
    tag TEXT DEFAULT 'prospect',                -- warm|cold|hot|ghosted|referrer|prospect|client

    -- Draft message
    draft_message TEXT DEFAULT '',
    draft_is_sent BOOLEAN DEFAULT FALSE,        -- TRUE = excluded from analysis

    -- Connection metadata
    connected_on TEXT DEFAULT '',
    source TEXT DEFAULT 'message',              -- 'message' or 'connection'
    linkedin_url TEXT DEFAULT '',

    -- Original LinkedIn Conversation ID (for easy cross-reference)
    linkedin_conversation_id TEXT DEFAULT '',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for filtering/sorting
CREATE INDEX IF NOT EXISTS idx_crm_contacts_user_tag
    ON crm_contacts (user_id, tag);

CREATE INDEX IF NOT EXISTS idx_crm_contacts_user_score
    ON crm_contacts (user_id, score DESC);

CREATE INDEX IF NOT EXISTS idx_crm_contacts_user_id
    ON crm_contacts (user_id);

CREATE INDEX IF NOT EXISTS idx_crm_contacts_profile
    ON crm_contacts (profile_id);

CREATE INDEX IF NOT EXISTS idx_crm_contacts_conversation
    ON crm_contacts (conversation_id);

-- Unique: one CRM contact per profile per user
CREATE UNIQUE INDEX IF NOT EXISTS idx_crm_contacts_user_profile
    ON crm_contacts (user_id, profile_id);

-- RLS
ALTER TABLE crm_contacts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read own crm contacts" ON crm_contacts;
DROP POLICY IF EXISTS "Users can insert own crm contacts" ON crm_contacts;
DROP POLICY IF EXISTS "Users can update own crm contacts" ON crm_contacts;
DROP POLICY IF EXISTS "Users can delete own crm contacts" ON crm_contacts;

CREATE POLICY "Users can read own crm contacts" ON crm_contacts
    FOR SELECT TO authenticated
    USING ((SELECT auth.uid())::text = user_id);

CREATE POLICY "Users can insert own crm contacts" ON crm_contacts
    FOR INSERT TO authenticated
    WITH CHECK ((SELECT auth.uid())::text = user_id);

CREATE POLICY "Users can update own crm contacts" ON crm_contacts
    FOR UPDATE TO authenticated
    USING ((SELECT auth.uid())::text = user_id)
    WITH CHECK ((SELECT auth.uid())::text = user_id);

CREATE POLICY "Users can delete own crm contacts" ON crm_contacts
    FOR DELETE TO authenticated
    USING ((SELECT auth.uid())::text = user_id);


-- ─────────────────────────────────────────────
-- 5. Helper function: update updated_at on row change
-- ─────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Auto-update triggers
DROP TRIGGER IF EXISTS trg_linkedin_profiles_updated ON linkedin_profiles;
CREATE TRIGGER trg_linkedin_profiles_updated
    BEFORE UPDATE ON linkedin_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_conversations_updated ON conversations;
CREATE TRIGGER trg_conversations_updated
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_crm_contacts_updated ON crm_contacts;
CREATE TRIGGER trg_crm_contacts_updated
    BEFORE UPDATE ON crm_contacts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ─────────────────────────────────────────────
-- 6. Wipe user processing state (so Voice Engine starts fresh)
-- ─────────────────────────────────────────────
-- Reset processing flags in user_profiles so the UI shows the upload form
-- Wrapped in DO block: skips safely if user_profiles table doesn't exist yet
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'user_profiles'
    ) THEN
        UPDATE user_profiles
        SET profile_data = profile_data
            - 'persona'
            - 'linkedin_imported'
            - 'linkedin_processing_status'
            - 'crm_contacts_count'
            - 'voice_chunks_count'
            - 'processing_phase';
    END IF;
END
$$;


-- ─────────────────────────────────────────────
-- DONE. Tables created:
--   linkedin_profiles  — scraped profiles with Gemini summaries
--   conversations      — message threads keyed by Conversation ID
--   crm_contacts       — LLM-analyzed CRM records with scoring
--
-- All tables have:
--   ✓ RLS enabled with tenant-isolated policies
--   ✓ Auto-updating updated_at triggers
--   ✓ Unique constraints to prevent duplicates
--   ✓ Indexes for fast filtering/sorting
-- ─────────────────────────────────────────────
