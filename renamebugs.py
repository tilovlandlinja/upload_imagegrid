from pathlib import Path
import unicodedata
import re
import shutil

ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_. ()")

def sanitize_name(name: str) -> str:
    n = unicodedata.normalize("NFKC", name)

    out = []
    for ch in n:
        cat = unicodedata.category(ch)
        if ch in ALLOWED and cat[0] != 'C':
            out.append(ch)
        else:
            out.append('_')
    safe = ''.join(out)

    safe = re.sub(r'_+', '_', safe).strip()
    safe = safe.rstrip(' .')

    return safe or "unnamed"

def copy_and_rename_tree(src: Path, dst: Path):
    for p in src.rglob('*'):
        rel = p.relative_to(src)  # beholder mappestruktur
        new_name = sanitize_name(p.name)
        new_rel = rel.with_name(new_name)
        target = dst / new_rel

        if p.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)  # bevarer metadata (tidspunkter osv.)

# Bruk:
copy_and_rename_tree(
    Path(r"T:\Linjebefaring2019\Romvesen-Eid-2708-2019\SFE Nett AS - Toppbefaring 2019\Dag 13 - Kjølsdalen mot Midthjell og rest Eid og Stårheim"),
    Path(r"T:\Linjebefaring2019\Romvesen-Eid-2708-2019\SFE Nett AS - Toppbefaring 2019\Dag 13 - Kjølsdalen mot Midthjell og rest Eid og Stårheim_renamed")
)
