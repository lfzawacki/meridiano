# simple-meridian/run_briefing.py

import os
import importlib
import feedparser
from datetime import datetime
import json
import time
import numpy as np
from sklearn.cluster import KMeans
from dotenv import load_dotenv
import openai
import argparse

from urllib.parse import urljoin

from utils import fetch_article_content_and_og_image

try:
    import config_base as config # Load base config first
except ImportError:
    print("ERROR: config_base.py not found. Please ensure it exists.")
    exit(1)

import database

# --- Setup ---
load_dotenv()
API_KEY = os.getenv("DEEPSEEK_API_KEY")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")

if not API_KEY:
    raise ValueError("DEEPSEEK_API_KEY not found in .env file")

if not EMBEDDING_API_KEY:
    raise ValueError("EMBEDDING_API_KEY not found in .env file")

# Use the correct client for Deepseek, not OpenAI
client = openai.Client(api_key=API_KEY, base_url="https://api.deepseek.com/v1")
embedding_client = openai.Client(api_key=EMBEDDING_API_KEY, base_url="https://api.together.xyz/v1")

def call_deepseek_chat(prompt, model=config.DEEPSEEK_CHAT_MODEL, system_prompt=None):
    """Calls the Deepseek Chat API."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2048, # Adjust as needed
            temperature=0.7, # Adjust for desired creativity/factuality
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling Deepseek Chat API: {e}")
        # Implement retry logic or better error handling here if needed
        time.sleep(1) # Basic backoff
        return None

def get_deepseek_embedding(text, model=config.EMBEDDING_MODEL):
    """Gets embeddings."""
    print(f"INFO: Attempting to get embedding for text snippet: '{text[:50]}...'")

    try:
         response = embedding_client.embeddings.create(
             model=model, # Use the actual model name from Deepseek docs
             input=[text] # API likely expects a list of strings
         )
         # Access the embedding vector based on the actual API response structure
         if response.data and len(response.data) > 0:
              return response.data[0].embedding
         else:
              print(f"Warning: No embedding returned for text.")
              return None
    except Exception as e:
         print(f"Error calling Embedding API: {e}")
         return None

# --- Core Functions ---

def scrape_articles(feed_profile, rss_feeds): # Added params
    """Scrapes articles for a specific feed profile."""
    print(f"\n--- Starting Article Scraping [{feed_profile}] ---")
    new_articles_count = 0
    if not rss_feeds:
        print(f"Warning: No RSS_FEEDS defined for profile '{feed_profile}'. Skipping scrape.")
        return

    for feed_url in rss_feeds:
        print(f"Fetching feed: {feed_url}")
        feed = feedparser.parse(feed_url)

        if feed.bozo: print(f"Warning: Potential issue parsing feed {feed_url}: {feed.bozo_exception}")

        for entry in feed.entries:
            url = entry.get('link')
            title = entry.get('title', 'No Title')
            published_parsed = entry.get('published_parsed')
            published_date = datetime(*published_parsed[:6]) if published_parsed else datetime.now()
            feed_source = feed.feed.get('title', feed_url)

            if not url: continue

            # --- Check if article exists ---
            conn = database.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM articles WHERE url = ?", (url,))
            exists = cursor.fetchone()
            conn.close()
            if exists: continue
            # --- End Check ---

            print(f"Processing new entry: {title} ({url})")

            # --- 1. Try getting image from RSS feed ---
            rss_image_url = None
            # Check enclosures
            if 'enclosures' in entry:
                for enc in entry.enclosures:
                    if enc.get('type', '').startswith('image/'):
                        rss_image_url = enc.get('href')
                        break # Take the first image enclosure
            # Check media_content if no enclosure image found
            if not rss_image_url and 'media_content' in entry:
                 for media in entry.media_content:
                     if media.get('medium') == 'image' and media.get('url'):
                          rss_image_url = media.get('url')
                          break # Take the first media image
                     elif media.get('type', '').startswith('image/') and media.get('url'):
                          rss_image_url = media.get('url')
                          break
            # Check simple image tag (less common)
            if not rss_image_url and 'image' in entry and isinstance(entry.image, dict) and entry.image.get('url'):
                rss_image_url = entry.image.get('url')

            if rss_image_url:
                print(f"  Found image in RSS: {rss_image_url[:60]}...")
            # --- End RSS Image Check ---

            # --- 2. Fetch Article Content & OG Image ---
            print(f"  Fetching article content and OG image...")
            fetch_result = fetch_article_content_and_og_image(url)
            raw_content = fetch_result['content']
            og_image_url = fetch_result['og_image']
            # --- End Fetch ---

            if not raw_content:
                print(f"  Skipping article, failed to extract main content: {title}")
                continue

            # --- 3. Determine Final Image URL and Save ---
            final_image_url = rss_image_url if rss_image_url else og_image_url
            if final_image_url:
                 print(f"  Using image URL: {final_image_url[:60]}...")
            else:
                 print("  No image found in RSS or OG tags.")

            article_id = database.add_article(
                url, title, published_date, feed_source, raw_content,
                feed_profile,
                final_image_url
            )
            if article_id: new_articles_count += 1
            time.sleep(0.5) # Be polite

    print(f"--- Scraping Finished [{feed_profile}]. Added {new_articles_count} new articles. ---")


def process_articles(feed_profile, effective_config):
    """Processes unprocessed articles: summarizes and generates embeddings."""
    print("\n--- Starting Article Processing ---")
    chat_model = getattr(effective_config, 'DEEPSEEK_CHAT_MODEL', 'deepseek-chat') # Get model from effective config
    summary_prompt_template = getattr(effective_config, 'PROMPT_ARTICLE_SUMMARY', config.PROMPT_ARTICLE_SUMMARY)

    unprocessed = database.get_unprocessed_articles(feed_profile, 1000)
    processed_count = 0
    if not unprocessed:
        print("No new articles to process.")
        return

    print(f"Found {len(unprocessed)} articles to process.")
    for article in unprocessed:
        print(f"Processing article ID: {article['id']} - {article['url'][:50]}...")

        # 1. Summarize using Deepseek Chat
        # Format the potentially profile-specific summary prompt
        summary_prompt = summary_prompt_template.format(
            article_content=article['raw_content'][:4000] # Limit context
        )
        summary = call_deepseek_chat(summary_prompt, model=chat_model)

        if not summary:
            print(f"Skipping article {article['id']} due to summarization error.")
            continue

        print(f"Article summary is: {summary}")

        # 2. Generate Embedding using Deepseek (or alternative)
        # Use summary for embedding to focus on core topics and save tokens/time
        embedding = get_deepseek_embedding(summary)

        if not embedding:
             print(f"Skipping article {article['id']} due to embedding error.")
             continue # Or store article without embedding if desired

        # 3. Update Database
        database.update_article_processing(article['id'], summary, embedding)
        processed_count += 1
        print(f"Successfully processed article ID: {article['id']}")
        time.sleep(1) # Avoid hitting API rate limits

    print(f"--- Processing Finished. Processed {processed_count} articles. ---")

def rate_articles(feed_profile, effective_config):
    """Rates the impact of processed articles using an LLM."""
    print("\n--- Starting Article Impact Rating ---")
    if not client:
        print("Skipping rating: Deepseek client not initialized.")
        return

    chat_model = getattr(effective_config, 'DEEPSEEK_CHAT_MODEL', 'deepseek-chat')
    rating_prompt_template = getattr(effective_config, 'PROMPT_IMPACT_RATING', config.PROMPT_IMPACT_RATING)

    unrated = database.get_unrated_articles(feed_profile, 1000)
    rated_count = 0
    if not unrated:
        print("No new articles to rate.")
        return

    print(f"Found {len(unrated)} processed articles to rate.")
    for article in unrated:
        print(f"Rating article ID: {article['id']}: {article['title']}...")
        summary = article['processed_content']
        if not summary:
            print(f"  Skipping article {article['id']} - no summary found.")
            continue

        # Format the potentially profile-specific rating prompt
        rating_prompt = rating_prompt_template.format(
            summary=summary
        )
        rating_response = call_deepseek_chat(rating_prompt, model=chat_model)

        impact_score = None
        if rating_response:
            try:
                # Attempt to extract the integer score
                score = int(rating_response.strip().split()[0]) # Take first part in case it adds extra text
                if 1 <= score <= 10:
                    impact_score = score
                    print(f"  Article ID {article['id']} rated as: {impact_score}")
                else:
                    print(f"  Warning: Rating response '{rating_response}' for article {article['id']} is out of range (1-10).")
            except (ValueError, IndexError):
                print(f"  Warning: Could not parse integer rating from response '{rating_response}' for article {article['id']}.")
        else:
            print(f"  Warning: No rating response received for article {article['id']}.")

        # Update database even if rating failed (impact_score will be None, prevents re-attempting failed ones immediately)
        # Or only update if impact_score is not None:
        if impact_score is not None:
             database.update_article_rating(article['id'], impact_score)
             rated_count += 1
        # else: # Decide if you want to mark failed attempts differently
             # database.update_article_rating(article['id'], -1) # Example: Mark as failed with -1? Or leave NULL? Leaving NULL for now.

        time.sleep(1) # API rate limiting

    print(f"--- Rating Finished. Rated {rated_count} articles. ---")


def generate_brief(feed_profile, effective_config): # Added feed_profile param
    """Generates the briefing for a specific feed profile."""
    print(f"\n--- Starting Brief Generation [{feed_profile}] ---")
    # Get articles *for this specific profile*
    articles = database.get_articles_for_briefing(
        config.BRIEFING_ARTICLE_LOOKBACK_HOURS,
        feed_profile
    )

    if not articles or len(articles) < config.MIN_ARTICLES_FOR_BRIEFING:
        print(f"Not enough recent articles ({len(articles)}) for profile '{feed_profile}'. Min required: {config.MIN_ARTICLES_FOR_BRIEFING}.")
        return

    print(f"Generating brief from {len(articles)} articles.")

    # Prepare data for clustering
    article_ids = [a['id'] for a in articles]
    summaries = [a['processed_content'] for a in articles]
    embeddings = [json.loads(a['embedding']) for a in articles if a['embedding']] # Load JSON string

    if len(embeddings) != len(articles):
        print("Warning: Some articles selected for briefing are missing embeddings. Proceeding with available ones.")
        # Filter articles, summaries, ids to match embeddings
        valid_indices = [i for i, a in enumerate(articles) if a['embedding']]
        articles = [articles[i] for i in valid_indices]
        article_ids = [article_ids[i] for i in valid_indices]
        summaries = [summaries[i] for i in valid_indices]
        # embeddings are already filtered

    if len(embeddings) < config.MIN_ARTICLES_FOR_BRIEFING:
         print(f"Not enough articles ({len(embeddings)}) with embeddings to cluster. Min required: {config.MIN_ARTICLES_FOR_BRIEFING}.")
         return

    embedding_matrix = np.array(embeddings)

    # Clustering (using KMeans as an example)
    n_clusters = min(config.N_CLUSTERS, len(embedding_matrix) // 2) # Ensure clusters < samples/2
    if n_clusters < 2 : # Need at least 2 clusters for KMeans typically
        print("Not enough articles to form meaningful clusters. Skipping clustering.")
        # Alternative: Treat all articles as one cluster or generate simple list summary
        # For now, we'll just exit brief generation
        return

    print(f"Clustering {len(embedding_matrix)} articles into {n_clusters} clusters...")
    try:
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10) # n_init='auto' in newer sklearn
        kmeans.fit(embedding_matrix)
        labels = kmeans.labels_
    except Exception as e:
        print(f"Error during clustering: {e}")
        return

    # Analyze each cluster
    cluster_analyses = []
    print("Analyzing clusters...")

   # *** Get the cluster analysis prompt template from effective_config ***
    cluster_analysis_prompt_template = getattr(
        effective_config,
        'PROMPT_CLUSTER_ANALYSIS',      # Look for this constant
        config.PROMPT_CLUSTER_ANALYSIS # Fallback to default if not found
    )
    print(f"DEBUG: Using Cluster Analysis Prompt Template:\n'''{cluster_analysis_prompt_template[:100]}...'''") # Debug

    for i in range(n_clusters): # Use the actual n_clusters determined
        cluster_indices = np.where(labels == i)[0]
        if len(cluster_indices) == 0: continue # Skip empty clusters

        cluster_summaries = [summaries[idx] for idx in cluster_indices]
        print(f"  Analyzing Cluster {i} ({len(cluster_summaries)} articles)")

        MAX_SUMMARIES_PER_CLUSTER = 10 # Consider making this configurable too?
        cluster_summaries_text = "\n\n".join([f"- {s}" for s in cluster_summaries[:MAX_SUMMARIES_PER_CLUSTER]])

        # *** Format the chosen prompt template ***
        analysis_prompt = cluster_analysis_prompt_template.format(
            cluster_summaries_text=cluster_summaries_text,
            feed_profile=feed_profile
        )

        # *** Call LLM with the formatted prompt ***
        cluster_analysis = call_deepseek_chat(analysis_prompt) # System prompt could also be configurable

        if cluster_analysis:
            # (Consider adding more robust filtering of non-analysis responses)
            if "unrelated" not in cluster_analysis.lower() or len(cluster_summaries) > 2:
                 cluster_analyses.append({"topic": f"Cluster {i+1}", "analysis": cluster_analysis, "size": len(cluster_summaries)})
        time.sleep(1) # Rate limiting
    # --- End Analyze each cluster ---

    if not cluster_analyses:
        print("No meaningful clusters found or analyzed.")
        return

    # Sort clusters by size (number of articles) to prioritize major themes
    cluster_analyses.sort(key=lambda x: x['size'], reverse=True)

    # Synthesize Final Brief using profile-specific or default prompt
    brief_synthesis_prompt_template = getattr(effective_config, 'PROMPT_BRIEF_SYNTHESIS', config.PROMPT_BRIEF_SYNTHESIS) # Fallback
    print(f"DEBUG: Using Brief Synthesis Prompt Template:\n'''{brief_synthesis_prompt_template[:100]}...'''") # Debug print

    cluster_analyses_text = ""
    for i, cluster in enumerate(cluster_analyses[:5]):
        cluster_analyses_text += f"--- Cluster {i+1} ({cluster['size']} articles) ---\nAnalysis: {cluster['analysis']}\n\n"

    synthesis_prompt = brief_synthesis_prompt_template.format(
        cluster_analyses_text=cluster_analyses_text,
        feed_profile=feed_profile
    )
    final_brief_md = call_deepseek_chat(synthesis_prompt)

    if final_brief_md:
        database.save_brief(final_brief_md, article_ids, feed_profile)
        print(f"--- Brief Generation Finished Successfully [{feed_profile}] ---")
    else:
        print(f"--- Brief Generation Failed [{feed_profile}]: Could not synthesize final brief. ---")

# --- Main Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Meridian Briefing Runner: Scrapes, processes, and generates briefings.",
        formatter_class=argparse.RawTextHelpFormatter # Nicer help text formatting
    )
    parser.add_argument(
        '--feed',
        type=str,
        default=config.DEFAULT_FEED_PROFILE, # Use default from base config
        help=f"Specify the feed profile name (e.g., brazil, tech). Default: '{config.DEFAULT_FEED_PROFILE}'."
    )
    parser.add_argument(
        '--rate-articles',
        dest='rate',
        action='store_true',
        help='Run only the article impact rating stage (requires processed articles).'
    )
    parser.add_argument(
        '--scrape-articles',
        dest='scrape',
        action='store_true',
        help='Run only the article scraping stage.'
    )
    parser.add_argument(
        '--process-articles',
        dest='process',
        action='store_true',
        help='Run only the article processing (summarize, embed) stage.'
    )
    parser.add_argument(
        '--generate-brief',
        dest='generate',
        action='store_true',
        help='Run only the brief generation (cluster, analyze, synthesize) stage.'
    )
    parser.add_argument(
        '--all',
        dest='run_all',
        action='store_true',
        help='Run all stages sequentially (scrape, process, generate).\nThis is the default behavior if no specific stage argument is given.'
    )

    args = parser.parse_args()

    # --- Load Feed Specific Config ---
    feed_profile_name = args.feed
    feed_module_name = f"feeds.{feed_profile_name}"
    try:
        feed_config = importlib.import_module(feed_module_name)
        print(f"Loaded feed configuration: {feed_module_name}")
        # Optionally merge settings if feed configs override base config values
        # For now, we just need RSS_FEEDS from it
        rss_feeds = getattr(feed_config, 'RSS_FEEDS', [])
        if not rss_feeds:
             print(f"Warning: RSS_FEEDS list not found or empty in {feed_module_name}.py")
    except ImportError:
        print(f"ERROR: Could not import feed configuration '{feed_module_name}.py'.")
        print(f"Please ensure the file exists and contains an RSS_FEEDS list.")
        # Decide how to handle: exit or continue without scraping/generation?
        # Let's allow processing/rating to run, but disable scrape/generate
        rss_feeds = None # Indicate feed load failure

    # --- Create Effective Config ---
    # Start with base config vars
    effective_config_dict = {k: v for k, v in config.__dict__.items() if not k.startswith('__')}
    # Override with feed_config vars if they exist
    if feed_config:
        for k, v in feed_config.__dict__.items():
            if not k.startswith('__'):
                effective_config_dict[k] = v

    # Convert dict to a simple object for easier access (optional)
    class EffectiveConfig:
        def __init__(self, dictionary):
            for k, v in dictionary.items():
                setattr(self, k, v)
    effective_config = EffectiveConfig(effective_config_dict)

    # Ensure RSS_FEEDS is correctly set in the effective config if loaded
    if rss_feeds is not None:
        effective_config.RSS_FEEDS = rss_feeds

    # Default to running all if no specific stage OR --all is provided
    should_run_all = args.run_all or not (args.scrape or args.process or args.generate or args.rate)

    print(f"\nMeridian Briefing Run [{feed_profile_name}] - {datetime.now()}")
    print("Initializing database...")
    database.init_db() # Initialize DB regardless of stage run

    current_rss_feeds = getattr(effective_config, 'RSS_FEEDS', None)

    if should_run_all:
        print("\n>>> Running ALL stages <<<")
        if current_rss_feeds: scrape_articles(feed_profile_name, current_rss_feeds)
        else: print("Skipping scrape stage: No RSS_FEEDS found for profile.")
        process_articles(feed_profile_name, effective_config)
        rate_articles(feed_profile_name, effective_config)
        if current_rss_feeds: generate_brief(feed_profile_name, effective_config)
        else: print("Skipping generate stage: No RSS_FEEDS found for profile.")
    else:
        if args.scrape:
            if current_rss_feeds:
                 print(f"\n>>> Running ONLY Scrape Articles stage [{feed_profile_name}] <<<")
                 scrape_articles(feed_profile_name, current_rss_feeds)
            else: print(f"Cannot run scrape stage: No RSS_FEEDS found for profile '{feed_profile_name}'.")
        if args.process:
            print("\n>>> Running ONLY Process Articles stage <<<")
            process_articles(feed_profile_name, effective_config)
        if args.rate:
            print("\n>>> Running ONLY Rate Articles stage <<<")
            rate_articles(feed_profile_name, effective_config)
        if args.generate:
            if current_rss_feeds: # Check if feeds exist, as brief relies on articles from them
                print(f"\n>>> Running ONLY Generate Brief stage [{feed_profile_name}] <<<")
                generate_brief(feed_profile_name, effective_config)
            else: print(f"Cannot run generate stage: No RSS_FEEDS found for profile '{feed_profile_name}'.")

    print(f"\nRun Finished [{feed_profile_name}] - {datetime.now()}")
