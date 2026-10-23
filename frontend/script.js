const API_URL = "/api";
let CONCERTS = [], TICKETS = [];
const state = { selectedConcertId: null, selectedConcert: null, selectedTicketTypeId: null, qty: 1, currentUser: null, pendingScreen: null, lastOrder: null, orderToCancel: null, activeTicketTab: "proximos", filters: { city: "", genres: [], date: "all", sort: "date", search: "" } };
const fmtCOP = n => "$" + Number(n || 0).toLocaleString("es-CO");
const token = () => localStorage.getItem("soundpass_token");
const concert = () => state.selectedConcert;
const ticketType = () => concert()?.ticket_types?.find(t => t.id === state.selectedTicketTypeId);
const venue = c => [c?.venue?.name, c?.venue?.city].filter(Boolean).join(", ");
const esc = (v = "") => String(v).replace(/[&<>'"]/g, x => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[x]));
 
function fmtDate(value, long = false) {
  if (!value) return "Fecha por confirmar";
  const [y, m, d] = value.slice(0, 10).split("-").map(Number);
  return new Intl.DateTimeFormat("es-CO", { day: "2-digit", month: long ? "long" : "short", year: "numeric", timeZone: "UTC" }).format(new Date(Date.UTC(y, m - 1, d))).replace(/\./g, "");
}
function fmtTime(value) {
  if (!value) return "Hora por confirmar";
  const [h, m] = value.split(":").map(Number);
  return new Intl.DateTimeFormat("es-CO", { hour: "numeric", minute: "2-digit", hour12: true }).format(new Date(2000, 0, 1, h, m));
}
function fmtDateTime(value) { return value ? new Intl.DateTimeFormat("es-CO", { day: "2-digit", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value)).replace(/\./g, "") : ""; }
function imageUrl(path) { return !path ? "" : /^(https?:|data:|blob:)/i.test(path) ? path : `${API_URL}${path.startsWith("/") ? "" : "/"}${path}`; }
function art(c, className = "") { const url = imageUrl(c?.image_url), style = url ? ` style="background-image:linear-gradient(0deg,rgba(0,0,0,.35),rgba(0,0,0,.08)),url('${esc(url)}')"` : ""; return `<div class="${className} dynamic-art${url ? " has-image" : ""}"${style} role="img" aria-label="${esc(c?.artist || "Concierto")}"></div>`; }
 
async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) }; if (token()) headers.Authorization = `Bearer ${token()}`;
  let response; try { response = await fetch(API_URL + path, { ...options, headers }); } catch { throw new Error("No fue posible conectar con la API. Verifica que el backend esté activo."); }
  const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(data.detail || "No fue posible completar la solicitud."); return data;
}
function goTo(id) {
  if (id !== "detail" && typeof demoState !== "undefined" && demoState) { demoStop(); demoRoot()?.classList.remove("is-playing"); }
  document.querySelectorAll("[data-screen]").forEach(el => el.classList.toggle("is-active", el.id === `screen-${id}`));
  document.querySelectorAll(".primary-nav__link[data-active-on]").forEach(el => el.classList.toggle("is-active", el.dataset.activeOn.split(",").includes(id)));
  if (id === "checkout") renderCheckout(); if (id === "mytickets") loadTickets(); window.scrollTo({ top: 0, behavior: "smooth" });
}
function collectionMessage(text) { document.getElementById("featured-grid").innerHTML = `<div class="empty-state collection-message"><p>${esc(text)}</p></div>`; document.getElementById("concert-list").innerHTML = `<div class="empty-state"><p>${esc(text)}</p></div>`; document.getElementById("concert-count").textContent = "Conciertos (0)"; }
async function loadConcerts() { collectionMessage("Cargando conciertos..."); CONCERTS = await api("/concerts?sort=date"); populateFilters(); renderFeatured(); renderListing(); }
function populateFilters() {
  const cities = [...new Set(CONCERTS.map(c => c.venue.city).filter(Boolean))].sort((a, b) => a.localeCompare(b, "es"));
  document.getElementById("f-city").innerHTML = `<option value="">Todas</option>${cities.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join("")}`;
  const genres = [...new Set(CONCERTS.map(c => c.genre).filter(Boolean))].sort((a, b) => a.localeCompare(b, "es"));
  document.getElementById("genre-filters").innerHTML = genres.map(v => `<label class="checkbox"><input type="checkbox" value="${esc(v)}"><span>${esc(v)}</span></label>`).join("");
}
function filteredConcerts() {
  const now = new Date(), monthStart = new Date(now.getFullYear(), now.getMonth(), 1), monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59), three = new Date(now); three.setMonth(three.getMonth() + 3); const q = state.filters.search.toLocaleLowerCase("es").trim();
  return CONCERTS.filter(c => { const d = new Date(`${c.event_date}T12:00:00`); return (!state.filters.city || c.venue.city === state.filters.city) && (!state.filters.genres.length || state.filters.genres.includes(c.genre)) && (!q || [c.artist, c.tour_name, c.genre, c.venue.name, c.venue.city].some(v => String(v || "").toLocaleLowerCase("es").includes(q))) && (state.filters.date === "month" ? d >= monthStart && d <= monthEnd : state.filters.date === "three_months" ? d >= now && d <= three : true); }).sort((a, b) => state.filters.sort === "price_asc" ? Number(a.price_from) - Number(b.price_from) : state.filters.sort === "price_desc" ? Number(b.price_from) - Number(a.price_from) : `${a.event_date}${a.event_time}`.localeCompare(`${b.event_date}${b.event_time}`));
}
function renderFeatured() { const rows = CONCERTS.slice(0, 6); document.getElementById("featured-grid").innerHTML = rows.length ? rows.map(c => `<article class="feature-card" data-open="${c.id}">${art(c, "feature-card__art")}<div class="feature-card__body"><p class="feature-card__title">${esc(c.artist)}</p><p class="feature-card__meta">${esc(c.venue.name)} — ${fmtDate(c.event_date)}</p></div></article>`).join("") : `<div class="empty-state collection-message"><p>No hay conciertos próximos disponibles.</p></div>`; }
function renderListing() { const rows = filteredConcerts(); document.getElementById("concert-count").textContent = `Conciertos (${rows.length})`; document.getElementById("concert-list").innerHTML = rows.length ? rows.map(c => `<article class="concert-row" data-open="${c.id}">${art(c, "concert-row__art")}<div class="concert-row__body"><p class="concert-row__title">${esc(c.artist)}</p><p class="concert-row__sub">${esc(c.tour_name)}</p><div class="concert-row__meta"><span>🗓 ${fmtDate(c.event_date)} · ${fmtTime(c.event_time)}</span><span>📍 ${esc(venue(c))}</span></div></div><div class="concert-row__price"><small>Desde</small><strong>${fmtCOP(c.price_from)}</strong></div><button class="btn btn--primary btn--sm" data-open="${c.id}">Ver evento</button></article>`).join("") : `<div class="empty-state"><h3>No encontramos conciertos</h3><p>Prueba con otros filtros o términos de búsqueda.</p></div>`; }
 
