"use client";

import { useEffect, useState } from "react";
import { ExternalLink, LocateFixed, Plug, ScanLine, Unlink } from "lucide-react";
import { api, type EstadoMercadoPago } from "@/lib/api";
import { ddmm } from "@/lib/fechas";
import { leerUbicacion } from "@/lib/mercadopago";
import { useComercioActivo } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Campo, Chip, claseInput, Tarjeta } from "../ui/base";

// Los nombres como los pide Mercado Pago (tienen que coincidir con la ciudad)
const PROVINCIAS = [
  "Capital Federal", "Buenos Aires", "Catamarca", "Chaco", "Chubut", "Córdoba", "Corrientes", "Entre Ríos",
  "Formosa", "Jujuy", "La Pampa", "La Rioja", "Mendoza", "Misiones", "Neuquén", "Río Negro", "Salta", "San Juan",
  "San Luis", "Santa Cruz", "Santa Fe", "Santiago del Estero", "Tierra del Fuego", "Tucumán",
];

const PANEL_MP = "https://www.mercadopago.com.ar/developers/panel/app";

// Cobrar con el QR de Mercado Pago (etapa 8). Cada comercio conecta SU cuenta: la plata le llega a él.
export function CuentaMercadoPago() {
  const enNube = useDatos((s) => s.modo === "nube");
  const comercio = useComercioActivo();
  return (
    <Tarjeta titulo={`Cobrar con Mercado Pago · ${comercio.nombre}`}>
      {enNube ? <ConCuenta key={comercio.id} comercioId={comercio.id} direccion={comercio.direccion} /> : <EnLaDemo />}
    </Tarjeta>
  );
}

function Explicacion() {
  return (
    <div className="flex gap-3">
      <ScanLine className="mt-0.5 size-5 shrink-0 text-texto-suave" strokeWidth={1.75} />
      <p className="text-texto-suave">
        En la Caja aparece el medio <b className="text-texto">Mercado Pago</b>: se muestra un QR por el total, el cliente lo escanea con su celular y la venta se guarda sola cuando paga.
        Cada comercio usa su propia cuenta (si tenés varios, elegí el comercio arriba).
      </p>
    </div>
  );
}

function EnLaDemo() {
  return (
    <div className="flex flex-col gap-3">
      <Explicacion />
      <p className="text-sm text-texto-suave">En la demo el QR es de prueba (hay un botón para simular el pago). La cuenta se conecta cuando usás Mantenete con tu Gmail.</p>
    </div>
  );
}

function ConCuenta({ comercioId, direccion }: { comercioId: number; direccion: string }) {
  const avisar = useInterfaz((s) => s.avisar);
  const [estado, setEstado] = useState<EstadoMercadoPago | null>(null);
  const [error, setError] = useState("");
  const [conectando, setConectando] = useState(false);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    api.mercadoPago(comercioId).then(setEstado, (err: Error) => setError(err.message));
  }, [comercioId]);

  if (error) return <p className="text-peligro">{error}</p>;
  if (!estado) return <p className="text-texto-suave">Cargando…</p>;

  if (estado.conectada) {
    return (
      <div className="flex flex-col gap-4">
        <Explicacion />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="flex flex-wrap items-center gap-2">
            <Chip tono="verde">Conectada</Chip>
            Cuenta <b>{estado.nombre || "de Mercado Pago"}</b>
            {estado.conectadaEl && <span className="text-sm text-texto-suave">desde el {ddmm(estado.conectadaEl, true)}</span>}
          </p>
          <Boton
            variante="peligro"
            icono={Unlink}
            disabled={ocupado}
            onClick={async () => {
              setOcupado(true);
              try {
                setEstado(await api.desconectarMercadoPago(comercioId));
                avisar("Listo: la Caja de este comercio ya no cobra con Mercado Pago.");
              } catch (err) {
                avisar((err as Error).message, "error");
              } finally {
                setOcupado(false);
              }
            }}
          >
            Desconectar
          </Boton>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Explicacion />
      {conectando ? (
        <FormularioConectar
          comercioId={comercioId}
          direccion={direccion}
          alConectar={(e) => {
            setEstado(e);
            setConectando(false);
            avisar("Listo: la cuenta de Mercado Pago quedó conectada. Ya podés cobrar con QR en la Caja.");
          }}
          alCancelar={() => setConectando(false)}
        />
      ) : (
        <Boton variante="primario" icono={Plug} className="self-start" onClick={() => setConectando(true)}>
          Conectar la cuenta de Mercado Pago
        </Boton>
      )}
    </div>
  );
}

/** La calle y el número a partir de la dirección del comercio ("Av. Corrientes 1234" → calle y 1234). */
function separarDireccion(direccion: string): [string, string] {
  const m = direccion.trim().match(/^(.*?)\s+(\d{1,6})\b/);
  return m ? [m[1], m[2]] : [direccion.trim(), ""];
}

