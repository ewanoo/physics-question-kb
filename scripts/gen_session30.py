#!/usr/bin/env python3
"""Session 30: Generate 5 questions each for 7 weakest subtopics."""
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
    ("matter.gas_pressure", "gas pressure: particle model of gases, pressure = force/area, gas pressure increases with temperature (particles move faster), pressure decreases as volume increases (Boyle's law concept), atmospheric pressure, uses like syringes and pumps"),
    ("matter.states", "states of matter: properties of solids (fixed shape/volume, particles vibrate), liquids (fixed volume, takes shape of container, particles slide), gases (fills container, particles move freely); changes of state: melting, freezing, evaporating, condensing, sublimation; latent heat concept"),
    ("forces.balanced", "balanced and unbalanced forces: resultant force = sum of all forces, Newton's first law (stationary or constant velocity when balanced), free-body diagrams, terminal velocity (air resistance = weight), skydiving phases, floating (upthrust = weight)"),
    ("matter.particles", "particle model: atoms and molecules, arrangement and movement in solids/liquids/gases, diffusion (particles spreading from high to low concentration), Brownian motion (evidence for random particle movement), particle size, density related to particle packing"),
    ("electricity.magnets", "magnets: poles (north/south), magnetic fields (field lines from N to S), attracted metals (iron, steel, nickel, cobalt), permanent vs temporary magnets, induced magnetism, magnetic field of Earth, compass, repulsion between like poles"),
    ("energy.resources", "energy resources: renewable (solar, wind, hydroelectric, tidal, geothermal, biomass) vs non-renewable (coal, oil, natural gas, nuclear); advantages/disadvantages of each; fossil fuels release CO2 causing climate change; nuclear fission, radioactive waste; energy security"),
    ("forces.pressure", "pressure in solids, liquids and gases: pressure = force / area (P = F/A, units Pa or N/m²); liquid pressure increases with depth (P = ρgh concept), hydraulic systems (pressure transmitted through liquids), atmospheric pressure, high heels vs flat shoes comparison"),
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
- Do NOT use LaTeX. Write equations in plain text (e.g. "pressure = force / area")
- Make questions test UNDERSTANDING, not just rote recall
- Do not generate trivial or overly simplistic questions

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
