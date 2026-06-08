/**
 * Normaliza un nombre de departamento para hacer match entre
 * el GeoJSON del Perú y los datos de ONPE.
 */
export function normName(s) {
  if (!s) return '';
  return s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toUpperCase()
    .trim();
}

/** Formatea un número con separadores de miles. */
export function fmtNum(n) {
  if (n == null) return '–';
  return Number(n).toLocaleString('es-PE');
}

/** Formatea un porcentaje. */
export function fmtPct(n) {
  if (n == null) return '–';
  return Number(n).toFixed(2) + '%';
}

/** Color de una barra de progreso de conteo. */
export function progressColor(pct) {
  if (pct >= 90) return '#22c55e';
  if (pct >= 60) return '#84cc16';
  if (pct >= 30) return '#f59e0b';
  return '#ef4444';
}

/** Apellido corto del candidato (para encabezados compactos). */
export function apellido(nombreCompleto) {
  if (!nombreCompleto) return '';
  const parts = nombreCompleto.trim().split(/\s+/);
  return parts.slice(-2).join(' ');
}
