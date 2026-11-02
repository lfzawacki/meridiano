import logging
import re
from collections import Counter
from datetime import datetime
from itertools import product
from urllib.parse import urljoin

import ftfy
import lxml.html
import requests
import trafilatura
from bs4 import BeautifulSoup
from lxml_html_clean import Cleaner

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger()


# Tags kept in the stored full-article HTML. Everything else is unwrapped (its
# text survives) or dropped by the cleaner, so the page can render it as-is.
FULL_CONTENT_ALLOWED_TAGS = frozenset(
    {
        "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6",
        "ul", "ol", "li", "blockquote", "pre", "code",
        "strong", "b", "em", "i", "u", "s", "sub", "sup",
        "a", "img", "figure", "figcaption",
        "table", "thead", "tbody", "tr", "th", "td",
    }
)
FULL_CONTENT_ALLOWED_ATTRS = frozenset({"href", "src", "alt", "title", "colspan", "rowspan"})

_full_content_cleaner = Cleaner(
    scripts=True,
    javascript=True,
    comments=True,
    style=True,
    inline_style=True,
    links=True,
    meta=True,
    page_structure=True,
    processing_instructions=True,
    embedded=True,
    frames=True,
    forms=True,
    annoying_tags=True,
    remove_unknown_tags=False,
    allow_tags=FULL_CONTENT_ALLOWED_TAGS,
    safe_attrs_only=True,
    safe_attrs=FULL_CONTENT_ALLOWED_ATTRS,
)


def _is_http_url(value):
    return bool(value) and value.lower().startswith(("http://", "https://"))


def sanitize_article_html(fragment, base_url):
    """Cleans extracted article HTML so it is safe to render with ``|safe``.

    Trafilatura emits images as ``<graphic>``; those become ``<img>``. Relative
    URLs are resolved against the article URL, anything that is not http(s)
    (javascript:, data:, ...) is dropped, and links open in a new tab without
    leaking the referrer. Returns None when nothing readable is left.
    """
    if not fragment:
        return None

    root = lxml.html.fragment_fromstring(fragment, create_parent="div")
    # Trafilatura's XML vocabulary leaks into its HTML output.
    for element in root.iter("graphic", "row", "cell"):
        if element.tag == "graphic":
            element.tag = "img"
        elif element.tag == "row":
            element.tag = "tr"
        else:
            element.tag = "th" if element.get("role") == "head" else "td"

    root = _full_content_cleaner.clean_html(root)

    seen_images = set()
    for img in list(root.iter("img")):
        raw_src = (img.get("src") or "").strip()
        src = urljoin(base_url, raw_src) if raw_src else ""
        # Trafilatura sometimes emits the same picture twice (once per scheme).
        image_key = src.split("://", 1)[-1]
        if not _is_http_url(src) or image_key in seen_images:
            img.drop_tree()
            continue
        seen_images.add(image_key)
        img.set("src", src)
        img.set("loading", "lazy")
        img.set("referrerpolicy", "no-referrer")

    for link in root.iter("a"):
        raw_href = (link.get("href") or "").strip()
        href = urljoin(base_url, raw_href) if raw_href else ""
        if _is_http_url(href):
            link.set("href", href)
            link.set("target", "_blank")
            link.set("rel", "noopener noreferrer nofollow")
        else:
            link.attrib.pop("href", None)

    if not root.text_content().strip() and root.find(".//img") is None:
        return None

    # The wrapper <div> added above is not part of the stored fragment.
    parts = [root.text or ""] + [lxml.html.tostring(child, encoding="unicode") for child in root]
    return "".join(parts).strip() or None


def decode_html_response(response):
    """Decodes a page body, not trusting requests' charset fallback.

    Without a charset in Content-Type, requests assumes ISO-8859-1 for text/*,
    which turns UTF-8 pages (e.g. Folha) into mojibake ("vegetaÃ§Ã£o"). In that
    case strict UTF-8 is tried first -- Latin-1 text with accents is almost never
    valid UTF-8 -- and the detected encoding is the fallback.
    """
    content_type = response.headers.get("Content-Type", "") or ""
    if "charset=" in content_type.lower():
        return response.text
    try:
        return response.content.decode("utf-8")
    except UnicodeDecodeError:
        return response.content.decode(response.apparent_encoding or "latin-1", errors="replace")


