/* Carga del protocolo.
 *
 * El navegador NO parsea protocolo/: lo recibe ya armado por
 * comun.protocolo.todo(). Así la demo y el escritorio leen el mismo
 * contenido con el mismo código Python.
 *
 * Ojo con los guiones: al pasar por JSON las claves de turno, que en Python
 * son enteros, llegan como strings ("1", "2", "3"). */

window.PROTOCOLO = null;

async function cargarProtocolo() {
  const resp = await fetch("/api/protocolo");
  if (!resp.ok) {
    throw new Error("el servidor no devolvió el protocolo (" + resp.status + ")");
  }
  window.PROTOCOLO = await resp.json();
  return window.PROTOCOLO;
}

/* La demo corre siempre con los tiempos cortos: la línea base de 5 minutos no
 * tiene sentido delante de una clase, y sin EDA tampoco tiene función. */
function parametros() {
  return window.PROTOCOLO.parametros.demo;
}

function textos() {
  return window.PROTOCOLO.textos;
}

/* El guion de un turno. `turno` es número; las claves vienen como string. */
function guion(tipo, turno) {
  const bloque = window.PROTOCOLO.guiones[tipo] || {};
  return bloque[String(turno)] || "";
}
