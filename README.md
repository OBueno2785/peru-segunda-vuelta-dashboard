# Segunda Vuelta Presidencial · Perú 2026

Dashboard de resultados de la **segunda vuelta presidencial** en tiempo real,
con datos oficiales de ONPE (`resultadosegundavuelta.onpe.gob.pe`).

Misma lógica y estructura que el proyecto de primera vuelta (`peru-elecciones-2026`),
simplificado al caso head-to-head: dos candidatos, solo elección presidencial.

## Estructura

```
backend/    FastAPI + scraper httpx de la API de ONPE
frontend/   React + Vite + Leaflet + Recharts
```

## Backend

```bash
cd backend
py -3 -m venv venv
venv/Scripts/python.exe -m pip install -r requirements.txt
venv/Scripts/python.exe -m uvicorn main:app --port 8030
```

- Refresca los datos de ONPE cada 5 minutos en segundo plano.
- Guarda un histórico (`data/historial.json`) cada vez que ONPE publica datos nuevos.

### Endpoints

| Endpoint | Descripción |
|----------|-------------|
| `GET /api/presidencial` | Resultado nacional + mapa por departamento |
| `GET /api/mapa/presidencial` | Solo el mapa por departamento |
| `GET /api/historial` | Snapshots para el gráfico de evolución |
| `GET /api/status` | Estado del cache |
| `POST /api/refresh` | Fuerza una descarga fresca (cooldown 30 s) |

## Frontend

```bash
cd frontend
npm install
npm run dev        # desarrollo (proxy a :8030)
npm run build      # build de producción -> dist/ (lo sirve el backend)
```

### Vistas

- **🗺️ Mapa**: cada departamento coloreado según el candidato líder; la intensidad
  refleja el margen de victoria. Clic en un departamento para ver el detalle.
- **📈 Evolución**: gráfico head-to-head del porcentaje de cada candidato a medida
  que avanza el escrutinio.

## Despliegue (GitHub Pages)

La página está publicada en:

**https://obueno2785.github.io/peru-segunda-vuelta-dashboard/**

Como GitHub Pages solo sirve estáticos, en producción el frontend lee JSON
generados por `backend/build_static.py` (`frontend/public/data/*.json`) en vez de la API.

El workflow `.github/workflows/deploy.yml` se ejecuta cada 30 minutos (cron),
scrapea ONPE, regenera los JSON, acumula el histórico en `backend/data/historial.json`
y redespliega el sitio automáticamente. Así la página queda siempre activa y al día.

Para regenerar los datos a mano:

```bash
cd backend
venv/Scripts/python.exe build_static.py
```

## Fuente

ONPE — Oficina Nacional de Procesos Electorales.
Los datos de estimación/proyección son derivados; los porcentajes oficiales son los publicados por ONPE.
