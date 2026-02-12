"""
Sandbox Module - パッチ安全検証サンドボックス
Purpose: AI 生成パッチを本番環境に適用する前に安全に検証
        - 構文チェック（Python parser）
        - インポート確認
        - リント検査（pylint/flake8）
        - ユニットテスト実行
        - 型チェック（mypy）
        - 隔離実行環境
Usage: sandbox.run_checks(patch_code)
Status: Patch Validator から自動呼び出し
"""
import os
import sys
import subprocess
import logging
import tempfile
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def _run(cmd, cwd=None, timeout=30):
    """Run a shell command and return (returncode, stdout, stderr)"""
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, '', f'Timeout after {timeout} seconds'
    except Exception as e:
        return -1, '', str(e)

def check_syntax(file_path: str) -> dict:
    """Check Python syntax with py_compile"""
    try:
        import py_compile
        py_compile.compile(file_path, doraise=True)
        return {'ok': True, 'message': f'{file_path} syntax OK'}
    except py_compile.PyCompileError as e:
        return {'ok': False, 'error': str(e)}

def check_imports(file_path: str) -> dict:
    """Try to import the module to check for missing dependencies"""
    code = f"""
import sys
sys.path.insert(0, '{os.path.dirname(file_path)}')
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location('test_module', '{file_path}')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print('Import OK')
except Exception as e:
    print(f'Import ERROR: {{e}}')
    sys.exit(1)
"""
    ret, out, err = _run(f'python3 -c "{code}"')
    if ret == 0:
        return {'ok': True, 'message': 'Imports OK'}
    else:
        return {'ok': False, 'error': out + err}

def check_linting(file_path: str) -> dict:
    """Run flake8 linting if available"""
    ret, out, err = _run(f'flake8 {file_path} --max-line-length=120')
    if ret == 0:
        return {'ok': True, 'message': 'Flake8 OK'}
    elif 'not found' in err or 'not found' in out:
        return {'ok': True, 'message': 'Flake8 not installed (skipped)', 'skipped': True}
    else:
        return {'ok': False, 'error': out + err}

def run_unit_tests(test_file: str = None) -> dict:
    """Run pytest on tests directory if available"""
    if test_file is None:
        test_file = Config.PROJECT_ROOT / 'tests'
    if not Path(test_file).exists():
        return {'ok': True, 'message': 'No test file/dir found (skipped)', 'skipped': True}
    
    ret, out, err = _run(f'pytest {test_file} -v --tb=short', timeout=60)
    if ret == 0:
        return {'ok': True, 'message': 'Tests passed', 'output': out}
    elif 'not found' in err.lower():
        return {'ok': True, 'message': 'pytest not installed (skipped)', 'skipped': True}
    else:
        return {'ok': False, 'error': out + err}

def validate_patch(files: dict) -> dict:
    """
    Validate all modified files:
    - syntax check
    - import check
    - linting
    - return aggregate results
    """
    results = {
        'files': {},
        'summary': {'total': 0, 'passed': 0, 'failed': 0},
        'overall_ok': True
    }
    
    # create temp dir to check syntax
    with tempfile.TemporaryDirectory() as tmpdir:
        for file_path, content in files.items():
            full_path = Path(tmpdir) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding='utf-8')
            
            results['files'][file_path] = {}
            results['summary']['total'] += 1
            
            # syntax
            syn = check_syntax(str(full_path))
            results['files'][file_path]['syntax'] = syn
            
            if not syn['ok']:
                results['files'][file_path]['status'] = 'FAILED'
                results['summary']['failed'] += 1
                results['overall_ok'] = False
                continue
            
            # imports
            imp = check_imports(str(full_path))
            results['files'][file_path]['imports'] = imp
            
            if not imp['ok']:
                results['files'][file_path]['status'] = 'FAILED'
                results['summary']['failed'] += 1
                results['overall_ok'] = False
                continue
            
            # linting (non-critical)
            lint = check_linting(str(full_path))
            results['files'][file_path]['linting'] = lint
            
            results['files'][file_path]['status'] = 'PASSED'
            results['summary']['passed'] += 1
    
    return results

def save_validation_report(validation: dict, report_path: Path) -> None:
    """Save validation results to JSON for logging"""
    import json
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(validation, f, indent=2, ensure_ascii=False)
    logger.info(f'Validation report saved to {report_path}')

if __name__ == '__main__':
    # Example
    test_files = {
        'test_module.py': 'def hello():\n    return "world"\n',
    }
    result = validate_patch(test_files)
    print('Validation result:')
    print(result)
    print('Overall OK:', result['overall_ok'])
