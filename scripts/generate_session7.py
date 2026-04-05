#!/usr/bin/env python3
"""Session 7: Generate questions for the 9 weakest subtopics (all ≤22 questions)."""
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
    path.write_text(json.dumps(q, indent=2))
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
- Mix of multiple_choice and short_answer (use calculation type for numeric problems)
- Multiple choice: 4 options (A/B/C/D), exactly 1 correct, distractors plausible not silly
- Explanations: clear, 1-3 sentences, suitable for a 12-year-old
- All questions must be distinct from each other
- Do NOT include any markdown formatting in text fields

Return ONLY a valid JSON array, no other text. Each object must have exactly these fields:
- "question_text": string
- "question_type": "multiple_choice" | "short_answer" | "calculation"
- "difficulty": "{difficulty}"
- "topic": "{topic}"
- "tags": array of 2-4 relevant tag strings
- "options": for multiple_choice — array of 4 objects: {{"label":"A","text":"...","is_correct":bool}}; null for others
- "correct_answer": string (for multiple_choice include the letter e.g. "B) 10 N")
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
    for q in questions:
        q["id"] = str(uuid.uuid4())
        q["scraped_at"] = now
        q["classified_at"] = now
        q["classification_confidence"] = 0.95
        q["year_group"] = "year8"
        q["curriculum"] = "ks3"
        q["source_url"] = None
        q["raw_html"] = None
    return questions


# Targets: the 9 subtopics with ≤22 questions, ~4-5 questions each across difficulties
TARGETS = [
    ("space.gravity", "easy", 2, "Focus on: weight vs mass, gravitational field strength g=10 N/kg, calculating weight W=mg."),
    ("space.gravity", "medium", 2, "Focus on: gravity keeping planets in orbit, comparing gravity on different planets, weight calculations."),
    ("space.gravity", "hard", 2, "Focus on: multi-step weight calculations, comparing gravitational field strengths, why orbits are maintained."),
    ("electricity.static", "easy", 2, "Focus on: how objects become charged (friction), positive/negative charges, attraction and repulsion rules."),
    ("electricity.static", "medium", 2, "Focus on: lightning, earthing, Van de Graaff generator, sparks, practical applications of static."),
    ("electricity.static", "hard", 2, "Focus on: detailed charge transfer explanation, electrostatic hazards and uses, comparing static scenarios."),
    ("energy.power", "easy", 2, "Focus on: definition of power, units (watts), identifying high/low power appliances."),
    ("energy.power", "medium", 2, "Focus on: calculating power P=E/t or P=W/t, comparing appliances, reading power ratings."),
    ("energy.power", "hard", 2, "Focus on: multi-step power calculations, energy cost calculations, comparing efficiency and power."),
    ("forces.moments", "easy", 2, "Focus on: what a moment is, turning effect of a force, levers, see-saws, moment = force × distance."),
    ("forces.moments", "medium", 2, "Focus on: calculating moments, principle of moments, balancing calculations on a see-saw."),
    ("forces.moments", "hard", 2, "Focus on: multi-step moment problems, unbalanced moments, real-world lever applications with calculations."),
    ("forces.pressure", "easy", 2, "Focus on: definition of pressure, units (Pascals), everyday examples of high/low pressure."),
    ("forces.pressure", "medium", 2, "Focus on: calculating pressure P=F/A, comparing sharp vs blunt objects, snowshoes, knife blades."),
    ("forces.pressure", "hard", 2, "Focus on: multi-step pressure calculations, hydraulics, atmospheric pressure effects, dams."),
    ("matter.particles", "easy", 2, "Focus on: particle model, arrangement of particles in solids/liquids/gases, properties explained by particles."),
    ("matter.particles", "medium", 2, "Focus on: diffusion, Brownian motion, particle movement in different states, explaining gas pressure."),
    ("matter.particles", "hard", 2, "Focus on: quantitative particle model questions, comparing particle behaviour, explaining unusual observations."),
    ("space.solar_system", "easy", 2, "Focus on: planets in order from Sun, planet names, the Sun being a star, Moon orbiting Earth."),
    ("space.solar_system", "medium", 2, "Focus on: comparing planet sizes, orbital periods, asteroids vs comets, inner vs outer planets."),
    ("space.solar_system", "hard", 2, "Focus on: why planets orbit the Sun, comparing orbital speeds, Kepler's ideas (qualitative), scale of Solar System."),
    ("waves.em_spectrum", "easy", 2, "Focus on: names of the 7 types of EM waves in order, all EM waves travel at speed of light, transverse waves."),
    ("waves.em_spectrum", "medium", 2, "Focus on: uses of each type (radio=communication, microwave=cooking/satellite, infrared=heat, UV=sunburn, X-ray=medical, gamma=cancer treatment), dangers."),
    ("waves.em_spectrum", "hard", 2, "Focus on: comparing wavelength/frequency/energy across spectrum, ionising vs non-ionising, evaluating uses and risks."),
    ("electricity.magnets", "easy", 2, "Focus on: magnetic materials (iron, steel, nickel, cobalt), poles attract/repel, compasses, Earth's magnetic field."),
    ("electricity.magnets", "medium", 2, "Focus on: magnetic field lines (shape and direction), permanent vs induced magnets, plotting field patterns."),
]


def main():
    total = 0
    for topic, difficulty, count, context in TARGETS:
        print(f"\nGenerating {count} {difficulty} questions for {topic}...")
        try:
            questions = generate_batch(topic, difficulty, count, context)
            for q in questions:
                save_question(q)
                total += 1
                print(f"  Saved: {q['id'][:8]}... [{q['question_type']}] {q['question_text'][:65]}...")
            print(f"  OK: {len(questions)} saved")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()

    print(f"\nTotal questions generated: {total}")


if __name__ == "__main__":
    main()
