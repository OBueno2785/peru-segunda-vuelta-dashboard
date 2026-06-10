"""
Descarga las actas NO contabilizadas de la segunda vuelta presidencial ONPE 2026
(estados "Para envío al JEE" = E y "Pendiente" = P), para proyectar el resultado.

Por cada acta objetivo guarda:
  - data/actas/<DEP>/<PROV>/<DIST>/acta_{id}.json   (detalle con nvotos + archivos + lineaTiempo)
  - data/actas_pdf/acta_{id}.pdf                     (ACTA DE ESCRUTINIO, para OCR de verificación)

El listado /actas trae el detalle VACÍO para las actas E/P; los votos digitados solo aparecen
en /actas/{id}. Por eso se pide el detalle individual de cada acta objetivo.

Reanudable: el avance por distrito se guarda en data/actas_progress.json.

Endpoints (idénticos a primera vuelta, dominio de segunda vuelta):
  /ubigeos/departamentos?idEleccion=10&idAmbitoGeografico=1
  /ubigeos/provincias?...&idUbigeoDepartamento=XXXXXX
  /ubigeos/distritos?...&idUbigeoProvincia=XXXXXX
  /actas?pagina=N&tamanio=100&idAmbitoGeografico=1&idUbigeo=DISTRITO_INT
  /actas/{id}              -> data.detalle[].nvotos, data.archivos[]
  /actas/file?id={fileId}  -> data = URL S3 firmada del PDF
"""
import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

import httpx

BASE = "https://resultadosegundavuelta.onpe.gob.pe/presentacion-backend"
SPA = "https://resultadosegundavuelta.onpe.gob.pe/"
ACTAS_PAGE = "https://resultadosegundavuelta.onpe.gob.pe/main/actas"

ID_ELECCION = 10  # presidencial segunda vuelta
AMBITO = 1        # Perú
PAGE_SIZE = 100
TARGET_ESTADOS = {"E", "P"}  # Para envío al JEE, Pendiente
# Pacing configurable (en CI conviene bajarlo: ONPE bloquea ráfagas desde una sola IP).
MAX_WORKERS = int(os.getenv("ACTAS_WORKERS", "6"))
DELAY = float(os.getenv("ACTAS_DELAY", "0.15"))  # espera entre distritos

DATA_DIR = Path(__file__).parent / "data"
ACTAS_DIR = DATA_DIR / "actas"
PDF_DIR = DATA_DIR / "actas_pdf"
PROGRESS_FILE = DATA_DIR / "actas_progress.json"

BROWSER_HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-PE,es;q=0.9",
}
API_HDR = {
    "Accept": "application/json, text/plain, */*",
    "Referer": ACTAS_PAGE,
    "Origin": "https://resultadosegundavuelta.onpe.gob.pe",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent / "scraper_actas.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("scraper_actas")


def slug(s: str) -> str:
    return (s or "").replace("/", "_").replace("\\", "_").strip()


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"completed_districts": [], "stats": {"json": 0, "pdf": 0, "errors": 0, "sin_pdf": 0}}


def save_progress(progress: dict) -> None:
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


async def api_get(client: httpx.AsyncClient, path: str, retries: int = 5) -> dict | None:
    """GET con recuperación de rate-limit: si ONPE responde el HTML del SPA (sesión perdida),
    re-prima la sesión y reintenta con backoff exponencial."""
    url = BASE + path
    for attempt in range(retries):
        try:
            r = await client.get(url, headers=API_HDR, timeout=25.0)
            if "json" in r.headers.get("content-type", ""):
                return r.json()
            log.warning("No-JSON (%s) en %s; re-primando sesión (intento %d/%d)",
                        r.status_code, path[-60:], attempt + 1, retries)
        except Exception as e:
            log.warning("api_get %s: %s (intento %d/%d)", path[-60:], e, attempt + 1, retries)
        if attempt < retries - 1:
            await asyncio.sleep(min(8.0, 0.8 * (2 ** attempt)))
            await prime_session(client)
    return None


