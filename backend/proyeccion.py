"""
Proyección del resultado de la segunda vuelta sumando las actas NO contabilizadas
(Para envío al JEE + Pendientes) al conteo oficial de ONPE.

  proyectado(candidato) = votos_contabilizados(candidato) + Σ votos_actas_EP(candidato)

Fuente de votos de las actas E/P: los JSON descargados por scraper_actas.py
(data/actas/**/acta_*.json, campo detalle[].nvotos). Las actas E/P sin votos digitados
(detalle vacío) se reportan como "sin datos" → banda de incertidumbre.

Escribe data/proyeccion.json e imprime un resumen.
"""
import json
import glob
import unicodedata
from pathlib import Path

import main as backend

DATA_DIR = Path(__file__).parent / "data"
ACTAS_DIR = DATA_DIR / "actas"
OUT = DATA_DIR / "proyeccion.json"

# Los dos finalistas; el resto (blanco/nulo/impugnado) no son votos válidos.
EXCLUIR = {"VOTOS NULOS", "VOTOS EN BLANCO", "VOTOS IMPUGNADOS"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").upper().strip()


def votos_validos_acta(detalle: list) -> dict:
    """{partido_norm: nvotos} solo de candidatos (excluye nulos/blancos/impugnados)."""
    out = {}
    for d in detalle or []:
        desc = d.get("descripcion", "")
        if norm(desc) in EXCLUIR:
            continue
        out[norm(desc)] = out.get(norm(desc), 0) + int(d.get("nvotos") or 0)
    return out


def cargar_contabilizado() -> dict:
    """Votos válidos contabilizados por partido + totales, desde build_cache()."""
    backend._invalidate()
    data = backend.build_cache()
    nac = data["presidencial"]["nacional"]
    top = nac["top"]
    totales = nac["totales"]
    return {
        "por_partido": {norm(c["partido"]): c["votos"] for c in top},
        "nombres": {norm(c["partido"]): c["partido"] for c in top},
        "candidatos": {norm(c["partido"]): c["candidato"] for c in top},
        "totales": totales,
    }


def agregar_actas_ep() -> dict:
    """Recorre los JSON de actas E/P descargados y agrega votos + cobertura."""
    agg = {}
    por_estado = {}
    leidas = sin_votos = 0
    archivos = glob.glob(str(ACTAS_DIR / "**" / "acta_*.json"), recursive=True)
    for fp in archivos:
        try:
            d = json.loads(Path(fp).read_text(encoding="utf-8"))
        except Exception:
            continue
        est = d.get("codigoEstadoActa", "?")
        por_estado[est] = por_estado.get(est, 0) + 1
        vv = votos_validos_acta(d.get("detalle", []))
        if sum(vv.values()) == 0:
            sin_votos += 1
            continue
        leidas += 1
        for k, v in vv.items():
            agg[k] = agg.get(k, 0) + v
    return {
        "por_partido": agg,
        "actas_total": len(archivos),
        "actas_con_votos": leidas,
        "actas_sin_votos": sin_votos,
        "por_estado": por_estado,
    }


def pct(d: dict) -> dict:
    t = sum(d.values())
    return {k: round(100 * v / t, 3) for k, v in d.items()} if t else {}


def main_run() -> dict:
    cont = cargar_contabilizado()
    ep = agregar_actas_ep()

    partidos = set(cont["por_partido"]) | set(ep["por_partido"])
    proyectado = {p: cont["por_partido"].get(p, 0) + ep["por_partido"].get(p, 0) for p in partidos}

    # Banda de incertidumbre: votos válidos aún sin leer (actas E/P sin votos digitados).
    # Promedio de votos válidos por acta leída, × actas sin datos → margen que podría ir
    # íntegro a un candidato u otro.
    validos_leidos = sum(ep["por_partido"].values())
    prom_validos = (validos_leidos / ep["actas_con_votos"]) if ep["actas_con_votos"] else 0
    votos_faltantes = round(prom_validos * ep["actas_sin_votos"])

    nombres = cont["nombres"]
    candidatos = cont["candidatos"]

    def fila(p):
        return {
            "partido": nombres.get(p, p),
            "candidato": candidatos.get(p, ""),
            "contabilizado": cont["por_partido"].get(p, 0),
            "actas_EP": ep["por_partido"].get(p, 0),
            "proyectado": proyectado.get(p, 0),
        }

    orden = sorted(partidos, key=lambda p: proyectado[p], reverse=True)
    filas = [fila(p) for p in orden]
    pct_cont = pct(cont["por_partido"])
    pct_proy = pct(proyectado)
    for f in filas:
        pp = norm(f["partido"])
        f["pct_contabilizado"] = pct_cont.get(pp, 0)
        f["pct_proyectado"] = pct_proy.get(pp, 0)

    # Banda min/max para el líder: repartir los votos faltantes al rival / a sí mismo.
    banda = None
    if len(orden) == 2 and votos_faltantes:
        lider, rival = orden[0], orden[1]
        base_l, base_r = proyectado[lider], proyectado[rival]
        tot = base_l + base_r + votos_faltantes
        banda = {
            "lider": nombres.get(lider, lider),
            "pct_min_lider": round(100 * base_l / tot, 3),                 # faltantes al rival
            "pct_max_lider": round(100 * (base_l + votos_faltantes) / tot, 3),  # faltantes al líder
            "votos_faltantes_estimados": votos_faltantes,
        }

    resultado = {
        "generado": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "contabilizado_totales": cont["totales"],
        "actas_EP": {
            "total_descargadas": ep["actas_total"],
            "con_votos": ep["actas_con_votos"],
            "sin_votos_digitados": ep["actas_sin_votos"],
            "por_estado": ep["por_estado"],
        },
        "resultado": filas,
        "banda_incertidumbre": banda,
    }
    OUT.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultado


def imprimir(r: dict) -> None:
    t = r["contabilizado_totales"]
    a = r["actas_EP"]
    print("=" * 64)
    print("PROYECCIÓN SEGUNDA VUELTA — contabilizado + actas E/P")
    print("=" * 64)
    print(f"Actas contabilizadas oficial: {t.get('actasContabilizadas')}%  "
          f"({t.get('contabilizadas')}/{t.get('totalActas')})")
    print(f"Actas E/P descargadas: {a['total_descargadas']}  "
          f"con votos: {a['con_votos']}  sin digitar: {a['sin_votos_digitados']}  "
          f"por estado: {a['por_estado']}")
    print("-" * 64)
    print(f"{'Candidato':<26}{'Contab.%':>10}{'Proyect.%':>11}{'+Votos E/P':>12}")
    for f in r["resultado"]:
        print(f"{f['candidato'][:25]:<26}{f['pct_contabilizado']:>10}{f['pct_proyectado']:>11}{f['actas_EP']:>12}")
    if r["banda_incertidumbre"]:
        b = r["banda_incertidumbre"]
        print("-" * 64)
        print(f"Banda líder ({b['lider']}): {b['pct_min_lider']}% – {b['pct_max_lider']}%  "
              f"(±{b['votos_faltantes_estimados']} votos sin digitar)")
    print("=" * 64)
    print(f"Escrito: {OUT}")


if __name__ == "__main__":
    imprimir(main_run())
