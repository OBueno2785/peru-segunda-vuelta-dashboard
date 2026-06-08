"""
Backend FastAPI - Segunda Vuelta Presidencial Perú 2026
Sirve datos procesados de ONPE (resultadosegundavuelta.onpe.gob.pe).
Solo hay elección presidencial con dos candidatos (head-to-head).
"""
import asyncio
import json
import logging
import threading
import time
import unicodedata
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import refresher
from refresher import UBIGEO_NOMBRE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

DATA_DIR = Path(__file__).resolve().parent / "data"
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

_cache: Optional[dict] = None
REFRESH_INTERVAL = 5 * 60  # 5 minutos
_refresh_lock = asyncio.Lock()
_cache_lock = threading.Lock()
REFRESH_COOLDOWN = 30
_last_refresh_ts = 0.0


def _invalidate():
    global _cache
    _cache = None


async def _fetch_and_invalidate():
    async with _refresh_lock:
        ok = await refresher.fetch_fresh()
        if ok:
            _invalidate()
    return ok


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(refresher.loop(REFRESH_INTERVAL, _fetch_and_invalidate))
    yield
    task.cancel()


app = FastAPI(title="Segunda Vuelta Perú 2026 API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"],
)

# Colores fijos por agrupación (los dos finalistas de la segunda vuelta)
COLORES_PARTIDO = {
    "FUERZA POPULAR":     "#F97316",
    "JUNTOS POR EL PERU": "#E63946",
    "DEFAULT":            "#888888",
}


def norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.upper().strip()


_COLORES_NORM = {norm(k): v for k, v in COLORES_PARTIDO.items() if k != "DEFAULT"}
_COLORES_KEYS = sorted(_COLORES_NORM, key=len, reverse=True)


def color_for(partido: str) -> str:
    p = norm(partido)
    if p in _COLORES_NORM:
        return _COLORES_NORM[p]
    for k in _COLORES_KEYS:
        if k in p:
            return _COLORES_NORM[k]
    return COLORES_PARTIDO["DEFAULT"]


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logging.getLogger(__name__).warning("load_json fallo en %s: %s", path, e)
        return {}


def candidatos_ordenados(lista: list) -> list:
    """Candidatos ordenados por % de votos válidos (excluye nulos/blancos)."""
    EXCLUIR = {"VOTOS NULOS", "VOTOS EN BLANCO", "VOTOS IMPUGNADOS"}
    validos = [c for c in lista
               if c.get("nombreAgrupacionPolitica", "").upper() not in EXCLUIR]
    sorted_list = sorted(
        validos, key=lambda x: float(x.get("porcentajeVotosValidos", 0)), reverse=True
    )
    result = []
    for c in sorted_list:
        partido = c.get("nombreAgrupacionPolitica", "")
        result.append({
            "partido": partido,
            "candidato": c.get("nombreCandidato", ""),
            "votos": int(c.get("totalVotosValidos", 0)),
            "pct": float(c.get("porcentajeVotosValidos", 0)),
            "pctEmitidos": float(c.get("porcentajeVotosEmitidos", 0)),
            "color": color_for(partido),
        })
    return result


