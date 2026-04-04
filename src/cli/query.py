"""
CLI tool for querying the physics question knowledge base.

Usage:
    physics-q --stats
    physics-q --list-topics
    physics-q --topic electricity --difficulty easy --count 5
    physics-q --random --count 10
"""

from __future__ import annotations

import random
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.config import get_settings
from src.db import count_questions, get_coverage_stats, get_questions, init_db
from src.models import Question
from src.taxonomy import ALL_TOPIC_SLUGS, TAXONOMY, get_topic_label

console = Console()


def _format_question(q: Question, number: int) -> None:
    """Print a single question in the standard format."""
    # Header line
    header = Text()
    header.append(f"  Q{number}  ", style="bold cyan")
    header.append(f"[{q.topic}]", style="bold yellow")
    header.append(f"  [{q.difficulty.value}]", style="bold green")
    header.append(f"  [{q.question_type.value}]", style="dim")
    console.print(header)
    console.print("  " + "─" * 58, style="dim")

    # Question text
    console.print(f"  {q.question_text}", style="white")
    console.print()

    # Options (for MC / true-false)
    if q.options:
        for opt in q.options:
            prefix = "  "
            style = "bold green" if opt.is_correct else "white"
            mark = " ✓" if opt.is_correct else ""
            console.print(f"{prefix}{opt.label}) {opt.text}{mark}", style=style)
        console.print()

    # Correct answer (for non-MC)
    if q.correct_answer and not q.options:
        console.print(f"  Answer: {q.correct_answer}", style="green")
        console.print()

    # Explanation
    if q.explanation:
        console.print(f"  Explanation: {q.explanation}", style="dim italic")
        console.print()

    # Source
    console.print(f"  Source: {q.source_name}", style="dim")
    console.print()


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    """Physics Question Knowledge Base CLI."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
def stats():
    """Show database statistics."""
    settings = get_settings()
    init_db(settings.db_path)
    data = get_coverage_stats(settings.db_path)

    total = data["total"]
    console.print(Panel(f"[bold cyan]Physics KB — {total} questions[/bold cyan]", expand=False))

    # By difficulty
    table = Table(title="By Difficulty", show_header=True)
    table.add_column("Difficulty", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Target", justify="right")
    for d in ["easy", "medium", "hard"]:
        count = data["by_difficulty"].get(d, 0)
        style = "green" if count >= 50 else "yellow" if count >= 20 else "red"
        table.add_row(d, f"[{style}]{count}[/{style}]", "50")
    console.print(table)

    # By source
    table2 = Table(title="By Source", show_header=True)
    table2.add_column("Source", style="bold")
    table2.add_column("Count", justify="right")
    for source, count in sorted(data["by_source"].items(), key=lambda x: -x[1]):
        table2.add_row(source, str(count))
    console.print(table2)

    # By topic (top-level)
    table3 = Table(title="By Topic", show_header=True)
    table3.add_column("Topic", style="bold")
    table3.add_column("Count", justify="right")
    table3.add_column("Target", justify="right")
    for topic_key, topic_data in TAXONOMY.items():
        target = topic_data["target_count"]
        # Sum all subtopics
        count = sum(data["by_topic"].get(slug, 0) for slug in topic_data["subtopics"])
        style = "green" if count >= target else "yellow" if count >= target // 2 else "red"
        table3.add_row(topic_data["label"], f"[{style}]{count}[/{style}]", str(target))
    console.print(table3)

    if data.get("mean_quality"):
        console.print(f"\n  Mean quality score: [bold]{data['mean_quality']:.2f}[/bold] / 5.0")


@main.command(name="list-topics")
def list_topics():
    """List all available topic slugs."""
    table = Table(title="Available Topics", show_header=True)
    table.add_column("Slug", style="bold yellow")
    table.add_column("Description")
    table.add_column("Count", justify="right")

    settings = get_settings()
    init_db(settings.db_path)
    data = get_coverage_stats(settings.db_path)

    for topic_key, topic_data in TAXONOMY.items():
        table.add_row(f"[bold]{topic_key}[/bold]", topic_data["label"], "")
        for slug, desc in topic_data["subtopics"].items():
            count = data["by_topic"].get(slug, 0)
            style = "green" if count >= 5 else "red"
            table.add_row(f"  {slug}", desc, f"[{style}]{count}[/{style}]")
    console.print(table)


@main.command()
@click.option("--topic", "-t", default=None, help="Topic slug (e.g. 'electricity' or 'electricity.circuits')")
@click.option("--difficulty", "-d", default=None, type=click.Choice(["easy", "medium", "hard"]))
@click.option("--count", "-n", default=5, show_default=True, help="Number of questions to show")
@click.option("--source", "-s", default=None, help="Filter by source name")
def query(topic, difficulty, count, source):
    """Query questions from the knowledge base."""
    settings = get_settings()
    init_db(settings.db_path)

    questions = get_questions(
        settings.db_path,
        topic=topic,
        difficulty=difficulty,
        source=source,
        limit=count,
    )

    if not questions:
        console.print("[yellow]No questions found matching your criteria.[/yellow]")
        return

    console.print(f"\n[bold]Found {len(questions)} question(s)[/bold]\n")
    for i, q in enumerate(questions, 1):
        _format_question(q, i)


@main.command()
@click.option("--count", "-n", default=10, show_default=True, help="Number of random questions")
@click.option("--topic", "-t", default=None, help="Optional topic filter")
def random_q(count, topic):
    """Show random questions from the knowledge base."""
    settings = get_settings()
    init_db(settings.db_path)

    # Fetch more than needed then sample
    questions = get_questions(
        settings.db_path,
        topic=topic,
        limit=min(count * 5, 500),
    )

    if not questions:
        console.print("[yellow]No questions in the database yet.[/yellow]")
        return

    sample = random.sample(questions, min(count, len(questions)))
    console.print(f"\n[bold]{len(sample)} random question(s)[/bold]\n")
    for i, q in enumerate(sample, 1):
        _format_question(q, i)


# Entry point alias for backward compatibility
@main.command(name="topic")
@click.argument("topic_slug")
@click.option("--count", "-n", default=5)
def topic_cmd(topic_slug, count):
    """Shortcut: physics-q topic electricity.circuits"""
    settings = get_settings()
    init_db(settings.db_path)
    questions = get_questions(settings.db_path, topic=topic_slug, limit=count)
    if not questions:
        console.print(f"[yellow]No questions found for topic: {topic_slug}[/yellow]")
        return
    for i, q in enumerate(questions, 1):
        _format_question(q, i)


if __name__ == "__main__":
    main()
