"use client";

// Animaciones de la página de presentación que necesitan JavaScript (framer-motion).
// Son solo un extra al pasar el mouse o tocar: si el JavaScript no carga, todo se ve igual.
// Las entradas al cargar y al hacer scroll están en Entradas.tsx, hechas con CSS.
// Si la persona pidió "reducir movimiento" en su compu o celular, se apagan solas.

import { motion, MotionConfig } from "framer-motion";

// Envuelve la página para respetar "reducir movimiento" del sistema.
export function ConfigAnimaciones({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}

// Se agranda un poquito al pasar el mouse y se achica al tocarlo.
export function Presionable({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <motion.div className={className ?? "inline-flex"} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} transition={{ type: "spring", stiffness: 400, damping: 25 }}>
      {children}
    </motion.div>
  );
}