# Text decoded with the wrong charset and then cleaned by trafilatura is lossy:
# the second byte of some letters was an invisible character that got stripped
# (soft hyphen in "í", NBSP in "à", C1 controls in uppercase accents), leaving a
# lone "Ã" that no codec round-trip can undo. These patterns cover what is left.
_LONE_A_TILDE_IN_WORD = re.compile(r"(?<=[^\W\d_])Ã(?=[a-zà-ÿ])")  # benefÃcios -> benefícios
_LONE_A_TILDE_END = re.compile(r"(?<=[a-zà-ÿ])Ã(?=[\s.,;:!?)\"'”»]|$)")  # daÃ -> daí
_LONE_A_TILDE_ALONE = re.compile(r"(?<!\w)Ã(?= )")  # Ã BBC -> à BBC
_WORD_WITH_A_TILDE = re.compile(r"[^\W\d_]*Ã[^\W\d_]*")  # Ãfrica, TAMBÃM, MÃS
_STRAY_CIRCUMFLEX = re.compile(r"Â(?=[\s\xa0])")  # mangled NBSP
# "Ã" itself (kept as-is, e.g. "SÃO") plus the uppercase letters whose UTF-8
# second byte is a C1 control and so was stripped.
_A_TILDE_CANDIDATES = "ÃÀÁÂÇÉÊÍÓÔÕÚ"
_WORD_RE = re.compile(r"[^\W\d_]+")


def word_vocabulary(texts):
    """Counts the lowercase accented words in ``texts``; used to pick between
    the candidates for a lost uppercase letter.

    A capital "Ã" is only real in all-caps words ("SÃO"); in any other word it
    is leftover mojibake ("Ãfrica") and must not vote for itself.
    """
    vocabulary = Counter()
    for text in texts:
        if text:
            vocabulary.update(
                w.lower() for w in _WORD_RE.findall(text) if not w.isascii() and ("Ã" not in w or w.isupper())
            )
    return vocabulary


def repair_mojibake(text, vocabulary=None):
    """Repairs UTF-8 text that was decoded as Latin-1 ("Ã©" -> "é").

    ftfy undoes the reversible sequences; the lossy leftovers are handled by
    the patterns above. Any remaining "Ã" (lost "Á", "Ê", "Ç"...) is resolved
    per word against ``vocabulary`` (see word_vocabulary) and left as-is when
    no candidate is more common than the word as written. Text without mojibake markers is returned as is.
    """
    if not text or ("Ã" not in text and "Â" not in text):
        return text

    fixed = ftfy.fix_encoding(text)
    fixed = _STRAY_CIRCUMFLEX.sub("", fixed)
    fixed = _LONE_A_TILDE_ALONE.sub("à", fixed)

    fixed = _LONE_A_TILDE_IN_WORD.sub("í", fixed)
    fixed = _LONE_A_TILDE_END.sub("í", fixed)
    if vocabulary:
        fixed = _WORD_WITH_A_TILDE.sub(lambda m: _resolve_a_tilde_word(m.group(0), vocabulary), fixed)
    return fixed


def _resolve_a_tilde_word(word, vocabulary):
    """Picks, for each "Ã" in ``word``, the letter that makes the most common
    known word. "Ã" itself is a candidate, so real words like "SÃO" survive."""
    positions = [i for i, char in enumerate(word) if char == "Ã"]
    if len(positions) > 2:
        return word

    best, best_count = word, vocabulary.get(word.lower(), 0)
    for letters in product(_A_TILDE_CANDIDATES, repeat=len(positions)):
        candidate = list(word)
        for position, letter in zip(positions, letters):
            # Keep the case of the word: lowercase inside a lowercase word.
            lower_word = position > 0 and word[position - 1].islower()
            candidate[position] = letter.lower() if lower_word else letter
        candidate = "".join(candidate)
        count = vocabulary.get(candidate.lower(), 0)
        if count > best_count:
            best, best_count = candidate, count
    return best


# Lazy-loading attributes that hold the real image URL, in order of preference.
LAZY_IMAGE_ATTRS = ("data-src", "data-lazy-src", "data-original", "data-url")


