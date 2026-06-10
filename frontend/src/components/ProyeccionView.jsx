import { useEffect, useState } from 'react';
import { fmtNum, fmtPct, apellido } from '../utils';
import { PROYECCION_URL } from '../api';

export default function ProyeccionView() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${PROYECCION_URL}?t=${Date.now()}`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(setData)
      .catch(e => setError(e.message));
  }, []);

  if (error) return (
    <div className="flex-1 p-8 text-center text-gray-500 max-w-lg mx-auto">
      <p className="text-lg font-semibold mb-1">Proyección no disponible</p>
      <p className="text-sm">{error}. Se genera en el backend con <code className="bg-gray-100 px-1 rounded">python proyeccion.py</code>.</p>
    </div>
  );
  if (!data) return <div className="flex-1 p-8 text-gray-500">Cargando proyección…</div>;

  const res = data.resultado || [];
  const [a, b] = res; // ordenados por proyectado desc
  const ep = data.actas_EP || {};
  const banda = data.banda_incertidumbre;
  const tot = data.contabilizado_totales || {};
  const gen = data.generado ? new Date(data.generado).toLocaleString('es-PE') : '';
  const estados = ep.por_estado || {};

  return (
    <div className="flex-1 overflow-auto p-4">
      <div className="max-w-4xl mx-auto space-y-4">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <h2 className="text-base font-bold text-gray-800">Proyección del resultado final</h2>
          <p className="text-xs text-gray-500 mb-4">
            Conteo oficial contabilizado <span className="font-semibold">({fmtPct(tot.actasContabilizadas)} de actas)</span>{' '}
            más los votos de las actas <span className="font-semibold">«Para envío al JEE»</span> que ONPE aún no computa.
          </p>

          {/* Barra head-to-head proyectada */}
          {a && b && (
            <div className="flex items-stretch h-10 rounded-md overflow-hidden text-sm font-bold shadow mb-2">
              <div className="flex items-center pl-3 transition-all duration-700"
                   style={{ width: `${a.pct_proyectado}%`, backgroundColor: a.color }}>
                <span className="truncate drop-shadow text-white">{apellido(a.candidato)} · {fmtPct(a.pct_proyectado)}</span>
              </div>
              <div className="flex items-center justify-end pr-3 transition-all duration-700"
                   style={{ width: `${b.pct_proyectado}%`, backgroundColor: b.color }}>
                <span className="truncate drop-shadow text-white">{fmtPct(b.pct_proyectado)} · {apellido(b.candidato)}</span>
              </div>
            </div>
          )}

          {/* Tabla contabilizado vs proyectado */}
          <table className="w-full text-sm mt-3">
            <thead>
              <tr className="text-gray-500 text-xs border-b border-gray-200">
                <th className="text-left font-medium py-1.5">Candidato</th>
                <th className="text-right font-medium">Contabilizado</th>
                <th className="text-right font-medium">+ Actas JEE</th>
                <th className="text-right font-medium">Proyectado</th>
              </tr>
            </thead>
            <tbody>
              {res.map((c, i) => {
                const sube = c.pct_proyectado >= c.pct_contabilizado;
                return (
                  <tr key={i} className="border-b border-gray-100 last:border-0">
                    <td className="py-2">
                      <span className="inline-flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: c.color }} />
                        <span className="font-semibold text-gray-800">{apellido(c.candidato)}</span>
                        <span className="text-gray-400 text-xs hidden sm:inline">{c.partido}</span>
                      </span>
                    </td>
                    <td className="text-right text-gray-500">{fmtPct(c.pct_contabilizado)}</td>
                    <td className="text-right text-gray-500">+{fmtNum(c.actas_EP)}</td>
                    <td className="text-right font-bold" style={{ color: c.color }}>
                      {fmtPct(c.pct_proyectado)}
                      <span className={`ml-1 text-xs ${sube ? 'text-green-600' : 'text-red-500'}`}>
                        {sube ? '▲' : '▼'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* Banda de incertidumbre */}
          {banda && (
            <div className="mt-4 bg-amber-50 border border-amber-200 rounded-md px-3 py-2 text-xs text-amber-900">
              <span className="font-bold">Banda de incertidumbre · {apellido(banda.lider) || banda.lider}:</span>{' '}
              {fmtPct(banda.pct_min_lider)} – {fmtPct(banda.pct_max_lider)}{' '}
              <span className="text-amber-700">(±{fmtNum(banda.votos_faltantes_estimados)} votos de actas pendientes aún sin digitar)</span>
            </div>
          )}
        </div>

        {/* Cobertura de actas */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 text-sm">
          <h3 className="font-bold text-gray-800 mb-2">Actas no contabilizadas incorporadas</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
            <Metric label="Descargadas" value={fmtNum(ep.total_descargadas)} />
            <Metric label="Con votos (sumadas)" value={fmtNum(ep.con_votos)} color="text-green-600" />
            <Metric label="Para envío al JEE" value={fmtNum(estados.E)} />
            <Metric label="Pendientes (sin datos)" value={fmtNum(estados.P)} color="text-amber-600" />
          </div>
          <p className="text-xs text-gray-500 mt-3">
            Las actas «Para envío al JEE» traen votos digitados (provisionales, en resolución del JEE) y se suman al
            conteo. Las «Pendientes» aún no tienen votos ni escaneo en ONPE, por eso entran solo como banda de incertidumbre.
          </p>
        </div>

        <p className="text-xs text-gray-400 text-right">
          Generado {gen} · Fuente: ONPE (actas) · proyección no oficial
        </p>
      </div>
    </div>
  );
}

function Metric({ label, value, color = 'text-gray-800' }) {
  return (
    <div className="bg-gray-50 rounded-md py-2">
      <div className={`text-xl font-bold ${color}`}>{value}</div>
      <div className="text-[11px] text-gray-500 leading-tight">{label}</div>
    </div>
  );
}
