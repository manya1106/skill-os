"""
AI-powered learning path generation with LLM + heuristic fallback.
"""

from __future__ import annotations

import json
import os
from typing import List, Optional

import httpx

CATEGORY_MAP = {
    "web-dev": "Web Development",
    "data-sci": "Data Science",
    "ml": "Machine Learning",
    "career": "Career Switch",
    "other": "General Learning",
}

FALLBACK_PATHS = {
    "Web Development": [
        {"title": "HTML & CSS Fundamentals", "description": "Semantic markup and responsive layout", "hours": 20},
        {"title": "JavaScript Core", "description": "Async patterns, DOM, and modern ES features", "hours": 30},
        {"title": "React & Component Design", "description": "Hooks, state, and UI architecture", "hours": 25},
        {"title": "Backend APIs", "description": "REST, auth, and database integration", "hours": 30},
        {"title": "Capstone Web App", "description": "Deploy a full-stack portfolio project", "hours": 40},
    ],
    "Data Science": [
        {"title": "Python for Data", "description": "NumPy, Pandas, visualization basics", "hours": 25},
        {"title": "Statistics Foundation", "description": "Inference, distributions, experimentation", "hours": 20},
        {"title": "Machine Learning Core", "description": "Supervised models and evaluation", "hours": 30},
        {"title": "Feature Engineering", "description": "Pipelines, leakage, and validation", "hours": 25},
        {"title": "Analytics Capstone", "description": "End-to-end analysis with storytelling", "hours": 40},
    ],
    "Machine Learning": [
        {"title": "Math & Python Refresher", "description": "Linear algebra and calculus essentials", "hours": 20},
        {"title": "Classical ML", "description": "Regression, trees, ensembles", "hours": 30},
        {"title": "Deep Learning Intro", "description": "Neural nets, CNNs, training loops", "hours": 35},
        {"title": "NLP / Transformers", "description": "Embeddings and fine-tuning basics", "hours": 30},
        {"title": "ML Engineering Project", "description": "Train, evaluate, and ship a model", "hours": 45},
    ],
    "Career Switch": [
        {"title": "Skills Audit", "description": "Map transferable skills and gaps", "hours": 5},
        {"title": "Domain Foundations", "description": "Core concepts for your target role", "hours": 30},
        {"title": "Portfolio Projects", "description": "2–3 demonstrable builds", "hours": 50},
        {"title": "Interview Prep", "description": "Technical and behavioral practice", "hours": 25},
        {"title": "Job Search Sprint", "description": "Networking, applications, follow-ups", "hours": 20},
    ],
}


def _analyze_skill_gaps(resources: List[dict], goal_category: str) -> List[str]:
    """Identify tags/platforms user lacks vs goal category."""
    have_tags = set()
    have_platforms = set()
    for r in resources:
        for t in r.get("tags") or []:
            have_tags.add(str(t).lower())
        if r.get("platform"):
            have_platforms.add(r["platform"].lower())

    category_keywords = {
        "Web Development": ["javascript", "react", "html", "css", "api"],
        "Data Science": ["python", "pandas", "statistics", "visualization"],
        "Machine Learning": ["ml", "deep learning", "neural", "tensorflow"],
        "Career Switch": ["portfolio", "interview", "project"],
    }
    expected = category_keywords.get(goal_category, ["fundamentals", "practice"])
    gaps = [k for k in expected if k not in have_tags]
    return gaps[:5]


async def _generate_with_openai(
    goal: dict,
    user_level: int,
    pace: str,
    skill_gaps: List[str],
    resources_summary: str,
) -> Optional[List[dict]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    category = CATEGORY_MAP.get(goal.get("category", ""), goal.get("category", "General"))
    prompt = f"""Create a personalized learning path as JSON array of 4-6 milestones.
Goal: {goal.get('title')} ({category})
Description: {goal.get('description') or 'N/A'}
User level: {user_level}/4
Pace: {pace}
Skill gaps to address: {', '.join(skill_gaps) or 'none identified'}
Existing resources: {resources_summary}

Return ONLY valid JSON:
[{{"title": "...", "description": "...", "hours": 20}}]
Order from foundational to advanced. Total hours should match pace ({pace})."""

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    "messages": [
                        {"role": "system", "content": "You are a curriculum designer. Output JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            milestones = json.loads(content)
            if isinstance(milestones, list) and len(milestones) >= 3:
                return milestones
    except Exception as e:
        print(f"[LearningPath AI] OpenAI failed: {e}")
    return None


def _heuristic_path(
    goal: dict,
    user_level: int,
    pace: str,
    skill_gaps: List[str],
) -> List[dict]:
    """Dynamic path without LLM — adapts titles to gaps and level."""
    category = CATEGORY_MAP.get(goal.get("category", ""), "General Learning")
    base = FALLBACK_PATHS.get(category, FALLBACK_PATHS["Web Development"])

    pace_mult = {"slow": 1.2, "moderate": 1.0, "fast": 0.85}.get(pace, 1.0)
    level_offset = max(0, user_level - 1)

    path = []
    for i, m in enumerate(base):
        title = m["title"]
        desc = m["description"]
        if skill_gaps and i == 0:
            desc = f"Address gaps: {', '.join(skill_gaps)}. " + desc
        if level_offset > 1 and i < level_offset:
            continue
        hours = max(5, int(m["hours"] * pace_mult))
        path.append({
            "title": title,
            "description": desc,
            "hours": hours,
        })

    if goal.get("title"):
        path.insert(0, {
            "title": f"Kickoff: {goal['title'][:50]}",
            "description": f"Define success criteria for your {category} goal",
            "hours": 5,
        })

    return path[:6]


async def generate_learning_path(
    supabase,
    goal: dict,
    user_id: str,
) -> List[dict]:
    """Generate and persist milestones; returns inserted rows."""
    resources = (
        supabase.table("resources")
        .select("title, platform, tags, progress, status")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    prefs = {}
    try:
        prefs = (
            supabase.table("learning_preferences")
            .select("pace, learning_style")
            .eq("user_id", user_id)
            .single()
            .execute()
            .data
            or {}
        )
    except Exception:
        pass

    user = (
        supabase.table("users")
        .select("level")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )
    level = goal.get("target_level") or user.get("level") or 1
    pace = prefs.get("pace", "moderate")
    category = CATEGORY_MAP.get(goal.get("category", ""), goal.get("category", "General"))

    gaps = _analyze_skill_gaps(resources, category)
    res_summary = ", ".join(
        f"{r.get('title', '?')} ({r.get('progress', 0)}%)"
        for r in resources[:8]
    ) or "none yet"

    milestones = await _generate_with_openai(goal, level, pace, gaps, res_summary)
    source = "ai"
    if not milestones:
        milestones = _heuristic_path(goal, level, pace, gaps)
        source = "heuristic"

    inserted = []
    for i, m in enumerate(milestones, 1):
        row = (
            supabase.table("learning_paths")
            .insert({
                "goal_id": goal["id"],
                "sequence": i,
                "milestone_title": m["title"],
                "description": m.get("description", ""),
                "target_duration_hours": m.get("hours", 20),
                "status": "not_started",
            })
            .execute()
        )
        if row.data:
            inserted.append({**row.data[0], "_source": source})

    return inserted
