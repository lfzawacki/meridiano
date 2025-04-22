# Meridiano: Your Personal Intelligence Briefing System

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](#) <!-- Replace with actual build status badge if you set up CI -->
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

**AI-powered intelligence briefings, tailored to your interests, built with simple, deployable tech.**

Meridiano cuts through the news noise by scraping configured sources, analyzing stories with AI (summaries, impact ratings), clustering related events, and delivering concise daily briefs via a web interface.

<p align="center">
  <video src="https://github.com/lfzawacki/meridiano/raw/refs/heads/main/meridiano-demo.mp4" alt="Meridiano Web Interface Demo" width="960"/>
</p>

## Why It Exists

Inspired by the concept of presidential daily briefings, Meridiano aims to provide similar focused intelligence, personalized for individual users. In an era of information overload, it helps you:

*   Stay informed on key global or specific topical events without drowning in noise.
*   Understand context beyond headlines through AI analysis.
*   Track developing stories via article clustering.
*   Leverage AI for summarization and impact assessment.
*   Maintain control through customizable feed profiles and open-source code.

Built for the curious mind wanting depth and relevance without the endless time sink of manual news consumption.

## Key Features

*   **Customizable Sources**: Define RSS feed lists via simple Python configuration files (`feeds/`).
*   **Multi-Stage Processing**: Modular pipeline (scrape, process, rate, brief) controllable via CLI.
*   **AI Analysis**: Uses Deepseek for summarization, impact rating, cluster analysis, and brief synthesis. Needs another AI provider for embeddings.
*   **Configurable Prompts**: Tailor LLM prompts for analysis and synthesis per feed profile.
*   **Smart Clustering**: Groups related articles using embeddings (via your chosen API) and KMeans.
*   **Impact Rating**: AI assigns a 1-10 impact score to articles based on their summary.
*   **Image Extraction**: Attempts to fetch representative images from RSS or article OG tags.
*   **FTS5 Search**: Fast and relevant full-text search across article titles and content.
*   **Web Interface**: Clean Flask-based UI to browse briefings and articles, with filtering (date, profile), sorting, pagination, and search.
*   **Simple Tech**: Built with Python, SQLite, and common libraries for easy setup and deployment.

## How It Works

```mermaid
graph TD
    A["Feed Profile Config (e.g., feeds/tech.py)"] --> B(run_briefing.py CLI);
    B -- Scrape --> C{RSS Feeds};
    C -- feedparser --> D[Article Metadata + URL];
    D -- requests/bs4 --> E[Fetch HTML + OG Image];
    E -- trafilatura --> F[Extract Content];
    G[RSS Image?] --> H{Select Image URL};
    E -- og_image --> H;
    F & H --> I(Add Article to DB);
    I -- feed_profile --> J[Articles Table (SQLite)];
    J -- image_url --> J;
    database.init_db -- Creates --> J;
    database.init_db -- Creates --> K[articles_fts Table (SQLite)];
    database.init_db -- Creates --> L[Briefs Table (SQLite)];
    I -- Trigger --> K;

    B -- Process --> M{Fetch Unprocessed Articles};
    M -- feed_profile --> J;
    M --> N[LLM Article Summary];
    N -- Deepseek API --> N;
    N -- embedding_client --> O[Generate Embeddings];
    O -- TogetherAI/Other API --> O;
    N & O --> P[Update Article Processing];
    P --> J;

    B -- Rate --> Q{Fetch Unrated Articles};
    Q -- feed_profile --> J;
    Q -- Summary --> R[LLM Impact Rating];
    R -- Deepseek API --> R;
    R --> S[Update Article Rating];
    S --> J;

    B -- Generate Brief --> T{Fetch Recent Processed Articles};
    T -- feed_profile --> J;
    T -- Embeddings --> U[Cluster Articles (KMeans)];
    U --> V[Analyze Clusters];
    V -- LLM Cluster Analysis --> V;
    V -- Deepseek API / Profile Prompt --> V;
    V --> W[Synthesize Brief];
    W -- LLM Brief Synthesis --> W;
    W -- Deepseek API / Profile Prompt --> W;
    W --> X[Save Brief to DB];
    X -- feed_profile --> L;

    Y[app.py (Flask Server)] --> Z{Web UI Request};
    Z -- Filters/Sort/Search --> Y;
    Y -- Reads --> J;
    Y -- Reads --> L;
    Y --> AA[Render HTML Template];
    AA --> BB[User Browser];

```

1.  **Configuration**: Load base settings (`config_base.py`) and feed-specific settings (`feeds/<profile_name>.py`), including RSS feeds and custom prompts.
2.  **CLI Control**: `run_briefing.py` orchestrates the stages based on CLI arguments (`--feed`, `--scrape`, `--process`, `--rate`, `--generate`, `--all`).
3.  **Scraping**: Fetches RSS, extracts article content, attempts to find an image (RSS or OG tag), and saves metadata (including `feed_profile`) to the `articles` table. FTS triggers populate `articles_fts`.
4.  **Processing**: Fetches unprocessed articles (per profile), generates summaries (using Deepseek), generates embeddings (using configured provider), and updates the `articles` table.
5.  **Rating**: Fetches unrated articles (per profile), asks Deepseek to rate impact based on summary, and updates the `articles` table.
6.  **Brief Generation**: Fetches recent, processed articles for the specified `feed_profile`, clusters them, analyzes clusters using profile-specific prompts (Deepseek), synthesizes a final brief using profile-specific prompts (Deepseek), and saves it to the `briefs` table.
7.  **Web Interface**: `app.py` (Flask) serves the UI, allowing users to browse briefs and articles, search (FTS), filter (profile, date), sort (date, impact), and paginate results.

## Tech Stack

*   **Backend**: Python 3.10+
*   **Database**: SQLite (with FTS5 enabled)
*   **Web Framework**: Flask
*   **AI APIs**:
    *   Deepseek API (Summaries, Rating, Analysis, Synthesis)
    *   Together AI API (Embeddings - or your configured provider)
*   **Core Libraries**:
    *   `feedparser` (RSS handling)
    *   `requests` (HTTP requests)
    *   `trafilatura` (Main content extraction)
    *   `beautifulsoup4` / `lxml` (HTML parsing for OG tags)
    *   `openai` (Python client for interacting with Deepseek/TogetherAI APIs)
    *   `scikit-learn`, `numpy` (Clustering)
    *   `python-dotenv` (Environment variables)
    *   `argparse` (CLI arguments)
    *   `markdown` (Rendering content in web UI)
*   **Frontend**: HTML, CSS, minimal vanilla JavaScript (for date filter toggle)

## Getting Started

**Prerequisites**:

*   Python 3.10 or later
*   Git (optional, for cloning)
*   API Keys:
    *   Deepseek API Key
    *   Together AI API Key (or key for your chosen embedding provider)

**Setup**:

1.  **Clone the repository (or download files):**
    ```bash
    git clone <your-repo-url> meridiano
    cd meridiano
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    # On macOS/Linux:
    source venv/bin/activate
    # On Windows:
    .\venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure API Keys:**
    *   Create a file named `.env` in the project root.
    *   Add your API keys:
        ```dotenv
        DEEPSEEK_API_KEY="your_deepseek_api_key_here"
        EMBEDDING_API_KEY="your_togetherai_or_other_embedding_api_key_here"
        ```

5.  **Configure Feeds and Prompts:**
    *   Review `config_base.py` for default settings and prompts.
    *   Create a `feeds/` directory in the project root.
    *   Inside `feeds/`, create profile configuration files (e.g., `default.py`, `tech.py`, `brazil.py`).
    *   Each `feeds/*.py` file **must** contain an `RSS_FEEDS = [...]` list.
    *   Optionally, define `PROMPT_CLUSTER_ANALYSIS` or `PROMPT_BRIEF_SYNTHESIS` in a `feeds/*.py` file to override the defaults from `config_base.py` for that specific profile. Define `EMBEDDING_MODEL` if overriding the default.

6.  **Initialize Database:**
    *   The database (`meridian.db`) and its schema (including FTS tables) are created automatically the first time you run `run_briefing.py` or `app.py`.

## Running the Application

Meridiano consists of a command-line script (`run_briefing.py`) for data processing and a web server (`app.py`) for viewing results.

**1. Running Processing Stages (`run_briefing.py`)**

Use the command line to run different stages for specific feed profiles.

*   **Arguments:**
    *   `--feed <profile_name>`: Specify the profile to use (e.g., `default`, `tech`, `brazil`). Defaults to `default`.
    *   `--scrape-articles`: Run only the scraping stage.
    *   `--process-articles`: Run only the summarization/embedding stage (per profile).
    *   `--rate-articles`: Run only the impact rating stage (per profile).
    *   `--generate-brief`: Run only the brief generation stage (per profile).
    *   `--all`: Run all stages sequentially for the specified profile.
    *   *(No stage argument)*: Defaults to running all stages (`--all`).

*   **Examples:**
    ```bash
    # Scrape articles for the 'tech' profile
    python run_briefing.py --feed tech --scrape-articles

    # Process and rate articles for the 'default' profile
    python run_briefing.py --feed default --process-articles
    python run_briefing.py --feed default --rate-articles

    # Generate the brief for the 'brazil' profile
    python run_briefing.py --feed brazil --generate-brief

    # Run all stages for the 'tech' profile
    python run_briefing.py --feed tech --all
    ```

*   **Scheduling:** For automatic daily runs, use `cron` (Linux/macOS) or Task Scheduler (Windows) to execute the desired `run_briefing.py` command(s) daily. Remember to use the full path to the Python executable within your virtual environment. Example cron job (runs all stages for 'default' profile at 7 AM):
    ```cron
    0 7 * * * /path/to/meridiano/venv/bin/python /path/to/meridiano/run_briefing.py --feed default --all >> /path/to/meridiano/meridiano.log 2>&1
    ```

**2. Running the Web Server (`app.py`)**

*   Start the Flask development server:
    ```bash
    python app.py
    ```
*   Access the web interface in your browser, usually at `http://localhost:5000`.
*   For more robust deployment, consider using a production WSGI server like Gunicorn:
    ```bash
    # pip install gunicorn
    gunicorn --bind 0.0.0.0:5000 app:app
    ```

## Contributing

1. Fork the repository on GitHub.
2. Create a new branch for your feature or bug fix (git checkout -b feature/your-feature-name).
3. Make your changes, adhering to the existing code style where possible.
4. (Optional but Recommended) Add tests for your changes if applicable.
5. Ensure your changes don't break existing functionality.
6. Commit your changes (git commit -am 'Add some feature').
7. Push to your branch (git push origin feature/your-feature-name).
8. Create a Pull Request on GitHub, describing your changes clearly.

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPLv3)**.

This license was chosen specifically to ensure that any modifications, derivative works, or network-hosted services based on this code remain open source and freely available to the community under the same terms.

In short, if you modify and distribute this software, or run a modified version as a network service that users interact with, you **must** make the complete corresponding source code of your version available under the AGPLv3.

You can find the full license text here:
[https://www.gnu.org/licenses/agpl-3.0.html](https://www.gnu.org/licenses/agpl-3.0.html)
