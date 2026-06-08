"""
Genera los JSON estáticos que consume el frontend en GitHub Pages.
Scrapea ONPE (refresher.fetch_fresh) y reutiliza build_cache/_append_historial
de main.py para producir:
  frontend/public/data/presidencial.json
  frontend/public/data/historial.json
El histórico se acumula leyendo backend/data/historial.json (persistido en el repo).
"""
import asyncio
import json
from pathlib import Path

import refresher
import main as backend

OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "data"


async def run() -> None:
    ok = await refresher.fetch_fresh()
    print("fetch_fresh ok =", ok)

    backend._invalidate()
    backend._load_historial()
    data = backend.get_data()  # build_cache + _append_historial (actualiza historial.json)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "presidencial.json").write_text(
        json.dumps(data["presidencial"], ensure_ascii=False), encoding="utf-8")
    (OUT / "historial.json").write_text(
        json.dumps({"snapshots": backend._historial}, ensure_ascii=False), encoding="utf-8")

    top = data["presidencial"]["nacional"]["top"]
    print(f"JSON estáticos escritos en {OUT}")
    print(f"  candidatos={len(top)} historial={len(backend._historial)} puntos")
    for c in top:
        print(f"  {c['partido']}: {c['pct']}%")


if __name__ == "__main__":
    asyncio.run(run())
