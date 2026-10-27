"use client";

import { useMemo } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { pesos } from "@/lib/formato";
import { useInterfaz } from "@/store/interfaz";

// Los gráficos toman los colores del tema (claro u oscuro) leyendo las variables de CSS,
// así cambian solos cuando se toca "Modo oscuro". (Solo se dibujan en el navegador: ver Marco.tsx)
function useColores() {
  const tema = useInterfaz((s) => s.tema);
  return useMemo(() => {
    const css = getComputedStyle(document.documentElement);
    const leer = (v: string) => css.getPropertyValue(v).trim();
    return { tema, verde: leer("--primary-color"), texto: leer("--texto-suave"), borde: leer("--borde"), fondo: leer("--superficie") };
  }, [tema]);
}

// "$ 1,2 M" / "$ 350 mil": los ejes no necesitan el número exacto
function corto(valor: number) {
  if (valor >= 1_000_000) return `$ ${(valor / 1_000_000).toFixed(1).replace(".", ",")} M`;
  if (valor >= 1_000) return `$ ${Math.round(valor / 1_000)} mil`;
  return `$ ${valor}`;
}

function Globito({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-borde bg-superficie px-3 py-2 text-sm shadow-lg shadow-black/5">
      <p className="text-texto-suave">{label}</p>
      <p className="numeros font-semibold">{pesos(payload[0].value)}</p>
    </div>
  );
}

type Props = { datos: object[]; x: string; y: string; alto?: number };

export function GraficoBarras({ datos, x, y, alto = 240 }: Props) {
  const c = useColores();
  return (
    <div style={{ height: alto }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={datos} margin={{ top: 8, right: 4, bottom: 0, left: 4 }}>
          <CartesianGrid vertical={false} stroke={c.borde} />
          <XAxis dataKey={x} tick={{ fill: c.texto, fontSize: 12 }} tickLine={false} axisLine={{ stroke: c.borde }} interval="preserveStartEnd" />
          <YAxis tickFormatter={corto} tick={{ fill: c.texto, fontSize: 12 }} tickLine={false} axisLine={false} width={76} />
          <Tooltip content={<Globito />} cursor={{ fill: c.borde, opacity: 0.4 }} />
          <Bar dataKey={y} fill={c.verde} radius={[4, 4, 0, 0]} maxBarSize={36} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function GraficoArea({ datos, x, y, alto = 260 }: Props) {
  const c = useColores();
  return (
    <div style={{ height: alto }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={datos} margin={{ top: 8, right: 4, bottom: 0, left: 4 }}>
          <defs>
            <linearGradient id="relleno" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={c.verde} stopOpacity={0.35} />
              <stop offset="100%" stopColor={c.verde} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke={c.borde} />
          <XAxis dataKey={x} tick={{ fill: c.texto, fontSize: 12 }} tickLine={false} axisLine={{ stroke: c.borde }} minTickGap={24} />
          <YAxis tickFormatter={corto} tick={{ fill: c.texto, fontSize: 12 }} tickLine={false} axisLine={false} width={76} />
          <Tooltip content={<Globito />} cursor={{ stroke: c.borde }} />
          <Area type="monotone" dataKey={y} stroke={c.verde} strokeWidth={2} fill="url(#relleno)" activeDot={{ r: 4, fill: c.verde, stroke: c.fondo, strokeWidth: 2 }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
