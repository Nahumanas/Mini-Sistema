import { redirect } from "next/navigation";

// La entrada lleva a Inicio. Si nadie ingresó todavía, el marco de adentro manda a /ingresar.
export default function Home() {
  redirect("/inicio");
}