async function openConcert(id) {
  state.selectedConcertId = Number(id); state.selectedConcert = null; state.selectedTicketTypeId = null; state.qty = 1; goTo("detail"); document.querySelector(".detail-title").textContent = "Cargando concierto..."; document.querySelector(".detail-sub").textContent = ""; document.getElementById("ticket-options").innerHTML = "";
  try { const c = await api(`/concerts/${id}`); state.selectedConcert = c; state.selectedTicketTypeId = (c.ticket_types.find(t => t.quantity_available > 0) || c.ticket_types[0])?.id ?? null; renderDetail(); } catch (error) { document.querySelector(".detail-title").textContent = "No fue posible cargar el concierto"; document.querySelector(".detail-sub").textContent = error.message; }
}
function renderDetail() {
  const c = concert(); if (!c) return; const poster = document.querySelector(".detail-poster"), url = imageUrl(c.image_url); poster.className = `detail-poster dynamic-art${url ? " has-image" : ""}`; poster.style.backgroundImage = url ? `linear-gradient(0deg,rgba(0,0,0,.62),transparent 60%),url("${url.replace(/"/g, "%22")}")` : ""; poster.querySelector(".poster__tag").textContent = c.artist; poster.querySelector(".poster__tag2").textContent = c.tour_name; document.querySelector(".detail-title").textContent = c.artist; document.querySelector(".detail-sub").textContent = `${c.tour_name} · ${c.genre}`;
  document.querySelector(".meta-info").innerHTML = `<p><span class="dot">•</span> ${fmtDate(c.event_date, true)} · ${fmtTime(c.event_time)}</p><p><span class="dot">•</span> ${esc(venue(c))}</p>${c.venue.address ? `<p><span class="dot">•</span> ${esc(c.venue.address)}</p>` : ""}<p><span class="dot">•</span> Capacidad: ${Number(c.venue.capacity || 0).toLocaleString("es-CO")} personas</p>`; document.querySelector(".detail-blurb").textContent = c.description || "Información adicional no disponible.";
  document.getElementById("stage-zones").innerHTML = c.ticket_types.map((t, i) => `<div class="stage-zone" style="width:${Math.min(96, 42 + i * 18)}%">${esc(t.name)}</div>`).join(""); document.getElementById("ticket-options").innerHTML = c.ticket_types.length ? c.ticket_types.map(t => `<label class="ticket-option ${t.id === state.selectedTicketTypeId ? "is-selected" : ""} ${t.quantity_available < 1 ? "is-disabled" : ""}" data-ticket-type="${t.id}"><span class="ticket-option__left"><span class="radio-outer"><span class="radio-inner"></span></span><span>${esc(t.name)}<small>${Number(t.quantity_available).toLocaleString("es-CO")} disponibles</small></span></span><span class="ticket-option__price">${fmtCOP(t.price)}</span></label>`).join("") : `<p class="form-message is-error">No hay tipos de boleto disponibles.</p>`; document.getElementById("qty-val").textContent = state.qty; document.querySelector('[data-nav="checkout"]').disabled = !ticketType(); renderDemos(c);
}
function renderCheckout() {
  const c = concert(), t = ticketType(); if (!c || !t) return goTo("listing"); const subtotal = Number(t.price) * state.qty, fee = 6000 * state.qty, total = subtotal + fee, box = document.querySelector(".summary-card"); box.querySelector(".summary-art").outerHTML = art(c, "thumb summary-art"); box.querySelector(".summary-item__title").textContent = c.artist; box.querySelector(".summary-item__sub").textContent = c.tour_name; const meta = box.querySelectorAll(".summary-item__meta"); meta[0].textContent = `${fmtDate(c.event_date)} · ${fmtTime(c.event_time)}`; meta[1].textContent = venue(c); const rows = box.querySelectorAll(".summary-rows div"); rows[0].querySelector("dd").textContent = t.name; document.getElementById("co-qty").textContent = state.qty; rows[2].querySelector("dd").textContent = fmtCOP(t.price); document.getElementById("co-subtotal").textContent = fmtCOP(subtotal); document.getElementById("co-service-fee").textContent = fmtCOP(fee); document.getElementById("co-total").textContent = fmtCOP(total); document.getElementById("pay-button-label").textContent = `Pagar ${fmtCOP(total)}`;
}
function renderSuccess() { const o = state.lastOrder; if (!o) return; document.getElementById("success-order").innerHTML = `<div class="order-card__head"><span>Orden #${esc(o.order_code)}</span><span class="order-card__date">${fmtDateTime(o.created_at)}</span></div><div class="summary-item">${art(o.concert, "thumb")}<div><p class="summary-item__title">${esc(o.concert.artist)}</p><p class="summary-item__sub">${esc(o.concert.tour_name)}</p><p class="summary-item__meta">${fmtDate(o.concert.event_date)} · ${fmtTime(o.concert.event_time)}</p><p class="summary-item__meta">${esc(venue(o.concert))}</p></div></div><div class="order-card__divider"></div><div class="order-card__row"><span>Boletos:</span><span>${o.items.map(i => `${i.quantity} × ${esc(i.ticket_type_name)}`).join(", ")}</span></div><div class="order-card__row"><span>Subtotal:</span><span>${fmtCOP(o.subtotal)}</span></div><div class="order-card__row"><span>Cargo por servicio:</span><span>${fmtCOP(o.service_fee)}</span></div><div class="order-card__row"><span>Estado:</span><span>${o.status === "confirmed" ? "Confirmada" : "Cancelada"}</span></div><div class="order-card__row order-card__row--total"><span>Total:</span><span>${fmtCOP(o.total)}</span></div>`; }
 