def build_cache() -> dict:
    presidencial_full = load_json(DATA_DIR / "presidencial_full.json")

    pres_url = next(
        (u for u in presidencial_full if "participantes" in u and "tipoFiltro=eleccion" in u),
        None,
    )
    pres_nacional = candidatos_ordenados(
        presidencial_full[pres_url].get("data", [])) if pres_url else []

    tot_url = next(
        (u for u in presidencial_full if "totales" in u and "tipoFiltro=eleccion" in u),
        None,
    )
    pres_totales = presidencial_full[tot_url].get("data", {}) if tot_url else {}

    # Mapa-calor por departamento (progreso de conteo)
    mapa_calor_data = {}
    nav_capture = load_json(DATA_DIR / "navigation_capture.json")
    for url, body in nav_capture.get("presidencial_navigation", {}).items():
        if "mapa-calor" in url:
            for item in body.get("data", []):
                ubigeo = item.get("ubigeoNivel01")
                if ubigeo:
                    mapa_calor_data[ubigeo] = item

    # Resultados por departamento
    pres_dep_raw = load_json(DATA_DIR / "presidencial_departamentos.json")
    mapa_pres_dep = {}
    for nombre, data in pres_dep_raw.items():
        cands = candidatos_ordenados(data.get("participantes", []))
        totales = data.get("totales", {})
        if not cands:
            continue
        total_actas_n = int(totales.get("totalActas", 0) or 0)
        total_votos = int(totales.get("totalVotosValidos", 0) or 0)
        pct_actas_raw = totales.get("actasContabilizadas")
        sin_datos = (pct_actas_raw is None or total_actas_n == 0 or total_votos == 0)
        margen = round(cands[0]["pct"] - cands[1]["pct"], 2) if len(cands) >= 2 else None
        mapa_pres_dep[norm(nombre)] = {
            "nombre": nombre,
            "lider": cands[0] if not sin_datos else None,
            "top": cands,
            "margen": margen,
            "actasContabilizadas": None if sin_datos else float(pct_actas_raw),
            "totalActas": total_actas_n,
            "contabilizadas": int(totales.get("contabilizadas", 0) or 0),
            "totalVotosValidos": total_votos,
        }

    # Combinar progreso de conteo (mapa-calor) con resultados por departamento
    mapa_pres = {}
    for ubigeo, item in mapa_calor_data.items():
        nombre = UBIGEO_NOMBRE.get(ubigeo, str(ubigeo))
        nombre_norm = norm(nombre)
        dep_data = mapa_pres_dep.get(nombre_norm, {})
        mapa_pres[nombre_norm] = {
            "nombre": nombre,
            "actasContabilizadas": dep_data.get("actasContabilizadas",
                                                float(item.get("porcentajeActasContabilizadas", 0))),
            "lider": dep_data.get("lider"),
            "top": dep_data.get("top") or pres_nacional,
            "margen": dep_data.get("margen"),
            "totalActas": dep_data.get("totalActas", int(item.get("totalActas", 0) or 0)),
            "contabilizadas": dep_data.get("contabilizadas", int(item.get("actasContabilizadas", 0) or 0)),
            "totalVotosValidos": dep_data.get("totalVotosValidos", 0),
        }
    # Departamentos sin entrada en mapa-calor pero con resultados
    for nombre_norm, dep_data in mapa_pres_dep.items():
        if nombre_norm not in mapa_pres:
            mapa_pres[nombre_norm] = {
                "nombre": dep_data["nombre"],
                "actasContabilizadas": dep_data["actasContabilizadas"],
                "lider": dep_data["lider"],
                "top": dep_data["top"],
                "margen": dep_data["margen"],
                "totalActas": dep_data["totalActas"],
                "contabilizadas": dep_data["contabilizadas"],
                "totalVotosValidos": dep_data["totalVotosValidos"],
            }

    return {
        "presidencial": {
            "nacional": {
                "top": pres_nacional,
                "totales": {
                    "actasContabilizadas": round(float(pres_totales.get("actasContabilizadas", 0)), 3),
                    "actasEnviadasJee":    round(float(pres_totales.get("actasEnviadasJee", 0)), 3),
                    "actasPendientes":     round(float(pres_totales.get("actasPendientesJee", 0)), 3),
                    "totalActas":          int(pres_totales.get("totalActas", 0)),
                    "contabilizadas":      int(pres_totales.get("contabilizadas", 0)),
                    "enviadasJee":         int(pres_totales.get("enviadasJee", 0)),
                    "totalVotosValidos":   int(pres_totales.get("totalVotosValidos", 0)),
                    "totalVotosEmitidos":  int(pres_totales.get("totalVotosEmitidos", 0)),
                    "participacionCiudadana": round(float(pres_totales.get("participacionCiudadana", 0)), 3),
                },
            },
            "mapa": mapa_pres,
            "nota": "Segunda vuelta presidencial. El mapa colorea cada departamento según el candidato líder.",
        },
    }


