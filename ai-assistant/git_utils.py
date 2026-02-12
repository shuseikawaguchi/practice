"""
Git utilities: create branch, write files into auto_edit dir, commit, and record patch.
This script requires `git` available in PATH and that repository is a git repo.
"""
import os
import subprocess
import logging
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def _run(cmd, cwd=None):
    proc = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr

def ensure_git_repo():
    ret, out, err = _run('git rev-parse --show-toplevel')
    if ret != 0:
        return False, None
    return True, out.strip()

def create_branch_and_commit(files: dict, branch_name: str, commit_message: str) -> dict:
    ok, repo_root = ensure_git_repo()
    if not ok:
        logger.warning('Not a git repo; writing files to auto_edits directory only')
        for path, content in files.items():
            outp = Config.AUTO_EDIT_DIR / path
            outp.parent.mkdir(parents=True, exist_ok=True)
            outp.write_text(content, encoding='utf-8')
        return {'status': 'no_git', 'written': [str(Config.AUTO_EDIT_DIR / p) for p in files.keys()]}

    full_branch = branch_name
    # create branch
    code, out, err = _run(f'git checkout -b {full_branch}', cwd=repo_root)
    if code != 0:
        # maybe branch exists; try checkout
        code, out, err = _run(f'git checkout {full_branch}', cwd=repo_root)
        if code != 0:
            logger.error(f'Could not create or checkout branch {full_branch}: {err}')
            return {'status': 'error', 'error': err}

    written = []
    for path, content in files.items():
        p = Path(repo_root) / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')
        written.append(str(p))

    # add and commit
    code, out, err = _run('git add -A', cwd=repo_root)
    if code != 0:
        logger.error(f'git add failed: {err}')
    code, out, err = _run(f'git commit -m "{commit_message}"', cwd=repo_root)
    if code != 0:
        logger.warning(f'git commit may have failed (no changes?): {err}')

    # create patch file
    patch_file = Config.AUTO_EDIT_DIR / f'{full_branch.replace("/","_")}.patch'
    code, out, err = _run(f'git format-patch -1 --stdout HEAD > "{patch_file}"', cwd=repo_root)
    if code != 0:
        logger.warning(f'Could not create patch: {err}')
    return {'status': 'ok', 'branch': full_branch, 'written': written, 'patch': str(patch_file)}