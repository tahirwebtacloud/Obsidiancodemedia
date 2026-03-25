# Supabase Database Migration Guide

> **Purpose:** Update your Supabase database to support CRM Pipeline Phases 1-4 + History Logging

---

## What Changed

### CRM Contacts Table (`crm_contacts`)

**Added Fields for Phase 1-4:**

| Field | Type | Purpose | Phase |
|-------|------|---------|-------|
| `title_source` | TEXT | Where title came from (connection/llm/apify) | 1 |
| `title_confidence` | TEXT | low/medium/high confidence | 1 |
| `reason_summary` | TEXT | LLM-extracted intent summary | 2 |
| `evidence` | JSONB | Array of supporting evidence | 2 |
| `buyer_stage` | TEXT | Lead stage (awareness/consideration/decision) | 2 |
| `urgency_score` | INT | 0-100 urgency rating | 2 |
| `fit_score` | INT | 0-100 fit rating | 2 |
| `cold_outreacher_flag` | BOOLEAN | Spam/cold outreach detection | 2 |
| `confidence` | TEXT | low/medium/high classification confidence | 2 |
| `inferred_title` | TEXT | LLM-inferred job title | 2 |
| `inferred_company` | TEXT | LLM-inferred company | 2 |
| `inferred_title_confidence` | TEXT | Confidence for inferred title | 2 |
| `draft` | TEXT | Per-row message draft | 4 |

**Added Index:**
- `idx_crm_contacts_user_buyer_stage` — for filtering by buyer stage

---

## Migration Steps

### Step 1: Backup Your Database (Recommended)

```sql
-- In Supabase Dashboard → Database → Backups
-- Create a new backup before running migration
```

### Step 2: Run the Updated Schema

1. Open **Supabase Dashboard** → **SQL Editor**
2. Copy the full contents of `supabase_setup.sql`
3. Paste into SQL Editor
4. Click **Run** (or press Ctrl+Enter)

**The SQL is idempotent** — you can run it multiple times safely. It uses:
- `CREATE TABLE IF NOT EXISTS` — won't fail if tables exist
- `CREATE INDEX IF NOT EXISTS` — won't fail if indexes exist
- `DROP POLICY IF EXISTS` — won't fail if policies don't exist
- `CREATE OR REPLACE FUNCTION` — updates function if exists

### Step 3: Verify Migration

Run this query to verify all new columns exist:

```sql
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'crm_contacts'
  AND table_schema = 'public'
ORDER BY ordinal_position;
```

**Expected Output:** Should include all fields listed above (30+ columns).

### Step 4: Test CRM Features

1. Upload a LinkedIn ZIP export via `/api/upload-linkedin`
2. Check `/api/crm/contacts` — should return contacts with new fields populated
3. Generate a message via `/api/crm/generate-message` — should save to `draft` field
4. Check `/api/history` — should show `crm_ingestion`, `crm_classification`, `crm_message_generation` entries

---

## What Happens to Existing Data?

- **Existing contacts** will have `NULL` values for new columns (safe default)
- **New contacts** will have all fields populated during ingestion
- **No data loss** — migration only adds columns, doesn't delete or modify existing data

---

## Troubleshooting

### Error: "column already exists"

**Cause:** Column was added manually before.

**Solution:** The SQL uses `CREATE TABLE IF NOT EXISTS`, but if you manually added columns, you may need to:
1. Drop and recreate the table (data loss — backup first!)
2. Or manually add missing columns only

```sql
-- Add only missing columns (safe, no data loss)
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
```

### Error: "relation already exists"

**Cause:** Table already exists (expected).

**Solution:** The SQL uses `CREATE TABLE IF NOT EXISTS`, so this should not occur. If it does, check for typos in table names.

### Error: "permission denied"

**Cause:** You're not using the service role key or don't have admin permissions.

**Solution:**
1. Use the **service role key** (not anon key) from Supabase Dashboard → Project Settings → API
2. Ensure you have admin access to the project

---

## Post-Migration Checklist

- [ ] Backup created
- [ ] SQL executed successfully
- [ ] All new columns visible in `crm_contacts` table
- [ ] Index `idx_crm_contacts_user_buyer_stage` created
- [ ] RLS policies still active for `crm_contacts`
- [ ] Test LinkedIn ZIP upload
- [ ] Test CRM contact retrieval
- [ ] Test message generation and draft persistence
- [ ] Test history logging (H1, H2, H3)

---

## Rollback (If Needed)

If migration causes issues, you can rollback by:

1. Restore from the backup you created in Step 1
2. Or manually drop the new columns:

```sql
ALTER TABLE crm_contacts
  DROP COLUMN IF EXISTS title_source,
  DROP COLUMN IF EXISTS title_confidence,
  DROP COLUMN IF EXISTS reason_summary,
  DROP COLUMN IF EXISTS evidence,
  DROP COLUMN IF EXISTS buyer_stage,
  DROP COLUMN IF EXISTS urgency_score,
  DROP COLUMN IF EXISTS fit_score,
  DROP COLUMN IF EXISTS cold_outreacher_flag,
  DROP COLUMN IF EXISTS confidence,
  DROP COLUMN IF EXISTS inferred_title,
  DROP COLUMN IF EXISTS inferred_company,
  DROP COLUMN IF EXISTS inferred_title_confidence,
  DROP COLUMN IF EXISTS draft;

DROP INDEX IF EXISTS idx_crm_contacts_user_buyer_stage;
```

---

## Support

If you encounter issues:
1. Check Supabase Dashboard → Database → Logs for error messages
2. Verify your `.env` file has correct Supabase credentials
3. Ensure you're using the service role key, not anon key
