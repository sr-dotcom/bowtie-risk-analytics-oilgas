"""corpus_v1 noise JSON quarantine.

Moves JSONs in structured_json/ that have no matching PDF in raw_pdfs/
into structured_json_noise/.
"""
import pathlib
import shutil
import urllib.parse

from src.corpus.manifest import CORPUS_V1_ROOT


def move_noise_jsons(
    corpus_root: pathlib.Path | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Move JSON files with no matching PDF to structured_json_noise/.

    Args:
        corpus_root: Override the default CORPUS_V1_ROOT (useful for tests).
        dry_run: If True, return the list without moving anything.

    Returns:
        List of filenames that were (or would be) moved.
    """
    root       = corpus_root or CORPUS_V1_ROOT
    raw_pdfs   = root / "raw_pdfs"
    structured = root / "structured_json"
    noise_dir  = root / "structured_json_noise"

    if not structured.exists():
        return []

    pdf_stems = {
        urllib.parse.unquote(f.stem)
        for f in raw_pdfs.glob("*.pdf")
    } if raw_pdfs.exists() else set()

    moved: list[str] = []
    for json_f in sorted(structured.glob("*.json")):
        stem = urllib.parse.unquote(json_f.stem)
        if stem not in pdf_stems:
            if not dry_run:
                noise_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(json_f), noise_dir / json_f.name)
            moved.append(json_f.name)

    return moved
