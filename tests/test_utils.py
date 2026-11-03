"""
Tests for utility functions.
"""

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from meridiano.utils import (
    decode_html_response,
    detect_paywall,
    extract_full_article_html,
    fetch_article_content_and_og_image,
    format_datetime,
    looks_truncated,
    repair_mojibake,
    sanitize_article_html,
    simplify_figures,
    word_vocabulary,
)


class TestFormatDatetime:
    """Tests for datetime formatting."""

    def test_format_datetime_none(self):
        """Test formatting None value."""
        result = format_datetime(None)
        assert result == "N/A"

    def test_format_datetime_datetime_object(self):
        """Test formatting datetime object."""
        dt = datetime(2024, 1, 15, 14, 30, 45)
        result = format_datetime(dt)
        assert result == "2024-01-15 14:30"

    def test_format_datetime_datetime_custom_format(self):
        """Test formatting datetime with custom format."""
        dt = datetime(2024, 1, 15, 14, 30, 45)
        result = format_datetime(dt, "%Y-%m-%d")
        assert result == "2024-01-15"

    def test_format_datetime_string(self):
        """Test formatting ISO format string."""
        iso_string = "2024-01-15T14:30:45"
        result = format_datetime(iso_string)
        assert result == "2024-01-15 14:30"

    def test_format_datetime_invalid_string(self):
        """Test formatting invalid string (should return original)."""
        invalid_string = "not-a-date"
        result = format_datetime(invalid_string)
        assert result == invalid_string

    def test_format_datetime_empty_string(self):
        """Test formatting empty string."""
        result = format_datetime("")
        assert result == ""


class TestSanitizeArticleHtml:
    """Full-article HTML is rendered with |safe, so the sanitizer is the guard."""

    def test_strips_scripts_handlers_and_unsafe_urls(self):
        html = (
            '<p onclick="x()">Hi <a href="javascript:alert(1)">bad</a> <a href="/rel">ok</a></p>'
            '<script>alert(1)</script><iframe src="https://evil.example"></iframe>'
            '<img src="data:image/gif;base64,AAA"><img src="/pic.jpg" onerror="alert(1)" style="x">'
        )
        result = sanitize_article_html(html, "https://example.com/a/b")

        assert "script" not in result
        assert "iframe" not in result
        assert "onclick" not in result
        assert "onerror" not in result
        assert "style" not in result
        assert "javascript:" not in result
        assert "data:image" not in result
        assert 'href="https://example.com/rel"' in result
        assert 'src="https://example.com/pic.jpg"' in result
        assert 'rel="noopener noreferrer nofollow"' in result

    def test_converts_trafilatura_graphics_and_tables(self):
        html = '<graphic src="/a.jpg"/><table><row><cell role="head">H</cell></row><row><cell>v</cell></row></table>'
        result = sanitize_article_html(html, "https://example.com/")

        assert '<img src="https://example.com/a.jpg"' in result
        assert "<th>H</th>" in result
        assert "<td>v</td>" in result

    def test_dedupes_the_same_image_across_schemes(self):
        html = '<img src="https://cdn.example.com/a.jpg"><img src="http://cdn.example.com/a.jpg">'
        assert sanitize_article_html(html, "https://example.com/").count("<img") == 1

    def test_empty_results_are_none(self):
        assert sanitize_article_html(None, "https://example.com/") is None
        assert sanitize_article_html("<script>x</script>", "https://example.com/") is None


class TestExtractFullArticleHtml:
    def test_keeps_body_images_and_drops_page_chrome(self):
        body = "Sentence of a real article body. " * 30
        html = (
            "<html><body><nav>Site menu</nav><article><h1>Title</h1>"
            f'<p>{body}</p><figure><img src="/photo.jpg" alt="Photo"></figure><p>{body}</p>'
            "</article><footer>Footer links</footer></body></html>"
        )
        result = extract_full_article_html(html, "https://example.com/story")

        assert result is not None
        assert "<html" not in result
        assert "<body" not in result
        assert 'src="https://example.com/photo.jpg"' in result
        assert "Site menu" not in result


class TestDecodeHtmlResponse:
    def _response(self, body, content_type):
        response = MagicMock()
        response.headers = {"Content-Type": content_type}
        response.content = body
        response.text = body.decode("latin-1")  # what requests guesses without a charset
        response.apparent_encoding = "windows-1252"
        return response

    def test_utf8_page_without_charset_is_not_latin1(self):
        """Folha serves UTF-8 as plain 'text/html'; requests would yield 'vegetaÃ§Ã£o'."""
        response = self._response("vegetação".encode(), "text/html")
        assert decode_html_response(response) == "vegetação"

    def test_latin1_page_without_charset_falls_back_to_detection(self):
        response = self._response("vegetação".encode("latin-1"), "text/html")
        assert decode_html_response(response) == "vegetação"

    def test_declared_charset_is_trusted(self):
        response = self._response(b"x", "text/html; charset=ISO-8859-1")
        response.text = "declared"
        assert decode_html_response(response) == "declared"


