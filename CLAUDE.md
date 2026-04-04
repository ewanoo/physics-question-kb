# Physics Question Knowledge Base — Autonomous Build Agent

## Mission

You are an autonomous agent building a KS3 / Year 8 UK Physics question knowledge base.
This repo is scaffolded with data models, taxonomy, config, and a database layer.
**Your job is to build the rest**: scrapers, classifier, deduplicator, storage, agent loop, and CLI.

Each session, read STATUS.md, pick up where you left off, make concrete progress,
run tests, update STATUS.md, and commit. The project is done when all completion
criteria in STATUS.md are met.

---

## Session Setup (run at the very start of every session, before anything else)

Your session prompt contains two secret values. Extract them and configure the environment:

```bash
# 1. Configure git to push using the GitHub PAT from your prompt
git config user.email "physics-kb-agent@autonomous.ai"
git config user.name "Physics KB Agent"
git remote set-url origin https://GITHUB_PAT@github.com/ewanoo/physics-question-kb.git

# 2. Write the Anthropic API key to .env so Python scripts can use it
echo "ANTHROPIC_API_KEY=YOUR_API_KEY" > .env
```

Replace `GITHUB_PAT` and `YOUR_API_KEY` with the values from your session prompt.
The `.env` file is gitignored — never commit it.

---

## Session Protocol (follow every run)

1. **Run Session Setup** — configure git remote and write .env (see above)
2. **Read STATUS.md** — understand the current phase and any blocked items
3. **Determine next action** — what's the next incomplete step in the current phase?
4. **Do the work** — implement, test, fix, iterate
5. **Run tests**: `python -m pytest tests/ -v` — fix failures before moving on
6. **Update STATUS.md** — record what you did, statistics (questions found, errors), and any new blocked items
7. **Commit and push**: `git add -A && git commit -m "Descriptive message" && git push`
8. If a phase is fully complete, advance `Current Phase` in STATUS.md

**Rule**: Always push at the end of every session. If push fails, investigate — don't skip it.

---

## Environment Setup (run on first session if not already done)

```bash
# Check Python version (need 3.11+)
python --version

# Install uv if not available
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv and install dependencies
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Verify
python -m pytest tests/ -v
```

If `ANTHROPIC_API_KEY` is not in the environment, the classification step will fail.
Check with `echo $ANTHROPIC_API_KEY`. If empty, the agent can still build and test
scrapers using mock data — flag this in STATUS.md under Blocked Items.

---

## Build Phases

Work through these phases in order. Each phase has a clear done condition.

---

### Phase 1: Scraper Foundation

**Goal**: Build the base scraper infrastructure that all scrapers share.

**Files to create**:
- `src/scraper/base.py` — Abstract `BaseScraper` class
- `src/scraper/utils.py` — HTTP helpers
- `tests/test_scraper_base.py` — Tests for utils

**`BaseScraper` must provide**:
```python
class BaseScraper(ABC):
    name: str                  # e.g. "bbc_bitesize"
    base_url: str

    @abstractmethod
    def discover_urls(self, topic_slugs: list[str] | None = None) -> list[str]:
        """Return URLs to scrape for given topics (or all topics if None)."""
        ...

    @abstractmethod
    def scrape_url(self, url: str) -> list[ScraperResult]:
        """Extract raw questions from a single page. Returns empty list on failure."""
        ...

    def fetch(self, url: str) -> str:
        """GET with retries, timeout, random user-agent. Returns HTML or raises."""
        ...
```

**`utils.py` must provide**:
- `get_html(url, retries=3, timeout=30, delay=1.5)` — HTTP GET with retry + backoff
- A list of 5+ realistic browser User-Agent strings to rotate
- `extract_text(html)` — strip HTML tags, normalise whitespace
- `safe_get(url)` — like get_html but returns None instead of raising

**Done condition**: `pytest tests/test_scraper_base.py -v` passes (mock HTTP, no live requests in tests)

---

### Phase 2: Scrapers (build one at a time)

For each scraper: implement → write fixture test → run live scrape → record results in STATUS.md.

**Important**: This agent runs in a cloud environment. Sites like BBC Bitesize and SaveMyExams
often return 403 from cloud IPs. **Prioritise API-based sources first** — they work reliably
from cloud. Fall back to HTML scraping sources only if APIs yield insufficient questions.

**Priority order** (skip one if blocked, come back later):

