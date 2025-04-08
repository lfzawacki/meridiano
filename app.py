# simple-meridian/app.py

from flask import Flask, render_template, request
from markupsafe import Markup # Import Markup from markupsafe instead
import markdown
from datetime import datetime
import math
import config

import database # Import our database functions

app = Flask(__name__)

# Helper function for date formatting (optional but nice)
def format_datetime(value, format='%Y-%m-%d %H:%M'):
    if value is None:
        return "N/A"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value # Return original string if parsing fails
    if isinstance(value, datetime):
        return value.strftime(format)
    return value

# Register the filter with Jinja
app.jinja_env.filters['datetimeformat'] = format_datetime

@app.route('/')
def index():
    """Displays the latest briefing."""
    brief_data = database.get_latest_brief()
    brief_content_html = "<h2>No Briefing Available Yet</h2><p>Please run the `run_briefing.py` script first.</p>"
    generation_time = "N/A"

    if brief_data:
        # Convert Markdown to HTML
        # Use 'fenced_code' extension for better code block formatting if needed
        brief_content_html = Markup(markdown.markdown(brief_data['brief_markdown'], extensions=['fenced_code']))
        # Format the generation time
        gen_time_dt = brief_data['generated_at']
        if isinstance(gen_time_dt, str): # SQLite might return string
            try:
                gen_time_dt = datetime.fromisoformat(gen_time_dt)
            except ValueError: # Handle potential format issues
                 gen_time_dt = None

        if gen_time_dt:
             generation_time = gen_time_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        else:
             generation_time = str(brief_data['generated_at']) # Fallback

    return render_template('brief.html',
                           brief_content=brief_content_html,
                           generation_time=generation_time)

@app.route('/articles')
def list_articles():
    """Displays a paginated list of stored articles."""
    # Get page number from query parameter, default to 1, ensure it's an integer >= 1
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
    page = max(1, page) # Ensure page is at least 1

    per_page = config.ARTICLES_PER_PAGE
    total_articles = database.get_total_article_count()

    # Fetch articles for the current page
    articles_data = database.get_all_articles(page=page, per_page=per_page)

    # Calculate total pages
    if total_articles > 0:
        total_pages = math.ceil(total_articles / per_page)
    else:
        total_pages = 0 # Or 1, depending on desired behavior for zero items

    # Ensure page does not exceed total_pages if navigating beyond last page manually
    if page > total_pages and total_pages > 0:
         page = total_pages
         # Optional: Could redirect to the last page instead of just showing empty

    return render_template('articles.html',
                           articles=articles_data,
                           page=page,
                           total_pages=total_pages,
                           per_page=per_page,
                           total_articles=total_articles)

if __name__ == '__main__':
    database.init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
