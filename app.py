# simple-meridian/app.py

from flask import Flask, render_template, request
from markupsafe import Markup
import markdown
from datetime import datetime, timedelta, date
import math
import json

import config_base as config # Use base config for app settings
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
    """Displays a list of briefings, filterable by feed profile."""
    current_feed_profile = request.args.get('feed_profile', '') # Get filter, empty means 'All'
    briefs_metadata = database.get_all_briefs_metadata(
        feed_profile=current_feed_profile if current_feed_profile else None # Pass None for 'All'
        )
    # Get profiles for dropdown
    available_profiles = database.get_distinct_feed_profiles(table='briefs')

    return render_template('index.html',
                           briefs=briefs_metadata,
                           available_profiles=available_profiles,
                           current_feed_profile=current_feed_profile)

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
    """ Displays a paginated list of stored articles with sorting and date filtering. """
    # --- Pagination ---
    try: page = int(request.args.get('page', 1))
    except ValueError: page = 1
    page = max(1, page)
    per_page = getattr(config, 'ARTICLES_PER_PAGE', 25)

    # --- Sorting ---
    sort_by = request.args.get('sort_by', 'published_date')
    direction = request.args.get('direction', 'desc')
    if direction not in ['asc', 'desc']: direction = 'desc'

    # --- Date Filtering ---
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    preset = request.args.get('preset', '')

    start_date, end_date = None, None # Initialize date objects

    # Calculate dates based on preset if provided
    if preset:
        today = date.today()
        if preset == 'yesterday':
            start_date = today - timedelta(days=1)
            end_date = start_date
        elif preset == 'last_week': # Last 7 days including today
            start_date = today - timedelta(days=6)
            end_date = today
        elif preset == 'last_30d':
            start_date = today - timedelta(days=29)
            end_date = today
        elif preset == 'last_3m': # Approx 90 days
            start_date = today - timedelta(days=89)
            end_date = today
        elif preset == 'last_12m': # Approx 365 days
            start_date = today - timedelta(days=364)
            end_date = today

        # Convert calculated dates back to strings for template pre-filling
        start_date_str = start_date.isoformat() if start_date else ''
        end_date_str = end_date.isoformat() if end_date else ''

    # If no preset, try parsing manual dates
    else:
        try:
            if start_date_str:
                start_date = date.fromisoformat(start_date_str)
        except ValueError:
            start_date_str = '' # Clear invalid date string
            start_date = None
            print(f"Warning: Invalid start_date format '{request.args.get('start_date')}'")
        try:
            if end_date_str:
                end_date = date.fromisoformat(end_date_str)
        except ValueError:
            end_date_str = '' # Clear invalid date string
            end_date = None
            print(f"Warning: Invalid end_date format '{request.args.get('end_date')}'")

    # --- End Date Filtering ---

    current_feed_profile = request.args.get('feed_profile', '') # Empty means 'All'

    # Fetch total count with ALL filters
    total_articles = database.get_total_article_count(
        start_date=start_date,
        end_date=end_date,
        feed_profile=current_feed_profile if current_feed_profile else None # Pass None for 'All'
        )

    # Fetch articles with ALL filters and sorting
    articles_data = database.get_all_articles(
        page=page, per_page=per_page, sort_by=sort_by, direction=direction,
        start_date=start_date, end_date=end_date,
        feed_profile=current_feed_profile if current_feed_profile else None # Pass None for 'All'
    )

    articles_data = [
        {**article, 'processed_content_html': Markup(markdown.markdown(article['processed_content'] or '',  extensions=['fenced_code']))}
        for article in articles_data
    ]

    # Calculate total pages based on filtered count
    if total_articles > 0: total_pages = math.ceil(total_articles / per_page)
    else: total_pages = 0
    if page > total_pages and total_pages > 0:
        # Optional: redirect to last valid page if request goes beyond
        args = request.args.copy()
        args['page'] = total_pages
        # return redirect(url_for('list_articles', **args)) # Redirect approach
        page = total_pages # Simpler: just set page to last page

    # Get profiles for dropdown
    available_profiles = database.get_distinct_feed_profiles(table='articles')

    return render_template('articles.html',
                           articles=articles_data,
                           page=page, total_pages=total_pages, per_page=per_page,
                           total_articles=total_articles, # Filtered total
                           current_sort_by=sort_by, current_direction=direction,
                           current_start_date=start_date_str, current_end_date=end_date_str,
                           current_preset=preset,
                           # Feed profile state
                           available_profiles=available_profiles,
                           current_feed_profile=current_feed_profile)

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
