import { useEffect, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Legend,
} from 'recharts';
import { fmtPct, apellido } from '../utils';

function horaCorta(ts) {
  const d = new Date(ts);
  return d.toLocaleString('es-PE', { day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export default function GraficaEvolucion() {
  const [snapshots, setSnapshots] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/api/historial')
      .then(r => r.json())
      .then(d => setSnapshots(d.snapshots || []))
      .catch(e => setError(e.message));
  }, []);

  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;
  if (!snapshots) return <div className="p-8 text-gray-500">Cargando histórico…</div>;
  if (snapshots.length < 2) {
    return (
      <div className="p-8 text-center text-gray-500 max-w-lg mx-auto">
        <p className="text-lg font-semibold mb-1">Aún no hay suficiente histórico</p>
        <p className="text-sm">El gráfico se construye automáticamente cada vez que ONPE publica nuevos datos.
        Hay {snapshots.length} punto(s) registrado(s). Vuelve más tarde.</p>
      </div>
    );
  }

  // Identificar los dos candidatos a partir del último snapshot
  const ultimo = snapshots[snapshots.length - 1];
  const cands = ultimo.candidatos.map(c => ({
    partido: c.partido, color: c.color, label: apellido(c.candidato) || c.partido,
  }));

  // Construir series: cada punto = { ts, actas, [partido]: pct }
  const serie = snapshots.map(s => {
    const punto = { ts: s.ts, hora: horaCorta(s.ts), actas: s.actas };
    s.candidatos.forEach(c => { punto[c.partido] = c.pct; });
    return punto;
  });

  function TooltipPers({ active, payload, label }) {
    if (!active || !payload?.length) return null;
    const actas = payload[0]?.payload?.actas;
    return (
      <div className="bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-xs">
        <p className="font-bold text-gray-700 mb-1">{label}</p>
        {payload.map(p => (
          <p key={p.dataKey} style={{ color: p.color }} className="font-semibold">
            {p.dataKey}: {fmtPct(p.value)}
          </p>
        ))}
        <p className="text-gray-400 mt-1">{fmtPct(actas)} actas</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto p-4">
      <div className="max-w-5xl mx-auto bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <h2 className="text-base font-bold text-gray-800 mb-1">Evolución del conteo · head to head</h2>
        <p className="text-xs text-gray-500 mb-4">
          Porcentaje de votos válidos de cada candidato a medida que avanza el escrutinio de actas.
        </p>
        <ResponsiveContainer width="100%" height={380}>
          <LineChart data={serie} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
            <XAxis dataKey="hora" tick={{ fontSize: 10, fill: '#9ca3af' }} />
            <YAxis domain={[45, 55]} tickFormatter={v => `${v}%`} tick={{ fontSize: 10, fill: '#9ca3af' }} />
            <Tooltip content={<TooltipPers />} />
            <Legend />
            <ReferenceLine y={50} stroke="#f59e0b" strokeDasharray="4 3" label={{ value: '50%', fontSize: 10, fill: '#f59e0b' }} />
            {cands.map(c => (
              <Line key={c.partido} type="monotone" dataKey={c.partido} name={c.label}
                stroke={c.color} strokeWidth={2.5} dot={false} isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
        <p className="text-xs text-gray-400 mt-2 text-right">{serie.length} snapshots · Fuente: ONPE</p>
      </div>
    </div>
  );
}
