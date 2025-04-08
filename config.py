# simple-meridian/config.py

# List of RSS feeds to scrape
# Add more sources relevant to your interests
RSS_FEEDS = [
  "https://techcrunch.com/feed/",
  "https://www.theverge.com/rss/index.xml",
  "https://arstechnica.com/feed/",
  "https://krebsonsecurity.com/feed/",
  "https://feeds.feedburner.com/TheHackersNews",
  "https://www.bleepingcomputer.com/feed/",
  "https://www.tomshardware.com/feeds/all",
  "https://www.scmp.com/rss/36/feed", # tech
  "https://www.scmp.com/rss/320663/feed", # china tech
  "https://www.scmp.com/rss/318220/feed", # startups
  "https://www.scmp.com/rss/318221/feed", # apps and gaming
  "https://www.scmp.com/rss/318224/feed", # science and research
  "https://www.scmp.com/rss/318222/feed", # innovation
  "https://www.wired.com/feed/category/backchannel/latest/rss",
  "https://www.wired.com/feed/rss",
  # Add more diverse sources (tech, finance, local etc.)
]

# --- Processing Settings ---
# How many hours back to look for articles when generating a brief
BRIEFING_ARTICLE_LOOKBACK_HOURS = 24

ARTICLES_PER_PAGE = 15

# --- Deepseek Model Settings ---
# Model for summarization and analysis (check Deepseek docs for latest models)
DEEPSEEK_CHAT_MODEL = "deepseek-chat"
# Model for embeddings
EMBEDDING_MODEL = "togethercomputer/m2-bert-80M-32k-retrieval"

# --- Clustering Settings ---
# Approximate number of clusters to aim for. Fine-tune based on results.
# Alternatively, use algorithms like DBSCAN that don't require specifying k.
N_CLUSTERS = 10 # Example, adjust as needed

# Minimum number of articles required to attempt clustering/briefing
MIN_ARTICLES_FOR_BRIEFING = 5

# --- Other ---
DATABASE_FILE = "meridian.db"
