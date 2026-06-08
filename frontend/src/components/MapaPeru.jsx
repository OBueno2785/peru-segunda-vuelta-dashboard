import { useEffect, useState, useRef } from 'react';
import { MapContainer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { normName, fmtPct } from '../utils';
import { GEOJSON_URL } from '../api';

function FitBounds({ geoJsonRef }) {
  const map = useMap();
  useEffect(() => {
    if (geoJsonRef.current) {
      const bounds = geoJsonRef.current.getBounds();
      if (bounds.isValid()) map.fitBounds(bounds, { padding: [20, 20] });
    }
  }, [geoJsonRef, map]);
  return null;
}

export default function MapaPeru({ mapaData, onClickDep, depSeleccionado, leyenda }) {
  const [geoData, setGeoData] = useState(null);
  const geoJsonRef = useRef(null);

  useEffect(() => {
    fetch(GEOJSON_URL)
      .then(r => r.json())
      .then(setGeoData)
      .catch(console.error);
  }, []);

  function getColor(feature) {
    const key = normName(feature.properties.NOMBDEP || '');
    const dep = mapaData?.[key];
    if (!dep || !dep.lider) return '#e5e7eb';
    return dep.lider.color || '#9ca3af';
  }

  function style(feature) {
    const key = normName(feature.properties.NOMBDEP || '');
    const isSelected = key === depSeleccionado;
    const dep = mapaData?.[key];
    // Opacidad según margen: más opaco = victoria más holgada
    const margen = dep?.margen ?? 0;
    const baseOpacity = Math.min(0.45 + Math.abs(margen) / 100 * 2.2, 0.92);
    return {
      fillColor: getColor(feature),
      weight: isSelected ? 3 : 1,
      opacity: 1,
      color: isSelected ? '#fbbf24' : '#ffffff',
      fillOpacity: isSelected ? 0.95 : baseOpacity,
    };
  }

  function onEachFeature(feature, layer) {
    const nombre = feature.properties.NOMBDEP || '';
    const key = normName(nombre);
    const dep = mapaData?.[key];

    let tip = `<strong>${nombre}</strong>`;
    if (dep?.lider) {
      tip += `<br/><span style="color:${dep.lider.color}">●</span> ${dep.lider.partido} · ${fmtPct(dep.lider.pct)}`;
      if (dep.margen != null) tip += `<br/>Margen: ${fmtPct(dep.margen)}`;
      tip += `<br/>Actas: ${dep.actasContabilizadas != null ? dep.actasContabilizadas.toFixed(1) + '%' : '—'}`;
    } else {
      tip += `<br/><em style="color:#9ca3af">Sin datos</em>`;
    }
    layer.bindTooltip(tip, {
      sticky: true,
      className: 'bg-white text-xs px-2 py-1 rounded shadow-md border border-gray-200',
    });

    layer.on({
      mouseover(e) { e.target.setStyle({ weight: 2, color: '#f59e0b', fillOpacity: 1 }); e.target.bringToFront(); },
      mouseout(e) {
        const isSel = key === depSeleccionado;
        e.target.setStyle(style(feature));
        if (!isSel) e.target.setStyle({ color: '#ffffff', weight: 1 });
      },
      click() { onClickDep(key, nombre); },
    });
  }

  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      <MapContainer
        center={[-9.19, -75.015]}
        zoom={5}
        scrollWheelZoom={true}
        style={{ height: '100%', width: '100%', position: 'absolute', inset: 0 }}
        zoomControl={true}
      >
        {geoData && (
          <GeoJSON
            key={JSON.stringify(depSeleccionado) + Object.keys(mapaData || {}).length}
            ref={geoJsonRef}
            data={geoData}
            style={style}
            onEachFeature={onEachFeature}
          />
        )}
        {geoData && <FitBounds geoJsonRef={geoJsonRef} />}
      </MapContainer>

      {/* Leyenda */}
      <div style={{ position: 'absolute', bottom: 24, left: 16, zIndex: 1000 }} className="bg-white bg-opacity-95 rounded-lg shadow-lg p-3 text-xs">
        <p className="font-bold text-gray-700 mb-1.5">Candidato líder</p>
        {leyenda?.map(l => (
          <div key={l.partido} className="flex items-center gap-2 mb-1">
            <span className="w-4 h-3 rounded" style={{ backgroundColor: l.color }} />
            <span className="text-gray-600 truncate">{l.partido}</span>
          </div>
        ))}
        <div className="flex items-center gap-2 mt-1">
          <span className="w-4 h-3 rounded border border-gray-200" style={{ backgroundColor: '#e5e7eb' }} />
          <span className="text-gray-400 italic">Sin datos</span>
        </div>
        <p className="text-gray-400 mt-1.5 leading-tight">Intensidad = margen de victoria</p>
      </div>
    </div>
  );
}
