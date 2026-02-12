"""
Patch Validator Module - パッチ検証・提案エンジン
Purpose: AI生成パッチを検証し、安全なコード提案を管理
        - パッチ構文検証
        - インポート確認
        - リント検査
        - サンドボックス実行
        - 提案・承認・却下管理
Usage: PatchValidator.validate_patch(...), list_proposals(...)
Status: Evolver からのパッチ提案を検証、承認時に自動適用
"""
import json
import logging
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from config import Config
from sandbox import validate_patch, save_validation_report
from git_utils import create_branch_and_commit

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class PatchProposal:
    """Represents a single patch proposal"""
    
    def __init__(self, title: str, description: str, files: dict, branch_name: str = None):
        self.id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.title = title
        self.description = description
        self.files = files
        self.branch_name = branch_name or f"{Config.AUTO_EDIT_BRANCH_PREFIX}/{self.id}"
        self.validation = None
        self.git_result = None
        self.status = 'DRAFT'  # DRAFT -> VALIDATED -> PROPOSED -> APPROVED -> MERGED
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'branch_name': self.branch_name,
            'files': list(self.files.keys()),
            'validation': self.validation,
            'git_result': self.git_result,
            'status': self.status,
            'created_at': self.id,
        }
    
    def validate(self) -> bool:
        """Run sandbox validation on all files"""
        logger.info(f'Validating patch {self.id}...')
        self.validation = validate_patch(self.files)
        
        if self.validation['overall_ok']:
            self.status = 'VALIDATED'
            logger.info(f'✓ Patch {self.id} passed validation')
        else:
            self.status = 'FAILED'
            logger.error(f'✗ Patch {self.id} failed validation')
            logger.error(f"  Failed files: {[f for f,r in self.validation['files'].items() if r.get('status') == 'FAILED']}")
        
        return self.validation['overall_ok']
    
    def create_git_branch(self) -> bool:
        """Create git branch and commit files"""
        if self.status not in ('VALIDATED', 'PROPOSED'):
            logger.warning(f'Cannot create git branch for patch in status {self.status}')
            return False
        
        logger.info(f'Creating git branch {self.branch_name} for patch {self.id}...')
        commit_msg = f"{Config.AUTO_EDIT_COMMIT_MESSAGE_TEMPLATE}\n\nPatch ID: {self.id}\nTitle: {self.title}"
        self.git_result = create_branch_and_commit(self.files, self.branch_name, commit_msg)
        
        if self.git_result.get('status') == 'ok':
            logger.info(f'✓ Git branch created: {self.branch_name}')
            return True
        else:
            logger.warning(f'Git branch creation: {self.git_result}')
            # still mark as proposed even if git fails
            return self.git_result.get('status') == 'no_git'
    
    def propose(self) -> bool:
        """Mark as PROPOSED and record to filesystem"""
        if self.status not in ('VALIDATED', 'FAILED'):
            logger.warning(f'Cannot propose patch in status {self.status}')
            return False
        
        if self.status == 'FAILED':
            logger.warning(f'Proposing failed patch {self.id} anyway (for manual review)')
        
        self.status = 'PROPOSED'
        
        # Save proposal to filesystem
        proposal_dir = Config.PROJECT_ROOT / 'data' / 'patches' / self.id
        proposal_dir.mkdir(parents=True, exist_ok=True)
        
        # save proposal metadata
        proposal_file = proposal_dir / 'proposal.json'
        with open(proposal_file, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        
        # save validation report
        if self.validation:
            validation_file = proposal_dir / 'validation.json'
            with open(validation_file, 'w', encoding='utf-8') as f:
                json.dump(self.validation, f, indent=2, ensure_ascii=False)
        
        # save individual files
        files_dir = proposal_dir / 'files'
        files_dir.mkdir(exist_ok=True)
        for path, content in self.files.items():
            fpath = files_dir / path.replace('/', '_')
            fpath.write_text(content, encoding='utf-8')
        
        logger.info(f'✓ Patch {self.id} proposed. Details saved to {proposal_dir}')
        return True

class PatchValidator:
    """Orchestrates patch generation, validation, and proposal"""
    
    @staticmethod
    def create_and_validate(title: str, description: str, files: dict, auto_propose: bool = True) -> PatchProposal:
        """
        Create, validate, and optionally propose a patch.
        
        Args:
            title: Patch title
            description: Detailed description
            files: dict of {file_path: content}
            auto_propose: if True and validation passes, automatically propose
        
        Returns:
            PatchProposal object
        """
        proposal = PatchProposal(title, description, files)
        
        # validate
        if not proposal.validate():
            logger.warning(f'Patch {proposal.id} validation failed; not proceeding with git')
            if auto_propose:
                proposal.propose()  # still save for review
            return proposal
        
        # create git branch
        proposal.create_git_branch()
        
        # propose
        if auto_propose:
            proposal.propose()

        # auto-approve / auto-apply (guarded)
        if proposal.validation and proposal.validation.get('overall_ok'):
            if Config.AUTO_APPLY_PATCHES and (not Config.AUTO_APPLY_REQUIRE_VALIDATION or proposal.status in ('VALIDATED', 'PROPOSED')):
                PatchValidator._auto_apply_if_allowed(proposal)
            elif Config.AUTO_APPROVE_PATCHES and proposal.status == 'PROPOSED':
                PatchValidator.approve_proposal(proposal.id)
        
        return proposal
    
    @staticmethod
    def list_proposals(status: str = None) -> list:
        """List all proposals, optionally filtered by status"""
        patches_dir = Config.PROJECT_ROOT / 'data' / 'patches'
        if not patches_dir.exists():
            return []
        
        proposals = []
        for patch_id_dir in patches_dir.iterdir():
            if not patch_id_dir.is_dir():
                continue
            proposal_file = patch_id_dir / 'proposal.json'
            if proposal_file.exists():
                with open(proposal_file, 'r', encoding='utf-8') as f:
                    prop = json.load(f)
                if status is None or prop.get('status') == status:
                    proposals.append(prop)
        
        return sorted(proposals, key=lambda p: p['id'], reverse=True)
    
    @staticmethod
    def approve_proposal(proposal_id: str) -> bool:
        """Mark a proposal as APPROVED (manual gate before merging)"""
        patches_dir = Config.PROJECT_ROOT / 'data' / 'patches' / proposal_id
        proposal_file = patches_dir / 'proposal.json'
        
        if not proposal_file.exists():
            logger.error(f'Proposal {proposal_id} not found')
            return False
        
        with open(proposal_file, 'r', encoding='utf-8') as f:
            prop = json.load(f)
        
        if prop['status'] not in ('PROPOSED', 'FAILED'):
            logger.warning(f"Cannot approve proposal in status {prop['status']}")
            return False
        
        prop['status'] = 'APPROVED'
        prop['approved_at'] = datetime.now().isoformat()
        
        with open(proposal_file, 'w', encoding='utf-8') as f:
            json.dump(prop, f, indent=2, ensure_ascii=False)
        
        logger.info(f'✓ Proposal {proposal_id} approved')
        return True

    @staticmethod
    def _is_allowed_path(path: str) -> bool:
        norm = path.replace('\\', '/').lstrip('/')
        if '..' in norm or norm.startswith('./'):
            return False
        for deny in Config.AUTO_APPLY_DENY_DIRS:
            if norm.startswith(deny):
                return False
        for allow in Config.AUTO_APPLY_ALLOWED_PATHS:
            if allow == "":
                return True
            if norm == allow.rstrip('/') or norm.startswith(allow):
                return True
        return False

    @staticmethod
    def _auto_apply_if_allowed(proposal: PatchProposal) -> bool:
        files = proposal.files or {}
        if Config.AUTO_APPLY_MAX_FILES and len(files) > int(Config.AUTO_APPLY_MAX_FILES):
            logger.warning('Auto-apply skipped: too many files')
            return False

        for path in files.keys():
            if not PatchValidator._is_allowed_path(path):
                logger.warning(f'Auto-apply skipped: path not allowed: {path}')
                return False

        backups = {}
        for path, content in files.items():
            target = (Config.PROJECT_ROOT / path).resolve()
            if not str(target).startswith(str(Config.PROJECT_ROOT.resolve())):
                logger.warning(f'Auto-apply skipped: unsafe path: {path}')
                return False
            if target.exists():
                backup_dir = Config.BACKUP_DIR / 'auto_apply'
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_path = backup_dir / f"{target.name}.{proposal.id}.bak"
                shutil.copy2(target, backup_path)
                backups[path] = str(backup_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')

        postcheck = None
        if Config.AUTO_APPLY_POSTCHECK_ENABLED:
            postcheck = PatchValidator._run_post_apply_checks()
            if not postcheck.get("ok"):
                PatchValidator._rollback_files(backups)
                logger.warning('Auto-apply rolled back due to post-check failure')
                PatchValidator._record_apply_result(proposal.id, files, backups, applied=False, postcheck=postcheck)
                return False

        # mark proposal as approved/applied
        PatchValidator._record_apply_result(proposal.id, files, backups, applied=True, postcheck=postcheck)

        logger.info(f'✓ Patch {proposal.id} auto-applied with backups')
        return True

    @staticmethod
    def _record_apply_result(proposal_id: str, files: dict, backups: dict, applied: bool, postcheck: dict | None = None) -> None:
        patches_dir = Config.PROJECT_ROOT / 'data' / 'patches' / proposal_id
        proposal_file = patches_dir / 'proposal.json'
        if not proposal_file.exists():
            return
        with open(proposal_file, 'r', encoding='utf-8') as f:
            prop = json.load(f)
        if applied:
            prop['status'] = 'APPROVED'
            prop['approved_at'] = datetime.now().isoformat()
        prop['applied'] = applied
        prop['applied_at'] = datetime.now().isoformat()
        prop['applied_files'] = list(files.keys())
        if backups:
            prop['backups'] = backups
        if postcheck is not None:
            prop['postcheck'] = postcheck
        with open(proposal_file, 'w', encoding='utf-8') as f:
            json.dump(prop, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _rollback_files(backups: dict) -> None:
        for path, backup_path in backups.items():
            try:
                target = (Config.PROJECT_ROOT / path).resolve()
                shutil.copy2(backup_path, target)
            except Exception as e:
                logger.warning(f'Rollback failed for {path}: {e}')

    @staticmethod
    def _run_cmd(cmd: str, timeout: int) -> dict:
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return {
                "ok": proc.returncode == 0,
                "cmd": cmd,
                "returncode": proc.returncode,
                "stdout": proc.stdout[-2000:],
                "stderr": proc.stderr[-2000:],
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "cmd": cmd, "returncode": -1, "stdout": "", "stderr": "timeout"}
        except Exception as e:
            return {"ok": False, "cmd": cmd, "returncode": -1, "stdout": "", "stderr": str(e)}

    @staticmethod
    def _run_post_apply_checks() -> dict:
        results = []
        timeout = int(Config.AUTO_APPLY_POSTCHECK_TIMEOUT or 60)

        # default: run pytest if tests directory exists
        tests_dir = Config.PROJECT_ROOT / 'tests'
        if tests_dir.exists():
            results.append(PatchValidator._run_cmd('pytest -q', timeout))

        # extra commands
        for cmd in Config.AUTO_APPLY_POSTCHECK_COMMANDS or []:
            results.append(PatchValidator._run_cmd(cmd, timeout))

        if not results:
            return {"ok": True, "skipped": True, "results": []}
        ok = all(r.get("ok") for r in results)
        return {"ok": ok, "results": results}

if __name__ == '__main__':
    # Example: create a test patch
    test_files = {
        'test_feature.py': '''def new_feature():
    """Example of auto-generated code"""
    return "Hello from auto-edit!"
'''
    }
    
    proposal = PatchValidator.create_and_validate(
        title='Add test feature',
        description='This is a test patch generated by the auto-edit system',
        files=test_files,
        auto_propose=True
    )
    
    print(f'Proposal ID: {proposal.id}')
    print(f'Status: {proposal.status}')
    print(f'Validation OK: {proposal.validation.get("overall_ok") if proposal.validation else "N/A"}')
    
    # List all proposals
    all_proposals = PatchValidator.list_proposals()
    print(f'\nTotal proposals: {len(all_proposals)}')
    for p in all_proposals[:3]:
        print(f"  {p['id']}: {p['title']} [{p['status']}]")
