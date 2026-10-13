"""Bounded PUBLIC navigation to official Indonesian publisher pages.

This is a source-directory aid, NOT a reviewed reference registry, content
license, archive/collection admission, or endorsement of publisher statements.
The selected publisher titles/dates link outward; no original bodies are loaded.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "research" / "indonesia_official_source_links.json"
SCHEMA = "ipr-indonesia-external-source-links/1"
PINNED = "43d9bc7bc94dcb0e257866e0f24e1ce404e98149"
# ID-05 deliberately omitted: Kemhan's Yonif TP 880 text conflicts on Kaltara/Kalbar.
IDS = ("id-01", "id-02", "id-03", "id-04",
       "id-06", "id-07", "id-08", "id-09",
       "id-10", "id-11", "id-12", "id-13", "id-14",
       "id-15", "id-16")
# Freeze newly selected identities, original Indonesian titles, and exact dates.
# Each addition must be explicitly reviewed; the directory must not expand
# merely because a publisher URL is syntactically valid.
ADDED = {
    "id-06": (
        "/2026/09/30/atas-nama-negara-menhan-sjafrie-anugerahkan-satyalancana-dharma-samudera-kepada-personel-jmsdf-yang-terlibat-penanganan-karhutla.html",
        "Atas Nama Negara, Menhan Sjafrie Anugerahkan Satyalancana Dharma Samudera kepada Personel JMSDF yang Terlibat Penanganan Karhutla",
        "2026-09-30",
    ),
    "id-07": (
        "/2026/10/03/tinjau-yonif-tp-881-baratama-dharma-di-sebuku-nunukan-menhan-sjafrie-prajurit-perbatasan-harus-siap-hadapi-ancaman-dan-mengawal-kedaulatan-nkri.html",
        "Tinjau Yonif TP 881/Baratama Dharma di Sebuku Nunukan, Menhan Sjafrie: Prajurit Perbatasan Harus Siap Hadapi Ancaman dan Mengawal Kedaulatan NKRI",
        "2026-10-03",
    ),
    "id-08": (
        "/2026/10/07/disaksikan-presiden-menhan-hadiri-penyerahan-rp132-triliun-dan-259-ribu-hektare-kawasan-hutan-kepada-negara.html",
        "Disaksikan Presiden, Menhan Hadiri Penyerahan Rp13,2 Triliun dan 259 Ribu Hektare Kawasan Hutan Kepada Negara",
        "2026-10-07",
    ),
    "id-09": (
        "/2026/10/09/mensos-dan-wamenhan-lepas-1-509-kadet-unhan-ri-untuk-mengabdi-di-181-sekolah-rakyat.html",
        "Mensos dan Wamenhan Lepas 1.509 Kadet Unhan RI untuk Mengabdi di 181 Sekolah Rakyat",
        "2026-10-09",
    ),
    "id-10": (
        "/2026/10/08/wamenhan-tinjau-area-gudang-utara-kodam-iii-siliwangi.html",
        "Wamenhan Tinjau Area Gudang Utara Kodam III/Siliwangi",
        "2026-10-08",
    ),
    "id-11": (
        "/2026/10/08/menhan-tekankan-bela-negara-dan-patriotisme-kepada-siswa-latsarmil-komcad.html",
        "Menhan Tekankan Bela Negara dan Patriotisme kepada Siswa Latsarmil Komcad",
        "2026-10-08",
    ),
    "id-12": (
        "/2026/10/08/wamenhan-bersama-wamenkes-tinjau-kesiapan-rs-tk-ii-dustira-layani-prajurit-dan-masyarakat.html",
        "Wamenhan Bersama Wamenkes Tinjau Kesiapan RS Tk. II Dustira Layani Prajurit dan Masyarakat",
        "2026-10-08",
    ),
    "id-14": (
        "/2026/10/12/menhan-dampingi-presiden-dalam-pertemuan-bilateral-dengan-presiden-republik-arab-mesir.html",
        "Menhan Dampingi Presiden Dalam Pertemuan Bilateral dengan Presiden Republik Arab Mesir",
        "2026-10-12",
    ),
    "id-13": (
        "/2026/10/09/wamenhan-ri-terima-audiensi-ketua-yayasan-gedung-veteran-ri-bahas-pengelolaan-dan-pemanfaatan-aset.html",
        "Wamenhan RI Terima Audiensi Ketua Yayasan Gedung Veteran RI, Bahas Pengelolaan dan Pemanfaatan Aset",
        "2026-10-09",
    ),
    "id-15": (
        "/2026/10/03/kunker-ke-malinau-menhan-sjafrie-tinjau-yonif-tp-921-alang-impang-dan-tegaskan-peran-prajurit-di-perbatasan.html",
        "Kunker ke Malinau, Menhan Sjafrie Tinjau Yonif TP 921/Alang Impang dan Tegaskan Peran Prajurit di Perbatasan",
        "2026-10-03",
    ),
    "id-16": (
        "/2026/10/03/menhan-beri-motivasi-prajurit-yonif-tp-922-ut-dalam-mengemban-tugas-di-perbatasan.html",
        "Menhan Beri Motivasi Prajurit Yonif TP 922/UT dalam Mengemban Tugas di Perbatasan",
        "2026-10-03",
    ),
}
FIELDS = {"id", "url", "title_original", "published_date", "language"}
EXPECTED = {"schema", "source_family", "publisher", "snapshot_date",
            "pinned_shadow_commit", "editorial_status", "collection_status",
            "references"}
PATH = re.compile(r"/([0-9]{4})/([0-9]{2})/([0-9]{2})/[a-z0-9-]+\.html\Z")


class PublicIndexError(ValueError):
    """Unexpected or unverified source-directory shape. Refuse to publish."""


def require(ok, reason):
    if not ok:
        raise PublicIndexError(reason)


def distinct(pairs):
    values = {}
    for key, value in pairs:
        require(key not in values, "repeated JSON field")
        values[key] = value
    return values


def validate(data):
    require(type(data) is dict and set(data) == EXPECTED, "unexpected index fields")
    require(data["schema"] == SCHEMA and data["source_family"] == "id_kemhan_news"
            and data["publisher"] == "Kementerian Pertahanan Republik Indonesia"
            and data["snapshot_date"] == "2026-10-12"
            and data["pinned_shadow_commit"] == PINNED
            and data["editorial_status"] == "publisher_links_not_independently_human_reviewed"
            and data["collection_status"] == "shadow_not_public_corpus",
            "public source-index provenance or status changed")
    entries = data["references"]
    require(type(entries) is list and len(entries) == len(IDS),
            "this frozen source directory permits exactly fifteen external publisher links")
    require([p.get("id") for p in entries if type(p) is dict] == list(IDS),
            "unrecognized or reordered pilot reference")
    seen = set()
    result = []
    for item in entries:
        require(type(item) is dict and set(item) == FIELDS,
                "unexpected metadata field (possibly private article data)")
        require(item["language"] == "id", "original title is not Indonesian")
        title = item["title_original"]
        require(type(title) is str and 8 <= len(title.strip()) <= 260
                and title == title.strip()
                and not any(ord(ch) < 32 or ch in "<>" for ch in title),
                "unsafe or missing Indonesian title")
        url = item["url"]
        require(type(url) is str and len(url) <= 350
                and not any(ord(ch) <= 32 or ord(ch) == 127 for ch in url),
                "unsafe official URL")
        try:
            parsed = urlsplit(url)
            exact_host = (parsed.scheme == "https"
                          and parsed.netloc == "www.kemhan.go.id"
                          and not parsed.username and not parsed.password
                          and not parsed.query and not parsed.fragment)
        except ValueError as exc:
            raise PublicIndexError("invalid official URL") from exc
        require(exact_host, "only exact first-party Kemhan HTTPS links are allowed")
        m = PATH.fullmatch(parsed.path)
        require(m is not None, "not a canonical dated Kemhan Berita link")
        try:
            url_date = date(*map(int, m.groups())).isoformat()
            meta_date = date.fromisoformat(item["published_date"]).isoformat()
        except (TypeError, ValueError) as exc:
            raise PublicIndexError("invalid official publication date") from exc
        require(url_date == item["published_date"] == meta_date,
                "publication date disagrees with official URL")
        if item["id"] in ADDED:
            require((parsed.path, title, meta_date) == ADDED[item["id"]],
                    "unqualified new Indonesia publisher link identity or title")
        require(url not in seen, "duplicate official publication")
        seen.add(url)
        result.append({
            "id": item["id"], "source_url": url, "title_original": title,
            "published_date": meta_date, "language": "id",
        })
    return result


def load(path=DEFAULT):
    path = Path(path)
    require(path.is_file() and not path.is_symlink()
            and path.stat().st_size <= 16384,
            "public source-index is absent, symlinked, or oversized")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=distinct)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PublicIndexError("cannot parse source index") from exc
    return validate(raw)
