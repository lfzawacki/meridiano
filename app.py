# simple-meridian/app.py

from flask import Flask, render_template
from markupsafe import Markup # Import Markup from markupsafe instead
import markdown
from datetime import datetime

import database # Import our database functions

app = Flask(__name__)

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

if __name__ == '__main__':
    # Make sure the database is initialized before running the app
    database.init_db()
    # Run on 0.0.0.0 to be accessible on the network
    # Use debug=False for any kind of "production" or shared use
    app.run(host='0.0.0.0', port=5000, debug=True)
