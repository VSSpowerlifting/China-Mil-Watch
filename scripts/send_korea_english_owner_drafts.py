"""Send each verified Korean source's English draft to owner ONCE, privately.

Reads only already published government text. Makes at most two bounded model
calls per selected source. Never emails editor/Dylan or publishes generated
translation/analysis; a successful owner-only SMTP send earns a hash receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from core.korea_english_publication import public_registry, KoreaEnglishHold
from core.korea_published_originals import read_release_index
from scripts.draft_korea_english_analysis import draft

ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = ROOT / "research/korea_english_draft_handoff_receipts.json"
SCHEMA = "ipr-korea-private-english-editorial-handoff/1"
MAX_DRAFTS = 2


def need(ok, reason):
    if not ok:
        raise KoreaEnglishHold(reason)


def address(text):
    from email.utils import getaddresses
    need(type(text) is str and "\r" not in text and "\n" not in text,
         "korea_owner_email_address_invalid")
    parsed = getaddresses([text])
    need(len(parsed) == 1 and parsed[0][1].count("@") == 1,
         "korea_owner_email_address_invalid")
    return parsed[0][1]


def read_receipts(path=RECEIPT_PATH):
    p=Path(path)
    need(p.is_file() and not p.is_symlink() and p.stat().st_size < 100000,
         "korea_english_owner_delivery_ledger_missing")
    try:
        d=json.loads(p.read_text(encoding="utf-8"))
    except (OSError,ValueError):
        raise KoreaEnglishHold("korea_english_owner_delivery_ledger_invalid") from None
    need(type(d) is dict and set(d)=={"schema","delivered"}
         and d["schema"]==SCHEMA and type(d["delivered"]) is list
         and len(d["delivered"])<=150,"korea_english_owner_delivery_ledger_invalid")
    known=set()
    for item in d["delivered"]:
        need(type(item) is dict and set(item)=={
             "source_identity","source_sha256","draft_sha256",
             "model_id","delivered_at_utc"},
             "korea_english_owner_delivery_row_invalid")
        key=(item["source_identity"],item["source_sha256"])
        need(key not in known and
             all(type(item[k]) is str and re.fullmatch(r"[0-9a-f]{64}",item[k])
                 for k in ("source_sha256","draft_sha256")),
             "korea_english_owner_delivery_duplicate_or_digest_invalid")
        known.add(key)
    return d, known


def pending(ledger=RECEIPT_PATH):
    receipts, known=read_receipts(ledger)
    originals=read_release_index()
    reviewed={r["source_identity"] for r,_,_ in public_registry()}
    selected=[]
    for row in sorted(originals,key=lambda r:(r["publisher_posted_date"],
                                               r["source_identity"])):
        key=(row["source_identity"],row["original_text_sha256"])
        if key not in known and row["source_identity"] not in reviewed:
            selected.append(row)
    return selected[:MAX_DRAFTS], receipts


def send_owner(row, review, receipt, *, sender, recipient, password,
               send=None):
    message=EmailMessage()
    message["From"]=sender
    message["To"]=recipient
    message["Reply-To"]=sender
    message["Subject"]="IPR Korea | PRIVATE translation and analysis review | "+row["source_identity"].split(":")[1]
    message.set_content(
        "PRIVATE / UNREVIEWED — DO NOT PUBLISH\n\n"
        "Attached is a machine-generated English translation and analytical "
        "source note package for the exact published Korean official original.\n"
        "Original government URL: "+row["official_url"]+"\n"
        "Original text SHA-256: "+row["original_text_sha256"]+"\n"
        "Draft canonical SHA-256: "+receipt["review_sha256"]+"\n\n"
        "Check every Korean-to-English segment, institutional names and "
        "chronology; confirm factual interpretation and original-Korean "
        "passage quotations. Source quotes do NOT independently corroborate "
        "the government's claims. To publish, change the JSON review fields "
        "only after a real editorial check, submit the reviewed packet as "
        "research/korea_english_reviewed/<newsId>.json in a reviewed PR, then "
        "use the separate owner-only exact-packet release workflow.\n"
        "No content in this email has been approved for the public site.\n"
    )
    body=(json.dumps(review,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")
    need(len(body)<=1_000_000,"korea_owner_draft_too_large")
    message.add_attachment(body,maintype="application",subtype="json",
                           filename="korea-"+row["source_identity"].split(":")[1]+"-UNREVIEWED.json")
    if send is not None:
        send(message)
    else:
        with smtplib.SMTP_SSL("smtp.gmail.com",465,
                             context=ssl.create_default_context(),timeout=30) as smtp:
            smtp.login(sender,password)
            smtp.send_message(message)


def run(*, ledger=RECEIPT_PATH, client, sender, recipient, password, send=None):
    need(type(sender) is str and type(recipient) is str
         and sender and recipient,
         "korea_owner_delivery_addresses_invalid")
    rows,data=pending(ledger)
    sent=[]
    for row in rows:
        draft_packet,receipt=draft(row,client=client)
        need(receipt["machine_only"] and
             draft_packet["review"]["status"]=="machine_unreviewed",
             "korea_owner_mail_model_not_unreviewed")
        send_owner(row,draft_packet,receipt,
                   sender=sender,recipient=recipient,password=password,send=send)
        now=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entry={
            "source_identity":row["source_identity"],
            "source_sha256":row["original_text_sha256"],
            "draft_sha256":receipt["review_sha256"],
            "model_id":draft_packet["model_id"],
            "delivered_at_utc":now,
        }
        data["delivered"].append(entry)
        # After a successful send, commit the receipt even if a later
        # candidate fails, so retry does not duplicate an earlier email.
        p=Path(ledger)
        temp=p.with_name(p.name+".new-delivery")
        need(not temp.exists() and not temp.is_symlink(),
             "korea_delivery_ledger_temp_path_exists")
        flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY
        if hasattr(os,"O_NOFOLLOW"): flags|=os.O_NOFOLLOW
        with os.fdopen(os.open(temp,flags,0o644),"w",encoding="utf-8") as f:
            json.dump(data,f,ensure_ascii=False,sort_keys=True,separators=(",",":"))
            f.write("\n")
        os.replace(temp,p)
        sent.append(entry["source_identity"])
    return {"status":"OWNER_PRIVATE_DRAFTS_DELIVERED" if sent else "NO_NEW_ENGLISH_DRAFTS",
            "count":len(sent),"ids":sent,"public_writes":0}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--send-owner-only-unreviewed",action="store_true")
    args=p.parse_args(argv)
    try:
        need(args.send_owner_only_unreviewed,"korea_owner_draft_delivery_not_approved")
        from scripts.sunday_editorial_handoff import single_address
        sender=single_address(os.environ.get("IPR_SMTP_USER",""),"IPR_SMTP_USER")
        recipient=single_address(os.environ.get("IPR_PREVIEW_TO",""),"IPR_PREVIEW_TO")
        need(sender!=os.environ.get("IPR_EDITOR_TO","") and
             recipient!=os.environ.get("IPR_EDITOR_TO",""),
             "korea_owner_delivery_editor_recipient_forbidden")
        password="".join(os.environ.get("IPR_SMTP_APP_PASSWORD","").split())
        need(len(password)==16 and password.isascii() and password.isalnum(),
             "korea_owner_draft_smtp_credential_unavailable")
        need(bool(os.environ.get("ANTHROPIC_API_KEY")),
             "korea_owner_draft_anthropic_credential_unavailable")
        import anthropic
        result=run(client=anthropic.Anthropic(),sender=sender,
                   recipient=recipient,password=password)
        print(json.dumps(result,sort_keys=True))
        return 0
    except Exception:
        # Provider and SMTP exceptions can include private draft text.
        # Report a fixed hold receipt only; do not log its exception string.
        print(json.dumps({"status":"HOLD","unreviewed_content_logged":False,
                          "public_writes":0},sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
