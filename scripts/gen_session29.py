#!/usr/bin/env python3
"""Session 29: Generate 5 questions each for 8 weakest subtopics (all at 85 questions)."""
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
    ("electricity.static", "static electricity: charging by friction and induction, attracting/repelling charges, uses of static (inkjet printers, spray painting), dangers (lightning, fuel tankers), earthing"),
    ("energy.efficiency", "energy efficiency: efficiency = (useful energy output / total energy input) x 100%, Sankey diagrams, reducing energy waste, insulation, LED vs filament bulbs, thermal conductivity"),
    ("forces.balanced", "balanced and unbalanced forces: resultant force, Newton's first law, equilibrium, terminal velocity, skydiving, free-body diagrams"),
    ("forces.gravity", "gravity: gravitational field strength g = 10 N/kg on Earth, weight = mass x g (W=mg), weight vs mass, mass stays constant, weight varies with gravitational field"),
    ("forces.moments", "moments: moment = force x perpendicular distance from pivot, principle of moments (sum of clockwise = sum of anticlockwise), levers, seesaws, cranes, wheelbarrows"),
    ("forces.speed", "speed and motion: speed = distance / time (v = d/t), distance-time graphs (gradient = speed), average speed, units m/s and km/h, stopping distances"),
    ("waves.em_spectrum", "electromagnetic spectrum: radio, microwave, infrared, visible, ultraviolet, X-rays, gamma rays; all travel at 3x10^8 m/s in vacuum; uses (microwave ovens, medical X-rays), dangers (UV skin damage, gamma radiation)"),
    ("waves.properties", "wave properties: amplitude (height), wavelength (distance between peaks), frequency (waves per second, Hz), wave speed = frequency x wavelength (v=fλ), transverse (light) vs longitudinal (sound) waves"),
]

BATCH_PROMPT = """You are an expert KS3 Year 8 UK Physics teacher. Generate exactly {n} high-quality physics questions for the subtopic: **{topic}** ({description}).

Requirements:
- Accurate KS3 Year 8 UK curriculum (age 12-13)
- Mix types: ~3 multiple_choice, ~1 short_answer, ~1 calculation (or short_answer if no calc applies)
- Difficulties: at least 1 easy, 1 medium, 1 hard across the {n} questions
  - easy: recall a fact or definition (no calculation)
  - medium: apply a concept, simple 1-step calculation
  - hard: multi-step problem, compare/evaluate, extended reasoning
- Multiple choice: 4 options (A,B,C,D), exactly 1 correct, distractors must be plausible
- Explanations: clear, 1-3 sentences, suitable for a 12-year-old
- Do NOT use LaTeX. Write equations in plain text (e.g. "weight = mass x gravitational field strength")
- Make questions test UNDERSTANDING, not just rote recall

Return a JSON array of exactly {n} objects (no other text). Each object must have:
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

For short_answer and calculation questions: set "options" to null and put the answer in "correct_answer".
For multiple_choice: set "correct_answer" to null.
"""

saved_count = 0

for topic, description in TARGETS:
    n = 5
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
            print(f"  Saved: {q_id[:8]}... [{q['difficulty']}] {q['question_text'][:70]}")

        print(f"  -> {len(questions)} questions saved for {topic}")

    except Exception as e:
        print(f"  ERROR for {topic}: {e}", file=sys.stderr)
        import traceback; traceback.print_exc()

print(f"\nTotal saved this session: {saved_count} questions")
print(f"Files in data/questions/: {len(list(OUT_DIR.glob('*.json')))}")
