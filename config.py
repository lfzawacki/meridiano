# simple-meridian/config.py

# List of RSS feeds to scrape
# Add more sources relevant to your interests
RSS_FEEDS = [
    "http://rss.cnn.com/rss/cnn_world.rss",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://feeds.reuters.com/Reuters/worldNews",
    "https://www.nytimes.com/svc/collections/v1/publish/https://www.nytimes.com/section/world/rss.xml"
    # Add more diverse sources (tech, finance, local etc.)
]

# --- Processing Settings ---
# How many hours back to look for articles when generating a brief
BRIEFING_ARTICLE_LOOKBACK_HOURS = 24

# --- Deepseek Model Settings ---
# Model for summarization and analysis (check Deepseek docs for latest models)
DEEPSEEK_CHAT_MODEL = "deepseek-chat"
# Model for embeddings
DEEPSEEK_EMBEDDING_MODEL = "deepseek-text-embedding-v1" # Fictional - replace with actual model name if available, otherwise might need separate embedding logic

# --- Clustering Settings ---
# Approximate number of clusters to aim for. Fine-tune based on results.
# Alternatively, use algorithms like DBSCAN that don't require specifying k.
N_CLUSTERS = 10 # Example, adjust as needed

# Minimum number of articles required to attempt clustering/briefing
MIN_ARTICLES_FOR_BRIEFING = 5

# --- Other ---
DATABASE_FILE = "meridian.db"
