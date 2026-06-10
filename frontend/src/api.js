// Fuente de datos según el entorno.
// - DEV: backend FastAPI local (proxy /api -> :8030), con scraping en vivo.
// - PROD (GitHub Pages): JSON estáticos regenerados por el workflow de GitHub Actions.
const PROD = import.meta.env.PROD;
const BASE = import.meta.env.BASE_URL; // '/' en dev, '/peru-segunda-vuelta-dashboard/' en Pages

export const PRESIDENCIAL_URL = PROD ? `${BASE}data/presidencial.json` : '/api/presidencial';
export const HISTORIAL_URL    = PROD ? `${BASE}data/historial.json`    : '/api/historial';
export const PROYECCION_URL   = PROD ? `${BASE}data/proyeccion.json`   : '/api/proyeccion';
export const GEOJSON_URL      = `${BASE}peru-departamentos.geojson`;

// El refresco manual (POST /api/refresh) solo existe con backend (dev).
// En Pages el botón simplemente vuelve a leer el JSON estático.
export const CAN_REFRESH = !PROD;
