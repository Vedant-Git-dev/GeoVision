"""Chat module — parse natural-language queries and orchestrate the GeoVision pipeline."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict

from groq import Groq

from .config import EE_PROJECT_ID
from .pipeline import run_pipeline
from . import explain

log = logging.getLogger(__name__)

# Initialize Groq client
api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None

GROQ_MODEL = "llama-3.3-70b-versatile"

# ---------------------------------------------------------------------------
# Intent parsing
# ---------------------------------------------------------------------------

_PARSE_SYSTEM_PROMPT = """\
You are an intelligent AI routing assistant for GeoVision, a satellite change-detection system.
Your job is to understand the user's message and determine whether they want to run a satellite analysis, or if they are just chatting/asking a question.

Always respond with valid JSON with the following schema:
{
  "intent": "chat" | "analyze",
  "location": "The full place name (e.g. 'Kharadi, Pune, India') or null",
  "city": "The specific city/town/sub-area if the user mentioned one (e.g. 'Kharadi, Pune'). null if only a district/region is given.",
  "before_date": "YYYY-MM-DD or null",
  "after_date": "YYYY-MM-DD or null",
  "question": "The core question rephrased for analysis, if applicable."
}

Rules:
  - If the user says hello, asks a general question, or is missing required parameters (location, before_date, after_date) to run an analysis, set intent to "chat".
  - If the user provides a location and a time range, set intent to "analyze".
  - If a location or date is missing in the current message but was established in the conversation history, you MUST reuse those established values and proceed with "analyze".
  - If the user confirms a parameter you previously asked about (e.g., "yes", "yepp", "correct"), set intent to "analyze" using the established location and dates.
  - "between 2022 and 2024" means before_date: "2022-01-01", after_date: "2024-01-01".
  - If only years are given, default to January 1st.
  - city vs location: "location" is the full place string. "city" is set ONLY when the user names a specific sub-area within a district (e.g. "Kharadi" in Pune district, "Whitefield" in Bangalore district). If the user only names a district/city like "Pune" or "Bangalore", set city to null — the system will analyze the full district.
  - For city, include the parent district for disambiguation: "Kharadi, Pune, India" not just "Kharadi".
"""

_PARSE_USER_TEMPLATE = 'Extract parameters from this message: "{message}"'


def _parse_intent(message: str, history: list = None) -> Dict[str, Any]:
    """Use the LLM to extract structured parameters and intent from a chat message."""
    if not client:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Cannot parse chat messages without an LLM."
        )
        
    history = history or []
    messages = [{"role": "system", "content": _PARSE_SYSTEM_PROMPT}]
    
    # Add history
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
        
    # Add current message
    messages.append({
        "role": "user",
        "content": _PARSE_USER_TEMPLATE.format(message=message),
    })

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.0,
        max_tokens=400,
        response_format={"type": "json_object"},
        messages=messages,
    )

    raw = response.choices[0].message.content.strip()
    log.info("LLM intent parse result: %s", raw)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("LLM returned non-JSON: %s", raw)
        parsed = {}

    return parsed


def _validate_date(date_str: str | None) -> str | None:
    """Return the date string if it's a valid YYYY-MM-DD, else None."""
    if not date_str:
        return None
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        # Try to salvage partial dates like "2022" or "2022-01"
        if re.match(r"^\d{4}$", date_str):
            return f"{date_str}-01-01"
        if re.match(r"^\d{4}-\d{2}$", date_str):
            return f"{date_str}-01"
        return None


def _generate_chat_reply(message: str, history: list, parsed: dict) -> str:
    """Use a dedicated conversational LLM call to handle back-and-forth chat."""
    if not client:
        return "I need a location and a time range (e.g., 'Pune between 2022 and 2024') to run the satellite analysis."

    system_prompt = (
        "You are GeoVision AI, a helpful and highly intelligent satellite analysis assistant. "
        "Your goal is to help the user run a satellite change-detection analysis using Google Earth Engine. "
        "To run an analysis, you MUST collect two things from the user: 1) A location, and 2) A time range (before and after dates). "
        "If the user is missing any of these parameters, politely and conversationally ask for them. "
        "If they are just chatting or asking general questions, chat back naturally using your vast knowledge. "
        "Keep your responses concise, friendly, and formatted nicely using markdown. "
    )

    # If the parser found some parameters but not all, inform the conversational LLM so it knows what's missing
    missing = []
    if not parsed.get("location"): missing.append("location")
    if not parsed.get("before_date") or not parsed.get("after_date"): missing.append("time range")
    
    if missing:
        system_prompt += f"\n\nNote: The user currently wants to analyze something, but is missing: {', '.join(missing)}. Ask for them naturally."

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.7,
            max_tokens=500,
            messages=messages,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        log.error("Error generating chat reply: %s", e)
        return "I'm having trouble connecting right now, but I need a location and a time range to run an analysis."


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def process_chat_message(user_message: str, history: list = None, on_progress=None) -> Dict[str, Any]:
    """Process a user chat message end-to-end.

    1. Parse the intent (location, dates, question) via Groq.
    2. If intent is 'chat', return conversational reply.
    3. Run the satellite change-detection pipeline.
    4. Generate an LLM explanation of the results.

    Args:
        on_progress: Optional callback for pipeline progress events.
    """
    # Step 1 — Parse intent
    parsed = _parse_intent(user_message, history)
    log.info("Parsed intent: %s", parsed)

    intent = parsed.get("intent", "chat")
    location = parsed.get("location")
    city = parsed.get("city")
    before_date = _validate_date(parsed.get("before_date"))
    after_date = _validate_date(parsed.get("after_date"))

    # If conversational or missing parameters, just chat back using the dedicated chat LLM
    if intent == "chat" or not location or not before_date or not after_date:
        reply = _generate_chat_reply(user_message, history or [], parsed)
        return {
            "success": True,
            "explanation": reply,
            "parsed": None,
            "config": None
        }

    question = parsed.get("question", user_message)

    # Step 2 — Run the change-detection pipeline
    log.info(
        "Running pipeline: location=%s, city=%s, before=%s, after=%s",
        location,
        city,
        before_date,
        after_date,
    )
    config = run_pipeline(
        location_query=location,
        before_date=before_date,
        after_date=after_date,
        project_id=EE_PROJECT_ID,
        city=city,
        on_progress=on_progress,
    )

    # Step 3 — Generate explanation
    explanation = explain.generate_explanation(
        location_query=location,
        before_date=before_date,
        after_date=after_date,
        config=config,
        question=question,
        history=history,
    )

    # Step 4 — Package response
    return {
        "success": True,
        "parsed": {
            "location": location,
            "city": city,
            "before_date": before_date,
            "after_date": after_date,
        },
        "config": config,
        "explanation": explanation,
    }
