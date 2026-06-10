const TABS = [
  { id: 'mapa', label: '🗺️ Mapa' },
  { id: 'evolucion', label: '📈 Evolución' },
  { id: 'proyeccion', label: '🔮 Proyección' },
];

export default function Header({ tabActiva, onCambia }) {
  return (
    <header className="bg-blue-900 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col sm:flex-row items-center gap-3">
        <div className="flex items-center gap-3 flex-1">
          <div className="bg-red-600 rounded px-2 py-1 text-sm font-bold tracking-wider">
            ONPE
          </div>
          <div>
            <h1 className="text-lg font-bold leading-tight">
              Segunda Vuelta Presidencial · Perú 2026
            </h1>
            <p className="text-blue-200 text-xs">
              Resultados oficiales en tiempo real
            </p>
          </div>
        </div>

        <nav className="flex gap-1">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => onCambia(t.id)}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                tabActiva === t.id
                  ? 'bg-white text-blue-900'
                  : 'text-blue-100 hover:bg-blue-800'
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>
    </header>
  );
}
