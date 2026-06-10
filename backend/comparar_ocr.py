"""
Compara, acta por acta, los votos del JSON oficial de ONPE contra lo detectado por OCR.
Lee data/ocr_verificacion.json (generado por ocr_actas.py) y resume coincidencias.

  python comparar_ocr.py           # tabla + estadísticas
  python comparar_ocr.py --csv     # además escribe data/comparacion_ocr.csv
"""
import argparse
import csv
import json
import unicodedata
from pathlib import Path

DATA = Path(__file__).parent / "data"
SRC = DATA / "ocr_verificacion.json"
CSV_OUT = DATA / "comparacion_ocr.csv"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").upper().strip()


def candidato_corto(desc: str) -> str:
    n = norm(desc)
    if "FUERZA" in n:
        return "FP"
    if "JUNTOS" in n:
        return "JP"
    return desc[:6]


def detectado(valor: int, ocr_nums: list[int]) -> bool:
    blob = " ".join(str(n) for n in ocr_nums)
    return valor in set(ocr_nums) or str(valor) in blob


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", action="store_true", help="Escribir data/comparacion_ocr.csv")
    args = ap.parse_args()

    if not SRC.exists():
        print(f"No existe {SRC}. Corre antes: python ocr_actas.py --limit N")
        return
    data = json.loads(SRC.read_text(encoding="utf-8"))
    filas = [r for r in data["detalle"] if "error" not in r]

    print(f"{'mesa':<8}{'est':<4}{'FP json':>8}{'FP ocr':>8}{'JP json':>9}{'JP ocr':>8}  ok")
    print("-" * 56)
    tot = {"FP": [0, 0], "JP": [0, 0]}  # [detectados, total]
    ambos = 0
    rows_csv = []
    for r in filas:
        esp = r["esperado"]
        ocr = r["ocr_numeros"]
        vals = {candidato_corto(k): v for k, v in esp.items()}
        fp, jp = vals.get("FP"), vals.get("JP")
        fp_ok = detectado(fp, ocr) if fp is not None else None
        jp_ok = detectado(jp, ocr) if jp is not None else None
        for c, v, ok in (("FP", fp, fp_ok), ("JP", jp, jp_ok)):
            if v is not None:
                tot[c][1] += 1
                tot[c][0] += 1 if ok else 0
        both = bool(fp_ok) and bool(jp_ok)
        ambos += 1 if both else 0
        mark = lambda b: "✓" if b else "·"
        print(f"{str(r.get('mesa')):<8}{str(r.get('estado')):<4}"
              f"{('-' if fp is None else fp):>8}{mark(fp_ok):>8}"
              f"{('-' if jp is None else jp):>9}{mark(jp_ok):>8}  {mark(both)}")
        rows_csv.append({
            "mesa": r.get("mesa"), "estado": r.get("estado"),
            "fp_json": fp, "fp_ocr_detectado": fp_ok,
            "jp_json": jp, "jp_ocr_detectado": jp_ok,
            "ocr_numeros": " ".join(map(str, ocr)),
        })

    n = len(filas)
    print("-" * 56)
    print(f"Actas comparadas: {n}")
    for c in ("FP", "JP"):
        d, t = tot[c]
        print(f"  {c}: número del JSON detectado por OCR en {d}/{t} ({100*d/t:.0f}%)" if t else f"  {c}: sin datos")
    print(f"  Ambos candidatos detectados: {ambos}/{n} ({100*ambos/n:.0f}%)")
    print("Nota: los votos van manuscritos en casilleros → el OCR es ruidoso; "
          "esto mide cobertura de detección, no exactitud dígito a dígito.")

    if args.csv:
        with open(CSV_OUT, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows_csv[0].keys()))
            w.writeheader()
            w.writerows(rows_csv)
        print(f"CSV: {CSV_OUT}")


if __name__ == "__main__":
    main()
