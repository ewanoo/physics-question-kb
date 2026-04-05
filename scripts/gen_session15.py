#!/usr/bin/env python3
"""Session 15: Generate questions for subtopics with lowest question counts."""

import json
import uuid
from datetime import datetime
from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()
QUESTIONS_DIR = Path("data/questions")
QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)

PROMPT = """Generate exactly {count} high-quality KS3 Year 8 UK physics questions for the following subtopics and difficulties:

{specs}

Rules:
- Accurate Year 8 UK KS3 physics (not A-level, not primary school)
- Mix types: ~50% multiple_choice, ~30% short_answer, ~20% calculation
- Difficulty: easy=recall a fact, medium=apply/1-step calc, hard=multi-step/evaluate
- multiple_choice: 4 options (A/B/C/D), exactly 1 correct, plausible distractors
- Explanations: 1-3 sentences, suitable for 12-year-olds
- Questions must be fresh and not repeat common examples

Return ONLY a JSON array of question objects. Each must have exactly these fields:
{{
  "question_text": "...",
  "question_type": "multiple_choice" | "short_answer" | "calculation",
  "difficulty": "easy" | "medium" | "hard",
  "topic": "topic.subtopic",
  "tags": ["tag1", "tag2"],
  "options": [{{"label": "A", "text": "...", "is_correct": false}}, ...] or null,
  "correct_answer": "string",
  "explanation": "...",
  "quality_score": 4 or 5
}}

For multiple_choice: options array of 4, exactly 1 has is_correct=true. correct_answer = text of correct option.
For short_answer/calculation: options = null, correct_answer = the answer.
No markdown, no extra text — just the JSON array."""


def generate(specs: list[tuple[str, str, int]], batch_label: str) -> list[dict]:
    """specs: list of (topic, difficulty, count)"""
    spec_lines = []
    total = 0
    for topic, diff, count in specs:
        spec_lines.append(f"- {topic} [{diff}]: {count} questions")
        total += count

    prompt = PROMPT.format(count=total, specs="\n".join(spec_lines))
    print(f"\n--- {batch_label}: requesting {total} questions ---")
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=14000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    questions = json.loads(text)
    print(f"  -> Parsed {len(questions)} questions")
    return questions


def save_question(q: dict) -> str:
    now = datetime.utcnow().isoformat()
    q_id = str(uuid.uuid4())
    record = {
        "id": q_id,
        "question_text": q["question_text"],
        "question_type": q["question_type"],
        "difficulty": q["difficulty"],
        "topic": q["topic"],
        "tags": q.get("tags", []),
        "options": q.get("options"),
        "correct_answer": q.get("correct_answer"),
        "explanation": q.get("explanation", ""),
        "quality_score": q.get("quality_score", 4),
        "source_name": "claude_generator",
        "scraped_at": now,
        "classified_at": now,
        "classification_confidence": 0.95,
        "year_group": "year8",
        "curriculum": "ks3",
        "source_url": f"claude://{q['topic']}/{q['difficulty']}",
        "raw_html": None,
    }
    path = QUESTIONS_DIR / f"{q_id}.json"
    path.write_text(json.dumps(record, indent=2))
    return q_id


def main():
    import subprocess

    grand_total = 0

    # Batch 1: 4 subtopics at 52 questions — add 5 each = 20 questions
    batch1_specs = [
        ("energy.efficiency", "easy", 2),
        ("energy.efficiency", "hard", 2),
        ("energy.efficiency", "medium", 1),
        ("forces.pressure", "easy", 2),
        ("forces.pressure", "hard", 2),
        ("forces.pressure", "medium", 1),
        ("space.gravity", "easy", 1),
        ("space.gravity", "medium", 2),
        ("space.gravity", "hard", 2),
        ("space.solar_system", "easy", 1),
        ("space.solar_system", "medium", 2),
        ("space.solar_system", "hard", 2),
    ]
    questions = generate(batch1_specs, "Batch 1 (weakest 4 subtopics, ~20 questions)")
    saved = 0
    for q in questions:
        save_question(q)
        saved += 1
        print(f"  [{q.get('topic')}] [{q.get('difficulty')}] {q.get('question_text','')[:55]}...")
    grand_total += saved
    print(f"  => Batch 1: saved {saved} questions")

    # Commit batch 1
    subprocess.run(["git", "add", "data/questions/"], check=True)
    subprocess.run(
        ["git", "commit", "-m",
         f"Session 15 batch 1: Add {saved} questions for energy.efficiency, forces.pressure, space.gravity, space.solar_system"],
        check=True
    )
    subprocess.run(["git", "push", "-u", "origin", "main"], check=True)
    print("  => Committed and pushed batch 1")

    # Batch 2: 10 subtopics at 53 questions — add 4 each = 40 questions
    batch2_specs = [
        ("energy.conservation", "easy", 1), ("energy.conservation", "medium", 2), ("energy.conservation", "hard", 1),
        ("energy.food", "easy", 1), ("energy.food", "medium", 1), ("energy.food", "hard", 2),
        ("energy.power", "easy", 1), ("energy.power", "medium", 2), ("energy.power", "hard", 1),
        ("forces.friction", "easy", 1), ("forces.friction", "medium", 1), ("forces.friction", "hard", 2),
        ("forces.gravity", "easy", 1), ("forces.gravity", "medium", 2), ("forces.gravity", "hard", 1),
        ("forces.moments", "easy", 1), ("forces.moments", "medium", 1), ("forces.moments", "hard", 2),
        ("forces.speed", "easy", 1), ("forces.speed", "medium", 2), ("forces.speed", "hard", 1),
        ("forces.springs", "easy", 1), ("forces.springs", "medium", 1), ("forces.springs", "hard", 2),
        ("matter.changes", "easy", 1), ("matter.changes", "medium", 2), ("matter.changes", "hard", 1),
        ("matter.density", "easy", 1), ("matter.density", "medium", 1), ("matter.density", "hard", 2),
    ]
    questions = generate(batch2_specs, "Batch 2 (10 subtopics at 53, ~40 questions)")
    saved = 0
    for q in questions:
        save_question(q)
        saved += 1
        print(f"  [{q.get('topic')}] [{q.get('difficulty')}] {q.get('question_text','')[:55]}...")
    grand_total += saved
    print(f"  => Batch 2: saved {saved} questions")

    # Commit batch 2
    subprocess.run(["git", "add", "data/questions/"], check=True)
    subprocess.run(
        ["git", "commit", "-m",
         f"Session 15 batch 2: Add {saved} questions for energy/forces/matter subtopics (53->57 each)"],
        check=True
    )
    subprocess.run(["git", "push", "-u", "origin", "main"], check=True)
    print("  => Committed and pushed batch 2")

    print(f"\nSession 15 complete: {grand_total} new questions saved and pushed.")


if __name__ == "__main__":
    main()
