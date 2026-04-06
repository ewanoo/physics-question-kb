#!/usr/bin/env python3
"""Session 31: Generate 3 questions each for 13 weakest subtopics (all at 93 count)."""
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
    ("electricity.circuits", "electrical circuits: series circuits (same current everywhere, voltages add up), parallel circuits (current splits, same voltage across branches), circuit symbols (cell, battery, bulb, switch, resistor, ammeter, voltmeter), short circuits, fuses as safety devices"),
    ("electricity.current_voltage", "current (amps, A) flows through components; voltage (volts, V) is the push; resistance (ohms, Ω) opposes current; Ohm's law V=IR; measuring current with ammeter (in series), voltage with voltmeter (in parallel); increasing resistance decreases current"),
    ("electricity.electromagnets", "electromagnet: coil of wire carrying current creates a magnetic field; strength increases with more turns, higher current, iron core; solenoid field pattern; uses: electric bells, loudspeakers, maglev trains, cranes, MRI scanners; can be switched on/off"),
    ("energy.food", "food as chemical energy store; energy measured in kilojoules (kJ) or kilocalories (kcal); food labels; carbohydrates, fats and proteins as energy sources; metabolic rate; energy used for movement, warmth, growth; athletes need more energy; comparing energy values of foods"),
    ("forces.friction", "friction: contact force opposing motion; surfaces in contact; rough surfaces = more friction; smooth/lubricated = less friction; air resistance is friction with air; drag in water; useful friction (gripping, braking) and unwanted friction (wears surfaces, generates heat); reducing with lubrication, streamlining"),
    ("forces.moments", "moment = force × perpendicular distance from pivot (measured in Nm); turning effect; lever: effort force × effort distance = load × load distance when balanced; principle of moments; everyday levers (scissors, see-saw, wheelbarrow, bottle opener); centre of gravity; stability"),
    ("forces.springs", "Hooke's Law: extension is proportional to force (F = ke); spring constant k (N/m or N/cm) - stiffness; elastic limit: point beyond which spring does not return to original shape; extension vs force graph is straight line up to elastic limit; elastic potential energy stored in stretched spring"),
    ("forces.types", "contact forces: friction, tension, normal reaction (reaction force), air resistance, upthrust; non-contact forces: gravity, magnetic, electrostatic; weight is gravitational pull; mass (kg) vs weight (N); free-body diagrams showing all forces on an object; resultant force"),
    ("matter.changes", "changes of state: melting (solid→liquid), freezing (liquid→solid), evaporation/boiling (liquid→gas), condensation (gas→liquid), sublimation (solid→gas); melting point and boiling point; energy needed to change state (latent heat concept); these are physical changes - reversible; particles rearrange"),
    ("matter.density", "density = mass ÷ volume (ρ = m/V); units: kg/m³ or g/cm³; dense materials have particles packed closely; water density = 1 g/cm³; objects less dense than water float, denser sink; measuring density: balance for mass, measuring cylinder for regular/irregular shapes; comparing densities of materials"),
    ("space.earth_moon", "Moon orbits Earth every 27.3 days; Moon phases (new, crescent, quarter, gibbous, full) caused by relative positions of Sun, Earth, Moon; tides caused by Moon's gravity; the Moon has no atmosphere, craters, extreme temperatures; distance ~384,000 km; same side always faces Earth (synchronous rotation)"),
    ("space.gravity", "gravity acts between any two masses; gravitational field strength g = 10 N/kg on Earth (varies on other planets); weight = mass × g (W = mg); mass stays the same anywhere, weight changes; objects fall at same rate regardless of mass (ignoring air resistance); gravity keeps planets in orbit"),
    ("space.seasons", "seasons caused by Earth's axial tilt (23.5°), NOT distance from Sun; summer in hemisphere tilted toward Sun (longer days, more direct sunlight, higher temperatures); winter when tilted away; equinoxes (equal day/night, March and September); solstices (longest/shortest day, June and December); Southern hemisphere has opposite seasons"),
]

BATCH_PROMPT = """You are an expert KS3 Year 8 UK Physics teacher. Generate exactly {n} high-quality physics questions for the subtopic: **{topic}** ({description}).

Requirements:
- Accurate KS3 Year 8 UK curriculum (age 12-13)
- Mix types: 2 multiple_choice, 1 short_answer or calculation
- Difficulties: 1 easy, 1 medium, 1 hard
  - easy: recall a fact or definition (no calculation)
  - medium: apply a concept, simple 1-step calculation
  - hard: multi-step problem, compare/evaluate, extended reasoning
- Multiple choice: 4 options (A,B,C,D), exactly 1 correct, distractors must be plausible common misconceptions (not obviously wrong)
- Explanations: clear, 1-3 sentences, suitable for a 12-year-old
- Do NOT use LaTeX. Write equations in plain text (e.g. "moment = force x distance")
- Make questions test UNDERSTANDING, not just rote recall
- Questions should be DIFFERENT in style/content from each other

Return a JSON array of exactly {n} objects (no other text, no markdown). Each object:
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

For short_answer and calculation: set "options" to null and put answer in "correct_answer".
For multiple_choice: set "correct_answer" to null.
"""

saved_count = 0

for topic, description in TARGETS:
    n = 3
    print(f"\nGenerating {n} questions for {topic}...")

    prompt = BATCH_PROMPT.format(n=n, topic=topic, description=description)

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=3000,
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
            print(f"  Saved [{q['difficulty']}] {q['question_type']}: {q['question_text'][:70]}")

        print(f"  -> {len(questions)} questions saved for {topic}")

    except Exception as e:
        print(f"  ERROR for {topic}: {e}", file=sys.stderr)
        import traceback; traceback.print_exc()

print(f"\nTotal saved this session: {saved_count} questions")
print(f"Files in data/questions/: {len(list(OUT_DIR.glob('*.json')))}")
