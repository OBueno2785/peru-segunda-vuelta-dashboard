# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Dashboard de la **segunda vuelta presidencial Perú 2026** con datos oficiales de ONPE.
Caso head-to-head: dos candidatos, solo elección presidencial. Réplica simplificada del
proyecto de primera vuelta `peru-elecciones-2026`.

## Comandos

### Backend (`backend/`)
```bash
py -3 -m venv venv
venv/Scripts/python.exe -m pip install -r requirements.txt
venv/Scripts/python.exe -m uvicorn main:app --port 8030   # API + scraper en vivo
venv/Scripts/python.exe build_static.py                   # regenera JSON estáticos a mano
venv/Scripts/python.exe refresher.py                      # un solo scrape de ONPE (debug)
```

### Frontend (`frontend/`)
```bash
npm install
npm run dev      # dev en :5173, proxy /api -> :8030
npm run build    # -> dist/ (lo sirve el backend o GitHub Pages)
npm run lint     # eslint
```

No hay suite de tests.

## Arquitectura

Hay **dos modos de ejecución** del mismo frontend, controlados por `import.meta.env.PROD`
en `frontend/src/api.js`:

- **Dev**: el frontend hace fetch a `/api/*` (proxy a FastAPI en :8030), que scrapea ONPE en vivo.
- **Prod (GitHub Pages)**: no hay backend. El frontend lee JSON estáticos
  (`frontend/public/data/presidencial.json`, `historial.json`) generados por `build_static.py`.
  El botón "Actualizar" solo relee el JSON (ver `CAN_REFRESH`).

### Pipeline de datos (backend)
1. `refresher.fetch_fresh()` — scrapea la API de ONPE
   (`resultadosegundavuelta.onpe.gob.pe/presentacion-backend`, `idEleccion=10`).
   **Debe visitar primero la SPA y `/main/resumen`** con headers de navegador para obtener
   la cookie de sesión, si no la API rechaza. Escribe JSON crudos en `data/` de forma atómica
   (tmp + `os.replace`): `presidencial_full.json` (nacional), `presidencial_departamentos.json`
   (25 departamentos en paralelo), `navigation_capture.json` (mapa-calor / progreso de conteo).
2. `main.build_cache()` — lee esos JSON crudos y arma la respuesta de la API: ordena candidatos
   por % de votos válidos (excluye nulos/blancos), combina resultados por departamento con el
   progreso del mapa-calor, calcula el `lider` y `margen` de cada departamento. Cache en memoria
   invalidado en cada refresco (`_invalidate`).
3. `main._append_historial()` — guarda un snapshot en `data/historial.json` **solo si** los %
   cambiaron ≥0.005 o las actas avanzaron (umbral variable según % escrutado). Es la serie del
   gráfico de evolución. **`historial.json` se versiona en git** (lo acumula el workflow).

`build_static.py` reutiliza `refresher.fetch_fresh` + `main.build_cache`/`_append_historial`
para volcar la respuesta de la API a los JSON estáticos del frontend. No dupliques la lógica
de scraping/transformación aquí: importa de `main` y `refresher`.

### Despliegue
`.github/workflows/deploy.yml` corre cada 30 min (cron) + en push a `main`: scrapea ONPE,
regenera los JSON, **commitea `historial.json` y `frontend/public/data/` al repo** (`[skip ci]`)
para acumular el histórico, builda el frontend y despliega a Pages.
URL: https://obueno2785.github.io/peru-segunda-vuelta-dashboard/

### Convenciones clave
- Los departamentos se identifican por `norm(nombre)` (uppercase sin tildes). El frontend cruza
  esa clave con las propiedades del `peru-departamentos.geojson`.
- `UBIGEO_NOMBRE` en `refresher.py` mapea ubigeo nivel 01 → nombre de departamento; lo importa
  `main.py` para combinar el mapa-calor con los resultados.
- Colores fijos por partido en `COLORES_PARTIDO` (`main.py`): Fuerza Popular naranja,
  Juntos por el Perú rojo.
- `base` de Vite es `/peru-segunda-vuelta-dashboard/` solo en build (Pages); `/` en dev.

### No confundir con proyectos hermanos
- `peru-elecciones-2026` — primera vuelta (proyecto original del que esto deriva).
- `peru-segunda-vuelta-2026` — OTRO proyecto (análisis/proyección de votos), no este dashboard.
