import ast
import json
from pathlib import Path


def test_revision_notebook_is_unexecuted_and_defaults_to_plan_only():
    path = Path('notebook/rev1-benchmark-ablation-kaggle.ipynb')
    notebook = json.loads(path.read_text())
    code = []
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code':
            assert cell['execution_count'] is None and cell['outputs'] == []
            source = ''.join(cell['source'])
            ast.parse(source)
            code.append(source)
    combined = '\n'.join(code)
    assert 'RUN_PHASE = False' in combined
    assert 'EXPECTED_PACKAGE_SHA256' in combined
    assert 'verify_package' in combined
    assert 'phase_driver.py' in combined
    assert '"--input-package"' in combined and '"--input-sha256"' in combined
    assert 'rmtree' not in combined
