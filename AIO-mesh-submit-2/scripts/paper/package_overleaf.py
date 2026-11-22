#!/usr/bin/env python3
"""Package the manuscript's transitive LaTeX dependencies at the ZIP root."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / 'docs/AIO-mesh-rev1'
OUTPUT = ROOT / 'FGCS_overleaf_final.zip'

def main():
    files = {}
    def add_tex(relative):
        if relative in files:
            return
        data = (PAPER / relative).read_bytes()
        files[relative] = data
        source = re.sub(r'(?<!\\)%[^\n]*', '', data.decode())
        for name in re.findall(r'\\(?:input|TableRows)\{([^}]+)\}', source):
            add_tex(name if Path(name).suffix else name + '.tex')
        for name in re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}', source):
            files[name] = (PAPER / name).read_bytes()
        for name in re.findall(r'\\bibliography\{([^}]+)\}', source):
            files[name + '.bib'] = (PAPER / (name + '.bib')).read_bytes()
    add_tex('rev1.tex')
    add_tex('rev_clean.tex')
    add_tex('supplement.tex')
    def flatten(relative, stack=()):
        if relative in stack:
            raise ValueError(f"Recursive input: {relative}")
        source = files[relative].decode()
        def replace(match):
            name = match[1]
            name = name if Path(name).suffix else name + '.tex'
            return flatten(name, (*stack, relative)).rstrip('\n')
        return re.sub(r'\\(?:input|TableRows)\{([^}]+)\}', replace, source)
    standalone = flatten('rev1.tex')
    if re.search(r'\\(?:input|TableRows)\{', standalone):
        raise ValueError('Standalone manuscript retains input commands')
    files['rev1_standalone.tex'] = standalone.encode()
    files['rev_clean_standalone.tex'] = ('\\def\\CleanRevision{1}\n' + standalone).encode()
    for name in ('rev1_standalone.tex', 'rev_clean_standalone.tex'):
        (PAPER / name).write_bytes(files[name])
    files['response_rev1.tex'] = (ROOT / 'docs/response_rev1.tex').read_bytes()
    files['README_OVERLEAF.txt'] = (
        'Upload this ZIP as a new Overleaf project. Keep the folder structure.\n'
        'Main document: rev1.tex (green) or rev_clean.tex (clean).\n'
        'Submit supplement.tex as a separate supplementary manuscript.\n'
        'These generated entry points inline all input files, including tabular rows.\n'
        'Standalone entry points are optional compatibility copies.\n'
        'Select response_rev1.tex separately to build the response letter.\n'
        'Compiler: pdfLaTeX; bibliography: BibTeX.\n'
        'generated/numbers.tex and all other referenced inputs are included.\n'
        'The ZIP is source-complete; PDF compilation has not been performed locally.\n'
    ).encode()
    files['SOURCE_SHA256.json'] = (json.dumps({name: hashlib.sha256(data).hexdigest()
                                            for name, data in sorted(files.items())}, indent=2) + '\n').encode()
    with zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    with zipfile.ZipFile(OUTPUT) as archive:
        assert archive.testzip() is None
        assert 'generated/numbers.tex' in archive.namelist()
        for name, data in files.items():
            assert archive.read(name) == data, name
    print(f'Created {OUTPUT}: {len(files)} entries, all source contents verified')

if __name__ == '__main__':
    main()
