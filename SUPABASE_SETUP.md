# Supabase Setup Guide

This app uses **Supabase** for user authentication, history persistence, and settings storage.

## Prerequisites

1. A Supabase account at [supabase.com](https://supabase.com)
2. A Supabase project created

## Setup Steps

### 1. Get Your Supabase Credentials

Go to your Supabase project dashboard → **Project Settings** → **API**:

- **Project URL**: `https://your-project-ref.supabase.co`
- **anon/public key**: Used by frontend (already in `frontend/auth.js`)
- **service_role key**: Used by backend (add to `.env`)

### 2. Create Database Tables

Run the SQL in `supabase_setup.sql` via **Supabase Dashboard → SQL Editor**:

```sql
-- Creates 'history' and 'user_settings' tables with proper indexes and RLS policies
-- See supabase_setup.sql for full schema
```

Or copy-paste from `supabase_setup.sql` and click **Run**.

### 3. Enable Google Authentication

Go to **Authentication → Providers → Google**:

1. Toggle **Enable Sign in with Google**
2. Choose either:
   - **Use Supabase's Google OAuth** (easiest — no config needed)
   - **Use your own Google OAuth credentials** (if you have a Google Cloud project)

### 4. Update `.env`

Add your Supabase credentials:

```bash
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_secret_key_here
```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs `supabase>=2.0.0` (the Python SDK).

### 6. Start the Server

```bash
python server.py
```

Navigate to `http://localhost:9999` and sign in with Google.

## Data Isolation

All user data is isolated by `user_id`:

- **History**: Each generation run is saved to Supabase `history` table with `user_id` column
- **Settings**: Profile URL and preferences stored in `user_settings` table per user
- **Surveillance**: Scraped LinkedIn data stored in `.tmp/surveillance_data_{uid}.json`
- **Leads**: CRM scan results stored in `.tmp/leads_data_{uid}.json`

## Local Fallbacks

If Supabase is unreachable, the app falls back to local JSON files:

- `.tmp/history_{uid}.json` — per-user history cache
- `.local_settings.json` — per-user settings cache
- `history.json` — legacy shared history (for uid="default" only)

## Troubleshooting

**Login doesn't work:**
- Check that Google Auth provider is enabled in Supabase Dashboard
- Verify `SUPABASE_URL` and anon key in `frontend/auth.js` match your project

**History not saving:**
- Check that `supabase_setup.sql` was run successfully
- Verify `SUPABASE_SERVICE_ROLE_KEY` in `.env` is correct
- Check server logs for Supabase connection errors

**Data mixing between users:**
- Ensure you're signed in (not using uid="default")
- Check that `X-User-ID` header is sent in all frontend fetch calls
- Verify server endpoints extract `uid` from headers correctly
