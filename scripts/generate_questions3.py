#!/usr/bin/env python3
"""Third batch: top up the 8 subtopics still at minimum 15-16."""
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
- Varied question types: mix of multiple_choice and short_answer (calculation for numeric problems)
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


# Third batch — top up the 8 subtopics at 15-16
TARGETS = [
    # electricity.current_voltage: 15 — add medium and hard
    ("electricity.current_voltage", "medium", 3, "Ohm's law (V=IR) calculations, plotting V-I graphs, resistance of components."),
    ("electricity.current_voltage", "hard", 3, "Series/parallel circuit calculations, total resistance, power calculations P=IV."),
    # electricity.static: 15 — add medium and hard
    ("electricity.static", "medium", 3, "Explaining static charge build-up, electric fields, sparks, earthing."),
    ("electricity.static", "hard", 3, "Comparing static and current electricity, applications of static (photocopier, paint spray), lightning rods."),
    # energy.power: 15 — add medium and hard
    ("energy.power", "medium", 3, "Calculating power (P=E/t), comparing device power ratings, watt vs joule."),
    ("energy.power", "hard", 3, "Multi-step power calculations, energy cost, comparing efficiency and power together."),
    # forces.moments: 15 — add medium and hard
    ("forces.moments", "medium", 3, "Calculating moments (M=Fd), levers, principle of moments, balancing a beam."),
    ("forces.moments", "hard", 3, "Multi-step moments problems, unbalanced moments, real-life lever applications."),
    # forces.pressure: 15 — add medium and hard
    ("forces.pressure", "medium", 3, "Calculating pressure (P=F/A), explaining why sharp objects pierce easily, hydraulics."),
    ("forces.pressure", "hard", 3, "Multi-step pressure calculations, pressure in fluids, atmospheric pressure effects."),
    # matter.particles: 15 — add medium and hard
    ("matter.particles", "medium", 3, "Particle model diagrams, diffusion, Brownian motion, comparing particle behaviour in states."),
    ("matter.particles", "hard", 3, "Explaining gas pressure using particle model, temperature and particle speed, comparing densities using particle model."),
    # space.solar_system: 15 — add medium and hard
    ("space.solar_system", "medium", 3, "Comparing planet distances from Sun, orbital periods, relative sizes of planets."),
    ("space.solar_system", "hard", 3, "Comparing conditions on different planets, why some planets have moons and others do not, life conditions."),
    # waves.em_spectrum: 15 — add medium and hard
    ("waves.em_spectrum", "medium", 3, "Order of EM spectrum by wavelength/frequency, properties of different waves, dangers and uses."),
    ("waves.em_spectrum", "hard", 3, "Comparing different EM waves, medical uses of X-rays and gamma, microwave communication vs danger."),
    # matter.gas_pressure: 16 — add medium
    ("matter.gas_pressure", "medium", 3, "Boyle's law (P inversely proportional to V), temperature and pressure, syringes and pumps."),
    # space.gravity: 16 — add medium
    ("space.gravity", "medium", 3, "Gravitational force between masses, orbital speed, why objects orbit, weight in space."),
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
