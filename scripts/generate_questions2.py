#!/usr/bin/env python3
"""Second batch: more questions for remaining gaps."""
import json
import uuid
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()
QUESTIONS_DIR = Path("data/questions")


def save_question(q: dict):
    qid = q.get("id") or str(uuid.uuid4())
    q["id"] = qid
    path = QUESTIONS_DIR / f"{qid}.json"
    with open(path, "w") as f:
        json.dump(q, f, indent=2)
    return qid


def generate_batch(topic: str, difficulty: str, count: int, extra_context: str = "") -> list[dict]:
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


# Second batch targets - more gaps after first batch
TARGETS = [
    # energy.efficiency hard=2
    ("energy.efficiency", "hard", 5, "Focus on calculating efficiency using the formula, comparing devices, improving efficiency, Sankey diagrams."),
    # forces.balanced hard=3
    ("forces.balanced", "hard", 5, "Focus on resolving forces, free body diagrams, net force calculations, motion under unbalanced forces."),
    # forces.gravity medium=3
    ("forces.gravity", "medium", 5, "Focus on weight = mass x gravitational field strength, comparing weight on different planets, g = 10 N/kg."),
    # waves.light hard=2
    ("waves.light", "hard", 5, "Focus on refraction, total internal reflection, lenses, ray diagrams, angle of incidence/refraction."),
    # waves.properties hard=2
    ("waves.properties", "hard", 5, "Focus on wave calculations (v=fλ), transverse vs longitudinal, wave diagrams, energy transfer."),
    # matter.changes medium=2
    ("matter.changes", "medium", 5, "Focus on dissolving, filtering, evaporation, distillation, reversible vs irreversible changes."),
    # forces.springs medium=7 but hard=3 (add more hard)
    ("forces.springs", "hard", 4, "Focus on Hooke's law calculations (F=kx), elastic limit, extension graphs, spring constant comparisons."),
    # electricity.electromagnets medium=4 (add more to reach 5+)
    ("electricity.electromagnets", "medium", 4, "Focus on how to increase electromagnet strength, uses of electromagnets, magnetic field direction using the right-hand rule."),
    # space.earth_moon: only 14 total
    ("space.earth_moon", "medium", 4, "Focus on lunar phases, tides, eclipses, moon's orbit period, near and far side of the moon."),
    # energy.food: only 15 total
    ("energy.food", "medium", 4, "Focus on food as a chemical energy store, respiration, metabolism, measuring energy in food using a calorimeter."),
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
