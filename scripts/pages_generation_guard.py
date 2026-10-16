"""Guarded git-backed Pages publisher prototype (issue #346).

Opt-in ONLY; no workflow calls this. The command reads an exact committed
main:output snapshot and the current gh-pages tree, detects untracked mutations,
and publishes either selected files or a complete lossless snapshot with a
same-commit generation manifest. Without --push it cannot mutate the remote.

A monotonic commit ancestry check is not a substitute for publication-policy
approvals, an independently authenticated source digest or cross-ref atomicity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile

MANIFEST = '.ipr-release.json'
PRESERVED = frozenset({'CNAME', '.nojekyll'})
FORMAT = 1

class Hold(Exception):
    """Release eligibility failed closed."""


def git(cwd: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    result = subprocess.run(['git', *args], cwd=cwd, input=input_bytes,
                            capture_output=True)
    if result.returncode:
        # Do not echo URL or credentials accidentally embedded in git stderr.
        raise Hold('git operation failed: ' + args[0])
    return result.stdout


def path_ok(s: str) -> bool:
    p = PurePosixPath(s)
    return bool(s) and not s.startswith('/') and str(p) == s and all(
        component not in ('.', '..', '') for component in p.parts
    ) and s != MANIFEST and s != '.git' and not s.startswith('.git/')


def digest(files: dict[str, bytes]) -> str:
    """Stable, unambiguous hash of paths and file contents, not timestamps."""
    h = hashlib.sha256()
    for name in sorted(files):
        if not path_ok(name):
            raise Hold('unsafe file in publication tree')
        encoded = name.encode('utf-8')
        raw = files[name]
        h.update(len(encoded).to_bytes(8, 'big') + encoded)
        h.update(len(raw).to_bytes(8, 'big') + raw)
    return h.hexdigest()


def tree_files(root: Path) -> dict[str, bytes]:
    result = {}
    for item in root.rglob('*'):
        if '.git' in item.relative_to(root).parts:
            continue
        if item.is_symlink():
            raise Hold('symlinks are not allowed in published files')
        if not item.is_file():
            continue
        rel = item.relative_to(root).as_posix()
        if rel == MANIFEST:
            continue
        if not path_ok(rel):
            raise Hold('unsafe output path')
        result[rel] = item.read_bytes()
    return result


def committed_output(repo: Path, source_sha: str) -> dict[str, bytes]:
    """Read the immutable commit's output/; no mutable working tree."""
    raw = git(repo, 'ls-tree', '-r', '-z', source_sha, '--', 'output')
    files = {}
    for entry in raw.split(b'\0'):
        if not entry:
            continue
        meta, raw_path = entry.split(b'\t', 1)
        mode, kind, blob = meta.split(b' ')
        if kind != b'blob' or mode != b'100644' and mode != b'100755':
            raise Hold('output contains an unsupported entry')
        path = raw_path.decode('utf-8', errors='strict')
        name = path[len('output/'):]
        if not path.startswith('output/') or (not path_ok(name) and name != MANIFEST):
            raise Hold('output contains unsafe path')
        if name == MANIFEST:
            raise Hold('source output cannot supply its own release manifest')
        files[name] = git(repo, 'cat-file', 'blob', blob.decode('ascii'))
    if not files:
        raise Hold('committed output is empty')
    return files


