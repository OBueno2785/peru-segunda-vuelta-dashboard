import { fmtNum, fmtPct, progressColor } from '../utils';

function BarraCandidato({ cand, rank }) {
  const pct = cand.pct || 0;
  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-0.5">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: cand.color }} />
          <span className="text-xs font-medium text-gray-800 truncate">{rank}. {cand.partido}</span>
        </div>
        <span className="text-sm font-bold text-gray-700 ml-2 tabular-nums">{fmtPct(pct)}</span>
      </div>
      {cand.candidato && <p className="text-xs text-gray-500 ml-5 mb-0.5 truncate">{cand.candidato}</p>}
      <div className="ml-5 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: cand.color }} />
      </div>
      <p className="text-xs text-gray-400 ml-5 mt-0.5">{fmtNum(cand.votos)} votos válidos</p>
    </div>
  );
}

export default function PanelDetalle({ departamento, data }) {
  if (!data) return null;
  const mapa = data.mapa || {};
  const nacional = data.nacional;

  const depKey = departamento
    ? Object.keys(mapa).find(k => k === departamento || k.includes(departamento) || departamento.includes(k))
    : null;
  const depData = depKey ? mapa[depKey] : null;

  const candidatos = depData?.top?.length ? depData.top : (nacional?.top || []);
  const actasPct = depData ? depData.actasContabilizadas : nacional?.totales?.actasContabilizadas;
  const totalActas = depData ? depData.totalActas : nacional?.totales?.totalActas;
  const contabilizadas = depData ? depData.contabilizadas : nacional?.totales?.contabilizadas;
  const nombreMostrado = depData ? depData.nombre : 'Nacional';
  const margen = depData?.margen ?? (candidatos.length >= 2 ? +(candidatos[0].pct - candidatos[1].pct).toFixed(2) : null);

  const titulo = departamento ? nombreMostrado : 'Resultados Nacionales';

  return (
    <aside className="w-80 bg-white border-l border-gray-200 flex flex-col overflow-hidden">
      <div className="bg-gray-50 border-b border-gray-200 px-4 py-3">
        <h2 className="font-bold text-gray-900 text-sm">{titulo}</h2>

        {margen != null && candidatos[0]?.color && (
          <div className="mt-1.5 inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full font-bold"
            style={{ backgroundColor: candidatos[0].color + '22', color: candidatos[0].color }}>
            Margen {fmtPct(margen)}
          </div>
        )}

        <div className="mt-2">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Actas contabilizadas</span>
            <span className="font-bold" style={{ color: actasPct != null ? progressColor(actasPct) : '#9ca3af' }}>
              {actasPct != null ? fmtPct(actasPct) : 'Sin datos'}
            </span>
          </div>
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div className="h-full rounded-full transition-all"
              style={{ width: `${Math.min(actasPct ?? 0, 100)}%`, backgroundColor: actasPct != null ? progressColor(actasPct) : '#e5e7eb' }} />
          </div>
          <p className="text-xs text-gray-400 mt-0.5">
            {actasPct != null ? `${fmtNum(contabilizadas)} de ${fmtNum(totalActas)} actas` : 'ONPE aún no reporta totales'}
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3">
        {candidatos.length === 0 ? (
          <p className="text-sm text-gray-400 text-center mt-8">Sin datos disponibles</p>
        ) : (
          <>
            <p className="text-xs text-gray-500 mb-3 font-medium uppercase tracking-wide">
              {departamento ? `Resultados en ${nombreMostrado}` : 'Resultados nacionales'}
            </p>
            {candidatos.map((c, i) => <BarraCandidato key={i} cand={c} rank={i + 1} />)}
          </>
        )}
      </div>

      <div className="bg-gray-50 border-t border-gray-200 px-4 py-2">
        <p className="text-xs text-gray-400 text-center">
          Fuente: ONPE · {new Date().toLocaleDateString('es-PE', { day: '2-digit', month: 'long', hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>
    </aside>
  );
}
