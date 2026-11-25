import type { CertificadoArca } from "./api";
import { ddmm } from "./fechas";

// El certificado de ARCA de cada ambiente es UNO solo para todos los comercios: si vence (o el cargado en Render no
// sirve), ninguno factura. /admin avisa desde 30 días antes (avisarDiasAntes, lo manda la API).

const NOMBRE = { homologacion: "de prueba", produccion: "de producción" } as const;

/** El texto del aviso de un certificado, o null si está todo bien (o si no está cargado: eso ya lo dice cada comercio). */
export function avisoCertificado(c: CertificadoArca, avisarDiasAntes: number): string | null {
  if (!c.cargado) return null;
  const quienes = c.ambiente === "produccion" ? "en producción" : "en prueba";
  if (c.problema) return `${c.problema} Mientras tanto, ningún comercio ${quienes} factura.`;
  if (c.vence && c.diasParaVencer !== null && c.diasParaVencer <= avisarDiasAntes) {
    const cuando = c.diasParaVencer <= 0 ? "hoy" : c.diasParaVencer === 1 ? "mañana" : `en ${c.diasParaVencer} días`;
    return (
      `El certificado ${NOMBRE[c.ambiente]} de ARCA vence ${cuando} (${ddmm(c.vence, true)}). Es uno solo para todos ` +
      `los comercios ${quienes}: renovalo en ARCA ("Administración de Certificados Digitales") y cargá el nuevo en ` +
      "Render antes de esa fecha."
    );
  }
  return null;
}
