#!/usr/bin/env python3
"""Entry point for the autonomous agent. Run: python main.py"""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from src.config import get_settings
from src.agent.loop import run_agent_session

if __name__ == "__main__":
    settings = get_settings()
    if not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY not set. Add it to .env file.")
        sys.exit(1)
    run_agent_session(settings)
