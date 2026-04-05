#!/usr/bin/env python3
"""Session 13 top-up: fill in missed batch + extra questions."""
import anthropic
import json
import re
import uuid
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()

DIFF_GUIDES = {
    "easy": "recall a fact or definition, no calculation needed",
    "medium": "apply a concept or do a simple 1-step calculation",
    "hard": "multi-step problem, compare/evaluate, extended reasoning",
}

PROMPT = """Generate exactly 3 KS3 Year 8 UK Physics questions about: {subtopic} ({difficulty} difficulty).
Focus: {hints}
Difficulty guide: {diff_guide}

Rules:
- Aim for 2 multiple_choice and 1 short_answer or calculation
- Each question tests a DIFFERENT specific concept
- Multiple choice: 4 options, exactly 1 correct, plausible distractors
- short_answer/calculation: correct_answer is a concise string
- Explanation: 1-3 sentences for a 12-year-old

Return ONLY a valid JSON array of exactly 3 question objects with these fields:
question_text, question_type, difficulty, topic, tags, options (array of 4 or null), correct_answer (null or string), explanation, quality_score, source_name.
"""


def strip_fences(text):
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def generate_batch(subtopic, difficulty, hints, n=3):
    prompt = PROMPT.format(
        subtopic=subtopic,
        difficulty=difficulty,
        hints=hints,
        diff_guide=DIFF_GUIDES[difficulty],
    ).replace("{n}", str(n))
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
    )
    text = strip_fences(msg.content[0].text)
    return json.loads(text)


targets = [
    ("forces.balanced", "hard", "multi-step resultant force problems, Newton's second law F=ma, free body diagram analysis"),
    ("energy.power", "easy", "what is power, units of power (watts), calculating power from energy and time definitions"),
    ("energy.power", "hard", "multi-step power calculations, comparing power of devices, efficiency and power combined"),
    ("forces.speed", "easy", "speed definition, speed formula, units of speed, average speed vs instantaneous speed"),
    ("matter.density", "easy", "density definition, units (kg/m3), density formula, comparing densities of materials"),
    ("space.solar_system", "medium", "order of planets, distances in solar system, comparing planet sizes, orbits"),
]

out_dir = Path("data/questions")
out_dir.mkdir(exist_ok=True)

total = 0
for subtopic, difficulty, hints in targets:
    print(f"Generating {subtopic} ({difficulty})...")
    try:
        questions = generate_batch(subtopic, difficulty, hints)
        for q in questions:
            q["id"] = str(uuid.uuid4())
            fname = out_dir / f"{q['id']}.json"
            with open(fname, "w") as f:
                json.dump(q, f, indent=2)
            total += 1
            print(f"  [{q['difficulty']}] {q['question_text'][:75]}...")
    except Exception as e:
        print(f"  ERROR for {subtopic} ({difficulty}): {e}")

print(f"\nTotal generated: {total}")
