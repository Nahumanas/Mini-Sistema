import { api } from "@/lib/api";
import { guardarLlave } from "@/lib/llave";
import { fraseCompleta, validarCodigoNuevo, validarPinNuevo } from "@/lib/pin";
import { useDatos } from "./datos";

// El cifrado de los datos en la nube (paso 5, etapa 5). Solo existe en la nube: la demo guarda todo en el
// navegador y no tiene frase ni código de empleados. Las cuentas las hace la API (servidor/app/cifrado.py);
// acá se guarda la llave de sesión que devuelve y se anota en pantalla lo que cambió.

/** Activa el cifrado con el PIN de jefe y la frase que anotó en papel. Devuelve la llave del jefe ya guardada. */
export async function activarCifrado(pin: string, frase: string) {
  if (!fraseCompleta(frase)) throw new Error("Escribí la frase completa: son 24 letras y números.");
  const r = await api.activarCifrado(pin, frase);
  guardarLlave(r.llave, r.vence);
  useDatos.setState({ cifradoActivo: true });
}

/** "Me olvidé el PIN": con la frase de recuperación se elige un PIN nuevo (los datos siguen todos). */
export async function recuperarPin(frase: string, nuevo: string, repetido: string) {
  if (!fraseCompleta(frase)) throw new Error("Escribí la frase completa: son 24 letras y números.");
  validarPinNuevo(nuevo, repetido);
  const r = await api.recuperarPin(frase, nuevo);
  guardarLlave(r.llave, r.vence);
  useDatos.setState({ pinConfigurado: true });
}

/** El empleado entra con el código del comercio. false si el código no es el correcto. */
export async function entrarConCodigo(comercioId: number, codigo: string) {
  const r = await api.llaveEmpleado(comercioId, codigo);
  if (r.ok && r.llave && r.vence) guardarLlave(r.llave, r.vence);
  return r.ok;
}

/** El jefe elige (o cambia) el código de empleados de un comercio. Pide su PIN otra vez. */
export async function elegirCodigo(comercioId: number, pin: string, codigo: string, repetido: string) {
  validarCodigoNuevo(codigo, repetido, pin);
  const r = await api.cambiarCodigo(comercioId, pin, codigo);
  useDatos.setState((s) => ({ codigos: { ...s.codigos, [comercioId]: r.codigoCambiado } }));
}
