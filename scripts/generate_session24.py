#!/usr/bin/env python3
"""Session 24: Generate questions for weakest subtopics."""
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
    ("forces.balanced", "balanced and unbalanced forces, resultant force, Newton's first law"),
    ("waves.light", "reflection, refraction, how light travels, transparent/opaque/translucent materials"),
    ("waves.properties", "wave amplitude, frequency, wavelength, wave speed, transverse vs longitudinal"),
    ("electricity.magnets", "magnetic fields, poles, force between magnets, compasses, plotting field lines"),
    ("electricity.static", "static electricity, charging by friction, attraction/repulsion, electric fields"),
    ("forces.speed", "speed calculations, distance-time graphs, average speed, instantaneous speed"),
    ("matter.changes", "physical and chemical changes, melting, boiling, dissolving, reversible/irreversible"),
    ("space.seasons", "Earth's tilt, seasons, day length, why seasons occur, hemispheres"),
    ("waves.colour", "colour of objects, colour addition, colour subtraction, filters, white light"),
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
- Do NOT use LaTeX. Write equations in plain text (e.g. "speed = distance / time")

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
    n = 4  # questions per subtopic per batch
    print(f"\nGenerating {n} questions for {topic}...")

    prompt = BATCH_PROMPT.format(n=n, topic=topic, description=description)

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
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

            # Ensure options is correct format
            if q.get("question_type") != "multiple_choice":
                q["options"] = None

            out_path = OUT_DIR / f"{q_id}.json"
            out_path.write_text(json.dumps(q, indent=2))
            saved_count += 1
            print(f"  Saved: {q_id[:8]}... [{q['difficulty']}] {q['question_text'][:60]}")

        print(f"  -> {len(questions)} questions saved for {topic}")

    except Exception as e:
        print(f"  ERROR for {topic}: {e}", file=sys.stderr)

print(f"\nTotal saved: {saved_count} questions")
print(f"Files in data/questions/: {len(list(OUT_DIR.glob('*.json')))}")
