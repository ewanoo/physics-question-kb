#!/usr/bin/env python3
"""Generate new questions for weak subtopics using the Anthropic API."""

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


SUBTOPIC_DESCRIPTIONS = {
    "electricity.electromagnets": "electromagnets, coils, solenoids, magnetic fields from current",
    "electricity.magnets": "permanent magnets, poles, magnetic fields, compasses",
    "energy.food": "food as an energy store, energy in food, calories, respiration",
    "energy.power": "power definition P=E/t, watts, power ratings of appliances",
    "forces.balanced": "balanced/unbalanced forces, resultant force, equilibrium, Newton's first law",
    "forces.friction": "friction force, lubricants, surfaces, air resistance, drag",
    "forces.gravity": "gravitational force, weight, mass, g on Earth, weight on other planets",
    "forces.springs": "Hooke's law, spring constant, elastic limit, extension, compression",
    "forces.types": "contact vs non-contact forces, types of forces: gravity, friction, tension, magnetic, electrostatic",
    "matter.changes": "physical vs chemical changes, reversible/irreversible changes, melting, freezing, burning",
    "matter.particles": "particle model, atoms, molecules, elements, compounds, diffusion",
    "matter.states": "solids/liquids/gases, state changes, melting point, boiling point",
    "space.earth_moon": "Earth-Moon system, tides, lunar phases, eclipses, Moon's orbit",
    "waves.colour": "visible light spectrum, colour mixing, filters, absorption, reflection of colour",
    "waves.properties": "wave properties: amplitude, frequency, wavelength, wave speed, transverse/longitudinal",
}

PROMPT_TEMPLATE = """Generate {count} high-quality KS3 Year 8 UK physics questions on the topic: {topic_desc}

Requirements:
- Accurate Year 8 UK KS3 physics (not A-level, not primary school)
- Mix types: some multiple_choice, some short_answer, some calculation
- For multiple_choice: 4 options (A/B/C/D), exactly 1 correct, plausible distractors
- Difficulties: mix of easy (recall a fact), medium (apply a concept or 1-step calc), hard (multi-step or evaluate)
- Explanations: clear, 1-3 sentences, suitable for a 12-year-old
- Do NOT duplicate these example topics (invent fresh angles)

Return a JSON array of {count} question objects. Each object must have EXACTLY these fields:
{{
  "question_text": "...",
  "question_type": "multiple_choice" | "short_answer" | "calculation",
  "difficulty": "easy" | "medium" | "hard",
  "topic": "{topic_slug}",
  "tags": ["tag1", "tag2"],
  "options": [  // for multiple_choice only, else null
    {{"label": "A", "text": "...", "is_correct": false}},
    {{"label": "B", "text": "...", "is_correct": true}},
    {{"label": "C", "text": "...", "is_correct": false}},
    {{"label": "D", "text": "...", "is_correct": false}}
  ],
  "correct_answer": "string or null",  // null for multiple_choice (answer in options), string for short_answer/calculation
  "explanation": "...",
  "quality_score": 4 or 5
}}

Return ONLY the JSON array, no markdown fences, no extra text."""


def generate_questions_for_subtopic(topic_slug: str, topic_desc: str, count: int = 2) -> list[dict]:
    prompt = PROMPT_TEMPLATE.format(
        count=count,
        topic_desc=topic_desc,
        topic_slug=topic_slug,
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()

    # Strip markdown fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    questions = json.loads(text)
    return questions


def save_question(q: dict) -> Path:
    now = datetime.utcnow().isoformat()
    q_id = str(uuid.uuid4())
    record = {
        "question_text": q["question_text"],
        "question_type": q["question_type"],
        "tags": q.get("tags", []),
        "options": q.get("options"),
        "correct_answer": q.get("correct_answer"),
        "explanation": q.get("explanation", ""),
        "quality_score": q.get("quality_score", 4),
        "source_name": "claude_generator",
        "id": q_id,
        "topic": q["topic"],
        "difficulty": q["difficulty"],
        "scraped_at": now,
        "classified_at": now,
        "classification_confidence": 0.95,
        "year_group": "year8",
        "curriculum": "ks3",
        "source_url": f"claude://{q['topic']}/{q['difficulty']}",
        "raw_html": None,
    }
    path = QUESTIONS_DIR / f"{q_id}.json"
    path.write_text(json.dumps(record, indent=2))
    return path


def main():
    total = 0
    for topic_slug, topic_desc in SUBTOPIC_DESCRIPTIONS.items():
        print(f"Generating for {topic_slug}...")
        try:
            questions = generate_questions_for_subtopic(topic_slug, topic_desc, count=2)
            for q in questions:
                save_question(q)
                total += 1
            print(f"  -> Saved {len(questions)} questions")
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nTotal new questions saved: {total}")


if __name__ == "__main__":
    main()