function FormularioConectar({ comercioId, direccion, alConectar, alCancelar }: { comercioId: number; direccion: string; alConectar: (e: EstadoMercadoPago) => void; alCancelar: () => void }) {
  const [calleInicial, numeroInicial] = separarDireccion(direccion);
  const [token, setToken] = useState("");
  const [calle, setCalle] = useState(calleInicial);
  const [numero, setNumero] = useState(numeroInicial);
  const [ciudad, setCiudad] = useState("");
  const [provincia, setProvincia] = useState("");
  const [ubicacion, setUbicacion] = useState("");
  const [buscando, setBuscando] = useState(false);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const coordenadas = leerUbicacion(ubicacion);

  function usarMiUbicacion() {
    if (!navigator.geolocation) {
      setError("Este navegador no da la ubicación. Copiala de Google Maps.");
      return;
    }
    setBuscando(true);
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setUbicacion(`${p.coords.latitude.toFixed(6)}, ${p.coords.longitude.toFixed(6)}`);
        setBuscando(false);
      },
      () => {
        setError("No se pudo saber la ubicación (¿no diste permiso?). Copiala de Google Maps.");
        setBuscando(false);
      },
      { enableHighAccuracy: true, timeout: 15000 },
    );
  }

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={async (e) => {
        e.preventDefault();
        setError("");
        if (!coordenadas) {
          setError("Falta la ubicación del local (latitud y longitud).");
          return;
        }
        setGuardando(true);
        try {
          alConectar(
            await api.conectarMercadoPago(comercioId, {
              accessToken: token.trim(),
              calle: calle.trim(),
              numero: numero.trim(),
              ciudad: ciudad.trim(),
              provincia,
              latitud: coordenadas[0],
              longitud: coordenadas[1],
            }),
          );
        } catch (err) {
          setError((err as Error).message);
        } finally {
          setGuardando(false);
        }
      }}
    >
      <ol className="list-decimal space-y-1 pl-5 text-[15px] text-texto-suave">
        <li>
          Entrá a{" "}
          <a href={PANEL_MP} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-texto underline underline-offset-2">
            Mercado Pago Developers <ExternalLink className="size-3.5" />
          </a>{" "}
          con la cuenta del comercio y abrí la aplicación.
        </li>
        <li>
          En <b className="text-texto">Credenciales de producción</b> (o <b className="text-texto">de prueba</b>, para probar sin plata de verdad) copiá el <b className="text-texto">Access Token</b> y pegalo acá.
        </li>
        <li>Completá la dirección del local: Mercado Pago la pide para crear la caja con QR.</li>
      </ol>

      <Campo etiqueta="Access Token" ayuda="Empieza con APP_USR-. Es secreto: no se lo pases a nadie. Mantenete lo guarda cifrado.">
        <input id="mp-token" type="password" autoComplete="off" spellCheck={false} value={token} onChange={(e) => setToken(e.target.value)} placeholder="APP_USR-…" className={claseInput} required />
      </Campo>

      <div className="grid gap-3 sm:grid-cols-[1fr_8rem]">
        <Campo etiqueta="Calle">
          <input id="mp-calle" value={calle} onChange={(e) => setCalle(e.target.value)} className={claseInput} required minLength={2} />
        </Campo>
        <Campo etiqueta="Número">
          <input id="mp-numero" value={numero} onChange={(e) => setNumero(e.target.value)} inputMode="numeric" className={claseInput} required />
        </Campo>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Campo etiqueta="Ciudad o barrio" ayuda="En Capital Federal, el barrio (por ejemplo, Palermo).">
          <input id="mp-ciudad" value={ciudad} onChange={(e) => setCiudad(e.target.value)} className={claseInput} required minLength={2} />
        </Campo>
        <Campo etiqueta="Provincia">
          <select id="mp-provincia" value={provincia} onChange={(e) => setProvincia(e.target.value)} className={claseInput} required>
            <option value="">Elegí…</option>
            {PROVINCIAS.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </Campo>
      </div>
      <Campo etiqueta="Ubicación del local" ayuda="Estando en el local, tocá «Usar mi ubicación». Si no, en Google Maps hacé clic derecho sobre el local y copiá los números.">
        <div className="flex gap-2">
          <input id="mp-ubicacion" value={ubicacion} onChange={(e) => setUbicacion(e.target.value)} placeholder="-34.603700, -58.381600" className={claseInput} required />
          <Boton icono={LocateFixed} onClick={usarMiUbicacion} disabled={buscando} className="shrink-0">
            {buscando ? "Buscando…" : "Usar mi ubicación"}
          </Boton>
        </div>
      </Campo>
      {ubicacion && !coordenadas && <p className="-mt-2 text-sm text-peligro">No entiendo esa ubicación: tienen que ser dos números de Argentina, como -34.6037, -58.3816.</p>}

      {error && <p className="text-sm text-peligro">{error}</p>}
      <div className="flex justify-end gap-2">
        <Boton variante="fantasma" onClick={alCancelar}>
          Cancelar
        </Boton>
        <Boton type="submit" variante="primario" icono={Plug} disabled={guardando || !token || !coordenadas || !provincia}>
          {guardando ? "Conectando…" : "Conectar"}
        </Boton>
      </div>
    </form>
  );
}
