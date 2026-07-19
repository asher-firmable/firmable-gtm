"""
Shared Utilities — data processing, Anthropic API wrapper, file helpers.
"""

import os
import csv
import json
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def load_csv(filepath: str) -> pd.DataFrame:
    """Load a CSV or Excel file, normalising column names to lowercase snake_case."""
    if filepath.endswith(".xlsx"):
        df = pd.read_excel(filepath)
    else:
        try:
            df = pd.read_csv(filepath)
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding="latin-1")
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    return df


def save_csv(df: pd.DataFrame, filepath: str) -> str:
    """Save a DataFrame to CSV, creating parent directories if needed."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    df.to_csv(filepath, index=False)
    return filepath


def ensure_dirs(*paths: str) -> None:
    """Create directories if they don't exist."""
    for path in paths:
        os.makedirs(path, exist_ok=True)


def timestamp() -> str:
    """Return current datetime as a compact string for filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def read_knowledge_file(filename: str) -> str:
    """Read a file from the knowledge/ directory relative to the repo root."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filepath = os.path.join(project_root, "knowledge", filename)
    with open(filepath, "r") as f:
        return f.read()


def reason_about(prompt: str, context: str = "", model: str = "claude-sonnet-4-6") -> str:
    """Use the Anthropic API for reasoning tasks like qualification scoring."""
    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic package not installed. Run: pip3 install anthropic")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set in .env")

    client = anthropic.Anthropic(api_key=api_key)
    full_prompt = f"{context}\n\n{prompt}" if context else prompt
    messages = [{"role": "user", "content": full_prompt}]
    response = client.messages.create(model=model, max_tokens=1024, messages=messages)
    return response.content[0].text
