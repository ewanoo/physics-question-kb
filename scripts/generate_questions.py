#!/usr/bin/env python3
"""Generate new questions for weak subtopics using Claude API."""

import json
import uuid
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()
QUESTIONS_DIR = Path("data/questions")
QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)

SUBTOPIC_CONTEXT = {
    "forces.speed": "speed, distance, time calculations (speed = distance/time), distance-time graphs, average speed, relative speed",
    "matter.changes": "physical changes (melting, freezing, evaporation, condensation, sublimation), chemical changes, reversible vs irreversible changes, signs of chemical change",
    "energy.resources": "renewable energy sources (solar, wind, hydroelectric, tidal, geothermal, biomass), non-renewable sources (fossil fuels, nuclear), advantages and disadvantages, environmental impact",
    "space.seasons": "Earth's orbit around the Sun, axial tilt (23.5°), why we have seasons, length of day, midnight sun, hemisphere differences, equinoxes and solstices",
    "energy.efficiency": "energy efficiency = useful output / total input × 100%, Sankey diagrams, reducing waste energy, insulation, LED vs incandescent bulbs",
    "energy.food": "food as a store of chemical energy, measuring energy in food (kJ/kcal), energy requirements for different activities, metabolism, balanced diet",
    "forces.springs": "Hooke's Law (F = ke), spring constant, elastic limit, elastic vs inelastic deformation, extension vs force graphs, elastic potential energy",
    "matter.density": "density = mass/volume (rho = m/V), units kg/m3 and g/cm3, comparing densities of solids/liquids/gases, floating and sinking, measuring density by displacement",
    "space.gravity": "gravity as a force of attraction, gravitational field strength (g = 10 N/kg on Earth), weight = mass x g, weight vs mass, gravity on different planets, orbits",
}

PROMPT_TEMPLATE = """You are writing KS3 Year 8 UK Physics exam questions about: {topic_description}

Generate exactly {count} questions for the subtopic "{subtopic}".

Requirements:
- Accurate UK KS3 Year 8 physics (age 12-13)
- Mix: {mc_count} multiple_choice, {sa_count} short_answer, {calc_count} calculation
- Difficulties: mix of easy/medium/hard
- All questions must be DIFFERENT from each other
- Distractors in MC should be plausible common misconceptions, not obviously wrong

Difficulty guide:
- easy: recall a fact or definition
- medium: apply a concept, single-step calculation
- hard: multi-step problem, evaluate/compare, interpret data

Return ONLY a JSON array (no markdown, no explanation) with this exact structure:
[
  {{
    "question_text": "...",
    "question_type": "multiple_choice",
    "difficulty": "easy",
    "tags": ["tag1", "tag2"],
    "options": [
      {{"label": "A", "text": "...", "is_correct": false}},
      {{"label": "B", "text": "...", "is_correct": true}},
      {{"label": "C", "text": "...", "is_correct": false}},
      {{"label": "D", "text": "...", "is_correct": false}}
    ],
    "correct_answer": "the correct option text",
    "explanation": "Clear 1-3 sentence explanation suitable for a 12-year-old."
  }},
  {{
    "question_text": "...",
    "question_type": "short_answer",
    "difficulty": "medium",
    "tags": ["tag1"],
    "options": null,
    "correct_answer": "...",
    "explanation": "..."
  }},
  {{
    "question_text": "...",
    "question_type": "calculation",
    "difficulty": "hard",
    "tags": ["tag1"],
    "options": null,
    "correct_answer": "...",
    "explanation": "..."
  }}
]"""


def generate_for_subtopic(subtopic: str, count: int = 4) -> list[str]:
    mc = max(2, count // 2)
    sa = max(1, count // 4)
    calc = count - mc - sa

    prompt = PROMPT_TEMPLATE.format(
        subtopic=subtopic,
        topic_description=SUBTOPIC_CONTEXT[subtopic],
        count=count,
        mc_count=mc,
        sa_count=sa,
        calc_count=calc,
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    # Strip markdown code blocks if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    questions = json.loads(text)
    now = datetime.utcnow().isoformat()

    saved = []
    for q in questions:
        qid = str(uuid.uuid4())
        full = {
            "id": qid,
            "question_text": q["question_text"],
            "question_type": q["question_type"],
            "difficulty": q["difficulty"],
            "topic": subtopic,
            "tags": q.get("tags", []),
            "options": q.get("options"),
            "correct_answer": q.get("correct_answer"),
            "explanation": q.get("explanation", ""),
            "quality_score": 4,
            "source_name": "claude_generator",
            "source_url": f"claude://{subtopic}/{q['difficulty']}",
            "scraped_at": now,
            "classified_at": now,
            "classification_confidence": 0.95,
            "year_group": "year8",
            "curriculum": "ks3",
            "raw_html": None,
        }
        out_path = QUESTIONS_DIR / f"{qid}.json"
        out_path.write_text(json.dumps(full, indent=2))
        saved.append(qid)

    return saved


def main():
    targets = [
        ("forces.speed", 4),
        ("matter.changes", 4),
        ("energy.resources", 4),
        ("space.seasons", 4),
        ("energy.efficiency", 4),
        ("energy.food", 4),
        ("forces.springs", 4),
        ("matter.density", 4),
        ("space.gravity", 4),
    ]

    total = 0
    for subtopic, count in targets:
        print(f"Generating {count} questions for {subtopic}...", flush=True)
        try:
            ids = generate_for_subtopic(subtopic, count)
            print(f"  Saved {len(ids)} questions", flush=True)
            total += len(ids)
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)

    print(f"\nTotal generated: {total}")


if __name__ == "__main__":
    main()