async def prime_session(client: httpx.AsyncClient) -> None:
    for u in (SPA, ACTAS_PAGE):
        try:
            await client.get(u, headers=BROWSER_HDR, timeout=20.0)
        except Exception:
            pass


async def download_pdf(client: httpx.AsyncClient, file_id: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    url_r = await api_get(client, f"/actas/file?id={file_id}")
    s3 = (url_r or {}).get("data")
    if not s3:
        return False
    try:
        r = await client.get(s3, timeout=40.0)
        if r.status_code != 200 or not r.content:
            log.warning("S3 %s para %s", r.status_code, file_id)
            return False
        dest.write_bytes(r.content)
        return True
    except Exception as e:
        log.error("download_pdf %s: %s", file_id, e)
        return False


async def process_acta(client, acta_min: dict, dist_dir: Path, progress: dict, want_pdf: bool) -> None:
    acta_id = acta_min["id"]
    json_path = dist_dir / f"acta_{acta_id}.json"

    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            data = None
    else:
        det = await api_get(client, f"/actas/{acta_id}")
        data = (det or {}).get("data")
        if not data:
            progress["stats"]["errors"] += 1
            return
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        progress["stats"]["json"] += 1

    if not want_pdf or not data:
        return

    pdf_path = PDF_DIR / f"acta_{acta_id}.pdf"
    if pdf_path.exists() and pdf_path.stat().st_size > 0:
        return
    file_id = next((a.get("id") for a in data.get("archivos", []) or [] if a.get("tipo") == 1), None)
    if not file_id:
        progress["stats"]["sin_pdf"] += 1
        return
    if await download_pdf(client, file_id, pdf_path):
        progress["stats"]["pdf"] += 1
    else:
        progress["stats"]["errors"] += 1


async def list_district_actas(client, dist_ubigeo_int: int) -> tuple[list[dict], dict, bool]:
    """Devuelve (actas, counts, ok). ok=False = no se pudo listar (bloqueo/HTML),
    distinto de un distrito legítimamente vacío (ok=True, actas=[])."""
    r0 = await api_get(client, f"/actas?pagina=0&tamanio={PAGE_SIZE}&idAmbitoGeografico={AMBITO}&idUbigeo={dist_ubigeo_int}")
    if r0 is None:
        return [], {}, False
    data0 = r0.get("data")
    if not data0:
        return [], {}, True
    counts = {
        "totalRegistros": data0.get("totalRegistros", 0),
        "contabilizada": data0.get("contabilizada", 0),
        "observada": data0.get("observada", 0),
        "pendiente": data0.get("pendiente", 0),
    }
    actas = list(data0.get("content", []))
    total_pages = data0.get("totalPaginas", 0)
    for page in range(1, total_pages):
        rp = await api_get(client, f"/actas?pagina={page}&tamanio={PAGE_SIZE}&idAmbitoGeografico={AMBITO}&idUbigeo={dist_ubigeo_int}")
        actas.extend(((rp or {}).get("data") or {}).get("content", []))
        await asyncio.sleep(0.1)
    return actas, counts, True


async def process_district(client, dept, prov, dist, progress, want_pdf) -> None:
    dist_key = f"{dept['nombre']}/{prov['nombre']}/{dist['nombre']}_{dist['ubigeo']}"
    if dist_key in progress["completed_districts"]:
        return

    actas, counts, ok = await list_district_actas(client, int(dist["ubigeo"]))
    if not ok:
        # Listado bloqueado tras reintentos: NO marcar el distrito como hecho.
        progress["stats"]["list_fail"] = progress["stats"].get("list_fail", 0) + 1
        log.error("Distrito sin listar (bloqueo): %s", dist_key)
        return
    objetivo = [a for a in actas if a.get("codigoEstadoActa") in TARGET_ESTADOS]

    if objetivo:
        dist_dir = ACTAS_DIR / slug(dept["nombre"]) / slug(prov["nombre"]) / slug(dist["nombre"])
        dist_dir.mkdir(parents=True, exist_ok=True)
        (dist_dir / "_summary.json").write_text(json.dumps({
            "ubigeo": dist["ubigeo"], "nombre": dist["nombre"],
            "departamento": dept["nombre"], "provincia": prov["nombre"],
            "counts": counts, "objetivo_EP": len(objetivo),
            "timestamp": int(time.time()),
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        sem = asyncio.Semaphore(MAX_WORKERS)

        async def one(a):
            async with sem:
                try:
                    await process_acta(client, a, dist_dir, progress, want_pdf)
                except Exception as e:
                    progress["stats"]["errors"] += 1
                    log.error("acta %s: %s", a.get("id"), e)

        await asyncio.gather(*(one(a) for a in objetivo))
        log.info("%s > %s > %s: %d actas E/P descargadas | stats=%s",
                 dept["nombre"], prov["nombre"], dist["nombre"], len(objetivo), progress["stats"])

    progress["completed_districts"].append(dist_key)
    save_progress(progress)


async def run(only_dept: str | None, want_pdf: bool) -> None:
    ACTAS_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    progress = load_progress()
    log.info("Inicio. Distritos hechos=%d stats=%s", len(progress["completed_districts"]), progress["stats"])

    async with httpx.AsyncClient(follow_redirects=True) as client:
        await prime_session(client)

        deps = await api_get(client, f"/ubigeos/departamentos?idEleccion={ID_ELECCION}&idAmbitoGeografico={AMBITO}")
        if not deps or not deps.get("data"):
            log.error("No se pudieron listar departamentos. Sesión bloqueada?")
            return 1
        depts = deps["data"]
        if only_dept:
            up = only_dept.upper()
            depts = [d for d in depts if d["nombre"].upper() == up]
            if not depts:
                log.error("Departamento '%s' no encontrado", only_dept)
                return 1

        for dept in depts:
            provs = await api_get(client, f"/ubigeos/provincias?idEleccion={ID_ELECCION}&idAmbitoGeografico={AMBITO}&idUbigeoDepartamento={dept['ubigeo']}")
            if provs is None:
                progress["stats"]["list_fail"] = progress["stats"].get("list_fail", 0) + 1
                log.error("Provincias sin listar (bloqueo) en %s", dept["nombre"])
                continue
            for prov in provs.get("data", []):
                dists = await api_get(client, f"/ubigeos/distritos?idEleccion={ID_ELECCION}&idAmbitoGeografico={AMBITO}&idUbigeoProvincia={prov['ubigeo']}")
                if dists is None:
                    progress["stats"]["list_fail"] = progress["stats"].get("list_fail", 0) + 1
                    log.error("Distritos sin listar (bloqueo) en %s/%s", dept["nombre"], prov["nombre"])
                    continue
                for dist in dists.get("data", []):
                    await process_district(client, dept, prov, dist, progress, want_pdf)
                    await asyncio.sleep(DELAY)
            log.info(">>> Departamento %s completo. stats=%s", dept["nombre"], progress["stats"])

    save_progress(progress)
    fallos = progress["stats"].get("list_fail", 0)
    log.info("FIN. stats=%s distritos=%d", progress["stats"], len(progress["completed_districts"]))
    if fallos:
        log.error("ABORTADO: %d listados bloqueados → datos incompletos, no usar para proyectar.", fallos)
        return 1
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Descarga actas E/P de la segunda vuelta ONPE.")
    ap.add_argument("--dep", help="Limitar a un departamento (p.ej. AMAZONAS) para pruebas")
    ap.add_argument("--no-pdf", action="store_true", help="No descargar PDFs (solo JSON con votos)")
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args.dep, want_pdf=not args.no_pdf)) or 0)


if __name__ == "__main__":
    main()
