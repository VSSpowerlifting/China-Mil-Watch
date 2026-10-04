#!/usr/bin/env python3
"""Prepare the reviewed No. 14 correction; canonical writes require --apply.

No network, database writes, HTML generation, numbering or approval changes.
The two original SHA-256 digests bind this migration to the reviewed files.
"""

import argparse
import copy
import difflib
import hashlib
import json
import os
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIDECAR = Path("output/the-pla-watch/posts/2026-08-15.json")
LINKEDIN = Path("the-pla-watch/linkedin/2026-08-15.txt")
BASE_SHA256 = {
    SIDECAR: "f5aa239888821a3279916ddc4387198eefc3620e62341f18421296410cb7baa0",
    LINKEDIN: "44488f0ca0f6f0ebf20fb1d0b277157b254da5a2dbd0dfdb0ea67e709a254b2c",
}

SIGNAL = (
    "One exercise, five reports across three outlets on three publication dates. "
    "Each headline names waters east of Taiwan; repetition does not prove coordination."
)
STOOD_OUT = """On 11 August, PLA Daily announced that the Chinese Navy ship Honghe and an Indonesian Navy frigate, identified in the Chinese report as “莱”号护卫舰, would conduct a passage exercise in waters east of Taiwan Island in mid-August. China Military Online carried an English announcement attributed to Xinhua and China's Ministry of National Defense. The captured Global Times headline names the same exercise and location, but its stored body contains unrelated snippets.

On 12 August, PLA Daily reported completion of the encounter. Its accounts describe communications, formation manoeuvring, replenishment drills and a separation ceremony. PLA Daily returned to the same encounter on 14 August; that later publication is not a second exercise.

That is one exercise represented by five selected headlines across three outlets on three publication dates. Five of the week's twelve model-flagged records refer to it. The completion accounts document reported activities; they do not independently establish operational performance, actual fuel or cargo transfer, or a wider naval arrangement.

Every one of the five captured headlines names the operating area east of Taiwan Island. That is an observation about preserved publication metadata. It remains traceable even where the body capture is incomplete."""

WHY = """The repeated framing supports a claim about publication emphasis. Across three outlets and three publication dates, the operating area appears in each selected headline. This comparison concerns the captured titles, not five independently verified accounts of the exercise.

The announcement carried by China Military Online attributes to China's defence ministry the aims of enhancing joint operational capabilities, deepening practical cooperation and maintaining regional peace and stability. Those are the ministry's stated aims. The repeated headlines do not independently establish either government's operational intent, Indonesia's interpretation of its participation, or a coordinated media plan. The preserved Global Times body is incomplete, so this edition cannot assess that article's full explanation of the exercise.

Nor does repetition strengthen the underlying facts. The China Military Online announcement is explicitly Xinhua copy reporting the ministry's announcement. The five reports are not five independent confirmations."""

ROUTINE = """Other items in the week are recorded separately and are not offered in support of the headline comparison.

On 12 August, China Military Online published China's Ambassador for Disarmament Affairs Li Chijiang's rebuttal to a US-led statement at the Conference on Disarmament concerning a 6 July submarine-launched ballistic missile test and advance notification. The publication date is not the meeting date. The report establishes that China publicly disputed the American account; it does not independently establish the circumstances of the test.

Two separate aviation accounts appeared. On 14 August, PLA Daily and MOD China carried the same PLA Daily report describing the Navy's female carrier-based helicopter pilot trainees completing daytime solo carrier-landing assessments in Bohai Bay. On 13 August, PLA Daily published a profile of J-16 pilot Tian Jing. These are different stories, and the two outlets carrying the helicopter account do not provide independent corroboration.

Political work, exercises and doctrine were the three largest model categories among analyzed China Desk records, with 65, 49 and 39 assignments respectively. These categories overlap; they are automated labels rather than independent editorial classifications. They do not by themselves establish a routine operational baseline.

On 9 August, PLA Daily published an essay on artificial intelligence and operational decision timing. The captured Global Times titles refer separately to a navigation alert near Xisha Qundao and an official-video claim about portable missiles. Their stored bodies contain unrelated snippets, so neither is used here as evidence of the underlying activity, who released footage, or demonstrated capability. The essay is conceptual writing, not a demonstration of capability."""

TERM = """通航演练 is the term used in the cited Chinese reports for this encounter. This edition retains “passage exercise” as its English rendering. The completion accounts list communications, formation manoeuvring, replenishment drills and a separation ceremony. The term alone does not establish a general rule about duration, a formal distinction from a combined exercise, or a standing relationship between the navies."""

WATCH = """Whether the location framing repeats. These five captured headlines concern a single encounter. Further reporting on separate exercises could show whether the operating area repeatedly receives headline emphasis within the collected record; this edition cannot establish a wider editorial practice from one event.

Also worth following: subsequent accounts of the Navy's carrier-based helicopter training. The 14 August report names formation flying and night carrier landings as the next training stages."""


def correction_note(correction_date):
    return (
        "Correction — " + date.fromisoformat(correction_date).strftime("%-d %B %Y")
        + ": This edition now identifies Honghe without an unsupported vessel classification, "
        "removes untraced exercise definitions and footage-release attribution, and limits "
        "the headline comparison to what the preserved records support. Three Global Times "
        "body captures contain unrelated snippets; their titles are retained for transparent "
        "metadata comparison. The coverage snapshot identifies four sources, and the counts "
        "are explicitly scoped to the China Desk. The original captured source records, "
        "issue number, URL and coverage dates are preserved. The English trail title for "
        "the 12 August completion report retains the source's Chinese vessel designation "
        "without assigning it an English proper name."
    )


