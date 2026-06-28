"""Generate natural language explanations of satellite change detection results using an LLM."""

from __future__ import annotations

import os
from typing import Dict, Any

from groq import Groq

from . import config

# Initialize Groq client if API key is available
api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None

# Model to use for explanations
GROQ_MODEL = "llama-3.3-70b-versatile"


def _format_land_cover_stats(stats: Dict[str, Any]) -> str:
    """Format land cover stats into a readable string."""
    lines = []
    for cls in stats.get("classes", []):
        name = cls["name"]
        before = cls["before"]
        after = cls["after"]
        delta = cls["delta"]
        arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
        sign = "+" if delta > 0 else ""
        lines.append(f"- {name}: {before}% → {after}% ({sign}{delta}% {arrow})")
    return "\n".join(lines)


def _format_settlements(settlements: list) -> str:
    """Format settlement names into a readable string."""
    if not settlements:
        return "No specific settlements detected."
    names = [s.get("name", "Unnamed") for s in settlements]
    return ", ".join(names[:10])  # limit to first 10


def generate_explanation(
    location_query: str,
    before_date: str,
    after_date: str,
    config: dict,
    question: str | None = None,
) -> str:
    """
    Generate a natural language explanation of the change detection results.

    Args:
        location_query: The location string entered by the user.
        before_date: Start date (YYYY-MM-DD).
        after_date: End date (YYYY-MM-DD).
        config: The dictionary returned by run_pipeline.
        question: Optional specific question from the user; if None, a general summary is generated.

    Returns:
        A string containing the LLM-generated explanation.
    """
    if not client:
        return (
            "LLM explanation is not available because GROQ_API_KEY is not set. "
            "Please set it in your .env file to enable AI-powered insights."
        )

    # Extract relevant info from config
    district_name = config.get("area_name", "the area")
    stats = config.get("land_cover_stats", {})
    settlements = config.get("settlements", [])
    center = config.get("center", [0, 0])

    # Format data for prompt
    location_info = f"Location: {district_name} (coordinates: {center[0]:.4f}, {center[1]:.4f})"
    date_info = f"Date range: {before_date} to {after_date}"
    lc_stats_text = _format_land_cover_stats(stats)
    settlements_text = _format_settlements(settlements)

    # Determine prompt based on whether a question was provided
    if question:
        user_prompt = f"""You are an expert satellite imagery analyst specializing in land cover change detection.
You have analyzed satellite images of {district_name} from {before_date} to {after_date} using Google Earth Engine and Dynamic World land cover classification.

Here are the quantitative results:
{location_info}
{date_info}

Land cover changes:
{lc_stats_text}

Notable settlements in the area: {settlements_text}

The user asks: "{question}"

Please provide a clear, concise, and informative answer in plain language. Focus on interpreting what the changes mean for the area, highlighting any significant trends, environmental impacts, or urban development patterns. Use the data to support your explanations. If the question cannot be answered from the available data, say so clearly and suggest what additional information would be needed."""
    else:
        user_prompt = f"""You are an expert satellite imagery analyst specializing in land cover change detection.
You have analyzed satellite images of {district_name} from {before_date} to {after_date} using Google Earth Engine and Dynamic World land cover classification.

Here are the quantitative results:
{location_info}
{date_info}

Land cover changes:
{lc_stats_text}

Notable settlements in the area: {settlements_text}

Please provide a clear, concise, and informative summary of what changed in this area during this period. Highlight the most significant transitions, discuss potential causes (e.g., urban expansion, deforestation, agricultural changes, water body changes), and mention any notable environmental or societal implications. Use the data to support your explanations."""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=1000,
            temperature=0.3,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful and knowledgeable satellite imagery analyst.",
                },
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating explanation: {str(e)}"