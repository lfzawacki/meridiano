# simple-meridian/config.py

import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def _env_int(name, default):
    """Reads an integer environment variable, falling back to the default when unset or invalid."""
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


# Used in process_articles (operates globally, so uses default)
PROMPT_ARTICLE_SUMMARY = """
Summarize the key points of this news article objectively in 2-4 sentences.
Identify the main topics covered.

Article:
{article_content}
"""

# Used in rate_articles (operates globally, so uses default)
PROMPT_IMPACT_RATING = """
Analyze the following news summary and estimate its overall impact. Consider factors like geographic scope
(local vs global), number of people affected, severity, and potential long-term consequences.

Rate the impact on a scale of 1 to 10, where:
1-2: Minor, niche, or local interest.
3-4: Notable event for a specific region or community.
5-6: Significant event with broader regional or moderate international implications.
7-8: Major event with significant international importance or wide-reaching effects.
9-10: Critical global event with severe, widespread, or potentially historic implications.

Summary:
"{summary}"

Output ONLY the integer number representing your rating (1-10).
"""

# Used in generate_brief (can be overridden per profile)
PROMPT_CLUSTER_ANALYSIS = """
These are summaries of potentially related news articles from a '{feed_profile}' context:

{cluster_summaries_text}

What is the core event or topic discussed? Summarize the key developments and significance in 3-5 sentences
based *only* on the provided text. If the articles seem unrelated, state that clearly.
"""

# Used in generate_brief (can be overridden per profile)
PROMPT_BRIEF_SYNTHESIS = """
You are an AI assistant writing a Presidential-style daily intelligence briefing using Markdown,
specifically for the '{feed_profile}' category.
Synthesize the following analyzed news clusters into a coherent, high-level executive summary.
Start with the 2-3 most critical overarching themes globally or within this category based *only* on these inputs.
Then, provide concise bullet points summarizing key developments within the most significant clusters
(roughly 3-5 clusters).
Maintain an objective, analytical tone relevant to the '{feed_profile}' context. Avoid speculation.

Analyzed News Clusters (Most significant first):
{cluster_analyses_text}
"""

# --- Processing Settings ---
# How many hours back to look for articles when generating a brief
BRIEFING_ARTICLE_LOOKBACK_HOURS = 24

# --- Model Settings ---
# Model for summarization and analysis (check Deepseek docs for latest models)
LLM_CHAT_MODEL = os.getenv("LLM_CHAT_MODEL", "deepseek/deepseek-chat")
# Model for embeddings
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "together_ai/intfloat/multilingual-e5-large-instruct")

# Approximate number of clusters to aim for. Fine-tune based on results.
# Alternatively, use algorithms like DBSCAN that don't require specifying k.
N_CLUSTERS = 10  # Example, adjust as needed

# Minimum number of articles required to attempt clustering/briefing
MIN_ARTICLES_FOR_BRIEFING = 5

ARTICLES_PER_PAGE = 15

MANUALLY_ADDED_PROFILE_NAME = "manual"
DEFAULT_FEED_PROFILE = "default"

# --- RSS output feeds (/<profile>.rss) ---
# How many articles each profile's RSS feed exposes (newest first).
RSS_MAX_ITEMS = _env_int("RSS_MAX_ITEMS", 50)
# Absolute base URL of this instance, used for the feed's self/channel links.
# Unset: derived from the incoming request's Host header.
RSS_BASE_URL = os.getenv("RSS_BASE_URL") or None

# --- Other ---
DATABASE_FILE = "meridian.db"  # Keep for backward compatibility

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_FILE}")

# Flask configuration
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-key-change-in-production")
FLASK_ENV = os.getenv("FLASK_ENV", "development")
