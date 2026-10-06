"""
The frontend: a Streamlit dashboard for a business owner.

Paste customer reviews (one per line), click Analyze, and see the results.
This app does NOT call Gemini directly. It calls OUR OWN backend (api.py),
exactly the way we called external APIs in Lesson 9.

Run it (in a SECOND terminal, while api.py is also running):
    uv run streamlit run app.py
"""

from collections import Counter

import requests
import streamlit as st

# Our own database code, kept in a separate file (database.py).
from database import init_db, save_results, load_history, DB_FILE

# The address of our own backend service.
API_URL = "http://127.0.0.1:8000/analyze"

# Make sure the table exists before the app uses it.
init_db()

st.title("📝 Customer Feedback Analyzer")
st.write("Paste your customer reviews below, one review per line.")

reviews_text = st.text_area("Reviews", height=200)

if st.button("Analyze"):
    # Split the text box into separate reviews, ignoring blank lines.
    reviews = [line.strip() for line in reviews_text.split("\n") if line.strip()]

    if not reviews:
        st.warning("Please paste at least one review.")
    else:
        results = []
        # Go through each review and ask our backend to analyze it.
        for review in reviews:
            try:
                response = requests.post(API_URL, json={"text": review}, timeout=30)
                if not response.ok:
                    try:
                        detail = response.json().get("detail", response.text)
                    except ValueError:
                        detail = response.text
                    raise RuntimeError(f"Backend returned HTTP {response.status_code}: {detail}")
                data = response.json()
                results.append({
                    "review": review,
                    "label": data["label"],
                    "score": data["score"],
                    "theme": data["theme"],
                    "method": data.get("method", "Gemini"),
                })
            except Exception as e:
                # One bad review should not stop the whole batch.
                # Print the real reason so it's visible in the Streamlit log.
                print(f"Failed to analyze '{review}': {e}")
                results.append({
                    "review": review,
                    "label": "error",
                    "score": 0,
                    "theme": "error",
                    "method": "Error",
                    "error": str(e),
                })

        # Save results in session_state so they survive button clicks.
        st.session_state.results = results

# Show the results if we have any.
if "results" in st.session_state:
    results = st.session_state.results

    st.subheader("Results")
    st.dataframe(results)
    if any(r.get("method") == "Local fallback" for r in results):
        st.info("Gemini quota is exhausted. These rows use a basic local sentiment estimate.")

    # ---- A simple summary for the business owner ----
    scores = [r["score"] for r in results if r["label"] != "error"]
    positive = [r for r in results if r["label"] == "positive"]
    themes = [r["theme"] for r in results if r["theme"] != "error"]

    st.subheader("Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Reviews", len(results))
    if scores:
        col2.metric("Average score", round(sum(scores) / len(scores), 1))
        col3.metric("% Positive", f"{round(len(positive) / len(scores) * 100)}%")

    if themes:
        # Counter tells us which theme appears most often.
        top_theme = Counter(themes).most_common(1)[0][0]
        st.info(f"Customers talk most about: **{top_theme}**")

    # ---- Save the full report to the database (Lesson 12) ----
    if st.button("💾 Save to database"):
        save_results(results)
        st.success(f"Saved {len(results)} reviews to {DB_FILE}")

# ---- Show everything we have ever saved (reads from the database) ----
with st.expander("📚 Saved history (all reviews in the database)"):
    history = load_history()
    if history:
        st.write(f"Total saved so far: {len(history)}")
        st.dataframe(
            [{"review": r[0], "label": r[1], "score": r[2], "theme": r[3]} for r in history]
        )
    else:
        st.write("Nothing saved yet. Analyze some reviews and click Save.")
