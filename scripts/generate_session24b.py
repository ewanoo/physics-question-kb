#!/usr/bin/env python3
"""Session 24b: Second batch - more questions for remaining weak subtopics."""
import json
import uuid
import os
import sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

OUT_DIR = Path("data/questions")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGETS = [
    ("energy.conservation", "conservation of energy, energy transfers, energy cannot be created or destroyed"),
    ("matter.density", "density formula (density = mass / volume), comparing densities, floating and sinking"),
    ("forces.moments", "moments and turning effects, moment = force x distance, levers, pivot points"),
    ("forces.pressure", "pressure formula (pressure = force / area), pressure in fluids, atmospheric pressure"),
    ("electricity.magnets", "induced magnetism, electromagnets vs permanent magnets, uses of magnets, demagnetising"),
    ("space.solar_system", "planets in order, solar system structure, asteroids, comets, moons"),
    ("space.earth_moon", "Moon phases, lunar cycle, eclipses, tides, why we see the same side of the Moon"),
    ("waves.colour", "mixing pigments vs mixing light, primary and secondary colours of light, cyan/magenta/yellow"),
]

BATCH_PROMPT = """You are an expert KS3 Year 8 UK Physics teacher. Generate {n} high-quality physics questions for the subtopic: **{topic}** ({description}).

Requirements:
- Accurate KS3 Year 8 UK curriculum (age 12-13)
- Mix: roughly 50% multiple_choice, 30% short_answer, 20% calculation
- Difficulties: mix of easy, medium, hard
  - easy: recall a fact or definition (no calculation)
  - medium: apply a concept, simple 1-step calculation
  - hard: multi-step problem, compare/evaluate, extended reasoning
- Multiple choice: 4 options (A,B,C,D), exactly 1 correct, distractors plausible
- Explanations: clear, 1-3 sentences, suitable for a 12-year-old
- Do NOT use LaTeX. Write equations in plain text (e.g. "pressure = force / area")
- Make questions DIFFERENT from typical basic recall - test understanding and application

Return a JSON array (no other text) where each object has:
{{
  "question_text": "...",
  "question_type": "multiple_choice" | "short_answer" | "calculation",
  "difficulty": "easy" | "medium" | "hard",
  "topic": "{topic}",
  "tags": ["tag1", "tag2"],
  "options": [
    {{"label": "A", "text": "...", "is_correct": false}},
    {{"label": "B", "text": "...", "is_correct": true}},
    {{"label": "C", "text": "...", "is_correct": false}},
    {{"label": "D", "text": "...", "is_correct": false}}
  ],
  "correct_answer": null,
  "explanation": "...",
  "quality_score": 4
}}

For short_answer and calculation: set "options" to null and put the answer in "correct_answer".
"""

saved_count = 0

for topic, description in TARGETS:
    n = 4
    print(f"\nGenerating {n} questions for {topic}...")

    prompt = BATCH_PROMPT.format(n=n, topic=topic, description=description)

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        questions = json.loads(raw)

        for q in questions:
            q_id = str(uuid.uuid4())
            q["id"] = q_id
            q["source_name"] = "claude_generator"
            q["year_group"] = "year8"
            q["curriculum"] = "ks3"
            q["scraped_at"] = datetime.utcnow().isoformat()

            if q.get("question_type") != "multiple_choice":
                q["options"] = None

            out_path = OUT_DIR / f"{q_id}.json"
            out_path.write_text(json.dumps(q, indent=2))
            saved_count += 1
            print(f"  Saved: {q_id[:8]}... [{q['difficulty']}] {q['question_text'][:60]}")

        print(f"  -> {len(questions)} questions saved for {topic}")

    except Exception as e:
        print(f"  ERROR for {topic}: {e}", file=sys.stderr)

print(f"\nTotal saved this batch: {saved_count} questions")
print(f"Files in data/questions/: {len(list(OUT_DIR.glob('*.json')))}")
