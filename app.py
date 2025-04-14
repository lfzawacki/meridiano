# simple-meridian/app.py

from flask import Flask, render_template, request
from markupsafe import Markup # Import Markup from markupsafe instead
import markdown
from datetime import datetime
import math
import config
import json

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
    """Displays a list of all generated briefings."""
    briefs_metadata = database.get_all_briefs_metadata()
    return render_template('index.html', # Render the new index template
                           briefs=briefs_metadata)

@app.route('/brief/<int:brief_id>')
def view_brief(brief_id):
    """Displays a single specific briefing."""
    brief_data = database.get_brief_by_id(brief_id)

    if brief_data is None:
        abort(404) # Return a 404 error if brief not found

    brief_content_html = Markup(markdown.markdown(brief_data['brief_markdown'], extensions=['fenced_code']))
    generation_time = format_datetime(brief_data['generated_at'], '%Y-%m-%d %H:%M:%S UTC')

    return render_template('brief.html', # Use a new template for viewing
                           brief_id=brief_data['id'],
                           brief_content=brief_content_html,
                           generation_time=generation_time)

@app.route('/articles')
def list_articles():
    """Displays a paginated list of stored articles with sorting."""
    # Pagination parameters
    try: page = int(request.args.get('page', 1))
    except ValueError: page = 1
    page = max(1, page)
    per_page = config.ARTICLES_PER_PAGE

    # --- Sorting parameters ---
    # Get sort parameters from query string, default to published_date desc
    sort_by = request.args.get('sort_by', 'published_date')
    direction = request.args.get('direction', 'desc')
    # Basic validation (more robust validation happens in database.py)
    if direction not in ['asc', 'desc']:
        direction = 'desc'
    # --- End Sorting parameters ---

    total_articles = database.get_total_article_count()

    # Fetch articles for the current page using sorting parameters
    articles_data = database.get_all_articles(
        page=page,
        per_page=per_page,
        sort_by=sort_by,        # Pass sorting params
        direction=direction
    )

    articles_data = [
        {**article, 'processed_content_html': Markup(markdown.markdown(article['processed_content'] or '',  extensions=['fenced_code']))}
        for article in articles_data
    ]

    # Calculate total pages
    if total_articles > 0: total_pages = math.ceil(total_articles / per_page)
    else: total_pages = 0
    if page > total_pages and total_pages > 0: page = total_pages

    return render_template('articles.html',
                           articles=articles_data,
                           page=page,
                           total_pages=total_pages,
                           per_page=per_page,
                           total_articles=total_articles,
                           # Pass current sort state to template
                           current_sort_by=sort_by,
                           current_direction=direction)

@app.route('/article/<int:article_id>')
def view_article(article_id):
    """Displays details for a single specific article."""
    article_data = database.get_article_by_id(article_id)

    if article_data is None:
        abort(404) # Return a 404 error if article not found

    # Basic check if embedding data exists (without showing the vector)
    embedding_status = "Not Generated"
    if article_data['embedding']:
        try:
            # Try loading to see if it's valid JSON and not empty
            embed_data = json.loads(article_data['embedding'])
            if embed_data:
                 # You could potentially calculate dimension here if needed: len(embed_data)
                 embedding_status = "Present"
            else:
                 embedding_status = "Present (Empty)"
        except (json.JSONDecodeError, TypeError):
            embedding_status = "Present (Invalid Format)"


    return render_template('view_article.html', # Use a new template
                           article=article_data,
                           embedding_status=embedding_status)

if __name__ == '__main__':
    database.init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
