#!/usr/bin/env python3
"""Generate new KS3 physics questions using Claude API for weak subtopics."""
import json
import uuid
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()
QUESTIONS_DIR = Path("data/questions")
QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)


def save_question(q: dict):
    qid = q.get("id") or str(uuid.uuid4())
    q["id"] = qid
    path = QUESTIONS_DIR / f"{qid}.json"
    with open(path, "w") as f:
        json.dump(q, f, indent=2)
    return qid


def generate_batch(topic: str, difficulty: str, count: int, extra_context: str = "") -> list[dict]:
    """Generate a batch of questions for a given topic and difficulty."""
    topic_parts = topic.split(".")
    main_topic = topic_parts[0]
    subtopic = topic_parts[1] if len(topic_parts) > 1 else topic

    difficulty_guide = {
        "easy": "recall a fact or definition (no calculation needed, 12-year-old can answer from memory)",
        "medium": "apply a concept or do a simple 1-step calculation",
        "hard": "multi-step problem, compare/evaluate two scenarios, or extended reasoning",
    }

    prompt = f"""Generate {count} unique KS3 Year 8 UK Physics questions on the topic: {topic}
Difficulty: {difficulty} — {difficulty_guide[difficulty]}
{extra_context}

STRICT RULES:
- Accurate Year 8 UK physics (not A-level, not primary school)
- Varied question types: mix of multiple_choice and short_answer (calculation for hard numeric problems)
- Multiple choice: 4 options (A/B/C/D), exactly 1 correct, distractors plausible not silly
- Explanations: clear, 1-3 sentences, suitable for a 12-year-old
- All questions must be distinct from each other
- Do NOT include any markdown in question_text or explanation fields

Return ONLY a valid JSON array, no other text. Each object must have exactly these fields:
- "question_text": string
- "question_type": "multiple_choice" | "short_answer" | "calculation"
- "difficulty": "{difficulty}"
- "topic": "{topic}"
- "tags": array of 2-4 relevant tag strings
- "options": for multiple_choice only — array of 4 objects: {{"label":"A","text":"...","is_correct":bool}}; null for others
- "correct_answer": string (the answer text; for multiple_choice also include the letter e.g. "B) 10 N")
- "explanation": string (1-3 sentences)
- "quality_score": 4 or 5 (integer)
- "source_name": "claude_generator"
"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    questions = json.loads(raw)

    now = datetime.utcnow().isoformat()
    enriched = []
    for q in questions:
        q["id"] = str(uuid.uuid4())
        q["scraped_at"] = now
        q["classified_at"] = now
        q["classification_confidence"] = 0.95
        q["year_group"] = "year8"
        q["curriculum"] = "ks3"
        q["source_url"] = None
        q["raw_html"] = None
        enriched.append(q)

    return enriched


# Weak topics to target: (topic, difficulty, count, extra_context)
TARGETS = [
    # electricity.magnets: medium=2, hard=3
    ("electricity.magnets", "medium", 5, "Focus on magnetic fields, poles, attraction/repulsion, field lines."),
    ("electricity.magnets", "hard", 5, "Focus on comparing magnetic materials, field strength, electromagnets vs permanent magnets."),
    # energy.stores: hard=2
    ("energy.stores", "hard", 5, "Focus on energy store calculations, energy dissipation, quantitative comparisons between energy stores."),
    # matter.states: hard=2
    ("matter.states", "hard", 5, "Focus on changes of state, latent heat, particle arrangement during melting/boiling, interpreting heating curves."),
    # space.seasons: medium=3
    ("space.seasons", "medium", 5, "Focus on Earth's tilt, day length changes, temperature variation, equinoxes, solstices."),
    # energy.resources: medium=2
    ("energy.resources", "medium", 5, "Focus on comparing renewable vs non-renewable, energy efficiency of power stations, carbon footprint."),
    # forces.speed: hard=1
    ("forces.speed", "hard", 6, "Focus on distance-time graphs (calculating speed from gradient), speed-time graphs, acceleration, multi-step problems."),
    # forces.types: medium=2
    ("forces.types", "medium", 5, "Focus on contact vs non-contact forces, resultant forces, identifying force pairs in scenarios."),
    # forces.friction: medium=1
    ("forces.friction", "medium", 6, "Focus on friction calculations, lubrication, factors affecting friction, grip and surfaces."),
    # electricity.circuits: easy=4 (lowest easy)
    ("electricity.circuits", "easy", 4, "Focus on basic circuit symbols, series vs parallel, components in circuits."),
    # energy.conservation: easy=4
    ("energy.conservation", "easy", 4, "Focus on the law of conservation of energy, energy transfers, Sankey diagrams."),
    # matter.density: easy=4
    ("matter.density", "easy", 4, "Focus on what density means, which materials are denser, floating and sinking."),
]


def main():
    total = 0
    for topic, difficulty, count, context in TARGETS:
        print(f"\nGenerating {count} {difficulty} questions for {topic}...")
        try:
            questions = generate_batch(topic, difficulty, count, context)
            saved = 0
            for q in questions:
                save_question(q)
                saved += 1
                total += 1
                print(f"  Saved: {q['id'][:8]}... [{q['question_type']}] {q['question_text'][:60]}...")
            print(f"  Saved {saved}/{count} questions for {topic} ({difficulty})")
        except Exception as e:
            print(f"  ERROR generating {topic} {difficulty}: {e}")

    print(f"\nTotal questions generated: {total}")


if __name__ == "__main__":
    main()
