#!/usr/bin/env python3
"""Session 33: Generate questions for difficulty gaps in weak subtopics."""
import json
import uuid
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv()

client = anthropic.Anthropic()
OUTPUT_DIR = Path("data/questions")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load existing questions to avoid duplicates
existing_texts = set()
for f in OUTPUT_DIR.glob("*.json"):
    try:
        data = json.loads(f.read_text())
        existing_texts.add(data.get("question_text", "").strip().lower()[:100])
    except Exception:
        pass

print(f"Loaded {len(existing_texts)} existing question texts for dedup check")

TARGETS = [
    ("energy.power", "hard", 7),
    ("forces.speed", "hard", 7),
    ("energy.stores", "medium", 7),
    ("waves.em_spectrum", "medium", 7),
    ("waves.properties", "medium", 7),
]

TOPIC_CONTEXT = {
    "energy.power": "power calculations (P=E/t, P=W/t), watts, kilowatts, comparing power of different appliances, power and time relationships, energy cost",
    "forces.speed": "distance-time graphs, speed=distance/time, average speed, instantaneous speed, speed-time graphs, acceleration calculations, relative speed",
    "energy.stores": "thermal, kinetic, gravitational potential, chemical, elastic, nuclear, electromagnetic energy stores; energy transfers between stores; dissipation",
    "waves.em_spectrum": "electromagnetic spectrum order (radio, microwave, infrared, visible, UV, X-ray, gamma), uses of each type, dangers, wavelength and frequency relationships, speed of light",
    "waves.properties": "amplitude, wavelength, frequency, wave speed equation (v=fλ), transverse vs longitudinal waves, reflection, refraction, diffraction, period",
}

DIFFICULTY_GUIDE = {
    "easy": "recall a fact or definition (no calculation needed, straightforward knowledge check)",
    "medium": "apply a concept or do a simple 1-step calculation",
    "hard": "multi-step problem, compare/evaluate different scenarios, or extended reasoning required",
}

def generate_batch(topic: str, difficulty: str, count: int) -> list:
    context = TOPIC_CONTEXT.get(topic, topic)
    diff_guide = DIFFICULTY_GUIDE[difficulty]

    prompt = f"""Generate {count} high-quality KS3 Year 8 UK physics questions about: {topic}
Context for this subtopic: {context}

Difficulty: {difficulty} — {diff_guide}

Requirements:
- Accurate UK KS3 Year 8 physics (NOT A-level, NOT primary school)
- Mix question types: multiple_choice (about half), short_answer and calculation (rest)
- For multiple_choice: exactly 4 options, exactly 1 correct, plausible distractors (not silly wrong answers)
- Explanations: clear, 1-3 sentences, suitable for a 12-year-old
- Questions must be DISTINCT from each other and from common textbook questions
- Difficulty level must be appropriate: {diff_guide}

Return a JSON array of {count} question objects. Each object must have EXACTLY these fields:
- "question_text": string
- "question_type": "multiple_choice" | "short_answer" | "calculation"
- "difficulty": "{difficulty}"
- "topic": "{topic}"
- "tags": array of 2-4 relevant string tags
- "options": for multiple_choice: [{{"label": "A", "text": "...", "is_correct": false}}, ...] (4 items, exactly 1 is_correct=true); for others: null
- "correct_answer": for short_answer/calculation: concise answer string; for multiple_choice: null
- "explanation": string (1-3 sentences)
- "quality_score": 4 or 5
- "source_name": "claude_generator"

Return ONLY the JSON array, no other text."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    return json.loads(text)


def save_question(q: dict) -> str:
    qid = str(uuid.uuid4())
    q["id"] = qid
    path = OUTPUT_DIR / f"{qid}.json"
    path.write_text(json.dumps(q, indent=2))
    return qid


total_saved = 0
for topic, difficulty, count in TARGETS:
    print(f"\nGenerating {count} {difficulty} questions for {topic}...")
    try:
        questions = generate_batch(topic, difficulty, count)
        saved = 0
        for q in questions:
            text_key = q.get("question_text", "").strip().lower()[:100]
            if text_key in existing_texts:
                print(f"  SKIP (duplicate): {q['question_text'][:60]}")
                continue
            existing_texts.add(text_key)
            qid = save_question(q)
            saved += 1
            total_saved += 1
            print(f"  [{saved}] {q['question_type']:16s} | {q['question_text'][:65]}")
        print(f"  => {saved}/{len(questions)} saved for {topic} {difficulty}")
    except Exception as e:
        import traceback
        print(f"  ERROR: {e}")
        traceback.print_exc()

print(f"\nTotal questions saved this session: {total_saved}")