function setAuthView(view) { const reg = view === "register"; document.getElementById("login-form").hidden = reg; document.getElementById("register-form").hidden = !reg; document.getElementById("auth-title").textContent = reg ? "Crea tu cuenta" : "Inicia sesión para continuar"; }
function openAuth(next = null) { state.pendingScreen = next; setAuthView("login"); document.getElementById("auth-modal").hidden = false; document.getElementById("login-email").focus(); }
function closeAuth() { document.getElementById("auth-modal").hidden = true; state.pendingScreen = null; }
function message(id, text, error = true) { const el = document.getElementById(id); el.textContent = text; el.classList.toggle("is-error", error); }
function renderAccount() { const b = document.getElementById("account-button"), logged = Boolean(state.currentUser); b.classList.toggle("is-signed-in", logged); b.title = logged ? `Cuenta de ${state.currentUser.full_name}` : "Iniciar sesión"; b.setAttribute("aria-label", b.title); if (logged) document.getElementById("account-greeting").textContent = `Hola, ${state.currentUser.full_name}`; }
async function restoreSession() { if (!token()) return; try { state.currentUser = await api("/auth/me"); renderAccount(); } catch { localStorage.removeItem("soundpass_token"); } }
async function loadTickets() { if (!token()) return openAuth("mytickets"); const list = document.getElementById("ticket-list"); list.innerHTML = `<div class="empty-state"><p>Cargando tus boletos...</p></div>`; try { TICKETS = await api("/orders/me"); renderTickets(); } catch (error) { list.innerHTML = `<div class="empty-state"><p>${esc(error.message)}</p></div>`; } }
function renderTickets() { const now = new Date(), rows = TICKETS.filter(o => state.activeTicketTab === "proximos" ? o.status === "confirmed" && new Date(`${o.concert.event_date}T23:59:59`) >= now : o.status === "cancelled" || new Date(`${o.concert.event_date}T23:59:59`) < now), list = document.getElementById("ticket-list"); if (!rows.length) { list.innerHTML = `<div class="empty-state"><h3>No hay boletos en esta sección</h3><p>Explora los conciertos y encuentra tu próxima experiencia en vivo.</p><button class="btn btn--primary" data-nav="listing">Ver conciertos</button></div>`; return; } list.innerHTML = rows.map(o => { const c = o.concert, q = o.items.reduce((s, i) => s + i.quantity, 0), cancelled = o.status === "cancelled"; return `<article class="ticket-card">${art(c, "ticket-card__art")}<div class="ticket-card__body"><p class="ticket-card__title">${esc(c.artist)}</p><p class="ticket-card__sub">${esc(c.tour_name)}</p><div class="ticket-card__meta"><span>🗓 ${fmtDate(c.event_date)} · ${fmtTime(c.event_time)}</span><span>📍 ${esc(venue(c))}</span></div><div class="ticket-card__foot"><span>${q} boleto${q === 1 ? "" : "s"}</span><span>${o.items.map(i => esc(i.ticket_type_name)).join(", ")}</span><span>Orden #${esc(o.order_code)}</span></div></div><div class="ticket-card__actions"><span class="badge ${cancelled ? "badge--cancelled" : "badge--confirmed"}">${cancelled ? "Cancelado" : "Confirmado"}</span><button class="btn btn--outline btn--sm" data-order-detail="${o.id}">Ver detalle</button>${cancelled ? "" : `<button class="btn btn--danger-outline btn--sm" data-cancel-order="${o.id}">Cancelar compra</button>`}</div></article>`; }).join(""); }
function openCancelModal(id) { const o = TICKETS.find(x => x.id === Number(id)); if (!o) return; state.orderToCancel = o; const q = o.items.reduce((s, i) => s + i.quantity, 0); document.getElementById("cancel-ticket").innerHTML = `${art(o.concert, "thumb")}<div><p class="summary-item__title">${esc(o.concert.artist)}</p><p class="summary-item__meta">${fmtDate(o.concert.event_date)} · ${esc(o.concert.venue.name)}</p><p class="summary-item__meta">${q} boleto${q === 1 ? "" : "s"} · ${o.items.map(i => esc(i.ticket_type_name)).join(", ")}</p></div>`; document.getElementById("cancel-modal").hidden = false; }
async function confirmCancellation() { if (!state.orderToCancel) return; const b = document.getElementById("modal-confirm"); b.disabled = true; b.textContent = "Cancelando..."; try { const o = await api(`/orders/${state.orderToCancel.id}/cancel`, { method: "POST" }); document.getElementById("cancel-modal").hidden = true; document.getElementById("cancelled-order-code").textContent = `Orden #${o.order_code}`; document.getElementById("cancelled-order-date").textContent = `Cancelada: ${fmtDateTime(o.cancelled_at)}`; state.orderToCancel = null; goTo("cancelled"); } catch (e) { alert(e.message); } finally { b.disabled = false; b.textContent = "Sí, cancelar compra"; } }
 
