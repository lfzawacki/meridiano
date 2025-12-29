RSS_FEEDS = [
  "https://krebsonsecurity.com/feed/",
  "https://feeds.feedburner.com/TheHackersNews",
  "https://www.darkreading.com/rss.xml",
  "https://www.bleepingcomputer.com/feed/",
  "https://www.wired.com/feed/category/security/latest/rss",
]

# Used in process_articles (operates globally, so uses default)
PROMPT_ARTICLE_SUMMARY = "Summarize the key points of this news article objectively in 3-5 sentences. Identify the main topics covered. Only include the result of the summarization, don't preface it with any text.\n\nArticle:\n{article_content}"

# Used in rate_articles (operates globally, so uses default)
PROMPT_IMPACT_RATING = """Analyze the following information security article summary and estimate its overall real-world impact.

Evaluate impact using security-relevant factors such as:
- Scope of affected systems (single org vs widespread/global)
- Severity of impact on the CIA triad (confidentiality, integrity, availability)
- Exploitability (theoretical vs proven, ease of exploitation)
- Evidence of active exploitation or real-world attacks
- Number and type of affected organizations/users
- Supply-chain implications
- Availability of mitigations or patches
- Regulatory, legal, or geopolitical consequences
- Potential long-term or systemic security implications

Be extremely critical and conservative when assigning scores. Higher scores should be reserved only for rare, high-impact security events with clear, demonstrated consequences.

Rate the impact on a scale of 1 to 10, using these guidelines:

1–2: Minimal security significance.
Informational, academic, or niche content with no immediate risk.
Examples:
- A theoretical vulnerability with no proof of concept
- A vendor blog about best practices
- A minor bug affecting a rarely used feature

3–4: Limited or localized security relevance.
Affects a small number of users or a specific product with low severity.
Examples:
- A low-severity vulnerability in a single product
- A minor breach with no sensitive data exposed
- Security updates for non-critical systems

5–6: Moderately significant security impact.
Affects multiple organizations or a widely used product, but with mitigations available or limited damage.
Examples:
- A medium-to-high CVSS vulnerability in common software
- A confirmed breach affecting one major organization
- A security policy or regulation change impacting an industry

7–8: Highly significant security event.
Widespread impact, active exploitation, or serious operational disruption.
Examples:
- A zero-day exploited in the wild affecting many organizations
- A major supply-chain compromise
- A large-scale ransomware campaign disrupting critical services

9–10: Extraordinary and historic security impact.
Global, systemic, and long-lasting consequences for the security landscape.
Examples:
- Internet-wide exploitation of a core protocol or library
- A catastrophic breach affecting critical infrastructure across countries
- A security incident fundamentally reshaping global cyber defense practices

Key Reminder: Scores of 9–10 should be exceedingly rare and reserved for truly world-defining security events. Always err toward a lower score unless the impact is clearly demonstrated, widespread, and severe.

Summary:
"{summary}"

Output ONLY the integer number representing your rating (1–10)."""

# Used in generate_brief (can be overridden per profile)
# Use default

# Used in generate_brief (can be overridden per profile)
PROMPT_BRIEF_SYNTHESIS = """
You are an AI assistant writing a daily intelligence briefing on information security using Markdown. The quality of this briefing is vital. Synthesize the following analyzed news clusters into a coherent, high-level executive summary. Start with the 2-3 most critical overarching themes globally based *only* on these inputs. Then, provide concise bullet points summarizing key developments within the most significant clusters (roughly 7-10 clusters) and a paragraph summarizing connections and conclusions between the points. Maintain an objective, analytical tone. Avoid speculation. Just include the briefing, don't preface it with any unecessary text.\n\n

Analyzed News Clusters (Most significant first):
{cluster_analyses_text}
"""