class TestRepairMojibake:
    def test_reversible_sequences(self):
        assert repair_mojibake("vegetaÃ§Ã£o e coraÃ§Ã£o, Ã©") == "vegetação e coração, é"

    def test_lossy_leftovers(self):
        """Stripped soft hyphen (í) and NBSP (à) leave a lone 'Ã'."""
        assert repair_mojibake("PacÃfico, paraÃso, LÃbano e Ã BBC") == "Pacífico, paraíso, Líbano e à BBC"

    def test_lost_uppercase_resolved_by_vocabulary(self):
        vocabulary = word_vocabulary(["África também mês justiça são"])
        assert repair_mojibake("na Ãfrica, TAMBÃM no MÃS da JUSTIÃA", vocabulary) == (
            "na África, TAMBÉM no MÊS da JUSTIÇA"
        )

    def test_real_a_tilde_is_kept(self):
        vocabulary = word_vocabulary(["são não"])
        assert repair_mojibake("SÃO PAULO diz NÃO", vocabulary) == "SÃO PAULO diz NÃO"

    def test_clean_text_untouched(self):
        assert repair_mojibake("Coração “aspas” — ok") == "Coração “aspas” — ok"
        assert repair_mojibake(None) is None


class TestSimplifyFigures:
    def test_lazy_image_in_widget_wrapper_survives_extraction(self):
        """Folha wraps photos in div.widget-image, which trafilatura drops as boilerplate."""
        body = "Texto do corpo do artigo com bastante conteúdo. " * 25
        html = (
            f"<html><body><article><p>{body}</p>"
            '<div class="widget-image"><figure><div class="ratio">'
            '<img class="c-lazyload" data-src="https://cdn.example.com/foto_md.jpg" alt="Foto">'
            '<noscript><img src="https://cdn.example.com/foto_md.jpg"></noscript>'
            "</div><figcaption>Legenda <span>Crédito</span></figcaption></figure></div>"
            f"<p>{body}</p></article></body></html>"
        )
        assert 'class="widget-image"' not in simplify_figures(html)

        result = extract_full_article_html(html, "https://example.com/story")
        assert result.count("<img") == 1
        assert 'src="https://cdn.example.com/foto_md.jpg"' in result
        assert "Legenda Crédito" in result


class TestDetectPaywall:
    def test_json_ld_boolean_false(self):
        html = (
            '<html><head><script type="application/ld+json">'
            '{"@type": "NewsArticle", "isAccessibleForFree": false}</script></head></html>'
        )
        assert detect_paywall(html) is True

    def test_json_ld_nested_in_has_part_and_graph(self):
        html = (
            '<html><head><script type="application/ld+json">'
            '{"@graph": [{"@type": "NewsArticle", "hasPart": {"@type": "WebPageElement",'
            ' "isAccessibleForFree": "https://schema.org/False", "cssSelector": ".paywall"}}]}'
            "</script></head></html>"
        )
        assert detect_paywall(html) is True

    def test_microdata_meta(self):
        html = (
            '<html><body><span itemprop="hasPart">'
            '<meta itemprop="isAccessibleForFree" content="false"></span></body></html>'
        )
        assert detect_paywall(html) is True

    def test_free_or_unmarked_pages(self):
        free = '<html><head><script type="application/ld+json">{"isAccessibleForFree": true}</script></head></html>'
        broken = '<html><head><script type="application/ld+json">{not json</script></head></html>'
        assert detect_paywall(free) is False
        assert detect_paywall(broken) is False
        assert detect_paywall("<html><body><p>paywall talk</p></body></html>") is False
        assert detect_paywall(None) is False

    def test_fetch_reports_paywall(self):
        html = (
            '<html><head><script type="application/ld+json">{"isAccessibleForFree": "False"}</script></head>'
            "<body><article><p>" + "Long paragraph of real article text. " * 20 + "</p></article></body></html>"
        )
        response = MagicMock(status_code=200, text=html, content=html.encode())
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        with patch("meridiano.utils.requests.get", return_value=response):
            result = fetch_article_content_and_og_image("https://example.com/paid")
        assert result["full_html"]
        assert result["paywalled"] is True


class TestLooksTruncated:
    def test_paragraph_cut_mid_sentence(self):
        assert looks_truncated("<p>First.</p><p>It was presented at a</p>") is True

    def test_complete_endings(self):
        assert looks_truncated("<p>Done.</p>") is False
        assert looks_truncated('<p>"Quote ends here."</p>') is False
        assert looks_truncated("<p>Is it?</p><p>   </p>") is False

    def test_trailing_list_or_table_is_not_judged(self):
        assert looks_truncated("<p>Schedule:</p><ul><li>Band: 19h30</li></ul>") is False
        assert looks_truncated("<p>Prices</p><table><tr><td>10</td></tr></table>") is False

    def test_empty(self):
        assert looks_truncated(None) is False
        assert looks_truncated("") is False
