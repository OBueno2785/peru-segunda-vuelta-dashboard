"""
Refresca los datos de la SEGUNDA VUELTA presidencial ONPE 2026 cada N minutos.
Solo hay elección presidencial (idEleccion=10) con dos candidatos.
Escribe los JSON en data/ de forma atómica y señala al cache para reconstruirse.
"""
import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
import httpx

DATA_DIR = Path(__file__).parent / "data"
BASE     = "https://resultadosegundavuelta.onpe.gob.pe/presentacion-backend"
SPA      = "https://resultadosegundavuelta.onpe.gob.pe/"
RESUMEN  = "https://resultadosegundavuelta.onpe.gob.pe/main/resumen"

ID_ELECCION = 10  # presidencial segunda vuelta

log = logging.getLogger("refresher")

BROWSER_HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-PE,es;q=0.9",
    "Connection": "keep-alive",
}
API_HDR = {
    "Accept": "application/json, text/plain, */*",
    "Referer": RESUMEN,
    "Origin": "https://resultadosegundavuelta.onpe.gob.pe",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
}

# ubigeo nivel 01 -> nombre departamento. Compartido con main.py (build_cache).
UBIGEO_NOMBRE = {
    10000: "AMAZONAS",    20000: "ANCASH",       30000: "APURIMAC",
    40000: "AREQUIPA",    50000: "AYACUCHO",     60000: "CAJAMARCA",
    70000: "CUSCO",       80000: "HUANCAVELICA", 90000: "HUANUCO",
    100000: "ICA",        110000: "JUNIN",       120000: "LA LIBERTAD",
    130000: "LAMBAYEQUE", 140000: "LIMA",        150000: "LORETO",
    160000: "MADRE DE DIOS", 170000: "MOQUEGUA", 180000: "PASCO",
    190000: "PIURA",      200000: "PUNO",        210000: "SAN MARTIN",
    220000: "TACNA",      230000: "TUMBES",      240000: "UCAYALI",
    250000: "CALLAO",
}


def write_json(path: Path, obj) -> None:
    """Escribe JSON de forma atómica: archivo temporal + os.replace."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


async def _get(client: httpx.AsyncClient, url: str) -> dict:
    try:
        r = await client.get(url, headers=API_HDR, timeout=15.0)
        if "json" not in r.headers.get("content-type", ""):
            return {}
        return r.json()
    except Exception as e:
        log.warning("GET error %s: %s", url[-80:], e)
        return {}


async def fetch_fresh() -> bool:
    """
    Descarga datos frescos de ONPE y actualiza los JSON en data/.
    Devuelve True si al menos los datos presidenciales nacionales se actualizaron.
    """
    log.info("Iniciando refresco de datos ONPE (segunda vuelta)...")
    ok = False

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Iniciar sesión visitando la SPA y la página de resumen
        try:
            await client.get(SPA, headers=BROWSER_HDR, timeout=15.0)
            await client.get(RESUMEN, headers=BROWSER_HDR, timeout=15.0)
        except Exception:
            pass

        # ── 1. Presidencial nacional: participantes + totales + mapa-calor ──
        part_url = f"{BASE}/resumen-general/participantes?idEleccion={ID_ELECCION}&tipoFiltro=eleccion"
        tot_url  = f"{BASE}/resumen-general/totales?idEleccion={ID_ELECCION}&tipoFiltro=eleccion"
        mc_url   = (f"{BASE}/resumen-general/mapa-calor"
                    f"?idAmbitoGeografico=1&idEleccion={ID_ELECCION}&tipoFiltro=ambito_geografico")
        pres_part, pres_tot, mapa_calor = await asyncio.gather(
            _get(client, part_url), _get(client, tot_url), _get(client, mc_url),
        )

        if pres_part.get("success"):
            existing = _read_json(DATA_DIR / "presidencial_full.json")
            existing[part_url] = pres_part
            if pres_tot.get("success"):
                existing[tot_url] = pres_tot
            write_json(DATA_DIR / "presidencial_full.json", existing)
            log.info("Presidencial: %d candidatos", len(pres_part.get("data", [])))
            ok = True

        if mapa_calor.get("success"):
            nc = _read_json(DATA_DIR / "navigation_capture.json")
            nc.setdefault("presidencial_navigation", {})[mc_url] = mapa_calor
            write_json(DATA_DIR / "navigation_capture.json", nc)
            log.info("Mapa-calor: %d departamentos", len(mapa_calor.get("data", [])))

        # ── 2. Presidencial por departamento (en paralelo) ─────────────────
        async def fetch_pres_dep(ubigeo: int, nombre: str):
            base_q = (f"?idAmbitoGeografico=1&idEleccion={ID_ELECCION}&tipoFiltro=ubigeo_nivel_01"
                      f"&idUbigeoDepartamento={ubigeo}")
            pp, pt = await asyncio.gather(
                _get(client, f"{BASE}/resumen-general/participantes{base_q}"),
                _get(client, f"{BASE}/resumen-general/totales{base_q}"),
            )
            if pp.get("success") and pp.get("data"):
                return nombre, {"participantes": pp["data"], "totales": pt.get("data", {})}
            return nombre, None

        pres_results = await asyncio.gather(
            *[fetch_pres_dep(u, n) for u, n in UBIGEO_NOMBRE.items()]
        )
        pres_dep = {n: d for n, d in pres_results if d}
        if pres_dep:
            write_json(DATA_DIR / "presidencial_departamentos.json", pres_dep)
            log.info("Presidencial por departamento: %d departamentos", len(pres_dep))

    log.info("Refresco completado: %s", datetime.now().strftime("%H:%M:%S"))
    return ok


async def loop(interval_seconds: int, refresh_fn):
    """Llama refresh_fn() cada interval_seconds (sync o async)."""
    import inspect
    first = True
    while True:
        if not first:
            await asyncio.sleep(interval_seconds)
        first = False
        try:
            result = refresh_fn()
            ok = await result if inspect.isawaitable(result) else result
            log.info("Refresco completado (ok=%s): %s", ok, datetime.now().strftime("%H:%M:%S"))
        except Exception as e:
            log.error("Error en refresco: %s", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    asyncio.run(fetch_fresh())