HISTORIAL_PATH = DATA_DIR / "historial.json"
_historial: list = []


def _load_historial():
    global _historial
    loaded = []
    if HISTORIAL_PATH.exists():
        try:
            loaded = json.loads(HISTORIAL_PATH.read_text(encoding="utf-8"))
        except Exception:
            loaded = []
    _historial = sorted(loaded, key=lambda x: x["ts"])


def _append_historial(data: dict):
    """Guarda un snapshot solo cuando ONPE publicó datos nuevos."""
    top = data["presidencial"]["nacional"]["top"]
    actas = data["presidencial"]["nacional"]["totales"].get("actasContabilizadas", 0)
    if not top:
        return

    candidatos = [
        {"partido": c["partido"], "candidato": c["candidato"],
         "pct": round(c["pct"], 3), "votos": c["votos"], "color": c["color"]}
        for c in top
    ]
    snapshot = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actas": round(actas, 2),
        "candidatos": candidatos,
    }

    if _historial:
        prev = _historial[-1]
        prev_pcts = {c["partido"]: c["pct"] for c in prev["candidatos"]}
        new_pcts = {c["partido"]: c["pct"] for c in candidatos}
        candidatos_cambiaron = any(
            abs(new_pcts.get(p, 0) - prev_pcts.get(p, 0)) >= 0.005 for p in new_pcts
        )
        umbral_actas = 0.1 if actas >= 90 else 0.3 if actas >= 75 else 0.5
        actas_avanzaron = abs(round(actas, 2) - prev["actas"]) >= umbral_actas
        if not candidatos_cambiaron and not actas_avanzaron:
            return

    _historial.append(snapshot)
    if len(_historial) > 500:
        _historial.pop(0)
    HISTORIAL_PATH.write_text(json.dumps(_historial, ensure_ascii=False), encoding="utf-8")
    logging.getLogger("historial").info(
        "Snapshot #%d guardado: actas=%.2f%% ts=%s", len(_historial), actas, snapshot["ts"]
    )


def get_data() -> dict:
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                data = build_cache()
                _append_historial(data)
                _cache = data
    return _cache


_load_historial()


# ── Endpoints ──────────────────────────────────────────

@app.get("/api/status")
def status():
    data = get_data()
    return {
        "ok": True,
        "presidencial_mapa": len(data["presidencial"]["mapa"]),
        "pres_candidatos": len(data["presidencial"]["nacional"]["top"]),
        "historial_puntos": len(_historial),
    }


@app.get("/api/presidencial")
def presidencial():
    return get_data()["presidencial"]


@app.get("/api/mapa/presidencial")
def mapa():
    return {"mapa": get_data()["presidencial"]["mapa"]}


@app.get("/api/historial")
def historial():
    return {"snapshots": _historial}


@app.post("/api/refresh")
async def refresh():
    """Descarga datos frescos de ONPE y reconstruye el cache (atómico, con cooldown)."""
    global _last_refresh_ts
    now = time.monotonic()
    en_cooldown = (now - _last_refresh_ts) < REFRESH_COOLDOWN
    if not en_cooldown:
        _last_refresh_ts = now
        await _fetch_and_invalidate()
        _load_historial()
    data = get_data()
    return {"ok": True, "cooldown": en_cooldown, "status": {
        "presidencial_mapa": len(data["presidencial"]["mapa"]),
        "historial_puntos": len(_historial),
    }}


# ── Frontend estático (build de React) ─────────────────
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")
    _STATIC_EXTS = {".geojson", ".svg", ".ico", ".png", ".webp", ".txt", ".json"}

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        candidate = FRONTEND_DIST / full_path
        if candidate.exists() and candidate.is_file() and candidate.suffix in _STATIC_EXTS:
            return FileResponse(candidate)
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        return {"error": "Frontend no compilado. Ejecuta: cd frontend && npm run build"}
