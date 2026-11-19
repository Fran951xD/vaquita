// Vaquita: el poco JavaScript propio que hace falta. Todo funciona también sin JS
// (formularios comunes y links); esto solo agrega comodidades.
"use strict";

function avisar(texto) {
  const aviso = document.getElementById("aviso");
  if (!aviso) return;
  aviso.replaceChildren();
  const p = document.createElement("p");
  p.textContent = texto;
  aviso.append(p);
  clearTimeout(avisar.temporizador);
  avisar.temporizador = setTimeout(() => aviso.replaceChildren(), 3500);
}

// Copiar alias o link con un toque.
document.addEventListener("click", async (evento) => {
  const boton = evento.target.closest("[data-copiar]");
  if (!boton) return;
  try {
    await navigator.clipboard.writeText(boton.dataset.copiar);
    avisar("Copiado. Ya lo podés pegar.");
  } catch {
    avisar("No se pudo copiar. Mantené apretado el texto para copiarlo a mano.");
  }
});

// Hoja de carga: los links con data-abrir abren un <dialog> en vez de navegar.
document.addEventListener("click", (evento) => {
  const abrir = evento.target.closest("[data-abrir]");
  if (abrir) {
    const dialogo = document.getElementById(abrir.dataset.abrir);
    if (dialogo && typeof dialogo.showModal === "function") {
      evento.preventDefault();
      dialogo.showModal();
      dialogo.querySelector("[autofocus], input:not([type=hidden])")?.focus();
    }
    return;
  }
  const cerrar = evento.target.closest("[data-cerrar]");
  if (cerrar) cerrar.closest("dialog")?.close();
});

// Cerrar tocando afuera de la hoja.
document.addEventListener("click", (evento) => {
  if (evento.target instanceof HTMLDialogElement) evento.target.close();
});

// El servidor avisa con HX-Trigger que el gasto se guardó: cerrar y limpiar.
document.body.addEventListener("gastoGuardado", (evento) => {
  const dialogo = document.getElementById("hoja-gasto");
  if (dialogo?.open) dialogo.close();
  if (evento.detail?.value) avisar(evento.detail.value);
});

// Formulario de gasto: mostrar solo los campos de la forma de dividir elegida
// y los de cotización cuando la moneda no es la del grupo.
function sincronizarGasto(form) {
  const forma = form.querySelector("[name=forma_division]:checked")?.value || "iguales";
  form.querySelectorAll("[data-forma]").forEach((el) => {
    el.hidden = el.dataset.forma !== forma;
    el.querySelectorAll("input").forEach((i) => (i.disabled = el.hidden));
  });
  const moneda = form.querySelector("[name=moneda]:checked")?.value;
  const cotizacion = form.querySelector("[data-cotizacion]");
  if (cotizacion) cotizacion.hidden = moneda === form.dataset.monedaGrupo;
  const varios = form.querySelector("[name=varios_pagadores]")?.checked;
  form.querySelectorAll("[data-pagadores]").forEach((el) => {
    el.hidden = el.dataset.pagadores !== (varios ? "varios" : "uno");
  });
}

document.addEventListener("change", (evento) => {
  const form = evento.target.closest("form[data-gasto]");
  if (form) sincronizarGasto(form);
});

function iniciar(raiz) {
  raiz.querySelectorAll("form[data-gasto]").forEach(sincronizarGasto);
}

document.addEventListener("DOMContentLoaded", () => iniciar(document));
document.body.addEventListener("htmx:afterSwap", (evento) => iniciar(evento.target));
