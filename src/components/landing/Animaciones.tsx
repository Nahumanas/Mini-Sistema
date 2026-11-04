"use client";

// Animaciones de la página de presentación (solo corren en el navegador).
// Si la persona pidió "reducir movimiento" en su compu o celular, se apagan solas.

import { motion, MotionConfig, type Variants } from "framer-motion";

const SUAVE = [0.22, 1, 0.36, 1] as const; // arranca rápido y frena despacio

// Envuelve la página para respetar "reducir movimiento" del sistema.
export function ConfigAnimaciones({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}

// Aparece desde un poquito más abajo al cargar la página. "demora" en segundos.
export function EntradaSuave({ children, demora = 0, className }: { children: React.ReactNode; demora?: number; className?: string }) {
  return (
    <motion.div className={className} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: demora, ease: SUAVE }}>
      {children}
    </motion.div>
  );
}

const PADRE: Variants = {
  oculto: {},
  visible: { transition: { staggerChildren: 0.15 } },
};

const HIJO: Variants = {
  oculto: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: SUAVE } },
};

// Contenedor (por ejemplo una grilla) cuyos hijos <CascadaItem> aparecen uno tras otro
// cuando la persona llega con el scroll.
export function Cascada({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <motion.div className={className} variants={PADRE} initial="oculto" whileInView="visible" viewport={{ once: true, amount: 0.2 }}>
      {children}
    </motion.div>
  );
}

export function CascadaItem({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <motion.div className={className} variants={HIJO}>
      {children}
    </motion.div>
  );
}

// Se agranda un poquito al pasar el mouse y se achica al tocarlo.
export function Presionable({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <motion.div className={className ?? "inline-flex"} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} transition={{ type: "spring", stiffness: 400, damping: 25 }}>
      {children}
    </motion.div>
  );
}
