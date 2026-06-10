"""
Verificación por OCR de las actas E/P descargadas.

OCR NO es la fuente de votos (los conteos del acta son manuscritos y el OCR es falible);
se usa solo para COTEJAR los números esperados del JSON (detalle[].nvotos) contra lo que
aparece en el "ACTA DE ESCRUTINIO" escaneada, y marcar discrepancias.

Uso:
  python ocr_actas.py --sample 5      # vuelca 5 PNG renderizados a data/ocr_muestra/ (calibrar recorte)
  python ocr_actas.py --limit 50      # verifica 50 actas y escribe data/ocr_verificacion.json
  python ocr_actas.py                 # verifica todas las actas con PDF
"""
import argparse
import glob
import io
import json
import unicodedata
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
ACTAS_DIR = DATA_DIR / "actas"
PDF_DIR = DATA_DIR / "actas_pdf"
MUESTRA_DIR = DATA_DIR / "ocr_muestra"
OUT = DATA_DIR / "ocr_verificacion.json"

ZOOM = 2.2  # render del PDF (~180 DPI)
# Recorte (fracciones x0,y0,x1,y1): columna "TOTAL DE VOTOS" en las filas de los dos
# candidatos del acta de escrutinio presidencial de 2ª vuelta. Calibrado con --sample.
CROP = (0.78, 0.28, 0.995, 0.50)

EXCLUIR = {"VOTOS NULOS", "VOTOS EN BLANCO", "VOTOS IMPUGNADOS"}
_reader = None


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").upper().strip()


def render_pdf_png(pdf_path: Path, zoom: float = ZOOM) -> "Image.Image":
    import fitz
    from PIL import Image
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    doc.close()
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def crop_img(img, box):
    if not box:
        return img
    w, h = img.size
    x0, y0, x1, y1 = box
    return img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))


def get_reader():
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["es"], gpu=False, verbose=False)
    return _reader


def ocr_numeros(img) -> list[int]:
    import numpy as np
    reader = get_reader()
    res = reader.readtext(np.array(img), allowlist="0123456789", detail=0, paragraph=False)
    nums = []
    for t in res:
        t = t.strip()
        if t.isdigit():
            nums.append(int(t))
    return nums


def acta_json_for_pdf(pdf_path: Path) -> dict | None:
    acta_id = pdf_path.stem.replace("acta_", "")
    for fp in glob.glob(str(ACTAS_DIR / "**" / f"acta_{acta_id}.json"), recursive=True):
        try:
            return json.loads(Path(fp).read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def esperados(acta: dict) -> dict:
    out = {}
    for d in acta.get("detalle", []) or []:
        if norm(d.get("descripcion", "")) in EXCLUIR:
            continue
        out[d.get("descripcion", "")] = int(d.get("nvotos") or 0)
    return out


def verificar(pdf_path: Path) -> dict:
    acta = acta_json_for_pdf(pdf_path)
    esp = esperados(acta) if acta else {}
    img = crop_img(render_pdf_png(pdf_path), CROP)
    ocr = ocr_numeros(img)
    # El OCR de dígitos manuscritos en casilleros es ruidoso: se considera "encontrado"
    # si el total esperado aparece como token exacto o como subcadena de los tokens OCR.
    blob = " ".join(str(n) for n in ocr)
    ocr_set = set(ocr)

    def hallado(v: int) -> bool:
        return v in ocr_set or str(v) in blob

    faltan = [f"{k}={v}" for k, v in esp.items() if not hallado(v)]
    return {
        "acta_id": pdf_path.stem.replace("acta_", ""),
        "mesa": (acta or {}).get("codigoMesa"),
        "estado": (acta or {}).get("codigoEstadoActa"),
        "esperado": esp,
        "ocr_numeros": ocr,
        "match": len(faltan) == 0 and bool(esp),
        "no_encontrados": faltan,
    }


def main():
    ap = argparse.ArgumentParser(description="OCR de verificación de actas E/P.")
    ap.add_argument("--sample", type=int, help="Volcar N PNG renderizados para calibrar el recorte")
    ap.add_argument("--limit", type=int, help="Verificar solo N actas")
    args = ap.parse_args()

    pdfs = sorted(Path(p) for p in glob.glob(str(PDF_DIR / "*.pdf")))
    if not pdfs:
        print("No hay PDFs en", PDF_DIR)
        return

    if args.sample:
        MUESTRA_DIR.mkdir(parents=True, exist_ok=True)
        for p in pdfs[: args.sample]:
            img = render_pdf_png(p)
            img.save(MUESTRA_DIR / f"{p.stem}.png")
            cr = crop_img(img, CROP)
            if CROP:
                cr.save(MUESTRA_DIR / f"{p.stem}_crop.png")
        print(f"Volcadas {min(args.sample, len(pdfs))} muestras en {MUESTRA_DIR}")
        return

    if args.limit:
        pdfs = pdfs[: args.limit]

    resultados, ok = [], 0
    for i, p in enumerate(pdfs, 1):
        try:
            r = verificar(p)
        except Exception as e:
            r = {"acta_id": p.stem, "error": str(e)}
        resultados.append(r)
        ok += 1 if r.get("match") else 0
        if i % 25 == 0:
            print(f"  {i}/{len(pdfs)} verificadas | match={ok}")

    resumen = {
        "total": len(resultados),
        "match": ok,
        "discrepancias": sum(1 for r in resultados if not r.get("match") and "error" not in r),
        "errores": sum(1 for r in resultados if "error" in r),
        "detalle": resultados,
    }
    OUT.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OCR verificación: {ok}/{len(resultados)} coinciden. Escrito {OUT}")


if __name__ == "__main__":
    main()
