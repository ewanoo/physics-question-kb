#!/usr/bin/env python3
"""Generate questions for weak subtopic/difficulty slots."""
import anthropic
import json
import uuid
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()
QUESTIONS_DIR = Path("data/questions")
QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)

def generate_batch(slots: list, questions_per_slot: int = 2) -> list:
    """Generate questions for a list of (topic, difficulty) slots."""

    slot_descriptions = []
    for topic, difficulty in slots:
        slot_descriptions.append(f"  - {topic} / {difficulty} ({questions_per_slot} questions)")

    difficulty_guide = """
Difficulty guidelines:
- easy: recall a fact or definition, no calculation needed
- medium: apply a concept, simple 1-step calculation
- hard: multi-step problem, compare/evaluate, extended reasoning
"""

    prompt = f"""You are generating KS3 Year 8 UK Physics questions for a question bank.
Generate exactly {questions_per_slot} questions for each of these topic/difficulty combinations:
{chr(10).join(slot_descriptions)}

{difficulty_guide}

Requirements:
- Accurate Year 8 UK physics content (12-13 year olds)
- Multiple choice: 4 options (A/B/C/D), exactly 1 correct, plausible distractors
- Mix of multiple_choice (~60%), short_answer (~25%), calculation (~15%)
- For short_answer and calculation: options = null, correct_answer = full answer string
- For multiple_choice: options array with label, text, is_correct fields; correct_answer = just the letter
- Explanations: clear, 1-3 sentences, suitable for a 12-year-old
- Do NOT duplicate obvious/trivial questions

Return a JSON array. Each question object must have exactly these fields:
- id: generate a new UUID v4 string
- question_text: the question (string)
- question_type: "multiple_choice", "short_answer", or "calculation"
- difficulty: "easy", "medium", or "hard"
- topic: the subtopic slug (e.g. "forces.gravity")
- tags: array of 2-4 relevant keyword strings
- options: array of {{label, text, is_correct}} objects for MC, or null otherwise
- correct_answer: the answer string (for MC: just the letter like "B")
- explanation: clear explanation (1-3 sentences)
- quality_score: 4 or 5 (integer)
- source_name: "claude_generator"

Return ONLY the JSON array, no other text."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    return json.loads(text)


def save_question(q: dict) -> Path:
    """Save a question to data/questions/{id}.json with full metadata."""
    now = datetime.utcnow().isoformat()
    # Always assign a fresh UUID to avoid overwriting existing questions
    q["id"] = str(uuid.uuid4())
    q.setdefault("source_url", f"claude://{q['topic']}/{q['difficulty']}")
    q.setdefault("scraped_at", now)
    q.setdefault("classified_at", now)
    q.setdefault("classification_confidence", 0.95)
    q.setdefault("year_group", "year8")
    q.setdefault("curriculum", "ks3")
    q.setdefault("raw_html", None)

    path = QUESTIONS_DIR / f"{q['id']}.json"
    with open(path, "w") as f:
        json.dump(q, f, indent=2)
    return path


def main():
    # All 40 weakest slots (all at 19 questions each)
    weak_slots = [
        ("electricity.current_voltage", "easy"),
        ("electricity.current_voltage", "hard"),
        ("electricity.magnets", "hard"),
        ("electricity.static", "easy"),
        ("electricity.static", "hard"),
        ("energy.conservation", "easy"),
        ("energy.efficiency", "easy"),
        ("energy.efficiency", "hard"),
        ("energy.efficiency", "medium"),
        ("energy.food", "easy"),
        ("energy.food", "hard"),
        ("energy.food", "medium"),
        ("energy.resources", "easy"),
        ("energy.resources", "hard"),
        ("energy.stores", "hard"),
        ("forces.balanced", "easy"),
        ("forces.balanced", "medium"),
        ("forces.friction", "easy"),
        ("forces.friction", "hard"),
        ("forces.friction", "medium"),
        ("forces.gravity", "easy"),
        ("forces.moments", "hard"),
        ("forces.pressure", "easy"),
        ("forces.pressure", "hard"),
        ("forces.speed", "easy"),
        ("forces.springs", "easy"),
        ("forces.springs", "hard"),
        ("forces.springs", "medium"),
        ("forces.types", "hard"),
        ("matter.changes", "easy"),
        ("matter.density", "hard"),
        ("matter.gas_pressure", "hard"),
        ("matter.particles", "medium"),
        ("matter.states", "hard"),
        ("space.gravity", "hard"),
        ("space.solar_system", "easy"),
        ("space.solar_system", "hard"),
        ("waves.colour", "easy"),
        ("waves.colour", "hard"),
        ("waves.colour", "medium"),
    ]

    # Process in batches of 10 slots
    batch_size = 10
    total_saved = 0

    for batch_start in range(0, len(weak_slots), batch_size):
        batch = weak_slots[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        print(f"\n=== Batch {batch_num} ({len(batch)} slots) ===")
        for s in batch:
            print(f"  {s[0]}/{s[1]}")

        try:
            questions = generate_batch(batch, questions_per_slot=2)
            print(f"Generated {len(questions)} questions")

            saved = 0
            for q in questions:
                try:
                    path = save_question(q)
                    saved += 1
                except Exception as e:
                    print(f"  Error saving question: {e}")

            total_saved += saved
            print(f"Saved {saved}/{len(questions)} questions (total so far: {total_saved})")

        except Exception as e:
            print(f"Batch {batch_num} failed: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n=== Done. Total new questions: {total_saved} ===")


if __name__ == "__main__":
    main()
