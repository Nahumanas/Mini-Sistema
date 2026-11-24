"use client";

import { useState } from "react";
import { BadgeCheck, ChevronDown, ChevronRight, FlaskConical } from "lucide-react";
import { apiAdmin, type AmbienteArca, type ClienteAdmin, type ComercioFacturacion } from "@/lib/api";
import { useAdmin } from "@/store/admin";
import { Boton, Chip } from "../ui/base";
import { Dialogo } from "../ui/Dialogo";

// Panel de administrador → Clientes → factura ARCA: cada comercio del cliente que ya cargó sus datos fiscales, con
// su ambiente. "Pasar a producción" le pregunta primero a ARCA de producción (que el punto de venta exista y que el
// comercio haya autorizado a Mantenete) y recién ahí lo cambia: desde ese momento cada factura nueva tiene validez
// fiscal. Las de antes (y sus notas de crédito) siguen en prueba. Con facturas sin respuesta de ARCA no se cambia.

const cuitConGuiones = (cuit: string) => cuit.replace(/^(\d{2})(\d{8})(\d)$/, "$1-$2-$3");

export function FacturacionComercios({ cliente }: { cliente: ClienteAdmin }) {
  const [abierto, setAbierto] = useState(false);
  const [comercios, setComercios] = useState<ComercioFacturacion[] | null>(null);
  const [produccionLista, setProduccionLista] = useState(false);
  const [error, setError] = useState("");
  const [cambiando, setCambiando] = useState<{ comercio: ComercioFacturacion; a: AmbienteArca } | null>(null);

  const cargar = () =>
    apiAdmin.comerciosFacturacion(cliente.duenoId).then(
      (r) => {
        setComercios(r.comercios);
        setProduccionLista(r.produccionLista);
        setError("");
      },
      (err: Error) => setError(err.message),
    );

  return (
    <div className="mt-1">
      <button
        type="button"
        className="inline-flex items-center gap-1 text-sm text-texto-suave hover:text-texto"
        aria-expanded={abierto}
        onClick={() => {
          if (!abierto && comercios === null) void cargar();
          setAbierto(!abierto);
        }}
      >
        {abierto ? <ChevronDown className="size-4" aria-hidden /> : <ChevronRight className="size-4" aria-hidden />}
        Factura ARCA por comercio
      </button>
      {abierto && (
        <div className="mt-1 flex flex-col gap-1.5 border-l-2 border-borde pl-3">
          {error && <p className="text-sm text-peligro">{error}</p>}
          {comercios === null && !error && <p className="text-sm text-texto-suave">Cargando…</p>}
          {comercios?.length === 0 && <p className="text-sm text-texto-suave">Ningún comercio cargó todavía sus datos fiscales.</p>}
          {comercios?.map((k) => (
            <div key={k.comercioId} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
              <span className="font-medium">{k.nombre}</span>
              <span className="text-texto-suave">CUIT {cuitConGuiones(k.cuit)} · PV {k.puntoVenta}</span>
              {k.ambiente === "produccion" ? <Chip tono="verde">Producción</Chip> : <Chip tono="amarillo">Prueba</Chip>}
              {k.porSalir > 0 && <span className="text-peligro">{k.porSalir} sin respuesta de ARCA</span>}
              {k.ambiente === "homologacion" ? (
                <Boton
                  variante="fantasma"
                  icono={BadgeCheck}
                  disabled={!produccionLista || k.porSalir > 0}
                  title={!produccionLista ? "Falta cargar el certificado de producción en Render" : undefined}
                  onClick={() => setCambiando({ comercio: k, a: "produccion" })}
                  className="!px-2 !py-1 text-sm"
                >
                  Pasar a producción
                </Boton>
              ) : (
                <Boton variante="fantasma" icono={FlaskConical} disabled={k.porSalir > 0}
                  onClick={() => setCambiando({ comercio: k, a: "homologacion" })} className="!px-2 !py-1 text-sm">
                  Volver a prueba
                </Boton>
              )}
            </div>
          ))}
        </div>
      )}
      {cambiando && (
        <CambiarAmbiente cliente={cliente} {...cambiando} alCerrar={() => setCambiando(null)} alListo={() => { setCambiando(null); void cargar(); }} />
      )}
    </div>
  );
}

function CambiarAmbiente({ cliente, comercio, a, alCerrar, alListo }: {
  cliente: ClienteAdmin;
  comercio: ComercioFacturacion;
  a: AmbienteArca;
  alCerrar: () => void;
  alListo: () => void;
}) {
  const { enviando, hacer } = useAdmin();
  const produccion = a === "produccion";
  return (
    <Dialogo
      titulo={produccion ? `¿Pasar ${comercio.nombre} a producción?` : `¿Volver ${comercio.nombre} a prueba?`}
      descripcion={
        produccion ? (
          <>
            Antes se le pregunta a ARCA de producción que el CUIT {cuitConGuiones(comercio.cuit)} tenga el punto de venta {comercio.puntoVenta} para
            web services y que haya autorizado a Mantenete. Si está todo, desde ese momento <b className="text-texto">cada factura nueva tiene validez fiscal</b>.
            Las de antes siguen siendo de prueba.
          </>
        ) : (
          <>Las facturas nuevas vuelven a salir en el ARCA de prueba (sin valor fiscal). Las que ya salieron en producción siguen siendo válidas.</>
        )
      }
      alCerrar={alCerrar}
      pie={
        <>
          <Boton onClick={alCerrar}>Cancelar</Boton>
          <Boton
            variante="primario"
            data-principal
            disabled={enviando}
            onClick={async () => {
              const ok = await hacer(
                () => apiAdmin.ambiente(cliente.duenoId, comercio.comercioId, a),
                produccion ? `Listo: ${comercio.nombre} ya factura de verdad con ARCA.` : `Listo: ${comercio.nombre} volvió al ARCA de prueba.`,
              );
              if (ok) alListo();
            }}
          >
            {enviando ? (produccion ? "Verificando con ARCA…" : "Cambiando…") : produccion ? "Verificar y pasar" : "Volver a prueba"}
          </Boton>
        </>
      }
    />
  );
}