def _image_source(img):
    """The real URL of an <img>, looking past lazy-loading placeholders."""
    for attr in LAZY_IMAGE_ATTRS + ("src",):
        value = (img.get(attr) or "").strip()
        if value and not value.startswith("data:"):
            return value
    for attr in ("data-srcset", "srcset"):
        candidates = [c.split()[0] for c in (img.get(attr) or "").split(",") if c.strip()]
        if candidates:
            return candidates[-1]  # srcset lists sizes ascending; take the largest
    return None


def simplify_figures(html_content):
    """Rewrites a page's images into markup trafilatura keeps.

    Trafilatura drops images it would otherwise keep when they sit inside
    containers it treats as boilerplate (Folha wraps every photo in
    ``div.widget-image``) or when the URL only lives in a lazy-load attribute.
    Each <figure> becomes a bare <figure><img> plus its caption, replacing the
    wrapper elements that held nothing else, and every <img> gets a usable src.
    """
    try:
        doc = lxml.html.document_fromstring(html_content)
    except Exception:
        return html_content

    for noscript in doc.xpath("//noscript"):
        noscript.drop_tree()  # holds a duplicate of the lazy image

    for img in doc.iter("img"):
        source = _image_source(img)
        if source:
            img.set("src", source)

    for figure in list(doc.iter("figure")):
        img = figure.find(".//img")
        source = img.get("src") if img is not None else None
        if not source:
            continue

        caption_el = figure.find(".//figcaption")
        caption = " ".join(caption_el.text_content().split()) if caption_el is not None else ""

        simple = lxml.html.Element("figure")
        simple.append(lxml.html.Element("img", src=source, alt=img.get("alt") or ""))
        if caption:
            caption_p = lxml.html.Element("p")
            caption_em = lxml.html.Element("em")
            caption_em.text = caption
            caption_p.append(caption_em)
            simple.append(caption_p)

        # Climb out of wrappers that contain nothing but this figure.
        target = figure
        figure_text = figure.text_content().strip()
        parent = target.getparent()
        while (
            parent is not None
            and parent.tag not in ("body", "article", "main")
            and len(parent.xpath(".//img")) == len(figure.xpath(".//img"))
            and parent.text_content().strip() == figure_text
        ):
            target, parent = parent, parent.getparent()

        if target.getparent() is not None:
            simple.tail = target.tail
            target.getparent().replace(target, simple)

    return lxml.html.tostring(doc, encoding="unicode")


def extract_full_article_html(html_content, url):
    """Extracts the article body from a page as sanitized HTML, images included."""
    try:
        extracted = trafilatura.extract(
            simplify_figures(html_content),
            url=url,
            output_format="html",
            include_images=True,
            include_links=True,
            include_formatting=True,
            include_tables=True,
            include_comments=False,
        )
        if not extracted:
            return None
        # Trafilatura wraps its output in <html><body>; keep only the body content.
        body = lxml.html.fromstring(extracted).find(".//body")
        if body is None:
            return sanitize_article_html(extracted, url)
        inner = (body.text or "") + "".join(lxml.html.tostring(child, encoding="unicode") for child in body)
        return sanitize_article_html(inner, url)
    except Exception as e:
        logger.warning(f"Could not extract full HTML for {url}: {e}")
        return None


# Helper function for date formatting (optional but nice)
def format_datetime(value, format="%Y-%m-%d %H:%M"):
    if value is None:
        return "N/A"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value  # Return original string if parsing fails
    if isinstance(value, datetime):
        return value.strftime(format)
    return value


