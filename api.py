"""
The backend: a small FastAPI service that analyzes ONE customer review.

Run it with:
    uv run fastapi dev api.py
    # or
    uvicorn api:app --reload

Then the Streamlit app (app.py) will call this service for every review.
"""

from typing import Literal
import re

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


client = genai.Client()

app = FastAPI()


# The model to use. Google rotates model names frequently.
# If you get a 404, run this to see what your key can access:
#   python -c "from google import genai; [print(m.name) for m in genai.Client().models.list()]"
# then set MODEL to whatever real name appears there.
MODEL = "gemini-3.8-flash"


# What the caller must SEND us
class Review(BaseModel):
    text: str


# What Gemini gives back, and what we SEND to the caller.
class Analysis(BaseModel):
    label: Literal["positive", "negative", "neutral"]
    score: int = Field(ge=1, le=5)   # 1 (very bad) to 5 (very good)
    theme: str                       # one word: what the review is mainly about
    method: Literal["Gemini", "Local fallback"] = "Gemini"


class GeminiAnalysis(BaseModel):
    label: Literal["positive", "negative", "neutral"]
    score: int = Field(ge=1, le=5)
    theme: str


def analyze_locally(text: str) -> Analysis:
    """Basic local sentiment result used only when Gemini quota is exhausted."""
    words = set(re.findall(r"[a-z]+", text.lower()))
    positive_words = {
        "amazing", "excellent", "great", "good", "love", "loved", "delicious",
        "fast", "friendly", "tasty", "recommend", "happy", "perfect", "wonderful",
    }
    negative_words = {
        "bad", "terrible", "slow", "disappointed", "poor", "worst", "cold",
        "late", "hate", "hated", "broken", "rude", "awful", "unhappy",
    }
    positive = len(words & positive_words)
    negative = len(words & negative_words)
    label: Literal["positive", "negative", "neutral"]
    if positive > negative:
        label = "positive"
    elif negative > positive:
        label = "negative"
    else:
        label = "neutral"

    theme_terms = {
        "delivery": {"delivery", "arrived", "late", "fast", "shipping"},
        "food": {"food", "taste", "tasty", "delicious", "flavor"},
        "service": {"service", "staff", "rude", "friendly", "support"},
        "price": {"price", "cost", "expensive", "cheap", "value"},
        "quality": {"quality", "broken", "defective", "product"},
    }
    theme = max(theme_terms, key=lambda name: len(words & theme_terms[name]))
    if not words & theme_terms[theme]:
        theme = "general"

    score = max(1, min(5, 3 + positive - negative))
    return Analysis(label=label, score=score, theme=theme, method="Local fallback")


@app.post("/analyze", response_model=Analysis)
def analyze(review: Review):
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=(
                "Analyze this customer review.\n"
                "label must be 'positive', 'negative', or 'neutral'.\n"
                "score must be a number from 1 (very bad) to 5 (very good).\n"
                "theme must be ONE lowercase word for the main topic "
                "(for example: delivery, taste, price, service, quality).\n"
                f"Review: {review.text}"
            ),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GeminiAnalysis,
            ),
        )
    except Exception as e:
        # Keep quota exhaustion usable with an explicitly labelled local result.
        status = getattr(e, "code", None)
        try:
            status = int(status)
        except (TypeError, ValueError):
            match = re.match(r"\s*(\d{3})\s+", str(e))
            status = int(match.group(1)) if match else 502
        if not (400 <= status <= 599):
            status = 502
        if status == 429:
            return analyze_locally(review.text)
        raise HTTPException(status_code=status, detail=str(e)) from e

    if response.parsed is None:
        raise HTTPException(
            status_code=502,
            detail="Gemini returned no parsable analysis.",
        )

    return Analysis(**response.parsed.model_dump(), method="Gemini")
