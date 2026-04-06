#!/usr/bin/env python3
"""Session 33b: Second batch — target more subtopic/difficulty gaps."""
import json
import uuid
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv()

client = anthropic.Anthropic()
OUTPUT_DIR = Path("data/questions")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

existing_texts = set()
for f in OUTPUT_DIR.glob("*.json"):
    try:
        data = json.loads(f.read_text())
        existing_texts.add(data.get("question_text", "").strip().lower()[:100])
    except Exception:
        pass

print(f"Loaded {len(existing_texts)} existing question texts for dedup check")

# Target next-weakest: count=31-32 difficulty combos
TARGETS = [
    ("energy.conservation", "easy", 7),
    ("forces.balanced", "hard", 7),
    ("forces.gravity", "hard", 7),
    ("forces.friction", "hard", 7),
    ("matter.gas_pressure", "easy", 7),
]

TOPIC_CONTEXT = {
    "energy.conservation": "conservation of energy law (energy cannot be created or destroyed), energy transfers, useful vs wasted energy, Sankey diagrams, energy in different scenarios",
    "forces.balanced": "balanced and unbalanced forces, resultant force, Newton's first and second laws, force diagrams, free body diagrams, equilibrium conditions",
    "forces.gravity": "weight vs mass, W=mg, gravitational field strength, falling objects, terminal velocity, gravitational potential energy, weight on different planets",
    "forces.friction": "friction force, static vs dynamic friction, factors affecting friction, lubrication, air resistance, effects of friction in real-world contexts, streamlining",
    "matter.gas_pressure": "gas pressure and particle collisions, pressure-volume relationship (Boyle's Law), pressure-temperature relationship, gas laws, atmospheric pressure, Pascal's principle",
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
- For multiple_choice: exactly 4 options, exactly 1 correct, plausible distractors
- Explanations: clear, 1-3 sentences, suitable for a 12-year-old
- Questions must be DISTINCT from each other
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

print(f"\nTotal questions saved this batch: {total_saved}")
