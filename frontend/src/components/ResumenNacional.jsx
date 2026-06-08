import { fmtNum, fmtPct, apellido } from '../utils';

export default function ResumenNacional({ data }) {
  if (!data?.nacional?.top?.length) return null;
  const { top, totales } = data.nacional;
  const [a, b] = top; // a = líder, b = segundo
  const margen = b ? (a.pct - b.pct) : 0;
  const publicadas = (totales?.actasContabilizadas || 0) + (totales?.actasEnviadasJee || 0);

  return (
    <div className="bg-blue-900 text-white">
      {/* Barra head-to-head */}
      <div className="max-w-5xl mx-auto px-4 pt-3">
        <div className="flex items-stretch h-9 rounded-md overflow-hidden text-sm font-bold shadow">
          <div
            className="flex items-center pl-3 transition-all duration-700"
            style={{ width: `${a.pct}%`, backgroundColor: a.color }}
          >
            <span className="truncate drop-shadow">{apellido(a.candidato)} · {fmtPct(a.pct)}</span>
          </div>
          {b && (
            <div
              className="flex items-center justify-end pr-3 transition-all duration-700"
              style={{ width: `${b.pct}%`, backgroundColor: b.color }}
            >
              <span className="truncate drop-shadow">{fmtPct(b.pct)} · {apellido(b.candidato)}</span>
            </div>
          )}
        </div>
      </div>

      {/* Métricas */}
      <div className="max-w-5xl mx-auto px-4 py-2 flex items-center justify-center gap-6 text-xs flex-wrap">
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: a.color }} />
          <span className="font-semibold">{a.partido}</span>
          <span className="text-blue-300">{fmtNum(a.votos)} votos</span>
        </span>
        <span className="bg-amber-400 text-amber-950 px-2 py-0.5 rounded-full font-bold">
          Margen {fmtPct(margen)}
        </span>
        {b && (
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: b.color }} />
            <span className="font-semibold">{b.partido}</span>
            <span className="text-blue-300">{fmtNum(b.votos)} votos</span>
          </span>
        )}
        <span className="text-blue-200">
          <span className="font-bold text-green-300">{fmtPct(publicadas)}</span> actas · {fmtNum(totales?.totalActas)} totales
        </span>
      </div>
    </div>
  );
}
