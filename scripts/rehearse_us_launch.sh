#!/usr/bin/env bash
# US shadow launch rehearsal. Eight scenarios, local only.
#   - a BARE repo stands in for origin; nothing touches GitHub
#   - collection runs live against DVIDS, politely, via the real runner
#   - no durable state branch is created on any remote
set -uo pipefail
REPO="${REPO:?set REPO to the collector worktree}"
LAB="${LAB:?set LAB to a scratch directory}"
PY="${PY:-python3}"
BRANCH="shadow/us-indopacom"
pass=0; fail=0
ok(){ printf '  PASS  %s\n' "$1"; pass=$((pass+1)); }
no(){ printf '  FAIL  %s\n' "$1"; fail=$((fail+1)); }
chk(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 (expected $3, got $2)"; fi; }

rm -rf "$LAB"; mkdir -p "$LAB"
git init --quiet --bare "$LAB/origin.git"

collect(){ # <statedir> <runid> <extra args...>
  local sd="$1" rid="$2"; shift 2
  ( cd "$REPO" && "$PY" scripts/shadow_collect_us.py \
      --state-dir "$sd" --run-id "$rid" --commit local \
      --lookback-days 3 --cap 6 "$@" ) 2>/dev/null
}
field(){ "$PY" -c "import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2]))" "$1" "$2"; }

# ---------------------------------------------------------------------------
# 0. The workflow's OWN shell, run against an empty orphan.
#
# This scenario exists because 32/32 passed and the first real run still
# failed. Everything below exercised the collector and git; nothing executed
# the workflow's shell steps, so a bug in one of them survived the whole
# rehearsal. `find state/ledger` on a fresh orphan exits non-zero, and under
# `set -euo pipefail` that failed the step and skipped collection entirely.
# ---------------------------------------------------------------------------
echo "=== 0. workflow shell steps against an empty orphan ==="
WF0="$REPO/.github/workflows/us_shadow.yml"
if [ ! -f "$WF0" ]; then
  no "workflow present for shell rehearsal"
else
  mkdir -p "$LAB/wf/shadow-state"
  ( cd "$LAB/wf/shadow-state" && git init -q . && git checkout -q --orphan "$BRANCH" 2>/dev/null; true )
  export RUNNER_TEMP="$LAB/wf"
  export GITHUB_OUTPUT="$LAB/wf/gh_output"
  : > "$GITHUB_OUTPUT"
  extract(){ "$PY" - "$WF0" "$1" <<'P'
import re,sys
raw=open(sys.argv[1]).read(); want=sys.argv[2]
blocks=re.split(r"^      - name: ", raw, flags=re.M)
for b in blocks[1:]:
    if b.splitlines()[0].strip()==want:
        m=re.search(r"^        run: \|\n(.*?)(?=^      - name: |\Z)", b, re.M|re.S)
        body=m.group(1)
        body=re.sub(r"^          ", "", body, flags=re.M)
        # Substitute the one GitHub expression these steps use.
        body=body.replace("${{ steps.before.outputs.count }}", "$STEP_BEFORE_COUNT")
        print(body); break
P
  }
  extract "Record the ledger count before collection" > "$LAB/wf/step_before.sh"
  extract "Assert the ledger is append-only"          > "$LAB/wf/step_append.sh"
  if bash "$LAB/wf/step_before.sh" >"$LAB/wf/out1" 2>&1; then
    ok "count step survives a missing state/ledger"
  else
    no "count step survives a missing state/ledger ($(tail -1 "$LAB/wf/out1"))"
  fi
  chk "it reports zero prior entries" "$(grep -o 'count=[0-9]*' "$GITHUB_OUTPUT" | tail -1)" "count=0"
  STEP_BEFORE_COUNT=$(grep -o 'count=[0-9]*' "$GITHUB_OUTPUT" | tail -1 | cut -d= -f2)
  export STEP_BEFORE_COUNT
  if bash "$LAB/wf/step_append.sh" >"$LAB/wf/out2" 2>&1; then
    ok "append-only step survives an unborn branch"
  else
    no "append-only step survives an unborn branch ($(tail -1 "$LAB/wf/out2"))"
  fi
  # And it must still FAIL when an entry really is removed.
  mkdir -p "$LAB/wf/shadow-state/state/ledger"
  echo '{}' > "$LAB/wf/shadow-state/state/ledger/a.json"
  ( cd "$LAB/wf/shadow-state" && git add -A >/dev/null && git -c user.email=a@b -c user.name=a commit -qm seed )
  rm "$LAB/wf/shadow-state/state/ledger/a.json"
  STEP_BEFORE_COUNT=1; export STEP_BEFORE_COUNT
  if bash "$LAB/wf/step_append.sh" >"$LAB/wf/out3" 2>&1; then
    no "append-only step rejects a deleted entry"
  else
    ok "append-only step rejects a deleted entry"
  fi
  unset RUNNER_TEMP GITHUB_OUTPUT STEP_BEFORE_COUNT
fi

echo "=== 1. day-zero bootstrap ==="
git clone --quiet "$LAB/origin.git" "$LAB/w1" 2>/dev/null
( cd "$LAB/w1" && git checkout --quiet --orphan "$BRANCH" && git rm -rqf . 2>/dev/null; true )
mkdir -p "$LAB/w1/state"
[ -f "$LAB/w1/state/clock.json" ] && no "clock absent before first run" || ok "no clock before the first run"
collect "$LAB/w1/state" bootstrap_1 --target-date "$(date -u +%F)" > "$LAB/r1.json"
chk "day zero written once" "$([ -f "$LAB/w1/state/clock.json" ] && echo yes || echo no)" "yes"
chk "shadow_day is 0"      "$(field "$LAB/r1.json" shadow_day)" "0"
Z1=$("$PY" -c "import json;print(json.load(open('$LAB/w1/state/clock.json'))['day_zero_utc'])")

echo "=== 2. first successful collection ==="
chk "result ok"            "$(field "$LAB/r1.json" result)" "ok"
chk "health ok"            "$(field "$LAB/r1.json" health)" "ok"
INS=$(field "$LAB/r1.json" inserted)
[ "$INS" -gt 0 ] && ok "inserted $INS record(s)" || no "inserted nothing"
chk "no fetch failures"    "$(field "$LAB/r1.json" fetch_failures)" "0"
chk "no access failures"   "$(field "$LAB/r1.json" access_failures)" "0"
EMPTY=$("$PY" - "$LAB/w1/state/shadow.db" <<'P'
import sys,sqlite3
c=sqlite3.connect("file:%s?mode=ro"%sys.argv[1],uri=True)
print(c.execute("SELECT COUNT(*) FROM shadow_records WHERE LENGTH(TRIM(COALESCE(text_original,'')))<200").fetchone()[0])
P
)
chk "no empty/short bodies" "$EMPTY" "0"
H1=$(shasum -a 256 "$LAB/w1/state/shadow.db" | cut -d' ' -f1)

echo "=== 3. duplicate-only second run ==="
collect "$LAB/w1/state" dup_2 --target-date "$(date -u +%F)" > "$LAB/r2.json"
chk "result all-duplicates" "$(field "$LAB/r2.json" result)" "ok_all_duplicates"
chk "inserted nothing"      "$(field "$LAB/r2.json" inserted)" "0"
chk "duplicates == first insert count" "$(field "$LAB/r2.json" duplicates)" "$INS"
H2=$(shasum -a 256 "$LAB/w1/state/shadow.db" | cut -d' ' -f1)
chk "state hash unchanged"  "$H2" "$H1"
chk "clock not rewritten"   "$("$PY" -c "import json;print(json.load(open('$LAB/w1/state/clock.json'))['day_zero_utc'])")" "$Z1"

echo "=== 4. independent deterministic rebuild ==="
mkdir -p "$LAB/w2/state"
collect "$LAB/w2/state" rebuild_3 --target-date "$(date -u +%F)" > "$LAB/r3.json"
CMP=$("$PY" - "$LAB/w1/state/shadow.db" "$LAB/w2/state/shadow.db" <<'P'
import sys,sqlite3
def rows(p):
    c=sqlite3.connect("file:%s?mode=ro"%p,uri=True)
    try:
        return c.execute("SELECT url,source_identity,title_original,text_original,"
                         "published_date,published_at_utc,location,units,content_sha256"
                         " FROM shadow_records ORDER BY source_identity").fetchall()
    finally: c.close()
print("same" if rows(sys.argv[1])==rows(sys.argv[2]) else "different")
P
)
chk "independent corpora identical" "$CMP" "same"

echo "=== 5. stale-writer / non-fast-forward rejection ==="
( cd "$LAB/w1" && git add state >/dev/null && git -c user.email=a@b -c user.name=a commit -qm "shadow(us-indopacom): run bootstrap_1" && git push -q origin "$BRANCH" ) 2>/dev/null
git clone --quiet --branch "$BRANCH" --single-branch "$LAB/origin.git" "$LAB/stale" 2>/dev/null
# another writer lands first
( cd "$LAB/w1" && echo "later" >> state/ledger/.marker && git add state && git -c user.email=a@b -c user.name=a commit -qm "shadow(us-indopacom): run other" && git push -q origin "$BRANCH" ) 2>/dev/null
( cd "$LAB/stale" && echo "stale" >> state/ledger/.marker2 && git add state && git -c user.email=a@b -c user.name=a commit -qm "shadow(us-indopacom): run stale" ) 2>/dev/null
if ( cd "$LAB/stale" && git push origin "$BRANCH" ) >/dev/null 2>&1; then
  no "stale writer was REJECTED"
else
  ok "stale writer rejected (non-fast-forward)"
fi
TIP=$(git --git-dir="$LAB/origin.git" rev-parse "$BRANCH")
EXP=$( cd "$LAB/w1" && git rev-parse HEAD )
chk "remote tip is the winner's commit" "$TIP" "$EXP"
WF="$REPO/.github/workflows/us_shadow.yml"
# Must not pass vacuously: an absent workflow is a failed check, not a clean
# one. The first dry run of this harness "passed" this because `cat || echo ""`
# fed grep an empty string.
if [ ! -f "$WF" ]; then
  no "workflow file present at .github/workflows/us_shadow.yml"
else
  ok "workflow file present"
  # Strip comments first. The header says "no --force-with-lease either", and
  # three guards in a row have now been tripped by the sentence that DENIES
  # the thing they look for. PyYAML is deliberately not a dependency of this
  # project, so everything here is text.
  EXEC=$(sed -e 's/^[[:space:]]*#.*$//' "$WF")
  if printf '%s' "$EXEC" | grep -qE -- '(--force|force-with-lease|push -f)'; then
    no "workflow contains no force push"
  else
    ok "workflow contains no force push"
  fi
  grep -q 'cancel-in-progress: false' "$WF" && ok "concurrency does not cancel in progress" || no "concurrency cancels in progress"
  PERMS=$(sed -n '/^permissions:/,/^[a-z]/p' "$WF" | grep -cE '^[[:space:]]+[a-z-]+:')
  chk "exactly one permission granted" "$PERMS" "1"
  grep -q '^  contents: write' "$WF" && ok "the one permission is contents:write" || no "permission is not contents:write"
  printf '%s' "$EXEC" | grep -q "shadow/us-indopacom" && ok "pushes only the US state branch" || no "state branch not named"
  if printf '%s' "$EXEC" | grep -qE 'shadow/(singapore-mindef|jp-mod)'; then
    no "workflow names another desk's state branch"
  else
    ok "workflow names no other desk's state branch"
  fi
  CRON=$(grep -oE "cron: '[^']+'" "$WF" | head -1 | sed "s/cron: '//;s/'//")
  chk "schedule is separated from Singapore and Japan" "$CRON" "40 8 * * *"
  OTHERS=$(grep -hoE "cron: '[^']+'" "$REPO"/.github/workflows/singapore_shadow.yml "$REPO"/.github/workflows/japan_shadow.yml | sed "s/cron: '//;s/'//")
  if printf '%s\n' "$OTHERS" | grep -qx "$CRON"; then
    no "US cron collides with Singapore or Japan"
  else
    ok "US cron collides with neither ($(printf '%s' "$OTHERS" | tr '\n' '/'))"
  fi
fi

echo "=== 6. interrupted-run recovery ==="
git clone --quiet --branch "$BRANCH" --single-branch "$LAB/origin.git" "$LAB/w3" 2>/dev/null
BEFORE=$(ls "$LAB/w3/state/ledger"/*.json 2>/dev/null | wc -l | tr -d ' ')
# a run that dies before publishing leaves the remote untouched
( cd "$LAB/w3" && rm -rf state/ledger && : ) 2>/dev/null   # simulate a half-written local state
TIP_AFTER=$(git --git-dir="$LAB/origin.git" rev-parse "$BRANCH")
chk "interrupted run pushed nothing" "$TIP_AFTER" "$TIP"
git clone --quiet --branch "$BRANCH" --single-branch "$LAB/origin.git" "$LAB/w4" 2>/dev/null
AFTER=$(ls "$LAB/w4/state/ledger"/*.json 2>/dev/null | wc -l | tr -d ' ')
chk "next clone is intact" "$AFTER" "$BEFORE"

echo "=== 7. missed-run gap detection ==="
rm -rf "$LAB/gap"; cp -R "$LAB/w1/state" "$LAB/gap"
"$PY" - "$LAB/gap" <<'P'
import sys,json,glob,os
files=sorted(glob.glob(os.path.join(sys.argv[1],"ledger","*.json")))
for path,day in zip(files,["2026-09-10","2026-09-13"]):
    e=json.load(open(path)); e["finished_utc"]="%sT12:00:00+00:00"%day
    json.dump(e,open(path,"w"),indent=1,sort_keys=True)
P
GAP=$( cd "$REPO" && "$PY" scripts/review_us_shadow_state.py --state-repo "$LAB/gap" --json 2>/dev/null \
       | "$PY" -c "import json,sys;print(sum(1 for f in json.load(sys.stdin)['findings'] if 'UNRECOVERABLE' in f))" )
chk "gap reported as unrecoverable" "$GAP" "1"

echo "=== 8. review-tool NOT READY verdict ==="
OUT=$( cd "$REPO" && "$PY" scripts/review_us_shadow_state.py --state-repo "$LAB/w1/state" 2>/dev/null )
echo "$OUT" | grep -q "NOT READY" && ok "verdict NOT READY" || no "verdict was not NOT READY"
echo "$OUT" | grep -qi "ELIGIBLE FOR HUMAN REVIEW" && no "claimed eligibility" || ok "did not claim eligibility"
echo "$OUT" | grep -q "SCOPE FITNESS" && ok "scope fitness reported" || no "no scope fitness"

echo
echo "=== durable-state safety ==="
git --git-dir="$LAB/origin.git" for-each-ref --format='  local bare ref: %(refname)' | head
echo "  (no GitHub remote was contacted; origin is $LAB/origin.git)"
echo
printf 'REHEARSAL: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