document.addEventListener("click", e => { const nav = e.target.closest("[data-nav]"), open = e.target.closest("[data-open]"), type = e.target.closest("[data-ticket-type]"), view = e.target.closest("[data-auth-view]"), cancel = e.target.closest("[data-cancel-order]"); if (nav && nav.dataset.nav !== "checkout") goTo(nav.dataset.nav); if (open) openConcert(open.dataset.open); if (type && !type.classList.contains("is-disabled")) { state.selectedTicketTypeId = Number(type.dataset.ticketType); state.qty = Math.min(state.qty, ticketType()?.quantity_available || 1); renderDetail(); } if (view) setAuthView(view.dataset.authView); if (cancel) openCancelModal(cancel.dataset.cancelOrder); });
document.getElementById("f-city").onchange = e => { state.filters.city = e.target.value; renderListing(); }; document.getElementById("f-date").onchange = e => { state.filters.date = e.target.value; renderListing(); }; document.getElementById("genre-filters").onchange = () => { state.filters.genres = [...document.querySelectorAll("#genre-filters input:checked")].map(x => x.value); renderListing(); }; document.getElementById("sort-select").onchange = e => { state.filters.sort = e.target.value; renderListing(); }; document.getElementById("concert-search").oninput = e => { state.filters.search = e.target.value; renderListing(); };
document.getElementById("account-button").onclick = () => { if (!state.currentUser) return openAuth(); const m = document.getElementById("account-menu"); m.hidden = !m.hidden; }; document.getElementById("account-tickets").onclick = () => { document.getElementById("account-menu").hidden = true; goTo("mytickets"); }; document.getElementById("logout-button").onclick = () => { localStorage.removeItem("soundpass_token"); state.currentUser = null; document.getElementById("account-menu").hidden = true; renderAccount(); goTo("home"); }; document.addEventListener("click", e => { if (!e.target.closest(".topbar__right")) document.getElementById("account-menu").hidden = true; });
document.getElementById("auth-close").onclick = closeAuth; document.getElementById("auth-modal").onclick = e => { if (e.target.id === "auth-modal") closeAuth(); }; document.getElementById("qty-minus").onclick = () => { state.qty = Math.max(1, state.qty - 1); renderDetail(); }; document.getElementById("qty-plus").onclick = () => { state.qty = Math.min(10, ticketType()?.quantity_available || 1, state.qty + 1); renderDetail(); }; document.querySelector('[data-nav="checkout"]').onclick = e => { e.preventDefault(); if (!ticketType()) return; token() ? goTo("checkout") : openAuth("checkout"); };
document.querySelectorAll(".payment-option").forEach(o => o.onclick = () => { document.querySelectorAll(".payment-option").forEach(x => x.classList.remove("is-selected")); o.classList.add("is-selected"); o.querySelector("input").checked = true; });
document.getElementById("login-form").onsubmit = async e => { e.preventDefault(); const f = new FormData(e.currentTarget); try { const r = await api("/auth/login", { method: "POST", body: JSON.stringify({ email: f.get("email"), password: f.get("password") }) }); localStorage.setItem("soundpass_token", r.access_token); state.currentUser = await api("/auth/me"); renderAccount(); const next = state.pendingScreen; closeAuth(); if (next) goTo(next); } catch (err) { message("login-message", err.message); } };
document.getElementById("register-form").onsubmit = async e => { e.preventDefault(); const f = new FormData(e.currentTarget); try { await api("/auth/register", { method: "POST", body: JSON.stringify({ full_name: f.get("full_name"), email: f.get("email"), password: f.get("password") }) }); document.getElementById("login-email").value = f.get("email"); setAuthView("login"); message("login-message", "Cuenta creada. Ahora inicia sesión.", false); } catch (err) { message("register-message", err.message); } };
document.getElementById("pay-button").onclick = async () => { if (!token()) return openAuth("checkout"); const b = document.getElementById("pay-button"), c = concert(), t = ticketType(), text = document.querySelector(".payment-option.is-selected").textContent, payment = text.includes("PSE") ? "pse" : text.includes("Nequi") ? "nequi" : "card"; b.disabled = true; document.getElementById("pay-button-label").textContent = "Procesando compra…"; try { state.lastOrder = await api("/orders", { method: "POST", body: JSON.stringify({ concert_id: c.id, payment_method: payment, items: [{ ticket_type_id: t.id, quantity: state.qty }] }) }); renderSuccess(); goTo("success"); } catch (err) { alert(err.message); } finally { b.disabled = false; renderCheckout(); } };
document.getElementById("download-receipt").onclick = () => { const o = state.lastOrder; if (!o) return; const lines = ["SoundPass — Comprobante de compra", `Orden: ${o.order_code}`, `Estado: ${o.status}`, `Concierto: ${o.concert.artist} — ${o.concert.tour_name}`, `Fecha: ${fmtDate(o.concert.event_date)} · ${fmtTime(o.concert.event_time)}`, `Recinto: ${venue(o.concert)}`, ...o.items.map(i => `${i.quantity} × ${i.ticket_type_name}: ${fmtCOP(Number(i.unit_price) * i.quantity)}`), `Subtotal: ${fmtCOP(o.subtotal)}`, `Cargo por servicio: ${fmtCOP(o.service_fee)}`, `Total: ${fmtCOP(o.total)}`]; const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" }), url = URL.createObjectURL(blob), a = document.createElement("a"); a.href = url; a.download = `${o.order_code}.txt`; a.click(); URL.revokeObjectURL(url); };
document.querySelectorAll(".tab").forEach(t => t.onclick = () => { document.querySelectorAll(".tab").forEach(x => x.classList.remove("is-active")); t.classList.add("is-active"); state.activeTicketTab = t.dataset.tab; renderTickets(); }); document.getElementById("modal-close").onclick = document.getElementById("modal-cancel").onclick = () => { document.getElementById("cancel-modal").hidden = true; state.orderToCancel = null; }; document.getElementById("modal-confirm").onclick = confirmCancellation;
/* ===== HU-03: Detalle de orden de compra ===== */
const PAYMENT_LABELS = { card: "Tarjeta de crédito / débito", pse: "PSE", nequi: "Nequi / Daviplata" };
function renderOrderDetail(o) {
  const c = o.concert || {}, items = o.items || [], cancelled = o.status === "cancelled", qty = items.reduce((s, i) => s + Number(i.quantity || 0), 0);
  const stateClass = cancelled ? "cancelled" : "confirmed", stateText = cancelled ? "Cancelado" : "Confirmado";
  const pay = o.payment_method ? (PAYMENT_LABELS[o.payment_method] || o.payment_method) : "";
  const banner = cancelled
    ? `<div class="od-banner od-banner--cancelled" role="status"><svg width="18" height="18" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/><path d="M15 9l-6 6M9 9l6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg><span>Esta orden fue cancelada${o.cancelled_at ? ` el ${fmtDateTime(o.cancelled_at)}` : ""}. El reembolso será procesado en un plazo de 3 a 5 días hábiles al mismo método de pago.</span></div>`
    : `<div class="od-banner od-banner--ok" role="status"><svg width="18" height="18" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/><path d="M8 12.5l2.7 2.7L16 9.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg><span>Compra confirmada. Conserva el código de la orden como referencia de tu compra.</span></div>`;
  document.getElementById("order-detail").innerHTML = `<article class="order-detail order-detail--${stateClass}">
    <header class="od-head"><div><p class="od-eyebrow">Orden de compra</p><h1 class="od-code">#${esc(o.order_code)}</h1><p class="od-date">Comprada el ${fmtDateTime(o.created_at) || "fecha no disponible"}</p></div><span class="badge badge--lg ${cancelled ? "badge--cancelled" : "badge--confirmed"}">${stateText}</span></header>
    ${banner}
    <div class="od-grid">
      <div class="od-main">
        <section class="od-card"><h2>Concierto</h2><div class="od-concert">${art(c, "od-concert__art")}<div class="od-concert__info"><p class="od-concert__title">${esc(c.artist)}</p><p class="od-concert__sub">${esc(c.tour_name)}</p><div class="od-meta"><span>🗓 ${fmtDate(c.event_date, true)} · ${fmtTime(c.event_time)}</span><span>📍 ${esc(venue(c))}</span>${c.venue?.address ? `<span>${esc(c.venue.address)}</span>` : ""}</div></div></div></section>
        <section class="od-card"><h2>Boletos</h2><ul class="od-lines">${items.map(i => `<li class="od-line"><div><strong>${esc(i.ticket_type_name)}</strong><small>${Number(i.quantity)} × ${fmtCOP(i.unit_price)}</small></div><span class="od-line__amount">${fmtCOP(Number(i.unit_price) * Number(i.quantity))}</span></li>`).join("")}</ul><div class="od-count"><span>Total de boletos</span><strong>${qty}</strong></div></section>
      </div>
      <aside class="od-card od-summary"><h2>Resumen de pago</h2>
        <dl class="summary-rows"><div><dt>Subtotal</dt><dd>${fmtCOP(o.subtotal)}</dd></div><div><dt>Cargo por servicio</dt><dd>${fmtCOP(o.service_fee)}</dd></div>${pay ? `<div><dt>Método de pago</dt><dd>${esc(pay)}</dd></div>` : ""}<div><dt>Estado</dt><dd>${stateText}</dd></div></dl>
        <div class="summary-total"><span>Total</span><span>${fmtCOP(o.total)}</span></div>
      </aside>
    </div></article>`;
}
function openOrderDetail(id) { const o = TICKETS.find(x => x.id === Number(id)); if (!o) return; renderOrderDetail(o); goTo("orderdetail"); }
document.addEventListener("click", e => { const b = e.target.closest("[data-order-detail]"); if (b) openOrderDetail(b.dataset.orderDetail); });
 
async function init() { goTo("home"); await restoreSession(); try { await loadConcerts(); } catch (error) { CONCERTS = []; collectionMessage("No fue posible cargar los conciertos."); console.error(error); } } init();
 
/* ===== Demos del concierto (front) =====
   Datos: c.demos = [{ id, title, duration_seconds, tag?, audio_url?, spotify_uri? }]
   Mientras el backend no los envíe se usan DEMO_SAMPLE (borrar esa línea al conectar la API).
   Reproducción: "providers" intercambiables. Hoy: <audio> si hay audio_url, o simulación visual.
   Para Spotify solo hay que registrar otro provider en DEMO_PROVIDERS y devolverlo en pickProvider(). */
const DEMO_SAMPLE = [
  { id: 1, title: "Apertura del show", duration_seconds: 90 },
  { id: 2, title: "Tema principal", duration_seconds: 75, tag: "estreno" },
  { id: 3, title: "Versión acústica", duration_seconds: 65, tag: "acustica" },
  { id: 4, title: "Invitado especial", duration_seconds: 80, tag: "colaboracion" },
  { id: 5, title: "Tema de la gira", duration_seconds: 70 },
  { id: 6, title: "Cierre del show", duration_seconds: 100 }
];
const DEMO_TAGS = { estreno: ["Estreno", ""], acustica: ["Acústica", "dm-tag--amber"], colaboracion: ["Colaboración", "dm-tag--green"] };
const ICO_PLAY = `<svg class="ico-play" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;
const ICO_PAUSE = `<svg class="ico-pause" viewBox="0 0 24 24" fill="currentColor"><path d="M7 5h4v14H7zM13 5h4v14h-4z"/></svg>`;
const ICO_PREV = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h2v14H6zM20 5v14L9 12z"/></svg>`;
const ICO_NEXT = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M16 5h2v14h-2zM4 5v14l11-7z"/></svg>`;
var demoState = { list: [], index: 0, playing: false, time: 0, provider: null };
const fmtClock = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const demoBars = (n, seed) => Array.from({ length: n }, (_, i) => `<i style="--h:${25 + Math.abs(Math.sin((i + 1) * (seed + 2) * 1.7)) * 75 | 0}%"></i>`).join("");
const demoRoot = () => document.getElementById("concert-demos");
 
/* --- Providers: { load(demo, onTick, onEnd, onError), play(), pause(), seek(sec), stop() } --- */
const DEMO_PROVIDERS = {
  audio() {
    const a = new Audio(); a.preload = "none"; let tick, end, err;
    a.ontimeupdate = () => tick?.(a.currentTime); a.onended = () => end?.(); a.onerror = () => err?.();
    return {
      load(d, t, e, r) { tick = t; end = e; err = r; a.src = d.audio_url || d.preview_url; },
      play: () => a.play(), pause: () => a.pause(), seek: s => { a.currentTime = s; }, stop() { a.pause(); a.removeAttribute("src"); a.load(); }
    };
  },
  simulated() { // sin audio: avanza el tiempo para poder ver el diseño funcionando
    let t = 0, id = null, dur = 0, tick, end;
    return {
      load(d, tk, e) { this.stop(); dur = d.duration_seconds; tick = tk; end = e; t = 0; },
      play() { clearInterval(id); id = setInterval(() => { t += .25; tick?.(t); if (t >= dur) { clearInterval(id); end?.(); } }, 250); return Promise.resolve(); },
      pause() { clearInterval(id); }, seek(s) { t = s; tick?.(t); }, stop() { clearInterval(id); t = 0; }
    };
  }
};
function pickProvider(d) { return (d.audio_url || d.preview_url) ? DEMO_PROVIDERS.audio() : DEMO_PROVIDERS.simulated(); }
 
function demoStop() { demoState.provider?.stop(); demoState.provider = null; demoState.playing = false; demoState.time = 0; }
function renderDemos(c) {
  const root = demoRoot(); if (!root) return;
  demoStop();
  const list = (Array.isArray(c?.demos) ? c.demos : DEMO_SAMPLE).filter(d => d && d.title);
  demoState.list = list; demoState.index = 0; root.classList.remove("is-playing");
  if (!list.length) { root.innerHTML = `<div class="empty-state dm-empty"><h3>Aún no hay demos</h3><p>Pronto podrás escuchar un adelanto de este concierto.</p></div>`; return; }
  const total = list.reduce((s, d) => s + Number(d.duration_seconds || 0), 0);
  const bg = imageUrl(c.image_url);
  root.innerHTML = `
    <div class="dm-head"><div><h2>Demos del concierto</h2><p class="dm-sub">Escucha un adelanto de las canciones que van a cantar.</p></div><span class="dm-count"><b>${list.length}</b> ${list.length === 1 ? "demo" : "demos"}</span></div>
    <div class="dm-board">
      <div class="dm-player">
        <div class="dm-player__art dynamic-art${bg ? " has-image" : ""}"${bg ? ` style="background-image:url('${esc(bg)}')"` : ""}>
          <span class="dm-badge" id="dm-badge"></span>
          <button class="dm-play-lg" data-dm="toggle" aria-label="Reproducir o pausar">${ICO_PLAY}${ICO_PAUSE}</button>
          <div class="dm-eq" aria-hidden="true">${demoBars(16, 3)}</div>
        </div>
        <div class="dm-player__body">
          <p class="dm-now" id="dm-now"></p><p class="dm-now-sub">${esc(c.artist || "")} · ${esc(c.tour_name || "")}</p>
          <div class="dm-progress"><span id="dm-cur">0:00</span><div class="dm-bar" id="dm-bar" role="slider" tabindex="0" aria-label="Progreso" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><i id="dm-fill"></i></div><span id="dm-dur">0:00</span></div>
          <div class="dm-controls">
            <button class="dm-ico" data-dm="prev" aria-label="Anterior">${ICO_PREV}</button>
            <button class="dm-ico dm-ico--main dm-main" data-dm="toggle" aria-label="Reproducir o pausar">${ICO_PLAY}${ICO_PAUSE}</button>
            <button class="dm-ico" data-dm="next" aria-label="Siguiente">${ICO_NEXT}</button>
          </div>
          <p class="dm-status" id="dm-status" role="status"></p>
        </div>
      </div>
      <div class="dm-list-wrap">
        <div class="dm-list-head"><strong>Canciones del show</strong><span>${list.length} ${list.length === 1 ? "demo" : "demos"} · ${Math.max(1, Math.round(total / 60))} min</span></div>
        <ul class="dm-list">${list.map((d, i) => { const t = DEMO_TAGS[d.tag]; return `<li class="dm-track" data-dm-track="${i}" tabindex="0"><span class="dm-num"><span class="dm-num__n">${i + 1}</span><span class="dm-num__eq" aria-hidden="true"><i></i><i></i><i></i></span></span><div class="dm-track__main"><p class="dm-track__title">${esc(d.title)}</p><div class="dm-track__meta">${t ? `<span class="dm-tag ${t[1]}">${t[0]}</span>` : ""}<span>Demo ${String(i + 1).padStart(2, "0")}</span></div></div><span class="dm-wave" aria-hidden="true">${demoBars(22, i)}</span><span class="dm-dur">${fmtClock(d.duration_seconds || 0)}</span><button class="dm-mini" data-dm-play="${i}" aria-label="Reproducir ${esc(d.title)}">${ICO_PLAY}${ICO_PAUSE}</button></li>`; }).join("")}</ul>
        <p class="dm-note">Los demos son un adelanto. El orden final del show puede variar.</p>
      </div>
    </div>`;
  demoSelect(0, false);
}
function demoUI() {
  const root = demoRoot(), d = demoState.list[demoState.index]; if (!root || !d) return;
  const dur = Number(d.duration_seconds || 0), pct = dur ? Math.min(100, demoState.time / dur * 100) : 0;
  root.classList.toggle("is-playing", demoState.playing);
  root.querySelectorAll(".dm-track").forEach((el, i) => { const cur = i === demoState.index; el.classList.toggle("is-current", cur); el.classList.toggle("is-playing", cur && demoState.playing); });
  root.querySelector("#dm-now").textContent = d.title; root.querySelector("#dm-badge").textContent = `Demo ${String(demoState.index + 1).padStart(2, "0")} de ${demoState.list.length}`;
  root.querySelector("#dm-cur").textContent = fmtClock(demoState.time); root.querySelector("#dm-dur").textContent = fmtClock(dur);
  root.querySelector("#dm-fill").style.width = pct + "%"; root.querySelector("#dm-bar").setAttribute("aria-valuenow", Math.round(pct));
}
function demoSelect(i, autoplay = true) {
  const d = demoState.list[i]; if (!d) return;
  demoState.provider?.stop(); demoState.index = i; demoState.time = 0; demoState.playing = false; document.getElementById("dm-status").textContent = "";
  const p = demoState.provider = pickProvider(d);
  p.load(d, t => { demoState.time = t; demoUI(); }, () => { if (i < demoState.list.length - 1) demoSelect(i + 1, true); else { demoState.playing = false; demoState.time = 0; demoUI(); } }, () => { demoState.playing = false; document.getElementById("dm-status").textContent = "No pudimos reproducir este demo."; demoUI(); });
  demoUI(); if (autoplay) demoToggle(true);
}
async function demoToggle(forcePlay) {
  const p = demoState.provider; if (!p) return;
  if (demoState.playing && !forcePlay) { p.pause(); demoState.playing = false; }
  else { try { await p.play(); demoState.playing = true; } catch { demoState.playing = false; document.getElementById("dm-status").textContent = "No pudimos reproducir este demo."; } }
  demoUI();
}
function demoSeek(clientX) {
  const bar = document.getElementById("dm-bar"), d = demoState.list[demoState.index]; if (!bar || !d) return;
  const r = bar.getBoundingClientRect(), s = Math.max(0, Math.min(1, (clientX - r.left) / r.width)) * Number(d.duration_seconds || 0);
  demoState.provider?.seek(s); demoState.time = s; demoUI();
}
document.addEventListener("click", e => {
  const root = demoRoot(); if (!root || !root.contains(e.target)) return;
  const btn = e.target.closest("[data-dm]"), mini = e.target.closest("[data-dm-play]"), row = e.target.closest("[data-dm-track]"), bar = e.target.closest("#dm-bar"), n = demoState.list.length;
  if (bar) return demoSeek(e.clientX);
  if (btn) { const a = btn.dataset.dm; if (a === "toggle") demoToggle(); else if (a === "next") demoSelect((demoState.index + 1) % n); else if (a === "prev") demoSelect(demoState.time > 3 ? demoState.index : (demoState.index - 1 + n) % n); return; }
  const i = Number((mini || row)?.dataset.dmPlay ?? row?.dataset.dmTrack); if (Number.isNaN(i)) return;
  i === demoState.index ? demoToggle() : demoSelect(i);
});
document.addEventListener("keydown", e => {
  const row = e.target.closest?.("[data-dm-track]"); if (row && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); row.click(); }
  if (e.target.id === "dm-bar" && (e.key === "ArrowLeft" || e.key === "ArrowRight")) { const d = demoState.list[demoState.index], s = Math.max(0, Math.min(d.duration_seconds, demoState.time + (e.key === "ArrowRight" ? 5 : -5))); demoState.provider?.seek(s); demoState.time = s; demoUI(); }
});
 