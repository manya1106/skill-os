-- Extension sync: store hashed email for PII-safe client verification
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_hash TEXT;

CREATE INDEX IF NOT EXISTS idx_resources_user_url ON resources(user_id, url);
CREATE INDEX IF NOT EXISTS idx_interactions_user_created ON interactions(user_id, created_at);
