#!/usr/bin/env python3
"""Session 13: Generate new questions targeting weak subtopics."""
import anthropic
import json
import re
import uuid
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()

targets = [
    ("electricity.current_voltage", "easy", "Ohm's Law, voltage, current, resistance definitions, units, reading ammeters/voltmeters"),
    ("electricity.current_voltage", "hard", "multi-step Ohm's Law problems, comparing circuits, evaluating experimental data"),
    ("forces.moments", "medium", "calculating moments, principle of moments, see-saws, levers, pivot"),
    ("forces.balanced", "easy", "Newton's first law, balanced vs unbalanced forces, resultant force equals zero"),
    ("forces.balanced", "hard", "multi-step resultant force problems, free body diagrams analysis, Newton's laws applied"),
    ("matter.gas_pressure", "easy", "gas pressure basics, particle model, compressing gases"),
    ("waves.colour", "easy", "colours of light, white light splitting, primary colours of light, absorption and reflection"),
    ("waves.colour", "hard", "colour filters, mixing coloured light, why objects appear different colours under different lights"),
    ("waves.properties", "easy", "wave vocabulary: amplitude, frequency, wavelength, period, crest, trough"),
    ("waves.properties", "hard", "wave calculations: wave speed = frequency x wavelength, multi-step problems"),
    ("waves.em_spectrum", "easy", "names of EM waves in order, visible light position, radio waves vs gamma rays"),
    ("waves.em_spectrum", "hard", "applications of EM waves, health dangers, comparing properties across spectrum"),
]

DIFF_GUIDES = {
    "easy": "recall a fact or definition, no calculation needed",
    "medium": "apply a concept or do a simple 1-step calculation",
    "hard": "multi-step problem, compare/evaluate, extended reasoning",
}

PROMPT_TEMPLATE = """Generate exactly 3 KS3 Year 8 UK Physics questions about: {subtopic} ({difficulty} difficulty).
Focus: {hints}
Difficulty guide: {diff_guide}

Rules:
- Aim for 2 multiple_choice and 1 short_answer or calculation
- Each question tests a DIFFERENT specific concept
- Multiple choice: 4 options, exactly 1 correct, plausible distractors
- short_answer/calculation: correct_answer is a concise string
- Explanation: 1-3 sentences for a 12-year-old

Return ONLY a JSON array of exactly 3 question objects. Each object has these fields:
- question_text (string)
- question_type: "multiple_choice" | "short_answer" | "calculation"
- difficulty: "{difficulty}"
- topic: "{subtopic}"
- tags: array of 2-3 strings
- options: array of 4 objects [{{"label":"A","text":"...","is_correct":bool}}] or null
- correct_answer: null (for multiple_choice) or string
- explanation: string
- quality_score: 4 or 5
- source_name: "claude_generator"
"""


def strip_fences(text):
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def generate_batch(subtopic, difficulty, hints):
    prompt = PROMPT_TEMPLATE.format(
        subtopic=subtopic,
        difficulty=difficulty,
        hints=hints,
        diff_guide=DIFF_GUIDES[difficulty],
    )
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
    )
    text = strip_fences(msg.content[0].text)
    return json.loads(text)


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