def corrected_sidecar(original, correction_date):
    result = copy.deepcopy(original)
    first_note = original["opening_note"].split("\n\n")[0]
    result.update({
        "dek": "Five of the twelve model-flagged records in the week ending 15 August 2026 refer to a single China–Indonesia naval passage exercise. Their captured headlines ran across three outlets on three publication dates, and all five named the operating area east of Taiwan.",
        "signal": SIGNAL,
        "opening_note": first_note + "\n\n" + correction_note(correction_date) + "\n\n"
        "The China Desk corpus for the week holds 229 records, of which 137 passed relevance screening and all 137 were analysed. None of those China Desk records was left unscreened. Four sources contributed to the analyzed set: PLA Daily 111, China Military Online 14, Global Times Defense 10 and MOD China 2. Source concentration is described in the methodology. These counts describe processing, not a finding that every captured body is complete.",
        "what_stood_out": STOOD_OUT,
        "why_it_matters": WHY,
        "what_was_routine": ROUTINE,
        "term_to_know_explanation": TERM,
        "what_im_watching_next": WATCH,
        "sources_seen": list(dict.fromkeys(e["source"] for e in original["source_trail"])),
    })
    entry = next(e for e in result["source_trail"] if e["url"] == "http://www.81.cn/yw_208727/16479044.html")
    entry["title"] = entry["title"].replace(" (Lái)", "")
    return result


def companion(sidecar, correction_date):
    return (
        "The PLA Watch No. 14: One Exercise, Five Reports East of Taiwan\n\n"
        "Retrospective edition. Covers 9–15 August 2026; originally prepared in September.\n\n"
        + correction_note(correction_date) + "\n\n"
        "This week's signal: " + sidecar["signal"] + "\n\n"
        "## What stood out\n\n" + sidecar["what_stood_out"] + "\n\n"
        "## Why it matters\n\n" + sidecar["why_it_matters"] + "\n\n"
        "## Recorded separately\n\n" + sidecar["what_was_routine"].split("\n\n")[1]
        + "\n\n" + sidecar["what_was_routine"].split("\n\n")[2] + "\n\n"
        "## The corpus behind this edition\n\n"
        "The China Desk holds 229 records for the week: 137 passed relevance screening and all 137 were analyzed; none of those China Desk records awaits screening. Seven publication dates are represented. Four sources contributed to the analyzed set; PLA Daily supplied 111 of 137 records. Three cited Global Times bodies contain unrelated snippets, so the headline comparison uses captured titles with that limitation disclosed. Global Times is state-linked rather than official.\n\n"
        "Full edition: https://indopacificrecord.org/the-pla-watch/posts/2026-08-15.html\n\n"
        "I welcome comments or corrections from people working on Chinese military media, PLA studies, or U.S.-China security.\n"
    )


def prepare(root, correction_date):
    originals = {path: (root / path).read_bytes() for path in BASE_SHA256}
    for path, digest in BASE_SHA256.items():
        if hashlib.sha256(originals[path]).hexdigest() != digest:
            raise ValueError("Reviewed file changed; re-review before migrating: " + str(path))
    sidecar = corrected_sidecar(json.loads(originals[SIDECAR]), correction_date)
    proposed = {
        SIDECAR: (json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        LINKEDIN: companion(sidecar, correction_date).encode("utf-8"),
    }
    return originals, proposed


def apply(root, originals, proposed):
    # Check both inputs again before staging either output. No force bypass.
    for path, content in originals.items():
        if (root / path).read_bytes() != content:
            raise ValueError("File changed during preparation: " + str(path))
    staged, written = {}, []
    try:
        for path, content in proposed.items():
            fd, name = tempfile.mkstemp(prefix=".no14-", dir=str((root / path).parent))
            staged[path] = Path(name)
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
            staged[path].chmod((root / path).stat().st_mode & 0o777)
        for path, temp in staged.items():
            os.replace(str(temp), str(root / path))
            written.append(path)
    except Exception:
        for path in written:
            (root / path).write_bytes(originals[path])
        raise
    finally:
        for temp in staged.values():
            if temp.exists():
                temp.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--correction-date", required=True, help="Actual correction date (YYYY-MM-DD); not approval or original publication date")
    parser.add_argument("--out", type=Path, default=ROOT / "tmp/no14-correction/candidate")
    parser.add_argument("--apply", action="store_true", help="Apply the two-file migration only after owner review; does not render or record approval")
    args = parser.parse_args()
    try:
        out = args.out.resolve()
        if out == (ROOT / "output").resolve() or (ROOT / "output").resolve() in out.parents:
            raise ValueError("Proposal destination must be outside output/")
        if out / LINKEDIN.name == (ROOT / LINKEDIN).resolve():
            raise ValueError("Proposal destination overlaps the canonical companion")
        originals, proposed = prepare(ROOT, args.correction_date)
        if args.apply:
            apply(ROOT, originals, proposed)
            print("Applied No. 14 prose/metadata and companion correction. HTML not regenerated; approval unchanged.")
        else:
            out.mkdir(parents=True, exist_ok=True)
            for path, content in proposed.items():
                (out / path.name).write_bytes(content)
            patch = "".join(
                "".join(difflib.unified_diff(originals[path].decode("utf-8").splitlines(True),
                                             proposed[path].decode("utf-8").splitlines(True),
                                             fromfile="a/" + str(path), tofile="b/" + str(path)))
                for path in originals
            )
            (out / "correction.diff").write_text(patch, encoding="utf-8")
            print("Prepared candidate sidecar, companion and diff in " + str(out) + "; canonical files unchanged.")
    except (ValueError, OSError, StopIteration) as exc:
        parser.exit(1, "REFUSED: " + str(exc) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
