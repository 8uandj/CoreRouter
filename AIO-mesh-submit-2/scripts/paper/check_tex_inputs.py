"""Check LaTeX braces, local manuscript references, and required assets without compiling."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "docs/AIO-mesh-rev1"
TOKEN = re.compile(r"\\(?:[A-Za-z@]+|[^A-Za-z@\n])|%[^\n]*|[{}]|\n[ \t]*\n")


def uncomment(source):
    return re.sub(r"(\\.)|%[^\n]*", lambda m: m[1] or "", source)


def check_braces(path):
    stack, previous = [], None
    source = path.read_text()
    for token in TOKEN.finditer(source):
        value = token.group()
        if value == "{":
            stack.append((token.start(), previous in (r"\newrev", r"\rev")))
        elif value == "}":
            if not stack:
                raise ValueError(f"{path}: stray closing brace at offset {token.start()}")
            stack.pop()
        elif value.startswith("\n") and any(revision for _, revision in stack):
            raise ValueError(f"{path}: paragraph break inside revision command")
        previous = value
    if stack:
        raise ValueError(f"{path}: unclosed braces at offsets {[offset for offset, _ in stack]}")


def manuscript_source(path, seen):
    if path in seen:
        raise ValueError(f"Recursive or repeated manuscript input: {path}")
    seen.add(path)
    check_braces(path)
    source = uncomment(path.read_text())
    return re.sub(r"\\(?:input|TableRows)\{([^}]+)\}",
                  lambda m: manuscript_source(PAPER / m[1], seen), source)


def main():
    seen = set()
    paper = manuscript_source(PAPER / "rev1.tex", seen)
    check_braces(ROOT / "docs/response_rev1.tex")
    check_braces(PAPER / "rev_clean.tex")
    labels = re.findall(r"\\label\{([^}]+)\}", paper)
    if len(set(labels)) != len(labels):
        raise ValueError("Duplicate manuscript labels")
    references = set(re.findall(r"\\(?:ref|eqref|autoref)\{([^}]+)\}", paper))
    if references - set(labels):
        raise ValueError(f"Missing labels: {sorted(references - set(labels))}")
    assets = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", paper)
    for asset in assets:
        if not (PAPER / asset).is_file():
            raise FileNotFoundError(PAPER / asset)
    bibkeys = set(re.findall(r"@\w+\s*\{\s*([^,]+),", (PAPER / "refs.bib").read_text()))
    citations = {
        key.strip()
        for group in re.findall(r"\\cite\{([^}]+)\}", paper)
        for key in group.split(",")
    }
    if citations - bibkeys:
        raise ValueError(f"Missing bibliography keys: {sorted(citations - bibkeys)}")
    print(f"Checked {len(seen)} manuscript inputs, {len(references)} references, "
          f"{len(assets)} figures, and {len(citations)} citation keys.")
    supplementary_seen = set()
    supplement = manuscript_source(PAPER / "supplement.tex", supplementary_seen)
    supplementary_labels = re.findall(r"\\label\{([^}]+)\}", supplement)
    if len(set(supplementary_labels)) != len(supplementary_labels):
        raise ValueError("Duplicate supplementary labels")
    supplementary_refs = set(re.findall(r"\\(?:ref|eqref|autoref)\{([^}]+)\}", supplement))
    if supplementary_refs - set(supplementary_labels):
        raise ValueError(f"Missing supplementary labels: {sorted(supplementary_refs - set(supplementary_labels))}")
    supplementary_assets = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", supplement)
    for asset in supplementary_assets:
        if not (PAPER / asset).is_file():
            raise FileNotFoundError(PAPER / asset)
    supplementary_citations = {
        key.strip()
        for group in re.findall(r"\\cite\{([^}]+)\}", supplement)
        for key in group.split(",")
    }
    if supplementary_citations - bibkeys:
        raise ValueError(f"Missing supplementary bibliography keys: {sorted(supplementary_citations - bibkeys)}")
    print(f"Checked {len(supplementary_seen)} supplementary inputs, {len(supplementary_refs)} references, "
          f"{len(supplementary_assets)} figures, and {len(supplementary_citations)} citation keys.")


if __name__ == "__main__":
    main()
