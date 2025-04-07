# Simple Meridian (Python/SQLite/Deepseek Version)

This is a simplified implementation of the Meridian concept, designed for easy setup and deployment using Python, SQLite, and the Deepseek API.

It fetches news from RSS feeds, analyzes articles using Deepseek, clusters them, generates a daily Markdown brief, and serves it via a basic web interface.

## Tech Stack

*   **Backend/Core Logic:** Python 3.10+
*   **Database:** SQLite
*   **AI:** Deepseek API (Chat + Hypothetical Embeddings)
*   **RSS Parsing:** `feedparser`
*   **HTTP/Extraction:** `requests`, `trafilatura`
*   **Clustering:** `scikit-learn` (KMeans)
*   **Web Framework:** Flask
*   **Dependencies:** See `requirements.txt`

## Setup

1.  **Clone:**
    ```bash
    git clone <your-repo-url> simple-meridian
    cd simple-meridian
    ```

2.  **Create Virtual Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure API Key:**
    *   Copy `.env.example` to `.env` (or create `.env` from scratch).
    *   Edit `.env` and add your Deepseek API key:
        ```dotenv
        DEEPSEEK_API_KEY="your_deepseek_api_key_here"
        ```

5.  **Customize Feeds (Optional):**
    *   Edit `config.py` to change the `RSS_FEEDS` list or adjust other settings like `BRIEFING_ARTICLE_LOOKBACK_HOURS`.

## Running

1.  **Generate the Briefing:**
    *   This script scrapes, processes, and saves the brief to the database.
    *   Run it manually first:
        ```bash
        python run_briefing.py
        ```
    *   For daily automatic runs, set up a cron job (Linux/macOS) or Task Scheduler (Windows) to execute `python /path/to/simple-meridian/run_briefing.py`. Example cron job (runs daily at 8:00 AM):
        ```cron
        0 8 * * * /path/to/simple-meridian/venv/bin/python /path/to/simple-meridian/run_briefing.py >> /path/to/simple-meridian/meridian.log 2>&1
        ```

2.  **Run the Web Server:**
    *   This serves the latest brief stored in the database.
    ```bash
    python app.py
    ```
    *   Access the brief in your browser at `http://localhost:5000` (or `http://<your-server-ip>:5000` if running remotely).
    *   For more robust deployment, use a production server like Gunicorn:
        ```bash
        # pip install gunicorn
        gunicorn --bind 0.0.0.0:5000 app:app
        ```

## Important Notes

*   **Deepseek Embeddings:** The `get_deepseek_embedding` function currently uses *placeholder logic*. You **must** adapt this based on whether Deepseek offers a dedicated embedding API endpoint or if you need to use an alternative embedding method (like local sentence-transformers).
*   **Error Handling:** Error handling is basic. Robustness could be improved (e.g., retries for API calls, better feed parsing error management).
*   **Clustering:** KMeans clustering is used with a simple configuration. Results can be improved by tuning `N_CLUSTERS` in `config.py` or experimenting with other algorithms like DBSCAN.
*   **Scalability:** This SQLite and single-script approach is suitable for personal use but won't scale like the original Meridian's Cloudflare architecture.
*   **Cost:** Be mindful of Deepseek API usage costs, especially with frequent runs or large numbers of articles.