#### 2a. Isaac Physics (API-based — start here)
- File: `src/scraper/isaac_physics.py`
- Base: `https://isaacphysics.org`
- Try the API first: `https://isaacphysics.org/api/pages/questions?tags=ks3,physics`
- Also try: `/api/pages?tags=physics_skills_1` and other topic tags
- Questions are well-structured JSON if using the API
- Expected yield: 100–300 questions

#### 2b. Oak National Academy
- File: `src/scraper/oak_national.py`
- Base: `https://www.thenational.academy/teachers/programmes/physics-secondary-ks3`
- Lesson quizzes contain MCQ questions
- Expected yield: 50–100 questions

#### 2c. CK-12 (API-based)
- File: `src/scraper/ck12.py`
- Base: `https://www.ck12.org`
- Explore the public API for practice questions — check `https://api.ck12.org`
- Map topics to KS3 taxonomy
- Expected yield: 50–150 questions

#### 2d. BBC Bitesize (may 403 from cloud — try anyway)
- File: `src/scraper/bbc_bitesize.py`
- KS3 Physics hub: `https://www.bbc.co.uk/bitesize/subjects/zh2xsbk`
- Navigate topic pages, find practice questions and test sections
- If 403 is returned, log it and skip — don't retry
- Expected yield: 50–150 questions (if accessible)

#### 2e. SaveMyExams (may 403 from cloud — try anyway)
- File: `src/scraper/savemyexams.py`
- Base: `https://www.savemyexams.com/ks3/physics/`
- Focus on freely accessible topic questions (avoid paywalled content)
- If 403 or paywall detected, skip gracefully
- Expected yield: 20–80 questions (free tier only)

**For each scraper, create a test in `tests/test_scrapers/`**:
- Load a saved HTML fixture (real page saved as a file) and test parsing
- Do NOT make live HTTP requests in tests
- Save fixture HTML: `tests/fixtures/{source_name}_sample.html`

**After building each scraper, run it live**:
```bash
python -c "
from src.scraper.bbc_bitesize import BBCBitesizeScraper
s = BBCBitesizeScraper()
urls = s.discover_urls()
print(f'Found {len(urls)} URLs')
results = s.scrape_url(urls[0])
print(f'Scraped {len(results)} questions from first page')
for r in results[:2]:
    print(r.raw_question_text[:100])
"
```

Save raw results to `data/raw/{source_name}/` as JSON files.

**Done condition**: At least 3 scrapers are working, raw data saved to `data/raw/`

---

### Phase 3: Classification

**Goal**: Use Claude to classify raw scraped questions into the taxonomy.

**File to create**: `src/classifier.py`

**Interface**:
```python
def classify_question(raw: ScraperResult, settings: Settings) -> Question | None:
    """
    Call Claude to classify a raw question. Returns None if question is invalid/unusable.
    Uses classification_model (Haiku) by default.
    Escalates to evaluation_model (Sonnet) if confidence < 0.7.
    """
    ...

def classify_batch(raws: list[ScraperResult], settings: Settings) -> list[Question]:
    """Classify a batch of raw results. Skip failures, log them."""
    ...
```

**Classification prompt** — include all of this context:
- The full TAXONOMY from `src/taxonomy.py`
- The raw question text, options, and source URL
- Ask Claude to return JSON with: `topic`, `difficulty` (easy/medium/hard), `question_type`, `tags`, `correct_answer`, `explanation`, `confidence` (0-1), `is_valid_ks3` (bool), `quality_score` (1-5), `cleaned_question_text`

**Difficulty guidelines for the prompt**:
- `easy`: recall a fact or definition (no calculation needed)
- `medium`: apply a concept, simple 1-step calculation
- `hard`: multi-step problem, compare/evaluate, extended reasoning

**Filter out**:
- `is_valid_ks3 = false`
- `quality_score < 2.5`
- `confidence < 0.5` (even after Sonnet escalation)

**Cost note**: Use Haiku for all classifications. Only use Sonnet for re-checks on
low-confidence items. This keeps classification cost under $2 for 1000 questions.

**Done condition**: Can classify 10 raw questions, all produce valid Question objects stored in DB

---

### Phase 4: Deduplication

**Goal**: Avoid storing near-identical questions from different sources.

**File to create**: `src/deduplicator.py`

