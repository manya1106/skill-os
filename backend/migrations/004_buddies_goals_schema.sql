-- Buddies, preferences, and schema alignment (run in Supabase SQL editor)
-- Matches ERD + application code expectations

-- ── Study buddies ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS buddy_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  from_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  to_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status TEXT DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(from_user_id, to_user_id)
);

CREATE TABLE IF NOT EXISTS buddy_interactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  buddy_request_id UUID NOT NULL REFERENCES buddy_requests(id) ON DELETE CASCADE,
  mode TEXT NOT NULL DEFAULT 'collaborative',
  scheduled_at TIMESTAMPTZ,
  duration_minutes INT DEFAULT 60,
  status TEXT DEFAULT 'scheduled',
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_buddy_requests_users ON buddy_requests(from_user_id, to_user_id);
CREATE INDEX IF NOT EXISTS idx_buddy_interactions_request ON buddy_interactions(buddy_request_id);

-- ── Learning preferences (pace, platforms, interaction mode) ────────────────
CREATE TABLE IF NOT EXISTS learning_preferences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  study_hours_per_week INT DEFAULT 10,
  preferred_platforms TEXT[] DEFAULT '{}',
  learning_style TEXT DEFAULT 'visual',
  pace TEXT DEFAULT 'moderate',
  preferred_interaction_mode TEXT DEFAULT 'collaborative',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id)
);

-- ── Flashcards: support both ERD (front/back) and app (question/answer) ─────
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS front TEXT;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS back TEXT;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS question TEXT;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS answer TEXT;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS deck_id UUID;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;

CREATE TABLE IF NOT EXISTS flashcard_decks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  color TEXT DEFAULT 'indigo',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Interactions: ERD uses `ts`; code may use created_at
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS ts TIMESTAMPTZ;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;
