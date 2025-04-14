# simple-meridian/run_briefing.py

import os
import feedparser
import requests
import trafilatura
from datetime import datetime
import json
import time
import numpy as np
from sklearn.cluster import KMeans
from dotenv import load_dotenv
import openai
import argparse

import config
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

# --- Helper Functions ---

def fetch_article_content(url):
    """Fetches and extracts main content from a URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:137.0) Gecko/20100101 Firefox/137.0',
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        # Extract main content using trafilatura
        content = trafilatura.extract(response.text, include_comments=False, include_tables=False)
        return content
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None
    except Exception as e:
        print(f"Error extracting content from {url}: {e}")
        return None

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

def scrape_articles():
    """Scrapes articles from configured RSS feeds."""
    print("\n--- Starting Article Scraping ---")
    new_articles_count = 0
    for feed_url in config.RSS_FEEDS:
        print(f"Fetching feed: {feed_url}")
        feed = feedparser.parse(feed_url)
        if feed.bozo:
            print(f"Warning: Potential issue parsing feed {feed_url}: {feed.bozo_exception}")

        for entry in feed.entries:
            url = entry.get('link')
            title = entry.get('title', 'No Title')
            published_parsed = entry.get('published_parsed')
            published_date = datetime(*published_parsed[:6]) if published_parsed else datetime.now()
            feed_source = feed.feed.get('title', feed_url)

            if not url:
                continue

            # Check if article exists before fetching content
            conn = database.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM articles WHERE url = ?", (url,))
            exists = cursor.fetchone()
            conn.close()

            if not exists:
                print(f"Fetching content for: {title} ({url})")
                raw_content = fetch_article_content(url)
                if raw_content:
                    article_id = database.add_article(url, title, published_date, feed_source, raw_content)
                    if article_id:
                        new_articles_count += 1
                else:
                    print(f"Skipping article due to content fetch/extraction error: {title}")
                time.sleep(1) # Be polite to servers

    print(f"--- Scraping Finished. Added {new_articles_count} new articles. ---")


def process_articles():
    """Processes unprocessed articles: summarizes and generates embeddings."""
    print("\n--- Starting Article Processing ---")
    unprocessed = database.get_unprocessed_articles(1000)
    processed_count = 0
    if not unprocessed:
        print("No new articles to process.")
        return

    print(f"Found {len(unprocessed)} articles to process.")
    for article in unprocessed:
        print(f"Processing article ID: {article['id']} - {article['url'][:50]}...")

        # 1. Summarize using Deepseek Chat
        summary_prompt = f"Summarize the key points of this news article objectively in 2-4 sentences. Identify the main topics covered.\n\nArticle:\n{article['raw_content'][:4000]}" # Limit context window
        summary = call_deepseek_chat(summary_prompt)

        if not summary:
            print(f"Skipping article {article['id']} due to summarization error.")
            continue

        summary += f"\n\nSource: [{article['title']}]({article['url']})"

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

def rate_articles():
    """Rates the impact of processed articles using an LLM."""
    print("\n--- Starting Article Impact Rating ---")
    if not client:
        print("Skipping rating: Deepseek client not initialized.")
        return

    unrated = database.get_unrated_articles(1000)
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

        # Define the prompt for impact rating
#         rating_prompt = f"""Analyze the following article summary and estimate its overall impact. Consider factors like newsworthiness, original reporting, geographic scope (local vs global), number of people affected, severity, and potential long-term consequences. Be strict with the scores, the quality of the estimate is VITAL for our understanding of the global landscape.
#
# Rate the impact on a scale of 1 to 10, where:
# 1-2: Low newsworthiness. Minor, niche, or local interest. Product or show reviews.
# 3-4: Opinion piece, notable pop culture happening, notable event for a specific region or community.
# 5-6: Hard hitting jornalism. Significant event with broader regional or moderate international implications.
# 7-8: Comprehensive jornalistic exposes. Major event with significant international importance or wide-reaching effects.
# 9-10: Critical global event with severe, widespread, or potentially historic implications.

        rating_prompt = f"""Analyze the following article summary and estimate its overall impact. Consider factors like newsworthiness, originality, geographic scope (local vs global), number of people affected, severity, and potential long-term consequences. Be extremely critical and conservative when assigning scores—higher scores should reflect truly exceptional or rare events.

Rate the impact on a scale of 1 to 10, using these guidelines:

    1-2: Minimal significance. Niche interest or local news with no broader relevance. Example: A review of a local restaurant or a minor product launch.

    3-4: Regionally notable. Pop culture happenings, local events, or community-focused stories. Example: A local mayor’s resignation or a regional festival.

    5-6: Regionally significant or moderately global. Affects multiple communities or industries. Example: A nationwide strike or a major company bankruptcy.

    7-8: Highly significant. Major international relevance, significant disruptions, or wide-reaching implications. Example: A large-scale natural disaster, global health alerts, or a major geopolitical shift.

    9-10: Extraordinary and historic. Global, severe, and long-lasting implications. Example: Declaration of war, groundbreaking global treaties, or critical climate crises.

Key Reminder: Scores of 9-10 should be exceedingly rare and reserved for world-defining events. Always err on the side of a lower score unless the impact is undeniably significant.

Summary:
"{summary}"

Output ONLY the integer number representing your rating (1-10)."""

        # Call the LLM
        rating_response = call_deepseek_chat(rating_prompt, model=config.DEEPSEEK_CHAT_MODEL) # Use chat model

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


