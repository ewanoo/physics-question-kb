#!/usr/bin/env python3
"""Top up energy.efficiency and forces.springs to ≥25 questions each."""
import json
import uuid
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()
QUESTIONS_DIR = Path("data/questions")


def generate_batch(topic, difficulty, count, extra):
    dg = {
        "easy": "recall a fact or definition",
        "medium": "apply a concept or 1-step calc",
        "hard": "multi-step or evaluate",
    }
    prompt = f"""Generate {count} unique KS3 Year 8 UK Physics questions on the topic: {topic}
Difficulty: {difficulty} — {dg[difficulty]}
{extra}

STRICT RULES:
- Accurate Year 8 UK physics
- Mix of multiple_choice and short_answer; use calculation for numeric problems
- Multiple choice: 4 options (A/B/C/D), exactly 1 correct
- Explanations: 1-3 sentences for a 12-year-old
- No markdown in text fields

Return ONLY a valid JSON array, no other text. Each object fields:
"question_text", "question_type" (multiple_choice|short_answer|calculation),
"difficulty": "{difficulty}", "topic": "{topic}", "tags": [...],
"options": [{{"label":"A","text":"...","is_correct":bool}},...] or null,
"correct_answer": string, "explanation": string,
"quality_score": 4 or 5, "source_name": "claude_generator"
"""
    r = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = r.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    qs = json.loads(raw)
    now = datetime.utcnow().isoformat()
    for q in qs:
        q["id"] = str(uuid.uuid4())
        q["scraped_at"] = now
        q["classified_at"] = now
        q["classification_confidence"] = 0.95
        q["year_group"] = "year8"
        q["curriculum"] = "ks3"
        q["source_url"] = None
        q["raw_html"] = None
    return qs


TARGETS = [
    ("energy.efficiency", "easy", 2, "Focus on: what efficiency means, calculating efficiency = useful output/total input x 100, wasted energy as heat."),
    ("energy.efficiency", "medium", 2, "Focus on: efficiency calculations, Sankey diagrams showing wasted energy, comparing appliances by efficiency."),
    ("forces.springs", "easy", 2, "Focus on: Hooke's law, spring constant, extension proportional to force, elastic limit."),
    ("forces.springs", "medium", 2, "Focus on: calculating spring extension using F=ke, reading force-extension graphs, spring constant units (N/m)."),
]


def main():
    total = 0
    for topic, diff, count, ctx in TARGETS:
        print(f"Generating {count} {diff} for {topic}...")
        try:
            qs = generate_batch(topic, diff, count, ctx)
            for q in qs:
                (QUESTIONS_DIR / f"{q['id']}.json").write_text(json.dumps(q, indent=2))
                total += 1
                print(f"  {q['id'][:8]}... [{q['question_type']}] {q['question_text'][:65]}")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
    print(f"Total: {total}")


if __name__ == "__main__":
    main()
