\
import argparse
import re
from pathlib import Path
from datetime import date

def inject_doi_in_main(main_path: Path, version_doi: str):
    text = main_path.read_text(encoding="utf-8", errors="ignore")
    # Replace patterns like DOI: [xxxx] or DOI:[xxxx] or DOI: <...>
    new_text, n1 = re.subn(r'(DOI:\s*)(\[[xX]{4}\]|<[^>]*>|"[^"]*"|\S+)', rf'\g<1>{version_doi}', text)
    # Also try to replace placeholder like {DOI_PLACEHOLDER}
    new_text, n2 = re.subn(r'\{DOI[_\-\s]*PLACEHOLDER\}', version_doi, new_text)
    if (n1 + n2) == 0:
        print("[warn] Não encontrei placeholder claro; nenhuma alteração feita no main.py.")
    main_path.write_text(new_text, encoding="utf-8")
    print(f"[ok] DOI inserido no {main_path}")

def update_citation_cff(cff_path: Path, version_doi: str, concept_doi: str|None):
    if not cff_path.exists():
        print("[info] CITATION.cff não encontrado; pulando.")
        return
    text = cff_path.read_text(encoding="utf-8")
    text = text.replace("<VERSION_DOI>", version_doi)
    if concept_doi:
        text = text.replace("<CONCEPT_DOI>", concept_doi)
    # update date
    text = re.sub(r'(date-released:\s*")[^"]+(")', rf'\1{date.today().isoformat()}\2', text)
    cff_path.write_text(text, encoding="utf-8")
    print(f"[ok] CITATION.cff atualizado em {cff_path}")

def main():
    ap = argparse.ArgumentParser(description="Injeta DOI no main.py e atualiza CITATION.cff")
    ap.add_argument("--file", required=True, help="caminho para o main.py")
    ap.add_argument("--doi", required=True, help="DOI da versão (ex: 10.5281/zenodo.xxxxx)")
    ap.add_argument("--concept-doi", default=None, help="DOI conceitual (opcional)")
    ap.add_argument("--also-update-citation-cff", action="store_true", help="também atualizar CITATION.cff se existir")
    args = ap.parse_args()

    main_path = Path(args.file)
    inject_doi_in_main(main_path, args.doi)

    if args.also_update_citation_cff:
        cff_path = main_path.parent / "CITATION.cff"
        update_citation_cff(cff_path, args.doi, args.concept_doi)

if __name__ == "__main__":
    main()
