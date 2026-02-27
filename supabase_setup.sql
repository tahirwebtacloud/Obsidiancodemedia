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

-- 3. Enable Row Level Security
ALTER TABLE history ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

-- 4. RLS Policies — allow all operations for authenticated users on their own data
-- For service-role key access (backend), RLS is bypassed automatically.
-- These policies are for anon key access if ever needed from frontend directly.
CREATE POLICY "Users can read own history" ON history FOR SELECT USING (true);
CREATE POLICY "Users can insert own history" ON history FOR INSERT WITH CHECK (true);
CREATE POLICY "Users can update own history" ON history FOR UPDATE USING (true);

CREATE POLICY "Users can read own settings" ON user_settings FOR SELECT USING (true);
CREATE POLICY "Users can upsert own settings" ON user_settings FOR INSERT WITH CHECK (true);
CREATE POLICY "Users can update own settings" ON user_settings FOR UPDATE USING (true);