**Strategy**:
1. Before inserting a question, compute a normalised fingerprint of the question text
   (lowercase, strip punctuation, split to sorted word set)
2. Check if any existing question in the DB has a very similar fingerprint (Jaccard similarity > 0.85)
3. If potential duplicate found, use Claude to confirm: "Are these two questions testing the same thing?"
4. Keep the higher quality_score version

```python
def is_duplicate(question: Question, db_path: Path) -> bool:
    """Check if this question is a duplicate of something already in the DB."""
    ...

def deduplicate_db(db_path: Path, settings: Settings) -> int:
    """Scan entire DB for duplicates, remove lower-quality ones. Returns count removed."""
    ...
```

**Done condition**: Deduplication runs on the existing DB without errors

---

### Phase 5: Storage

**Goal**: Persist questions to S3 if available; always persist to SQLite + local files.

**File to create**: `src/storage.py`

**Interface**:
```python
class StorageBackend(Protocol):
    def save_question(self, question: Question) -> None: ...
    def load_question(self, question_id: str) -> Question | None: ...
    def save_coverage_report(self, report: CoverageReport) -> None: ...

class LocalStorage:
    """Saves JSON files to data/questions/{id}.json"""
    ...

class S3Storage:
    """Saves to s3://{bucket}/questions/{id}.json"""
    ...

def get_storage(settings: Settings) -> StorageBackend:
    """Returns LocalStorage or S3Storage depending on settings."""
    ...
```

If `STORAGE_BACKEND=local` (the default), use `LocalStorage` only.
If S3 credentials are not configured, fall back to LocalStorage and log a warning.

**Done condition**: Can save and load 10 questions via the storage layer

---

### Phase 6: Coverage Analysis & Gap Filling

**Goal**: Understand what's in the KB and target weak areas.

**File to create**: `src/agent/evaluator.py`

```python
def build_coverage_report(db_path: Path, settings: Settings) -> CoverageReport:
    """
    Analyse the database and return a CoverageReport.
    is_complete = True when all completion criteria are met.
    """
    ...

def get_weak_topics(report: CoverageReport) -> list[str]:
    """Return subtopic slugs that are below the minimum question threshold."""
    ...
```

**Completion criteria** (all must be true for `is_complete = True`):
- Total questions >= 500
- All 33 subtopic slugs have at least 5 questions
- All three difficulty levels (easy/medium/hard) have at least 50 questions each
- At least 3 different sources represented
- Mean quality score >= 3.5 (if quality scoring has been run)

Also create `src/agent/planner.py`:

```python
def decide_next_action(report: CoverageReport, scraped_urls: set[str]) -> dict:
    """
    Given coverage gaps, decide what to scrape next.
    Returns: {"scraper": "bbc_bitesize", "topic_hints": ["electricity.circuits"],
              "reason": "electricity.circuits has only 2 questions"}
    """
    ...
```

Save the coverage report to `data/coverage_report.json` after generating.

**Done condition**: Coverage report generates correctly, weak topics identified

---

### Phase 7: Full Agent Loop

**Goal**: Wire everything together into an autonomous loop.

**File to create**: `src/agent/loop.py`

```python
def run_agent_session(settings: Settings, max_iterations: int = 50) -> None:
    """
    Run one session of the autonomous agent loop.
    Designed to be called repeatedly (each remote agent run calls this).
    Stops when max_iterations reached or KB is complete.
    """
    state = load_state()  # Load from data/agent_state.json

    for i in range(max_iterations):
        # 1. Evaluate
        report = build_coverage_report(db_path, settings)
        if report.is_complete:
            log("KB complete! All criteria met.")
            save_state({...status: "complete"})
            break

        # 2. Plan
        action = decide_next_action(report, get_scraped_urls(db_path))

        # 3. Scrape
        scraper = get_scraper(action["scraper"])
        urls = scraper.discover_urls(action.get("topic_hints"))
        # Filter already-scraped URLs
        urls = [u for u in urls if u not in get_scraped_urls(db_path)][:5]

        # 4. Process
        for url in urls:
            try:
                raws = scraper.scrape_url(url)
                for raw in raws:
                    q = classify_question(raw, settings)
                    if q and not is_duplicate(q, db_path):
                        insert_question(db_path, q)
                        storage.save_question(q)
                log_scrape(db_path, url, scraper.name, "success", len(raws))
            except Exception as e:
                log_scrape(db_path, url, scraper.name, "error", error_message=str(e))

        save_state({...})
```

