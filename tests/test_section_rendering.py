"""Jinja2 rendering tests for contract section partials.

TDD red phase — section partials do not exist yet.
Tests verify that section-driven rendering produces the expected HTML content.
"""

from typing import Any

import pytest
from jinja2 import Environment, FileSystemLoader

# ── Sample data ──────────────────────────────────────────────────────────────

SAMPLE_CONTRACT_DATA: dict[str, Any] = {
    "metadata": {
        "contract_id": "test-contract-123",
        "contract_number": "V-2026-001",
        "created_at": "2026-01-15T10:30:00Z",
    },
    "vermieter": {
        "name": "Max Mustermann GmbH",
        "email": "vermieter@example.com",
        "phone": "+49 30 12345678",
        "anschrift": "Musterstraße 1, 10115 Berlin",
    },
    "mieter1": {
        "vorname": "Anna",
        "nachname": "Schmidt",
        "geburtstag": "1990-05-15",
        "email": "anna.schmidt@example.com",
        "telefon": "+49 176 12345678",
        "anschrift": {
            "strasse": "Alte Straße",
            "hausnummer": "42",
            "plz": "80331",
            "stadt": "München",
        },
    },
    "mietobjekt": {
        "liegenschaft": "Wohnanlage Sonnenhof",
        "strasse": "Sonnenallee",
        "hausnummer": "100",
        "plz": "10115",
        "ort": "Berlin",
        "lage": "3. OG links",
        "zimmer_anzahl": 3,
    },
    "mietzeit": {
        "beginn": "2026-02-01",
        "befristet": False,
    },
    "miete": {
        "kaltmiete": 1200.00,
        "betriebskosten": 150.00,
        "heizkosten": 80.00,
        "gesamtmiete": 1430.00,
    },
    "kaution": {
        "betrag": 3600.00,
    },
    "bankverbindung": {
        "bank_name": "Deutsche Bank",
        "iban": "DE89370400440532013000",
        "bic": "COBADEFFXXX",
    },
}

# 16 canonical section keys with titles
ALL_SECTION_KEYS: list[tuple[str, str]] = [
    ("vermieter", "Vermieter"),
    ("mieter", "Mieter"),
    ("mietobjekt", "Mietobjekt / Mietsache"),
    ("mietzeit", "Mietzeit"),
    ("miete_nebenkosten", "Miete und Nebenkosten"),
    ("kaution", "Kaution"),
    ("schoenheitsreparaturen", "Schönheitsreparaturen"),
    ("kleinreparaturen", "Kleinreparaturen"),
    ("tierhaltung", "Tierhaltung"),
    ("untervermietung", "Untervermietung"),
    ("hausordnung", "Hausordnung"),
    ("rauchmelder", "Rauchwarnmelder"),
    ("legionellen", "Legionellen"),
    ("zustellung", "Zustellung"),
    ("sonstige_vereinbarungen", "Sonstige Vereinbarungen"),
    ("unterschriften", "Unterschriften"),
]


