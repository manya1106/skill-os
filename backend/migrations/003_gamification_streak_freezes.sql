-- Gamification: streak freezes + lesson XP tracking
-- Run in Supabase SQL editor

CREATE TABLE IF NOT EXISTS streak_freezes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  protected_date DATE NOT NULL,
  used_at DATE NOT NULL DEFAULT CURRENT_DATE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_streak_freezes_user_month
  ON streak_freezes(user_id, used_at);

CREATE INDEX IF NOT EXISTS idx_streak_freezes_protected
  ON streak_freezes(user_id, protected_date);

-- Prevent duplicate freeze for same day
CREATE UNIQUE INDEX IF NOT EXISTS idx_streak_freezes_user_date
  ON streak_freezes(user_id, protected_date);

-- Lesson/video XP awarded once per resource (extension completions)
ALTER TABLE resources ADD COLUMN IF NOT EXISTS lesson_xp_awarded BOOLEAN DEFAULT FALSE;
