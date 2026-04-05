#!/usr/bin/env python3
"""Session 17: Generate questions for the 7 weakest subtopics."""
import json
import uuid
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import anthropic

load_dotenv()

client = anthropic.Anthropic()
QUESTIONS_DIR = Path("data/questions")
QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)


def generate_batch(slots: list, questions_per_slot: int = 6) -> list:
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
- Multiple choice: 4 options (A/B/C/D), exactly 1 correct, plausible distractors (not silly/obvious)
- Mix of multiple_choice (~55%), short_answer (~25%), calculation (~20%)
- For short_answer and calculation: options = null, correct_answer = full answer string
- For multiple_choice: options array with label, text, is_correct fields; correct_answer = just the letter
- Explanations: clear, 1-3 sentences, suitable for a 12-year-old
- Each question must be distinct and non-trivial

Return a JSON array. Each question object must have exactly these fields:
- id: generate a new UUID v4 string
- question_text: the question (string)
- question_type: "multiple_choice", "short_answer", or "calculation"
- difficulty: "easy", "medium", or "hard"
- topic: the subtopic slug (e.g. "waves.properties")
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
    now = datetime.utcnow().isoformat()
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
    # Weakest subtopics (70-71 total questions each):
    # energy.resources=70, matter.states=70, energy.efficiency=71,
    # energy.food=71, forces.springs=71, matter.gas_pressure=71, space.gravity=71
    batches = [
        # Batch 1: energy.resources (easy + hard are weakest at 23)
        [
            ("energy.resources", "easy"),
            ("energy.resources", "hard"),
            ("matter.states", "medium"),
        ],
        # Batch 2: matter.states + energy.efficiency
        [
            ("matter.states", "hard"),
            ("energy.efficiency", "easy"),
            ("energy.efficiency", "hard"),
        ],
        # Batch 3: energy.food + forces.springs
        [
            ("energy.food", "easy"),
            ("energy.food", "hard"),
            ("forces.springs", "easy"),
        ],
        # Batch 4: forces.springs + matter.gas_pressure + space.gravity
        [
            ("forces.springs", "hard"),
            ("matter.gas_pressure", "hard"),
            ("space.gravity", "easy"),
            ("space.gravity", "medium"),
        ],
    ]

    total_saved = 0

    for i, batch in enumerate(batches, 1):
        print(f"\n=== Batch {i}/{len(batches)} ===")
        for s in batch:
            print(f"  {s[0]}/{s[1]}")

        try:
            questions = generate_batch(batch, questions_per_slot=4)
            print(f"  Generated {len(questions)} questions")

            saved = 0
            for q in questions:
                try:
                    save_question(q)
                    saved += 1
                except Exception as e:
                    print(f"  Error saving: {e}")

            total_saved += saved
            print(f"  Saved {saved} (running total: {total_saved})")

            # Commit after each batch
            import subprocess
            result = subprocess.run(
                ["git", "add", "data/questions/"],
                capture_output=True, text=True
            )
            topics = ", ".join(f"{s[0]}" for s in batch)
            msg = f"Session 17 batch {i}: {len(questions)} questions for {topics}"
            result = subprocess.run(
                ["git", "commit", "-m", msg],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"  Committed: {msg}")
            else:
                print(f"  Commit output: {result.stdout} {result.stderr}")

        except Exception as e:
            print(f"  Batch {i} FAILED: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n=== Done. Total new questions: {total_saved} ===")


if __name__ == "__main__":
    main()
