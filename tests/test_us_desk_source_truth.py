"""The U.S. Desk's public coverage claims must follow admitted source rows.

Render only the two self-contained template panels with synthetic link counts.
No production SQLite, source network, Pages, or release side effects.
"""
import unittest
from pathlib import Path
from types import SimpleNamespace

from bs4 import BeautifulSoup
from jinja2 import Environment, StrictUndefined

TEMPLATE = Path(__file__).resolve().parents[1] / "site/preview/templates/desk.html"


def template_fragment(start, end, close=""):
    source = TEMPLATE.read_text(encoding="utf-8")
    return Environment(autoescape=True, undefined=StrictUndefined).from_string(
        source[source.index(start):source.index(end, source.index(start))] + close
    )


def render_panels(uscc=10, treasury=0, bis=0, slug="us-indopacific"):
    fields = {
        "desk": SimpleNamespace(slug=slug),
        "uscc_official_links": [{}] * uscc,
        "us_treasury_official_links": [{}] * treasury,
        "us_bis_authenticated_links": [{}] * bis,
        "display_limits": ["Fallback desk limit"],
    }
    summary = template_fragment(
        "{% if desk.slug == 'us-indopacific' and uscc_official_links | default([]) %}\n<dl class=\"stat-rows\">",
        "{% else %}\n<dl class=\"stat-rows\">",
        close="\n{% endif %}",
    ).render(**fields)
    limits = template_fragment(
        "{% if display_limits %}\n<h2>Limits of this desk, stated plainly</h2>",
        "{% if desk.slug == 'china' %}\n<h2>Earlier Briefs</h2>",
    ).render(**fields)
    return BeautifulSoup(summary, "html.parser"), BeautifulSoup(limits, "html.parser")


class USDDeskSourceTruthTests(unittest.TestCase):
    def test_uscc_only_never_claims_treasury_or_bis_live(self):
        stats, limits = render_panels(uscc=10)
        self.assertIn("from USCC", stats.get_text(" ", strip=True))
        self.assertNotIn("from USCC and Treasury", stats.get_text(" ", strip=True))
        self.assertIn("official USCC press listing", limits.get_text(" ", strip=True))
        self.assertNotIn("official USCC and Treasury press listings", limits.get_text(" ", strip=True))
        self.assertNotIn("Collected official BIS metadata links", stats.get_text())
        self.assertNotIn("BIS covers a bounded homepage sample", limits.get_text())

    def test_treasury_live_is_not_mislabeled_uscc_only(self):
        stats, limits = render_panels(uscc=10, treasury=10)
        text = stats.get_text(" ", strip=True)
        self.assertIn("from USCC and Treasury", text)
        self.assertIn("Collected official Treasury metadata links", text)
        self.assertNotIn("Collected official BIS metadata links", text)
        self.assertIn("official USCC and Treasury press listings",
                      limits.get_text(" ", strip=True))
        self.assertNotIn("press listing only", limits.get_text(" ", strip=True))

    def test_bis_public_rows_add_typed_count_and_bounded_scope(self):
        stats, limits = render_panels(uscc=10, treasury=10, bis=4)
        numbers = [dd.get_text(strip=True) for dd in stats.select("dt + dd")]
        self.assertEqual(numbers[:3], ["10", "10", "4"])
        text = stats.get_text(" ", strip=True)
        self.assertIn("from USCC, Treasury and BIS", text)
        self.assertIn("None of these feeds collect PACOM", text)
        limits_text = limits.get_text(" ", strip=True)
        self.assertIn("official USCC, Treasury and BIS press listings", limits_text)
        self.assertIn("bounded homepage sample", limits_text)
        self.assertIn("not original documents, photographs, summaries or IPR analysis",
                      limits_text)

    def test_other_desk_retains_its_own_limits(self):
        stats, limits = render_panels(slug="china")
        self.assertEqual(stats.get_text(" ", strip=True), "")
        self.assertIn("Fallback desk limit", limits.get_text(" ", strip=True))
        self.assertNotIn("official USCC press listing", limits.get_text(" ", strip=True))


if __name__ == "__main__":
    unittest.main()