def generate_brief():
    """Generates the daily briefing by clustering articles and synthesizing."""
    print("\n--- Starting Brief Generation ---")
    articles = database.get_articles_for_briefing(config.BRIEFING_ARTICLE_LOOKBACK_HOURS)

    if not articles or len(articles) < config.MIN_ARTICLES_FOR_BRIEFING:
        print(f"Not enough recent articles ({len(articles)}) to generate a brief. Min required: {config.MIN_ARTICLES_FOR_BRIEFING}.")
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
    for i in range(n_clusters):
        cluster_indices = np.where(labels == i)[0]
        cluster_summaries = [summaries[idx] for idx in cluster_indices]

        if not cluster_summaries:
            continue

        print(f"  Analyzing Cluster {i} ({len(cluster_summaries)} articles)")

        # Limit summaries sent to LLM to avoid excessive length/cost
        MAX_SUMMARIES_PER_CLUSTER = 10
        analysis_prompt = "These are summaries of potentially related news articles:\n\n"
        analysis_prompt += "\n\n".join([f"- {s}" for s in cluster_summaries[:MAX_SUMMARIES_PER_CLUSTER]])
        analysis_prompt += "\n\nWhat is the core event or topic discussed? Summarize the key developments and significance in 3-5 sentences based *only* on the provided text. If the articles seem unrelated, state that."

        cluster_analysis = call_deepseek_chat(analysis_prompt, system_prompt="You are an intelligence analyst identifying key news themes.")
        if cluster_analysis:
            # Simple check to filter out potentially "unrelated" clusters if desired
            if "unrelated" not in cluster_analysis.lower() or len(cluster_summaries) > 2:
                 cluster_analyses.append({"topic": f"Cluster {i+1}", "analysis": cluster_analysis, "size": len(cluster_summaries)})
        time.sleep(2) # API rate limiting

    if not cluster_analyses:
        print("No meaningful clusters found or analyzed.")
        return

    # Sort clusters by size (number of articles) to prioritize major themes
    cluster_analyses.sort(key=lambda x: x['size'], reverse=True)

    # Synthesize Final Brief
    print("Synthesizing final brief...")
    synthesis_prompt = "You are an AI assistant writing a daily intelligence briefing for a tech and politics youtuber using Markdown. The quality of this briefing is vital for the development of the channel. Synthesize the following analyzed news clusters into a coherent, high-level executive summary. Start with the 2-3 most critical overarching themes globally based *only* on these inputs. Then, provide concise bullet points summarizing key developments within the most significant clusters (roughly 7-10 clusters) and a paragraph summarizing connections and conclusions between the points. Maintain an objective, analytical tone. Avoid speculation. Try to include the sources of each statement using a numbered reference style using Markdown link syntax. The link should reference the article title and NOT the news cluster, and link to the article link which is available right after it's summary. It's vital to understand the source of the information for later analysis.\n\n"
    synthesis_prompt += "Analyzed News Clusters (Most significant first):\n\n"
    for i, cluster in enumerate(cluster_analyses[:10]): # Limit to top 5 clusters for final brief
        synthesis_prompt += f"--- Cluster {i+1} ({cluster['size']} articles) ---\n"
        synthesis_prompt += f"Analysis: {cluster['analysis']}\n\n"

    final_brief_md = call_deepseek_chat(synthesis_prompt)

    if final_brief_md:
        # Save the brief
        database.save_brief(final_brief_md, article_ids) # Save IDs of all articles considered
        print("--- Brief Generation Finished Successfully ---")
    else:
        print("--- Brief Generation Failed: Could not synthesize final brief. ---")

# --- Main Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Meridian Briefing Runner: Scrapes, processes, and generates briefings.",
        formatter_class=argparse.RawTextHelpFormatter # Nicer help text formatting
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

    # Default to running all if no specific stage OR --all is provided
    should_run_all = args.run_all or not (args.scrape or args.process or args.generate or args.rate)

    print(f"Meridian Briefing Run - {datetime.now()}")
    database.init_db() # Initialize DB regardless of stage run

    if should_run_all:
        print("\n>>> Running ALL stages <<<")
        scrape_articles()
        process_articles()
        generate_brief()
    else:
        # Run specific stages if their flags are set
        if args.scrape:
            print("\n>>> Running ONLY Scrape Articles stage <<<")
            scrape_articles()
        if args.rate:
            print("\n>>> Running ONLY Rate Articles stage <<<")
            rate_articles()
        if args.process:
            print("\n>>> Running ONLY Process Articles stage <<<")
            process_articles()
        if args.generate:
            print("\n>>> Running ONLY Generate Brief stage <<<")
            generate_brief()

    print(f"\nRun Finished - {datetime.now()}")
