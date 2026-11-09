// La caja del logo, animada: entra con dos saltitos, se abre y salen las tres
// plataformas y el nombre. Dura 2,5 segundos y corre una sola vez al cargar.
//
// Por qué está hecha así:
// - Es un dibujo (SVG) movido con CSS, sin JavaScript ni librerías 3D: no pesa
//   casi nada y no demora la carga de la página.
// - No tapa la página: el título y el botón se ven desde el primer momento.
// - El dibujo "quieto" es el final de la animación. Si la persona pidió
//   "reducir movimiento", o el navegador no anima, se ve el logo terminado.
// Los movimientos están en globals.css (buscar "Caja animada").

const LINEA = { stroke: "#0F2340", strokeWidth: 16, strokeLinejoin: "round", strokeLinecap: "round" } as const;

// Cada solapa "nace" desde su bisagra (el borde de la caja donde está pegada).
const SOLAPAS_FONDO = [
  { bisagra: [393.5, 301], d: "M275,352 L195,292 L432,190 L512,250 Z", color: "#28A7DB" },
  { bisagra: [630.5, 301], d: "M512,250 L592,190 L829,292 L749,352 Z", color: "#28A7DB" },
];
const SOLAPAS_FRENTE = [
  { bisagra: [393.5, 407], d: "M275,352 L512,462 L432,522 L195,412 Z", color: "#28A7DB" },
  { bisagra: [630.5, 407], d: "M512,462 L749,352 L829,412 L592,522 Z", color: "url(#caja-solapa)" },
];

// Las tres plataformas, de arriba hacia abajo: altura final y colores (tapa y costado).
const PLATAFORMAS = [
  { y: 112, tapa: "#43DDE3", costado: "#2FB6DD" },
  { y: 186, tapa: "#2A9FDA", costado: "#1C7BD6" },
  { y: 260, tapa: "#1C7BD6", costado: "#1767B4" },
];

function Solapa({ bisagra, d, color }: { bisagra: number[]; d: string; color: string }) {
  const [x, y] = bisagra;
  return (
    <g transform={`translate(${x} ${y})`}>
      <g className="caja-solapa">
        <path transform={`translate(${-x} ${-y})`} d={d} fill={color} {...LINEA} />
      </g>
    </g>
  );
}

export function CajaAnimada({ className = "" }: { className?: string }) {
  return (
    <div className={`caja-animada inline-flex items-center gap-3 ${className}`} role="img" aria-label="Mantenete">
      <span className="caja-salto block h-[84px] w-[72px] shrink-0">
        <svg viewBox="160 40 704 824" className="size-full overflow-visible" aria-hidden="true">
          <defs>
            <linearGradient id="caja-cuerpo" x1="278" y1="0" x2="746" y2="0" gradientUnits="userSpaceOnUse">
              <stop offset="0" stopColor="#1C7BD6" />
              <stop offset="0.5" stopColor="#2A9FDA" />
              <stop offset="0.5" stopColor="#2FB6DD" />
              <stop offset="1" stopColor="#43DDE3" />
            </linearGradient>
            <linearGradient id="caja-solapa" x1="512" y1="0" x2="829" y2="0" gradientUnits="userSpaceOnUse">
              <stop offset="0" stopColor="#2BB3DC" />
              <stop offset="1" stopColor="#3CCFE0" />
            </linearGradient>
            <radialGradient id="caja-luz">
              <stop offset="0" stopColor="#43DDE3" stopOpacity="0.75" />
              <stop offset="1" stopColor="#43DDE3" stopOpacity="0" />
            </radialGradient>
          </defs>

          {/* Luz celeste que sale de adentro */}
          <g transform="translate(512 330)">
            <circle className="caja-luz" r="400" fill="url(#caja-luz)" />
          </g>

          {/* Cuerpo de la caja (el mismo dibujo del logo) */}
          <path d="M278,516 L477.6,609.8 Q512,626 546.4,609.8 L746,516 L746,674 Q746,712 711.6,728.2 L546.4,805.8 Q512,822 477.6,805.8 L312.4,728.2 Q278,712 278,674 Z" fill="url(#caja-cuerpo)" {...LINEA} />
          <path d="M278,516 L512,626 L746,516 L746,546 L512,656 L278,546 Z" fill="#2A72AE" />
          <path d="M278,546 L512,656 L746,546" fill="none" {...LINEA} />
          <path d="M278,352 L512,462 L746,352 L746,454 Q746,492 711.6,508.2 L546.4,585.8 Q512,602 477.6,585.8 L312.4,508.2 Q278,492 278,454 Z" fill="url(#caja-cuerpo)" {...LINEA} />
          <path d="M512,462 L512,588" fill="none" {...LINEA} />

          {SOLAPAS_FONDO.map((s) => <Solapa key={s.d} {...s} />)}

          {/* El hueco de la caja */}
          <path d="M275,352 L512,250 L512,462 Z" fill="#0F2340" {...LINEA} />
          <path d="M512,250 L749,352 L512,462 Z" fill="#2373A6" {...LINEA} />

          {/* Las tres plataformas que salen de adentro */}
          {PLATAFORMAS.map((p, i) => (
            <g key={p.y} transform={`translate(512 ${p.y})`}>
              <g className={`caja-plataforma caja-plataforma-${i + 1}`}>
                <path d="M-112,0 L0,50 L112,0 L112,24 L0,74 L-112,24 Z" fill={p.costado} {...LINEA} strokeWidth={13} />
                <path d="M-112,0 L0,-50 L112,0 L0,50 Z" fill={p.tapa} {...LINEA} strokeWidth={13} />
              </g>
            </g>
          ))}

          {SOLAPAS_FRENTE.map((s) => <Solapa key={s.d} {...s} />)}

          {/* Tapa cerrada: solo se ve mientras la caja entra saltando */}
          <g className="caja-tapa">
            <path d="M275,352 L512,250 L749,352 L512,462 Z" fill="#28A7DB" {...LINEA} />
            <path d="M393.5,301 L630.5,407" fill="none" {...LINEA} strokeWidth={12} />
          </g>
        </svg>
      </span>
      <span className="caja-nombre text-2xl font-extrabold tracking-[0.2em] sm:text-[1.7rem]" aria-hidden="true">
        MANTENETE
      </span>
    </div>
  );
}
