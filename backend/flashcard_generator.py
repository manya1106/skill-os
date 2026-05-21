"""
Auto-generate flashcards from completed learning resources.

NLP pipeline (lightweight, no heavy models):
  • Keyword extraction (TF-style frequency + stopword filter)
  • Key phrase detection (n-grams)
  • Concept summarization (template from top terms)
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Optional

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "this", "that", "these", "those", "it", "its", "as", "if", "then",
    "than", "so", "such", "no", "not", "only", "own", "same", "too",
    "very", "just", "about", "into", "through", "during", "before", "after",
    "above", "below", "between", "out", "off", "over", "under", "again",
    "further", "once", "here", "there", "when", "where", "why", "how",
    "all", "each", "few", "more", "most", "other", "some", "any", "your",
    "you", "we", "they", "he", "she", "his", "her", "their", "our", "my",
    "course", "lesson", "chapter", "part", "section", "video", "module",
    "introduction", "intro", "basics", "fundamentals", "overview",
}


def _tokenise(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    return [t for t in text.split() if len(t) > 2 and t not in STOPWORDS]


def extract_keywords(text: str, top_n: int = 8) -> list[str]:
    """Keyword extraction via term frequency."""
    tokens = _tokenise(text)
    if not tokens:
        return []
    counts = Counter(tokens)
    return [w for w, _ in counts.most_common(top_n)]


def extract_key_phrases(text: str, top_n: int = 5) -> list[str]:
    """Key phrase detection using bigrams and trigrams."""
    tokens = _tokenise(text)
    if len(tokens) < 2:
        return []

    phrases: Counter = Counter()
    for n in (2, 3):
        for i in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[i : i + n])
            if any(t in STOPWORDS for t in phrase.split()):
                continue
            phrases[phrase] += 1

    return [p for p, _ in phrases.most_common(top_n)]


def summarize_concepts(title: str, tags: list[str], keywords: list[str]) -> str:
    """One-line concept summary from extracted signals."""
    parts = []
    if tags:
        parts.append(", ".join(tags[:4]))
    if keywords:
        parts.append(", ".join(keywords[:5]))
    if parts:
        return f"Core topics from «{title}»: {'; '.join(parts)}."
    return f"Key concepts from «{title}»."


def _title_to_question(title: str, keyword: str) -> str:
    templates = [
        f"What is {keyword} in the context of {title}?",
        f"Define {keyword} as covered in {title}.",
        f"Explain the role of {keyword} in {title}.",
    ]
    return templates[hash(keyword) % len(templates)]


def _phrase_to_qa(phrase: str, title: str) -> tuple[str, str]:
    return (
        f"What does «{phrase}» mean in {title}?",
        f"{phrase.title()} — a key concept from {title}. Review your notes for details.",
    )


def _tag_to_qa(tag: str, title: str) -> tuple[str, str]:
    return (
        f"How does «{tag}» relate to {title}?",
        f"{tag} is a central topic in {title}. Recall definitions, examples, and applications.",
    )


def generate_cards_from_resource(
    resource: dict,
    max_cards: int = 8,
) -> list[dict]:
    """
    Build flashcard dicts {question, answer, source} from a completed resource.

    Args:
        resource: {title, tags, platform, ...}
        max_cards: Maximum cards to auto-create
    """
    title = (resource.get("title") or "this resource").strip()
    tags = resource.get("tags") or []
    platform = resource.get("platform") or "Unknown"

    corpus = " ".join([title, " ".join(tags), platform])
    keywords = extract_keywords(corpus, top_n=10)
    phrases = extract_key_phrases(corpus, top_n=6)
    summary = summarize_concepts(title, tags, keywords)

    cards: list[dict] = []
    seen_questions: set[str] = set()

    def add(question: str, answer: str):
        q_norm = question.strip().lower()
        if q_norm in seen_questions or len(cards) >= max_cards:
            return
        seen_questions.add(q_norm)
        cards.append({
            "question": question,
            "answer": answer,
            "source": f"{platform}: {title[:60]}",
        })

    add(
        f"What are the main takeaways from «{title}»?",
        summary,
    )

    for tag in tags[:4]:
        q, a = _tag_to_qa(tag, title)
        add(q, a)

    for kw in keywords[:5]:
        add(
            _title_to_question(title, kw),
            f"{kw.title()} — important term from {title}. "
            f"Review the material on {platform} to recall the full definition.",
        )

    for phrase in phrases[:4]:
        q, a = _phrase_to_qa(phrase, title)
        add(q, a)

    add(
        f"Which platform did you use for «{title}»?",
        f"{platform}. You completed this resource — revisit it if you need a refresher.",
    )

    return cards[:max_cards]


def get_or_create_resource_deck(supabase, user_id: str, resource: dict) -> Optional[str]:
    """
    Find or create a deck for a resource. Returns deck_id.
    """
    title = (resource.get("title") or "Course")[:80]
    deck_title = f"{title} — Review"

    existing = (
        supabase.table("flashcard_decks")
        .select("id")
        .eq("user_id", user_id)
        .eq("title", deck_title)
        .execute()
    )
    if existing.data:
        return existing.data[0]["id"]

    created = (
        supabase.table("flashcard_decks")
        .insert({"user_id": user_id, "title": deck_title, "color": "indigo"})
        .execute()
    )
    if created.data:
        return created.data[0]["id"]
    return None


def auto_generate_for_completed_resource(
    supabase,
    user_id: str,
    resource: dict,
    max_cards: int = 8,
) -> dict:
    """
    Triggered on resource completion: NLP → cards → user deck.

    Returns summary {deck_id, cards_created, skipped_duplicates}.
    """
    deck_id = get_or_create_resource_deck(supabase, user_id, resource)
    if not deck_id:
        return {"deck_id": None, "cards_created": 0, "error": "Could not create deck"}

    proposed = generate_cards_from_resource(resource, max_cards=max_cards)

    existing = (
        supabase.table("flashcards")
        .select("question")
        .eq("deck_id", deck_id)
        .execute()
    )
    existing_q = {c["question"].strip().lower() for c in (existing.data or [])}

    from fsrs import new_card_state

    state = new_card_state()
    created = 0

    for card in proposed:
        if card["question"].strip().lower() in existing_q:
            continue
        from db_compat import card_insert_payload

        supabase.table("flashcards").insert(
            card_insert_payload(
                user_id=user_id,
                card["question"],
                card["answer"],
                deck_id=deck_id,
                source=card.get("source"),
                due_date=str(state.due_date),
                stability=state.stability,
                difficulty=state.difficulty,
            )
        ).execute()
        existing_q.add(card["question"].strip().lower())
        created += 1

    return {
        "deck_id": deck_id,
        "cards_created": created,
        "deck_title": f"{(resource.get('title') or 'Course')[:80]} — Review",
    }