def fetch_article_content_and_og_image(url):
    """
    Fetches HTML, extracts main content using Trafilatura,
    and extracts the og:image URL using BeautifulSoup.

    Returns:
        dict: {'content': str|None, 'og_image': str|None, 'full_html': str|None}
        'full_html' is the article body as sanitized HTML with its images, taken
        from the same response so no extra request is made.
    """
    content = None
    og_image = None
    full_html = None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:137.0) Gecko/20100101 Firefox/137.0",
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
            "referer": "https://www.google.com",
        }
        response = requests.get(url, headers=headers, timeout=20)  # Increased timeout slightly
        response.raise_for_status()
        html_content = decode_html_response(response)

        # 1. Extract text content
        content = trafilatura.extract(html_content, include_comments=False, include_tables=False)

        # 2. Extract og:image using BeautifulSoup
        soup = BeautifulSoup(html_content, "lxml")  # Use lxml or html.parser
        og_image_tag = soup.find("meta", property="og:image")
        if og_image_tag and og_image_tag.get("content"):
            og_image = og_image_tag["content"]
            # Optionally resolve relative URLs - less common for og:image but possible
            og_image = urljoin(url, og_image)

        # 3. Full article body as HTML, with images, for the reader views
        if content:
            full_html = extract_full_article_html(html_content, url)

        return {"content": content, "og_image": og_image, "full_html": full_html}

    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return {"content": None, "og_image": None, "full_html": None}
    except Exception as e:
        # Catch potential BeautifulSoup errors or others
        print(f"Error processing content/og:image from {url}: {e}")
        # Still return content if it was extracted before the error
        return {"content": content, "og_image": None, "full_html": None}


def scrape_single_article_details(article_url):
    """
    Fetches and extracts details (title, raw_content, image_url) for a single article URL.

    Args:
        article_url (str): The URL of the article to scrape.

    Returns:
        dict: {'title', 'raw_content', 'image_url', 'full_content_html', 'error'} (each str|None)
              'error' key will be present if fetching/processing failed.
    """
    print(f"Attempting to scrape single article: {article_url}")
    fetched_title = None
    raw_content = None
    final_image_url = None
    full_content_html = None
    error_message = None

    try:
        # Use the existing fetch_article_content_and_og_image helper
        fetch_result = fetch_article_content_and_og_image(article_url)  # This already logs its own errors

        raw_content = fetch_result["content"]
        og_image_url = fetch_result["og_image"]
        full_content_html = fetch_result.get("full_html")

        if not raw_content:
            # fetch_article_content_and_og_image might have already logged, but good to have a specific error here
            error_message = "Failed to extract main content from the article."
            logger.warning(f"{error_message} URL: {article_url}")
            # Even if content fails, we might still get a title or image from OG tags if fetch worked partially
            # So, continue to try and extract title if possible.

        # --- Attempt to get a title from the page if not from RSS ---
        # We need to re-fetch or use the already fetched HTML if available from fetch_article_content_and_og_image
        # Let's assume fetch_article_content_and_og_image doesn't return the full soup object.
        # If it did, we could reuse it. For now, we might need a minimal re-fetch or a helper modification.
        # Simplification: If trafilatura got content, it often implies page was fetched.
        # We could parse the title from the raw_content's source HTML (if fetch_... stored it)
        # or do another small HEAD request or parse from a snippet.
        # For now, we'll use a placeholder if the feed didn't provide it.
        # A more robust solution would be to enhance fetch_article_content_and_og_image
        # to also return the <title> tag content.

        if raw_content:  # If we got content, try to get title from HTML
            try:
                # Need to parse the HTML again if not already available from previous fetch
                headers = {"User-Agent": "Mozilla/5.0 ..."}  # Your headers
                response = requests.get(article_url, headers=headers, timeout=15)
                response.raise_for_status()
                soup = BeautifulSoup(decode_html_response(response), "lxml")
                title_tag = soup.find("title")
                if title_tag and title_tag.string:
                    fetched_title = title_tag.string.strip()
                # Fallback to OG title if HTML title is poor/missing
                if not fetched_title:
                    og_title_tag = soup.find("meta", property="og:title")
                    if og_title_tag and og_title_tag.get("content"):
                        fetched_title = og_title_tag["content"].strip()
            except Exception as title_e:
                logger.warning(f"Could not extract title for {article_url}: {title_e}")
                # Continue without title if it fails

        final_image_url = og_image_url  # For a single manual add, OG image is the primary target

        if not raw_content and not fetched_title and not final_image_url:
            # If absolutely nothing was fetched, it's a more significant error
            error_message = "Failed to fetch any content, title, or image from the URL."

    except Exception as e:
        error_message = f"General error scraping single article {article_url}: {e}"
        logger.error(error_message, exc_info=True)

    return {
        "title": fetched_title,
        "raw_content": raw_content,
        "image_url": final_image_url,
        "full_content_html": full_content_html,
        "error": error_message,
    }
