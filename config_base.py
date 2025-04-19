# simple-meridian/config.py

# --- Processing Settings ---
# How many hours back to look for articles when generating a brief
BRIEFING_ARTICLE_LOOKBACK_HOURS = 24

# --- Model Settings ---
# Model for summarization and analysis (check Deepseek docs for latest models)
DEEPSEEK_CHAT_MODEL = "deepseek-chat"
# Model for embeddings
EMBEDDING_MODEL = "togethercomputer/m2-bert-80M-32k-retrieval"

# Approximate number of clusters to aim for. Fine-tune based on results.
# Alternatively, use algorithms like DBSCAN that don't require specifying k.
N_CLUSTERS = 10 # Example, adjust as needed

# Minimum number of articles required to attempt clustering/briefing
MIN_ARTICLES_FOR_BRIEFING = 5

ARTICLES_PER_PAGE = 15

DEFAULT_FEED_PROFILE = 'default'

# --- Other ---
DATABASE_FILE = "meridian.db"
