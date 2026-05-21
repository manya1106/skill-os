# Database schema alignment

Reference ERD vs application code. Run migrations in order: `001` → `002` → `003` → `004`.

## Tables in your ERD (confirmed)

| Table | Key columns | Used by |
|-------|-------------|---------|
| `users` | id, email, xp, level, streak, last_active | Auth, gamification |
| `resources` | user_id, platform, title, url, tags, progress, status | Learning, ML, extension |
| `interactions` | user_id, resource_id, event_type, value, **ts** | Extension sync, DAE-CF |
| `flashcards` | user_id, **front**, **back**, stability, difficulty, due_date | FSRS |
| `learning_goals` | user_id, category, target_level, status | Goals wizard |
| `learning_paths` | goal_id, sequence, milestone_title, hours | AI path generator |
| `user_achievements` | user_id, achievement_id | Rewards |
| `recommendation_feedback` | user_id, resource_id, action | ML feedback |

## Tables added by migrations (not in ERD image)

| Table | Migration | Purpose |
|-------|-----------|---------|
| `buddy_requests` | 004 | Study buddy connections |
| `buddy_interactions` | 004 | Scheduled sessions |
| `learning_preferences` | 004 | Pace, platforms, **interaction mode** |
| `flashcard_decks` | 004 | Deck grouping (optional if cards use user_id only) |
| `streak_freezes` | 003 | Streak protection |
| `notification_settings` | 001 | Email reminders |
| `activity_log` | (assumed) | Analytics heatmap |

## Column compatibility (`db_compat.py`)

- **Flashcards**: API uses `question`/`answer`; DB ERD uses `front`/`back` — both written on insert.
- **Interactions**: Writes both `ts` (ERD) and `created_at` (legacy).

## Goal categories

Wizard sends: `web-dev`, `data-sci`, `ml`, `career` → mapped to path templates in `learning_path_ai.CATEGORY_MAP`.

## AI learning paths

Set `OPENAI_API_KEY` for LLM-generated paths; otherwise heuristic + skill-gap analysis runs automatically.