def verify_committed_release(pages: Path, wanted: dict[str, bytes], manifest: dict) -> None:
    """Attest *Git HEAD*, not just the working files before `git add`.

    A tracked .gitignore or .gitattributes filter can make staged/committed
    bytes differ from the proposed filesystem tree. Comparing blob OIDs to
    the exact planned bytes prevents a manifest from claiming omitted or
    silently transformed content. IPR's GitHub repository uses SHA-1 objects.
    """
    canonical = (json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n').encode()
    expected = dict(wanted)
    expected[MANIFEST] = canonical
    raw = git(pages, 'ls-tree', '-r', '-z', 'HEAD')
    observed = {}
    for entry in raw.split(b'\0'):
        if not entry:
            continue
        try:
            meta, path_bytes = entry.split(b'\t', 1)
            mode, kind, oid = meta.split(b' ')
            name = path_bytes.decode('utf-8', errors='strict')
        except (ValueError, UnicodeDecodeError) as exc:
            raise Hold('malformed committed Pages tree') from exc
        if kind != b'blob' or mode not in (b'100644', b'100755'):
            raise Hold('committed Pages tree contains unsupported entry')
        if name != MANIFEST and not path_ok(name):
            raise Hold('committed Pages tree contains unsafe path')
        observed[name] = oid.decode('ascii')
    if set(observed) != set(expected):
        raise Hold('committed Pages tree omitted or added a planned file')
    for name, content in expected.items():
        header = b'blob ' + str(len(content)).encode('ascii') + b'\0'
        blob = hashlib.sha1(header + content).hexdigest()
        if observed[name] != blob:
            raise Hold('committed Pages tree transformed planned file bytes')


def parse_manifest(raw: bytes) -> dict:
    try:
        doc = json.loads(raw)
        if not isinstance(doc, dict) or set(doc) != {
            'schema', 'generation', 'source_sha', 'writer', 'tree_sha256', 'rollback'
        }:
            raise ValueError('invalid keys')
        if type(doc['schema']) is not int or doc['schema'] != FORMAT:
            raise ValueError('schema')
        if type(doc['generation']) is not int or doc['generation'] < 1:
            raise ValueError('generation')
        if not isinstance(doc['source_sha'], str) or len(doc['source_sha']) != 40 or not all(c in '0123456789abcdef' for c in doc['source_sha']):
            raise ValueError('source sha')
        if not isinstance(doc['tree_sha256'], str) or len(doc['tree_sha256']) != 64 or not all(c in '0123456789abcdef' for c in doc['tree_sha256']):
            raise ValueError('digest')
        if not isinstance(doc['writer'], str) or not 1 <= len(doc['writer']) <= 80:
            raise ValueError('writer')
        if doc['rollback'] is not None:
            if not isinstance(doc['rollback'], dict) or set(doc['rollback']) != {'expected_current', 'target'}:
                raise ValueError('rollback')
            if any(not isinstance(v, str) or len(v) != 40 or not all(c in '0123456789abcdef' for c in v) for v in doc['rollback'].values()):
                raise ValueError('rollback sha')
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        raise Hold('untrusted or malformed release manifest') from exc
    return doc


def write_worktree(pages: Path, wanted: dict[str, bytes], manifest: dict) -> None:
    before = tree_files(pages)
    for rel in set(before) - set(wanted):
        (pages / rel).unlink()
    for rel, raw in wanted.items():
        dest = pages / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    (pages / MANIFEST).write_text(json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n')


def prepare(repo: Path, *, mode: str, writer: str, paths: tuple[str, ...] = (),
            preserve: tuple[str, ...] = (), rollback: dict | None = None,
            bootstrap: bool = False, push: bool = False) -> dict:
    """Read refs, attest the final tree and optionally publish by non-force CAS.

    No partial writes to the source checkout, main, or tracked output. During
    --push a temp gh-pages clone is the ONLY mutable tree. Existing site bytes
    may be carried forward only through an explicitly pinned --preserve list.
    """
    repo = repo.resolve()
    if mode not in {'file-only', 'full-tree'} or not writer or len(writer) > 80:
        raise Hold('invalid release mode or writer')
    if any(not path_ok(p) for p in paths + preserve):
        raise Hold('unsafe publication path')
    if len(set(paths)) != len(paths) or len(set(preserve)) != len(preserve):
        raise Hold('duplicate publication path')
    if set(paths) & set(preserve):
        raise Hold('a file cannot be published and preserved simultaneously')
    if mode == 'file-only' and (not paths or preserve):
        raise Hold('file-only requires --path and prohibits --preserve')
    if mode == 'full-tree' and paths:
        raise Hold('full-tree must not select individual paths')
    if any(p in PRESERVED for p in paths):
        raise Hold('cannot write infrastructure files with file-only release')
    if rollback is not None:
        raise Hold('rollback publication is not implemented in this pilot')

    git(repo, 'fetch', '-q', 'origin', 'main', 'gh-pages')
    main_sha = git(repo, 'rev-parse', 'origin/main').decode().strip()
    source_sha = git(repo, 'rev-parse', 'HEAD').decode().strip()
    if source_sha != main_sha:
        raise Hold('candidate source is not current origin/main')
    output = committed_output(repo, source_sha)
    remote = git(repo, 'remote', 'get-url', 'origin').decode().strip()
    # Never log the remote URL (may contain a credential).
    with tempfile.TemporaryDirectory(prefix='ipr-pages-guard-') as tmp:
        pages = Path(tmp) / 'pages'
        git(repo, 'clone', '-q', '--single-branch', '--branch', 'gh-pages', remote, str(pages))
        old_pages_sha = git(pages, 'rev-parse', 'HEAD').decode().strip()
        old = tree_files(pages)
        manifest_path = pages / MANIFEST
        if manifest_path.exists():
            previous = parse_manifest(manifest_path.read_bytes())
            if digest(old) != previous['tree_sha256']:
                raise Hold('Pages tree diverged from its integrity manifest')
            if bootstrap:
                raise Hold('release already bootstrapped')
        else:
            if not bootstrap:
                raise Hold('Pages release has no manifest; bootstrap approval required')
            # A safe bootstrap proves the existing site already mirrors the
            # authoritative output; CNAME/.nojekyll are infrastructure files.
            comparable = {k: v for k, v in old.items() if k not in PRESERVED}
            if comparable != {k: v for k, v in output.items() if k not in PRESERVED}: 
                raise Hold('cannot bootstrap: published tree differs from current main output')
            previous = None

        if previous is not None:
            prior_sha = previous['source_sha']
            ancestor = subprocess.run(['git', 'merge-base', '--is-ancestor', prior_sha, source_sha], cwd=repo, capture_output=True)
            if ancestor.returncode != 0:
                raise Hold('candidate main source is not descendant of published source')

        # Explicitly prevent writes that silently reintroduce stale content
        # previously published outside main:output (including shared file names).
        previous_output = committed_output(repo, previous['source_sha']) if previous else output
        divergent_pages_paths = {p for p in old if p in previous_output and
                                 old[p] != previous_output[p] and p not in PRESERVED}
        if mode == 'file-only':
            if any(p not in output for p in paths):
                raise Hold('file-only path is absent from committed main output')
            # A file-only release may legitimately leave unrelated files at an
            # older version of main, but it MUST NOT renew a generation with
            # content explicitly removed from current main:output. A separate
            # owner-attested Pages-only preservation policy is still needed.
            withdrawn = {p for p in old if p not in output and
                         p in previous_output and p not in PRESERVED}
            if withdrawn:
                raise Hold('file-only would retain source content removed from main')
            target = dict(old)
            target.update({p: output[p] for p in paths})
        else:
            target = dict(output)
            if divergent_pages_paths:
                raise Hold('full-tree would overwrite a Pages-only changed file')
            for p in preserve:
                if p not in old or p in output or p in PRESERVED:
                    raise Hold('carry-forward path must exist only on Pages')
                target[p] = old[p]
            # Keep special Pages infrastructure identical. If main supplies
            # CNAME or .nojekyll it MUST already equal Pages, otherwise hold.
            for p in PRESERVED:
                if p in old:
                    if p in output and output[p] != old[p]:
                        raise Hold('DNS / Pages infrastructure mismatch')
                    target[p] = old[p]
            unapproved = set(old) - set(target)
            if unapproved:
                raise Hold('full-tree would erase non-authorized Pages-only files')
        # File-only publications also have to respect the committed site
        # infrastructure contract. Otherwise a narrowly scoped desk writer
        # can silently attest a generation whose live DNS/nojekyll metadata
        # contradicts current main:output. The same rule applies at bootstrap.
        for special in PRESERVED:
            if special in output and special in old and output[special] != old[special]:
                raise Hold('DNS / Pages infrastructure mismatch')
        new_doc = {
            'schema': FORMAT, 'generation': previous['generation'] + 1 if previous else 1,
            'source_sha': source_sha, 'writer': writer,
            'tree_sha256': digest(target), 'rollback': None,
        }
        # Dry-run must prove the *same committed Git bytes* as --push. Building
        # the candidate in an ephemeral Pages clone is harmless to the remote,
        # and detects ignored files, smudge/clean filters, wrong file modes,
        # and other stage/commit differences before anyone treats a green
        # preflight as permission to deploy.
        write_worktree(pages, target, new_doc)
        if digest(tree_files(pages)) != new_doc['tree_sha256']:
            raise Hold('staged release tree digest mismatch')
        git(pages, 'add', '-A')
        git(pages, '-c', 'user.name=ipr-release-guard', '-c',
            'user.email=release-guard@users.noreply.github.com', 'commit',
            '-q', '-m', 'Guarded Pages generation %s' % new_doc['generation'])
        verify_committed_release(pages, target, new_doc)
        # A no-op still records a generation because the same-commit manifest
        # advances. Never push or mutate the remote unless explicitly approved.
        if push:
            # Source freshness check just before push, in addition to the Pages
            # fast-forward CAS. Main and Pages are two refs, not one atomic txn.
            git(repo, 'fetch', '-q', 'origin', 'main')
            if git(repo, 'rev-parse', 'origin/main').decode().strip() != source_sha:
                raise Hold('main advanced during candidate preparation')
            git(pages, 'fetch', '-q', 'origin', 'gh-pages')
            if git(pages, 'rev-parse', 'origin/gh-pages').decode().strip() != old_pages_sha:
                raise Hold('Pages changed during candidate preparation')
            git(pages, 'push', '-q', 'origin', 'HEAD:gh-pages')
        return {'published': bool(push), 'generation': new_doc['generation'],
                'source_sha': source_sha, 'writer': writer,
                'tree_sha256': new_doc['tree_sha256'], 'changed_paths': len(set(old) ^ set(target))
                     + sum(old[k] != target[k] for k in set(old) & set(target))}


def cli() -> None:
    parser = argparse.ArgumentParser(description='Opt-in guarded gh-pages generation prototype (#346)')
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--mode', choices=('file-only', 'full-tree'), required=True)
    parser.add_argument('--writer', required=True)
    parser.add_argument('--path', action='append', default=[])
    parser.add_argument('--preserve', action='append', default=[])
    parser.add_argument('--bootstrap', action='store_true')
    parser.add_argument('--push', action='store_true', help='explicitly publish (not used by production workflows)')
    args = parser.parse_args()
    try:
        data = prepare(args.repo, mode=args.mode, writer=args.writer,
                       paths=tuple(args.path), preserve=tuple(args.preserve),
                       bootstrap=args.bootstrap, push=args.push)
    except Hold as exc:
        print('HOLD: ' + str(exc), file=sys.stderr)
        raise SystemExit(2) from None
    print(json.dumps(data, sort_keys=True))

if __name__ == '__main__':
    cli()