Also create a simple entry point `main.py` in the repo root:
```python
#!/usr/bin/env python3
"""Entry point for the autonomous agent. Run: python main.py"""
from src.config import get_settings
from src.agent.loop import run_agent_session

if __name__ == "__main__":
    settings = get_settings()
    run_agent_session(settings)
```

**Done condition**: `python main.py` runs without crashing, scrapes at least 1 URL, stores questions

---

### Phase 8: CLI Tool

**Goal**: A working command-line tool to query the knowledge base.

**File to create**: `src/cli/query.py`

```bash
# Example usage:
physics-q --topic electricity --difficulty easy --count 10
physics-q --topic forces.speed --count 5
physics-q --list-topics
physics-q --stats
physics-q --random --count 20
```

Use `click` for argument parsing and `rich` for formatted output.

Format each question like this:
```
  Q1  [electricity.circuits]  [easy]  [multiple_choice]
  ──────────────────────────────────────────────────────────
  What happens to the current when you add a bulb in series?

  A) Increases
  B) Decreases  ✓
  C) Stays the same
  D) Doubles

  Explanation: Adding a bulb increases resistance, decreasing current.
  Source: BBC Bitesize
```

**Done condition**: `physics-q --stats` shows real data, `physics-q --topic forces --count 3` returns 3 questions

---

### Phase 9: Quality Pass & Completion

**Goal**: Ensure the KB meets all completion criteria.

1. Run `python main.py` until `data/coverage_report.json` shows `is_complete: true`
2. Run full deduplication: `python -c "from src.deduplicator import deduplicate_db; ..."`
3. Run all tests: `python -m pytest tests/ -v`
4. Update STATUS.md with final statistics and mark as **COMPLETE**

---

## Taxonomy Reference

The complete taxonomy is in `src/taxonomy.py`. The 6 top-level topics and their subtopics:

| Topic | Subtopics | Target count |
|-------|-----------|-------------|
| energy | stores, conservation, resources, efficiency, power, food | 30 |
| forces | types, gravity, friction, balanced, speed, pressure, moments, springs | 40 |
| waves | properties, sound, light, colour, em_spectrum | 30 |
| electricity | circuits, current_voltage, static, magnets, electromagnets | 30 |
| matter | particles, states, changes, density, gas_pressure | 25 |
| space | solar_system, earth_moon, seasons, gravity | 20 |

Total: 33 subtopics, 195 minimum questions target, 500 total target.

---

## Source Reference

| Source | URL | Notes |
|--------|-----|-------|
| BBC Bitesize | `bbc.co.uk/bitesize/subjects/zh2xsbk` | Well-structured, quiz pages |
| Isaac Physics | `isaacphysics.org` | REST API available |
| Oak National | `thenational.academy` | Lesson quiz quesitons |
| SaveMyExams | `savemyexams.com/ks3/physics/` | Free tier only |
| PMT | `physicsandmathstutor.com/physics-revision/ks3/` | Mix of HTML + PDFs |

---

## Error Handling Rules

- **Scraper fails**: log to `scrape_log` in DB, skip URL, continue
- **Classification fails**: log warning, skip question, continue
- **API rate limit**: exponential backoff, max 3 retries, then skip
- **Paywall detected**: log and skip (detect by: page title contains "Sign up", content is <100 words)
- **Never crash the whole run** — wrap per-URL and per-question work in try/except
- **Stuck for 2+ attempts**: add to STATUS.md "Blocked Items" and move on

---

## Completion Criteria (all must be true)

- [ ] `python -m pytest tests/ -v` — all tests pass
- [ ] `python -m src.cli.query --stats` shows >= 500 questions
- [ ] All 33 subtopics have >= 5 questions each
- [ ] Difficulty distribution: easy >= 50, medium >= 50, hard >= 50
- [ ] >= 3 sources represented
- [ ] Mean quality score >= 3.5
- [ ] `data/coverage_report.json` exists with `is_complete: true`
- [ ] STATUS.md Phase = COMPLETE

---

## Git Practices

- Commit after each meaningful chunk of work (not after every file)
- Descriptive messages: `"Add BBC Bitesize scraper — 83 questions found"`
- Never commit: `.env`, `data/*.db`, `data/questions/`, `logs/`
- Always run tests before committing
