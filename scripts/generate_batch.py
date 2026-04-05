#!/usr/bin/env python3
"""Generate a batch of questions for specified subtopics/difficulties."""
import json
import uuid
from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()
OUTPUT_DIR = Path("data/questions")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_questions(topic: str, difficulty: str, count: int, question_types: list[str] | None = None) -> list[dict]:
    """Generate `count` questions for the given topic+difficulty via Claude."""
    if question_types is None:
        question_types = ["multiple_choice", "multiple_choice", "short_answer"]  # 2:1 ratio

    subtopic_notes = {
        "energy.conservation": "conservation of energy, energy cannot be created or destroyed, energy transfers between stores",
        "electricity.circuits": "series and parallel circuits, switches, bulbs, cells, circuit symbols",
        "electricity.current_voltage": "current (amps), voltage (volts), measuring with ammeters/voltmeters",
        "electricity.electromagnets": "electromagnets, coils, iron cores, uses in relays/bells/cranes",
        "electricity.magnets": "magnetic fields, poles, attraction/repulsion, plotting field lines",
        "electricity.static": "static electricity, charging by friction, attraction/repulsion of charges",
        "energy.power": "power = energy transferred / time, watts, kilowatts, comparing power ratings",
        "energy.resources": "renewable and non-renewable energy resources, fossil fuels, wind/solar/nuclear",
        "forces.balanced": "balanced forces, equilibrium, resultant force = 0, stationary/constant velocity",
        "forces.gravity": "gravity, weight = mass × gravitational field strength, g = 10 N/kg on Earth",
        "forces.moments": "moments = force × distance, levers, pivots, turning effect",
        "forces.pressure": "pressure = force / area, units Pa or N/m², hydraulics",
        "forces.speed": "speed = distance / time, distance-time graphs, average speed, units m/s and km/h",
        "forces.friction": "friction force, surfaces, lubrication, grip, heat from friction",
        "forces.types": "contact and non-contact forces, gravity, magnetism, electrostatic, tension, normal reaction",
        "forces.springs": "Hooke's law, spring constant, extension = force / k, elastic limit",
        "matter.changes": "melting, freezing, evaporation, condensation, sublimation, boiling vs evaporation, latent heat",
        "matter.density": "density = mass / volume, g/cm³ or kg/m³, floating and sinking",
        "matter.particles": "particle model, atoms, molecules, arrangement in solids/liquids/gases",
        "matter.states": "states of matter, melting point, boiling point, changes of state",
        "matter.gas_pressure": "gas pressure, Boyle's law concept, pressure and temperature, compression",
        "space.gravity": "gravity in space, orbits, Moon's gravity vs Earth, weightlessness, tides",
        "space.solar_system": "8 planets in order, dwarf planets, asteroids, comets, moons, orbits, Milky Way",
        "space.earth_moon": "Moon phases, lunar cycle 28 days, tides, solar/lunar eclipses, Moon as natural satellite",
        "space.seasons": "seasons caused by Earth's tilt, not distance from Sun, solstice, equinox, day length",
        "waves.em_spectrum": "electromagnetic spectrum, radio waves to gamma rays, uses and dangers, speed of light",
        "waves.sound": "sound as longitudinal waves, speed of sound, pitch and frequency, loudness and amplitude, echo",
        "waves.light": "reflection, refraction, law of reflection, ray diagrams, transparent/translucent/opaque, shadows",
        "waves.colour": "white light dispersion, prism, ROYGBIV, colour filters, why objects appear coloured",
        "waves.properties": "amplitude, frequency, wavelength, wave speed = f × λ, transverse vs longitudinal waves",
        "energy.efficiency": "efficiency = useful energy out / total energy in × 100%, Sankey diagrams",
        "energy.food": "food as energy store, calories/joules, energy in diet, metabolic rate, food chains",
        "energy.stores": "kinetic, gravitational potential, elastic, thermal, chemical, nuclear, magnetic energy stores",
    }

    topic_note = subtopic_notes.get(topic, topic.replace(".", " ").replace("_", " "))
    difficulty_note = {
        "easy": "Recall a fact or definition (no calculation needed). Suitable for a confident Year 8 student who has just learned the topic.",
        "medium": "Apply a concept or do a simple 1-step calculation. Requires understanding, not just recall.",
        "hard": "Multi-step problem, comparison, evaluation, or extended reasoning. Challenging for Year 8.",
    }[difficulty]

    prompt = f"""You are writing KS3 Year 8 UK physics questions for a question bank.

Topic: {topic}
Topic focus: {topic_note}
Difficulty: {difficulty} — {difficulty_note}

Generate EXACTLY {count} questions. Return a JSON array (no other text) where each object has:
- "question_text": the question (clear, age-appropriate for 12-13 year olds)
- "question_type": one of "multiple_choice", "short_answer", "calculation"
- "difficulty": "{difficulty}"
- "topic": "{topic}"
- "tags": array of 2-4 relevant keyword strings
- "options": for multiple_choice ONLY — array of 4 objects: {{"label":"A","text":"...","is_correct":bool}} (exactly 1 correct); null for other types
- "correct_answer": for short_answer/calculation — a concise answer string; for multiple_choice — the label of the correct option e.g. "B"
- "explanation": 1-3 sentences explaining the correct answer, suitable for a 12-year-old
- "quality_score": 4 or 5
- "source_name": "claude_generator"

Rules:
- Multiple choice: 4 plausible options, exactly 1 correct, distractors are NOT silly
- Short answer: answer should be 1-2 sentences max
- Calculation: always include units in the answer
- Do NOT include any question that tests A-level or primary school content
- Vary the question_type: aim for roughly {count//2} multiple_choice and the rest short_answer/calculation
- Each question must be clearly different from the others
- Do not start every question with "What is..."

Return ONLY the JSON array."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()

    questions = json.loads(text)
    return questions


def save_questions(questions: list[dict]) -> int:
    saved = 0
    for q in questions:
        qid = str(uuid.uuid4())
        q["id"] = qid
        # Ensure options is proper format for multiple_choice
        if q.get("question_type") == "multiple_choice" and q.get("options"):
            opts = q["options"]
            if opts and isinstance(opts[0], str):
                # Malformed - skip
                print(f"  SKIP malformed options: {q['question_text'][:50]}")
                continue
        filepath = OUTPUT_DIR / f"{qid}.json"
        filepath.write_text(json.dumps(q, indent=2))
        saved += 1
    return saved


def main():
    # Target slots: (topic, difficulty, count)
    # Targeting the 9 weakest subtopics (68-69 questions each)
    targets = [
        # waves.light (68) — add 4
        ("waves.light", "easy", 2),
        ("waves.light", "hard", 2),
        # waves.properties (68) — add 4
        ("waves.properties", "easy", 2),
        ("waves.properties", "hard", 2),
        # waves.sound (68) — add 4
        ("waves.sound", "easy", 2),
        ("waves.sound", "hard", 2),
        # forces.gravity (69) — add 4
        ("forces.gravity", "easy", 2),
        ("forces.gravity", "hard", 2),
        # forces.speed (69) — add 4
        ("forces.speed", "easy", 2),
        ("forces.speed", "hard", 2),
        # matter.changes (69) — add 4
        ("matter.changes", "easy", 2),
        ("matter.changes", "hard", 2),
        # space.earth_moon (69) — add 4
        ("space.earth_moon", "easy", 2),
        ("space.earth_moon", "hard", 2),
        # space.solar_system (69) — add 4
        ("space.solar_system", "easy", 2),
        ("space.solar_system", "hard", 2),
        # waves.colour (69) — add 4
        ("waves.colour", "easy", 2),
        ("waves.colour", "hard", 2),
    ]

    total = 0
    for topic, difficulty, count in targets:
        print(f"Generating {count}x {topic}/{difficulty}...", end=" ", flush=True)
        try:
            qs = generate_questions(topic, difficulty, count)
            saved = save_questions(qs)
            total += saved
            print(f"saved {saved}")
        except Exception as e:
            print(f"ERROR: {e}")

    print(f"\nDone. Total saved: {total}")


if __name__ == "__main__":
    main()