def make_sections(
    pairs: list[tuple[str, str]],
    overrides: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Build a sections list from (key, title) pairs with optional custom_html overrides."""
    overrides = overrides or {}
    return [
        {
            "sort_order": idx + 1,
            "title": title,
            "section_key": key,
            "custom_html": overrides.get(key),
        }
        for idx, (key, title) in enumerate(pairs)
    ]


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def jinja_env() -> Environment:
    """Jinja2 environment pointing at src/templates."""
    return Environment(
        loader=FileSystemLoader("/home/projects/casasign/src/templates"),
        autoescape=True,
    )


@pytest.fixture
def render_context() -> dict[str, Any]:
    """Template context matching contract_polished.html variable extraction."""
    data = SAMPLE_CONTRACT_DATA.copy()
    return {"contract_data": data}


def render_polished(
    jinja_env: Environment,
    contract_data: dict[str, Any],
) -> str:
    """Render contract_polished.html with the given contract_data dict."""
    tmpl = jinja_env.get_template("partials/contract_polished.html")
    return tmpl.render(contract_data=contract_data)


# ── Test classes ──────────────────────────────────────────────────────────────


class TestSectionRendererFallback:
    """When no sections key is present, fall back to monolithic clause includes."""

    def test_fallback_renders_clause_includes(
        self, jinja_env: Environment, render_context: dict[str, Any]
    ) -> None:
        """Without sections, all four clause partials must be rendered."""
        # contract_data has no 'sections' key
        html = render_polished(jinja_env, render_context["contract_data"])
        # Fallback path renders the old hardcoded clauses — spot-check a known string
        assert "Rauchwarnmelder" in html

    def test_fallback_no_section_tags_for_keys(
        self, jinja_env: Environment, render_context: dict[str, Any]
    ) -> None:
        """Fallback must NOT produce section-driven paragraph placeholders."""
        html = render_polished(jinja_env, render_context["contract_data"])
        # section-driven path produces 'Siehe Angaben oben.' for vermieter key
        assert "Siehe Angaben oben." not in html


class TestSectionRendererWithSections:
    """Section-driven rendering tests."""

    def _render(
        self,
        jinja_env: Environment,
        sections: list[dict[str, Any]],
        extra: dict[str, Any] | None = None,
    ) -> str:
        data = {**SAMPLE_CONTRACT_DATA, "sections": sections}
        if extra:
            data.update(extra)
        return render_polished(jinja_env, data)

    def test_all_16_default_sections_render_non_empty(
        self, jinja_env: Environment
    ) -> None:
        """All 16 default section keys must produce non-empty rendered content."""
        sections = make_sections(ALL_SECTION_KEYS)
        html = self._render(jinja_env, sections)
        for _, title in ALL_SECTION_KEYS:
            assert title in html, f"Section title '{title}' not found in output"

    def test_custom_html_overrides_default_content(
        self, jinja_env: Environment
    ) -> None:
        """A section with custom_html must render that HTML, not the default."""
        custom = "<p>Meine eigene Klausel</p>"
        sections = make_sections(
            [("schoenheitsreparaturen", "Schönheitsreparaturen")],
            overrides={"schoenheitsreparaturen": custom},
        )
        html = self._render(jinja_env, sections)
        assert "Meine eigene Klausel" in html

    def test_section_mietobjekt_excludes_rauchmelder(
        self, jinja_env: Environment
    ) -> None:
        """mietobjekt section must NOT contain Rauchwarnmelder content."""
        sections = make_sections([("mietobjekt", "Mietobjekt / Mietsache")])
        html = self._render(jinja_env, sections)
        assert "Rauchwarnmelder" not in html

    def test_section_rauchmelder_contains_din_14676(
        self, jinja_env: Environment
    ) -> None:
        """rauchmelder section must contain Rauchwarnmelder text and DIN 14676."""
        sections = make_sections([("rauchmelder", "Rauchwarnmelder")])
        html = self._render(jinja_env, sections)
        assert "Rauchwarnmelder" in html
        assert "DIN 14676" in html

    def test_sonstige_vereinbarungen_includes_personenmehrheit_when_mieter2(
        self, jinja_env: Environment
    ) -> None:
        """sonstige_vereinbarungen must include Personenmehrheit clause when mieter2 present."""
        mieter2 = {
            "vorname": "Klaus",
            "nachname": "Müller",
            "email": "k.mueller@example.com",
        }
        sections = make_sections([("sonstige_vereinbarungen", "Sonstige Vereinbarungen")])
        html = self._render(jinja_env, sections, extra={"mieter2": mieter2})
        assert "Personenmehrheit" in html

    def test_sonstige_vereinbarungen_excludes_personenmehrheit_when_no_mieter2(
        self, jinja_env: Environment
    ) -> None:
        """sonstige_vereinbarungen must NOT include Personenmehrheit when mieter2 is None."""
        data = {**SAMPLE_CONTRACT_DATA, "mieter2": None}
        sections = make_sections([("sonstige_vereinbarungen", "Sonstige Vereinbarungen")])
        data["sections"] = sections
        html = render_polished(jinja_env, data)
        assert "Personenmehrheit" not in html

    def test_unknown_section_key_does_not_crash(
        self, jinja_env: Environment
    ) -> None:
        """An unknown section_key must be silently ignored (no exception)."""
        sections = [
            {
                "sort_order": 1,
                "title": "Unbekannte Klausel",
                "section_key": "totally_unknown_key_xyz",
                "custom_html": None,
            }
        ]
        # Must not raise
        html = self._render(jinja_env, sections)
        assert "Unbekannte Klausel" in html

    def test_sequential_paragraph_numbering(self, jinja_env: Environment) -> None:
        """Sections must use § 1, § 2, … sequential numbering."""
        sections = make_sections(ALL_SECTION_KEYS[:3])
        html = self._render(jinja_env, sections)
        assert "§ 1" in html
        assert "§ 2" in html
        assert "§ 3" in html


class TestSectionPartialsContent:
    """Verify specific legal content inside individual section partials."""

    def _render_single(
        self,
        jinja_env: Environment,
        key: str,
        title: str,
        extra: dict[str, Any] | None = None,
    ) -> str:
        sections = make_sections([(key, title)])
        data = {**SAMPLE_CONTRACT_DATA, "sections": sections}
        if extra:
            data.update(extra)
        return render_polished(jinja_env, data)

    def test_mietzeit_shows_formatted_beginn_date(
        self, jinja_env: Environment
    ) -> None:
        """mietzeit section must show formatted beginn date (DD.MM.YYYY)."""
        html = self._render_single(jinja_env, "mietzeit", "Mietzeit")
        # 2026-02-01 → 01.02.2026
        assert "01.02.2026" in html

    def test_miete_shows_kaltmiete_amount(self, jinja_env: Environment) -> None:
        """miete_nebenkosten section must show formatted kaltmiete."""
        html = self._render_single(jinja_env, "miete_nebenkosten", "Miete und Nebenkosten")
        # 1200.00 → 1.200,00 €
        assert "1.200,00" in html

    def test_kaution_shows_betrag_and_551_reference(
        self, jinja_env: Environment
    ) -> None:
        """kaution section must show betrag and § 551 BGB reference."""
        html = self._render_single(jinja_env, "kaution", "Kaution")
        assert "3.600,00" in html
        assert "551" in html

    def test_schoenheitsreparaturen_has_5_and_8_year_intervals(
        self, jinja_env: Environment
    ) -> None:
        """schoenheitsreparaturen section must mention 5- and 8-year intervals."""
        html = self._render_single(
            jinja_env, "schoenheitsreparaturen", "Schönheitsreparaturen"
        )
        assert "5" in html
        assert "8" in html

    def test_kleinreparaturen_has_110_eur_cap(self, jinja_env: Environment) -> None:
        """kleinreparaturen section must state 110 EUR cap per repair."""
        html = self._render_single(jinja_env, "kleinreparaturen", "Kleinreparaturen")
        assert "110" in html

    def test_kleinreparaturen_has_6_percent_annual_cap(
        self, jinja_env: Environment
    ) -> None:
        """kleinreparaturen section must state 6% annual cap."""
        html = self._render_single(jinja_env, "kleinreparaturen", "Kleinreparaturen")
        assert "6" in html

    def test_untervermietung_mentions_airbnb(self, jinja_env: Environment) -> None:
        """untervermietung section must reference Airbnb as an example platform."""
        html = self._render_single(jinja_env, "untervermietung", "Untervermietung")
        assert "Airbnb" in html

    def test_zustellung_references_126b_bgb(self, jinja_env: Environment) -> None:
        """zustellung section must reference § 126b BGB (Textform)."""
        html = self._render_single(jinja_env, "zustellung", "Zustellung")
        assert "126b" in html

    def test_unterschriften_references_fes_aes(self, jinja_env: Environment) -> None:
        """unterschriften section must reference FES/AES electronic signatures."""
        html = self._render_single(jinja_env, "unterschriften", "Unterschriften")
        assert "FES" in html or "AES" in html
