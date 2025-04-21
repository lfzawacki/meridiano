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
]

# Used in process_articles (operates globally, so uses default)
PROMPT_ARTICLE_SUMMARY = "Summarize the key points of this news article objectively in 2-4 sentences. Identify the main topics covered.\n\nArticle:\n{article_content}"

# Used in rate_articles (operates globally, so uses default)
PROMPT_IMPACT_RATING = """Analyze the following article summary and estimate its overall impact. Consider factors like newsworthiness, originality, geographic scope (local vs global), number of people affected, severity, and potential long-term consequences. Be extremely critical and conservative when assigning scores—higher scores should reflect truly exceptional or rare events.

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

# Used in generate_brief (can be overridden per profile)
# Use default

# Used in generate_brief (can be overridden per profile)
PROMPT_BRIEF_SYNTHESIS = """
You are an AI assistant writing a daily intelligence briefing for a tech and politics youtuber using Markdown. The quality of this briefing is vital for the development of the channel. Synthesize the following analyzed news clusters into a coherent, high-level executive summary. Start with the 2-3 most critical overarching themes globally based *only* on these inputs. Then, provide concise bullet points summarizing key developments within the most significant clusters (roughly 7-10 clusters) and a paragraph summarizing connections and conclusions between the points. Maintain an objective, analytical tone. Avoid speculation. Try to include the sources of each statement using a numbered reference style using Markdown link syntax. The link should reference the article title and NOT the news cluster, and link to the article link which is available right after it's summary. It's vital to understand the source of the information for later analysis.\n\n
"""
