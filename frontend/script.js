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
function art(c, className = "", extra = "") { const url = imageUrl(c?.image_url), style = url ? ` style="background-image:linear-gradient(0deg,rgba(0,0,0,.35),rgba(0,0,0,.08)),url('${esc(url)}')"` : ""; return `<div class="${className} dynamic-art${url ? " has-image" : ""}"${style} role="img" aria-label="${esc(c?.artist || "Concierto")}">${extra}</div>`; }
 
async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) }; if (token()) headers.Authorization = `Bearer ${token()}`;
  let response; try { response = await fetch(API_URL + path, { ...options, headers }); } catch { throw new Error("No fue posible conectar con la API. Verifica que el backend esté activo."); }
  const data = await response.json().catch(() => ({})); if (!response.ok) { const d = data.detail, expired = response.status === 401 && token() && !path.startsWith("/auth/"), err = new Error(expired ? "Tu sesión expiró. Inicia sesión de nuevo." : typeof d === "string" && d ? d : typeof d?.message === "string" && d.message ? d.message : Array.isArray(d) ? "Revisa los datos ingresados." : "No fue posible completar la solicitud."); err.status = response.status; err.data = data; if (expired) sessionExpired(); throw err; } return data;
}
function goTo(id) {
  if (id !== "detail" && typeof spotifyView !== "undefined" && spotifyView) spotifyClear();
  if (id !== "detail" && typeof artistBioView !== "undefined" && artistBioView) artistBioClear();
  if (id !== "detail" && typeof upcomingView !== "undefined" && upcomingView) upcomingClear();
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
/* ===== Cuenta regresiva y estado de disponibilidad =====
   Umbrales (ajustables): por tipo de boleto y por concierto completo. */
const LOW_STOCK_TYPE = 50, LOW_STOCK_TOTAL = 100;
const ICO_CLOCK = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/><path d="M12 7v5l3 2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`;
function daysUntil(c) { if (!c?.event_date) return null; const [y, m, d] = c.event_date.slice(0, 10).split("-").map(Number), n = new Date(); return Math.round((Date.UTC(y, m - 1, d) - Date.UTC(n.getFullYear(), n.getMonth(), n.getDate())) / 864e5); }
function countdownInfo(c) {
  const n = daysUntil(c); if (n === null) return null;
  if (n < 0) return { text: "Finalizado", cls: "cs--muted", past: true };
  if (n === 0) return { text: "¡Es hoy!", cls: "cs--hot" };
  if (n === 1) return { text: "Mañana", cls: "cs--hot" };
  return { text: `Faltan ${n.toLocaleString("es-CO")} días`, cls: n <= 7 ? "cs--hot" : "" };
}
/* Total de boletos: del detalle (ticket_types) o, si el listado lo trae, de c.tickets_available. null = dato desconocido. */
function totalStock(c) {
  if (Array.isArray(c?.ticket_types) && c.ticket_types.length) return c.ticket_types.reduce((s, t) => s + Number(t.quantity_available || 0), 0);
  const v = c?.tickets_available; return v === undefined || v === null || Number.isNaN(Number(v)) ? null : Number(v);
}
function stockInfo(c) {
  if (countdownInfo(c)?.past) return null; const t = totalStock(c); if (t === null) return null;
  if (t <= 0) return { text: "Agotado", cls: "cs--soldout", state: "soldout" };
  if (t <= LOW_STOCK_TOTAL) return { text: "Últimos boletos", cls: "cs--low", state: "low" };
  return null;
}
function typeStock(t) {
  const q = Number(t?.quantity_available || 0);
  if (q <= 0) return { text: "Agotado", cls: "is-out" };
  if (q <= LOW_STOCK_TYPE) return { text: `¡Quedan solo ${q.toLocaleString("es-CO")}!`, cls: "is-low" };
  return { text: `${q.toLocaleString("es-CO")} disponibles`, cls: "" };
}
function statusChips(c) {
  const cd = countdownInfo(c), st = stockInfo(c); if (!cd && !st) return "";
  return `<div class="cs-row">${st ? `<span class="cs cs--dot ${st.cls}">${st.text}</span>` : ""}${cd ? `<span class="cs ${cd.cls}">${cd.past ? "" : ICO_CLOCK}${cd.text}</span>` : ""}</div>`;
}
const soldClass = c => stockInfo(c)?.state === "soldout" ? " is-soldout" : "";
function renderStatus(c) {
  const box = document.getElementById("detail-status"); if (box) box.innerHTML = statusChips(c);
  const btn = document.querySelector('[data-nav="checkout"]'), t = ticketType(), out = !t || Number(t.quantity_available) <= 0;
  if (btn) { btn.disabled = out; btn.textContent = t && out ? "Agotado" : "Continuar"; }
}
function renderFeatured() { const rows = CONCERTS.slice(0, 6); document.getElementById("featured-grid").innerHTML = rows.length ? rows.map(c => `<article class="feature-card${soldClass(c)}" data-open="${c.id}">${art(c, "feature-card__art", statusChips(c))}<div class="feature-card__body"><p class="feature-card__title">${esc(c.artist)}</p><p class="feature-card__meta">${esc(c.venue.name)} — ${fmtDate(c.event_date)}</p></div></article>`).join("") : `<div class="empty-state collection-message"><p>No hay conciertos próximos disponibles.</p></div>`; }
function renderListing() { const rows = filteredConcerts(); document.getElementById("concert-count").textContent = `Conciertos (${rows.length})`; document.getElementById("concert-list").innerHTML = rows.length ? rows.map(c => `<article class="concert-row${soldClass(c)}" data-open="${c.id}">${art(c, "concert-row__art")}<div class="concert-row__body"><p class="concert-row__title">${esc(c.artist)}</p><p class="concert-row__sub">${esc(c.tour_name)}</p>${statusChips(c)}<div class="concert-row__meta"><span>🗓 ${fmtDate(c.event_date)} · ${fmtTime(c.event_time)}</span><span>📍 ${esc(venue(c))}</span></div></div><div class="concert-row__price"><small>Desde</small><strong>${fmtCOP(c.price_from)}</strong></div><button class="btn btn--primary btn--sm" data-open="${c.id}">Ver evento</button></article>`).join("") : `<div class="empty-state"><h3>No encontramos conciertos</h3><p>Prueba con otros filtros o términos de búsqueda.</p></div>`; }
 
async function openConcert(id) {
  spotifyClear(); loadUpcomingEvents(Number(id)); loadArtistBio(Number(id)); // la biografía va por su cuenta: si Wikipedia falla, el detalle y la compra siguen igual
  state.selectedConcertId = Number(id); state.selectedConcert = null; state.selectedTicketTypeId = null; state.qty = 1; goTo("detail"); document.querySelector(".detail-title").textContent = "Cargando concierto..."; document.querySelector(".detail-sub").textContent = ""; document.getElementById("ticket-options").innerHTML = "";
  try { const c = await api(`/concerts/${id}`); state.selectedConcert = c; state.selectedTicketTypeId = (c.ticket_types.find(t => t.quantity_available > 0) || c.ticket_types[0])?.id ?? null; renderDetail(); } catch (error) { document.querySelector(".detail-title").textContent = "No fue posible cargar el concierto"; document.querySelector(".detail-sub").textContent = error.message; }
}
function renderDetail() {
  const c = concert(); if (!c) return; const poster = document.querySelector(".detail-poster"), url = imageUrl(c.image_url); poster.className = `detail-poster dynamic-art${url ? " has-image" : ""}`; poster.style.backgroundImage = url ? `linear-gradient(0deg,rgba(0,0,0,.62),transparent 60%),url("${url.replace(/"/g, "%22")}")` : ""; poster.querySelector(".poster__tag").textContent = c.artist; poster.querySelector(".poster__tag2").textContent = c.tour_name; document.querySelector(".detail-title").textContent = c.artist; document.querySelector(".detail-sub").textContent = `${c.tour_name} · ${c.genre}`;
  document.querySelector(".meta-info").innerHTML = `<p><span class="dot">•</span> ${fmtDate(c.event_date, true)} · ${fmtTime(c.event_time)}</p><p><span class="dot">•</span> ${esc(venue(c))}</p>${c.venue.address ? `<p><span class="dot">•</span> ${esc(c.venue.address)}</p>` : ""}<p><span class="dot">•</span> Capacidad: ${Number(c.venue.capacity || 0).toLocaleString("es-CO")} personas</p>`; document.querySelector(".detail-blurb").textContent = c.description || "Información adicional no disponible.";
  document.getElementById("stage-zones").innerHTML = c.ticket_types.map((t, i) => `<div class="stage-zone" style="width:${Math.min(96, 42 + i * 18)}%">${esc(t.name)}</div>`).join(""); document.getElementById("ticket-options").innerHTML = c.ticket_types.length ? c.ticket_types.map(t => `<label class="ticket-option ${t.id === state.selectedTicketTypeId ? "is-selected" : ""} ${t.quantity_available < 1 ? "is-disabled" : ""}" data-ticket-type="${t.id}"><span class="ticket-option__left"><span class="radio-outer"><span class="radio-inner"></span></span><span>${esc(t.name)}<small class="${typeStock(t).cls}">${typeStock(t).text}</small></span></span><span class="ticket-option__price">${fmtCOP(t.price)}</span></label>`).join("") : `<p class="form-message is-error">No hay tipos de boleto disponibles.</p>`; document.getElementById("qty-val").textContent = state.qty; document.querySelector('[data-nav="checkout"]').disabled = !ticketType(); renderStatus(c); loadSpotify(c);
}
function renderCheckout() {
  const c = concert(), t = ticketType(); if (!c || !t) return goTo("listing"); const subtotal = Number(t.price) * state.qty, fee = 6000 * state.qty, total = subtotal + fee, box = document.querySelector(".summary-card"); box.querySelector(".summary-art").outerHTML = art(c, "thumb summary-art"); box.querySelector(".summary-item__title").textContent = c.artist; box.querySelector(".summary-item__sub").textContent = c.tour_name; const meta = box.querySelectorAll(".summary-item__meta"); meta[0].textContent = `${fmtDate(c.event_date)} · ${fmtTime(c.event_time)}`; meta[1].textContent = venue(c); const rows = box.querySelectorAll(".summary-rows div"); rows[0].querySelector("dd").textContent = t.name; document.getElementById("co-qty").textContent = state.qty; rows[2].querySelector("dd").textContent = fmtCOP(t.price); document.getElementById("co-subtotal").textContent = fmtCOP(subtotal); document.getElementById("co-service-fee").textContent = fmtCOP(fee); document.getElementById("co-total").textContent = fmtCOP(total); document.getElementById("pay-button-label").textContent = `Pagar ${fmtCOP(total)}`;
}
function renderSuccess() { const o = state.lastOrder; if (!o) return; document.getElementById("success-order").innerHTML = `<div class="order-card__head"><span>Orden #${esc(o.order_code)}</span><span class="order-card__date">${fmtDateTime(o.created_at)}</span></div><div class="summary-item">${art(o.concert, "thumb")}<div><p class="summary-item__title">${esc(o.concert.artist)}</p><p class="summary-item__sub">${esc(o.concert.tour_name)}</p><p class="summary-item__meta">${fmtDate(o.concert.event_date)} · ${fmtTime(o.concert.event_time)}</p><p class="summary-item__meta">${esc(venue(o.concert))}</p></div></div><div class="order-card__divider"></div><div class="order-card__row"><span>Boletos:</span><span>${o.items.map(i => `${i.quantity} × ${esc(i.ticket_type_name)}`).join(", ")}</span></div><div class="order-card__row"><span>Subtotal:</span><span>${fmtCOP(o.subtotal)}</span></div><div class="order-card__row"><span>Cargo por servicio:</span><span>${fmtCOP(o.service_fee)}</span></div><div class="order-card__row"><span>Estado:</span><span>${o.status === "confirmed" ? "Confirmada" : "Cancelada"}</span></div><div class="order-card__row order-card__row--total"><span>Total:</span><span>${fmtCOP(o.total)}</span></div>`; }
 
function setAuthView(view) { const reg = view === "register"; document.getElementById("login-form").hidden = reg; document.getElementById("register-form").hidden = !reg; document.getElementById("auth-title").textContent = reg ? "Crea tu cuenta" : "Inicia sesión para continuar"; }
function resetAuthForms() { document.getElementById("login-form").reset(); document.getElementById("register-form").reset(); message("login-message", "", false); message("register-message", "", false); }
function openAuth(next = null) { resetAuthForms(); state.pendingScreen = next; setAuthView("login"); document.getElementById("auth-modal").hidden = false; document.getElementById("login-email").focus(); }
function closeAuth() { document.getElementById("auth-modal").hidden = true; state.pendingScreen = null; resetAuthForms(); }
function sessionExpired() { // el servidor rechazó el token (401): limpiar la sesión y pedir login sin perder la pantalla actual
  localStorage.removeItem("soundpass_token"); state.currentUser = null; renderAccount();
  const screen = document.querySelector("[data-screen].is-active")?.id.replace("screen-", ""); openAuth(["mytickets", "checkout"].includes(screen) ? screen : null);
  message("login-message", "Tu sesión expiró. Inicia sesión de nuevo.");
}
function message(id, text, error = true) { const el = document.getElementById(id); el.textContent = text; el.classList.toggle("is-error", error); }
function renderAccount() { const b = document.getElementById("account-button"), logged = Boolean(state.currentUser); b.classList.toggle("is-signed-in", logged); b.title = logged ? `Cuenta de ${state.currentUser.full_name}` : "Iniciar sesión"; b.setAttribute("aria-label", b.title); if (logged) document.getElementById("account-greeting").textContent = `Hola, ${state.currentUser.full_name}`; }
async function restoreSession() { if (!token()) return; try { state.currentUser = await api("/auth/me"); renderAccount(); } catch (error) { if (error.status === 401) localStorage.removeItem("soundpass_token"); } }
async function loadTickets() { if (!token()) return openAuth("mytickets"); const list = document.getElementById("ticket-list"); list.innerHTML = `<div class="empty-state"><p>Cargando tus boletos...</p></div>`; try { TICKETS = await api("/orders/me"); renderTickets(); } catch (error) { list.innerHTML = `<div class="empty-state"><p>${esc(error.message)}</p></div>`; } }
function renderTickets() { const now = new Date(), rows = TICKETS.filter(o => state.activeTicketTab === "proximos" ? o.status === "confirmed" && new Date(`${o.concert.event_date}T23:59:59`) >= now : o.status === "cancelled" || new Date(`${o.concert.event_date}T23:59:59`) < now), list = document.getElementById("ticket-list"); if (!rows.length) { list.innerHTML = `<div class="empty-state"><h3>No hay boletos en esta sección</h3><p>Explora los conciertos y encuentra tu próxima experiencia en vivo.</p><button class="btn btn--primary" data-nav="listing">Ver conciertos</button></div>`; return; } list.innerHTML = rows.map(o => { const c = o.concert, q = o.items.reduce((s, i) => s + i.quantity, 0), cancelled = o.status === "cancelled"; return `<article class="ticket-card">${art(c, "ticket-card__art")}<div class="ticket-card__body"><p class="ticket-card__title">${esc(c.artist)}</p><p class="ticket-card__sub">${esc(c.tour_name)}</p><div class="ticket-card__meta"><span>🗓 ${fmtDate(c.event_date)} · ${fmtTime(c.event_time)}</span><span>📍 ${esc(venue(c))}</span></div><div class="ticket-card__foot"><span>${q} boleto${q === 1 ? "" : "s"}</span><span>${o.items.map(i => esc(i.ticket_type_name)).join(", ")}</span><span>Orden #${esc(o.order_code)}</span></div></div><div class="ticket-card__actions"><span class="badge ${cancelled ? "badge--cancelled" : "badge--confirmed"}">${cancelled ? "Cancelado" : "Confirmado"}</span><button class="btn btn--outline btn--sm" data-order-detail="${o.id}">Ver detalle</button>${cancelled ? "" : `<button class="btn btn--danger-outline btn--sm" data-cancel-order="${o.id}">Cancelar compra</button>`}</div></article>`; }).join(""); }
function openCancelModal(id) { const o = TICKETS.find(x => x.id === Number(id)); if (!o) return; state.orderToCancel = o; const q = o.items.reduce((s, i) => s + i.quantity, 0); document.getElementById("cancel-ticket").innerHTML = `${art(o.concert, "thumb")}<div><p class="summary-item__title">${esc(o.concert.artist)}</p><p class="summary-item__meta">${fmtDate(o.concert.event_date)} · ${esc(o.concert.venue.name)}</p><p class="summary-item__meta">${q} boleto${q === 1 ? "" : "s"} · ${o.items.map(i => esc(i.ticket_type_name)).join(", ")}</p></div>`; document.getElementById("cancel-modal").hidden = false; }
async function confirmCancellation() { if (!state.orderToCancel) return; const b = document.getElementById("modal-confirm"); b.disabled = true; b.textContent = "Cancelando..."; try { const o = await api(`/orders/${state.orderToCancel.id}/cancel`, { method: "POST" }); document.getElementById("cancel-modal").hidden = true; document.getElementById("cancelled-order-code").textContent = `Orden #${o.order_code}`; document.getElementById("cancelled-order-date").textContent = `Cancelada: ${fmtDateTime(o.cancelled_at)}`; state.orderToCancel = null; goTo("cancelled"); } catch (e) { alert(e.message); } finally { b.disabled = false; b.textContent = "Sí, cancelar compra"; } }
 
document.addEventListener("click", e => { const nav = e.target.closest("[data-nav]"), open = e.target.closest("[data-open]"), type = e.target.closest("[data-ticket-type]"), view = e.target.closest("[data-auth-view]"), cancel = e.target.closest("[data-cancel-order]"); if (nav && nav.dataset.nav !== "checkout") goTo(nav.dataset.nav); if (open) openConcert(open.dataset.open); if (type && !type.classList.contains("is-disabled")) { state.selectedTicketTypeId = Number(type.dataset.ticketType); state.qty = Math.min(state.qty, ticketType()?.quantity_available || 1); renderDetail(); } if (view) setAuthView(view.dataset.authView); if (cancel) openCancelModal(cancel.dataset.cancelOrder); });
document.getElementById("f-city").onchange = e => { state.filters.city = e.target.value; renderListing(); }; document.getElementById("f-date").onchange = e => { state.filters.date = e.target.value; renderListing(); }; document.getElementById("genre-filters").onchange = () => { state.filters.genres = [...document.querySelectorAll("#genre-filters input:checked")].map(x => x.value); renderListing(); }; document.getElementById("sort-select").onchange = e => { state.filters.sort = e.target.value; renderListing(); }; document.getElementById("concert-search").oninput = e => { state.filters.search = e.target.value; renderListing(); };
document.getElementById("account-button").onclick = () => { if (!state.currentUser) return openAuth(); const m = document.getElementById("account-menu"); m.hidden = !m.hidden; }; document.getElementById("account-tickets").onclick = () => { document.getElementById("account-menu").hidden = true; goTo("mytickets"); }; document.getElementById("logout-button").onclick = () => { localStorage.removeItem("soundpass_token"); state.currentUser = null; document.getElementById("account-menu").hidden = true; renderAccount(); goTo("home"); }; document.addEventListener("click", e => { if (!e.target.closest(".topbar__right")) document.getElementById("account-menu").hidden = true; });
document.getElementById("auth-close").onclick = closeAuth; document.getElementById("auth-modal").onclick = e => { if (e.target.id === "auth-modal") closeAuth(); }; document.getElementById("qty-minus").onclick = () => { state.qty = Math.max(1, state.qty - 1); renderDetail(); }; document.getElementById("qty-plus").onclick = () => { state.qty = Math.min(10, ticketType()?.quantity_available || 1, state.qty + 1); renderDetail(); }; document.querySelector('[data-nav="checkout"]').onclick = e => { e.preventDefault(); if (!ticketType()) return; token() ? goTo("checkout") : openAuth("checkout"); };
document.querySelectorAll(".payment-option").forEach(o => o.onclick = () => { document.querySelectorAll(".payment-option").forEach(x => x.classList.remove("is-selected")); o.classList.add("is-selected"); o.querySelector("input").checked = true; });
document.getElementById("login-form").onsubmit = async e => { e.preventDefault(); const btn = e.currentTarget.querySelector("[type=submit]"); if (btn.disabled) return; btn.disabled = true; message("login-message", "", false); const f = new FormData(e.currentTarget); try { const r = await api("/auth/login", { method: "POST", body: JSON.stringify({ email: f.get("email"), password: f.get("password") }) }); localStorage.setItem("soundpass_token", r.access_token); state.currentUser = await api("/auth/me"); renderAccount(); const next = state.pendingScreen; closeAuth(); if (next) goTo(next); } catch (err) { message("login-message", err.message); } finally { btn.disabled = false; } };
document.getElementById("register-form").onsubmit = async e => { e.preventDefault(); const btn = e.currentTarget.querySelector("[type=submit]"); if (btn.disabled) return; btn.disabled = true; message("register-message", "", false); const f = new FormData(e.currentTarget); try { await api("/auth/register", { method: "POST", body: JSON.stringify({ full_name: f.get("full_name"), email: f.get("email"), password: f.get("password") }) }); document.getElementById("login-email").value = f.get("email"); setAuthView("login"); message("login-message", "Cuenta creada. Ahora inicia sesión.", false); } catch (err) { message("register-message", err.message); } finally { btn.disabled = false; } };
document.getElementById("pay-button").onclick = async () => { if (!token()) return openAuth("checkout"); const b = document.getElementById("pay-button"), c = concert(), t = ticketType(), text = document.querySelector(".payment-option.is-selected").textContent, payment = text.includes("PSE") ? "pse" : text.includes("Nequi") ? "nequi" : "card"; b.disabled = true; document.getElementById("pay-button-label").textContent = "Procesando compra…"; try { state.lastOrder = await api("/orders", { method: "POST", body: JSON.stringify({ concert_id: c.id, payment_method: payment, items: [{ ticket_type_id: t.id, quantity: state.qty }] }) }); renderSuccess(); goTo("success"); } catch (err) { alert(err.message); } finally { b.disabled = false; renderCheckout(); } };
// HU-48: authenticated PDF ticket download.
document.getElementById("download-receipt").onclick = async function () {
  const button = this;
  if (button.disabled) return;

  const order = state.lastOrder;
  const accessToken = token();

  if (!order?.id) {
    alert("No hay una orden disponible para descargar.");
    return;
  }

  if (!accessToken) {
    alert("Inicia sesión para descargar tus boletas.");
    openAuth();
    return;
  }

  if (order.status !== "confirmed") {
    alert("Solo puedes descargar boletas de órdenes confirmadas.");
    return;
  }

  const originalContent = button.innerHTML;
  const originalDisabled = button.disabled;
  const originalBusy = button.getAttribute("aria-busy");

  button.disabled = true;
  button.textContent = "Descargando...";
  button.setAttribute("aria-busy", "true");

  let objectUrl = null;

  try {
    let response;

    try {
      response = await fetch(
        `${API_URL}/orders/${encodeURIComponent(order.id)}/tickets/pdf`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${accessToken}`,
            Accept: "application/pdf",
          },
          cache: "no-store",
        }
      );
    } catch {
      throw new Error(
        "No fue posible conectar con el servidor. Intenta nuevamente."
      );
    }

    if (!response.ok) {
      const messages = {
        401: "Tu sesión venció. Inicia sesión nuevamente.",
        403: "No tienes permiso para descargar estas boletas.",
        404: "La orden no está disponible o no pertenece a tu cuenta.",
        409: "La orden no permite descargar boletas. Puede estar cancelada.",
      };

      let errorMessage = messages[response.status];

      if (!errorMessage && response.status >= 500) {
        errorMessage =
          "No fue posible generar las boletas. Intenta más tarde.";
      }

      if (!errorMessage) {
        const data = await response.json().catch(() => null);
        errorMessage =
          typeof data?.detail === "string"
            ? data.detail
            : "No fue posible descargar las boletas.";
      }

      throw new Error(errorMessage);
    }

    const contentType = (
      response.headers.get("Content-Type") || ""
    ).split(";")[0].trim().toLowerCase();

    if (contentType !== "application/pdf") {
      throw new Error("El servidor no devolvió un archivo PDF.");
    }

    const blob = await response.blob();

    if (!blob.size || (await blob.slice(0, 5).text()) !== "%PDF-") {
      throw new Error("El archivo recibido no es un PDF válido.");
    }

    objectUrl = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = `soundpass-orden-${order.id}.pdf`;
    link.hidden = true;

    document.body.appendChild(link);
    try {
      link.click();
    } finally {
      link.remove();
    }
  } catch (error) {
    alert(error.message || "No fue posible descargar las boletas.");
  } finally {
    // Dar tiempo al navegador para iniciar la descarga.
    if (objectUrl) {
      const urlToRelease = objectUrl;
      setTimeout(() => URL.revokeObjectURL(urlToRelease), 60000);
    }

    button.innerHTML = originalContent;
    button.disabled = originalDisabled;

    if (originalBusy === null) {
      button.removeAttribute("aria-busy");
    } else {
      button.setAttribute("aria-busy", originalBusy);
    }
  }
};
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
 
 
/* ===== Demos del concierto: reproductor oficial de Spotify =====
   GET /concerts/{id}/spotify  (misma base de API que el resto: API_URL)
   -> { status: "ok" | "not_found" | "ambiguous", message?, artist?: { name, embed_url, spotify_url } }
   ok               -> iframe oficial + enlace "Abrir en Spotify"
   not_found/ambig. -> solo el mensaje, sin reproductor
   error HTTP/red   -> aviso con "Reintentar"; nunca bloquea el detalle ni la compra
   El iframe se retira al salir del detalle y al cambiar de concierto. */
var spotifyView = { concertId: null, req: 0, controller: null };
const SPOTIFY_URL = /^https:\/\/open\.spotify\.com\//i;
const spotifyRoot = () => document.getElementById("concert-demos");
function spotifyClear() {
  spotifyView.req++; spotifyView.controller?.abort(); spotifyView.controller = null; spotifyView.concertId = null;
  const root = spotifyRoot(); if (!root) return;
  root.querySelectorAll("iframe").forEach(f => { f.src = "about:blank"; f.remove(); });
  root.innerHTML = "";
}
const spotifyHead = (name, extra = "") => `<div class="dm-head"><div><h2>Demos del concierto</h2><p class="dm-sub">Escucha a ${esc(name)} en Spotify antes del show.</p></div>${extra}</div>`;
const spotifyNotice = (name, text, retry = false) => spotifyHead(name) + `<div class="dm-card dm-notice" role="status"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/><path d="M12 8v5M12 16.5v.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg><p>${esc(text)}</p>${retry ? `<button class="btn btn--sm dm-retry" type="button" data-spotify-retry>Reintentar</button>` : ""}</div>`;
async function loadSpotify(c, force = false) {
  const root = spotifyRoot(); if (!root || !c) return;
  if (!force && spotifyView.concertId === c.id) return; // renderDetail se repite al cambiar cantidad o zona: no recargar el iframe
  spotifyClear(); spotifyView.concertId = c.id;
  const req = spotifyView.req, controller = spotifyView.controller = new AbortController();
  root.innerHTML = spotifyHead(c.artist) + `<div class="dm-card dm-loading" role="status" aria-live="polite"><div class="dm-skel"></div><p>Cargando reproductor de Spotify...</p></div>`;
  try {
    const data = await api(`/concerts/${c.id}/spotify`, { signal: controller.signal });
    if (req !== spotifyView.req) return; // el usuario ya cambió de concierto o salió del detalle
    const a = data?.artist || {}, name = a.name || c.artist;
    if (data?.status === "ok" && SPOTIFY_URL.test(a.embed_url || "")) {
      const link = SPOTIFY_URL.test(a.spotify_url || "") ? `<a class="btn btn--primary btn--sm dm-open" href="${esc(a.spotify_url)}" target="_blank" rel="noopener noreferrer">Abrir en Spotify</a>` : "";
      root.innerHTML = spotifyHead(name, link) + `<div class="dm-card dm-embed"><iframe src="${esc(a.embed_url)}" title="Reproductor de Spotify: ${esc(name)}" width="100%" height="352" loading="lazy" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"></iframe></div>`;
    } else if (data?.status === "not_found" || data?.status === "ambiguous") {
      root.innerHTML = spotifyNotice(c.artist, data.message || "No pudimos encontrar a este artista en Spotify.");
    } else {
      root.innerHTML = spotifyNotice(c.artist, "No pudimos cargar el reproductor de Spotify. Puedes continuar con tu compra con normalidad.", true);
    }
  } catch (error) {
    if (req !== spotifyView.req) return;
    root.innerHTML = spotifyNotice(c.artist, "No pudimos cargar el reproductor de Spotify. Puedes continuar con tu compra con normalidad.", true);
  }
}
document.addEventListener("click", e => { if (e.target.closest("[data-spotify-retry]")) loadSpotify(concert(), true); });
 
/* ===== Sobre el artista: biografía desde Wikipedia (es) =====
   GET /concerts/{id}/artist-bio  (misma base y mismo api() que el resto)
   -> { concert_id, artist, status: "ok"|"not_found"|"ambiguous"|"unavailable", biography?, article_title?, article_url?, source }
   HTTP 503 / unavailable -> aviso temporal con "Reintentar" · 404 -> concierto inexistente
   Todo lo que viene de la API se inserta con textContent (nunca innerHTML).
   Una respuesta solo se pinta si sigue siendo la del concierto abierto (req + id). */
var artistBioView = { concertId: null, req: 0, controller: null, loading: false };
const artistBioRoot = () => document.getElementById("artist-bio");
const artistBioBody = () => document.getElementById("artist-bio-body");
const ARTIST_BIO_MSG = {
  loading: "Cargando información del artista…",
  not_found: "No hay una biografía disponible para este artista.",
  ambiguous: "No pudimos identificar con certeza la biografía de este artista.",
  unavailable: "La información del artista no está disponible en este momento.",
  concert_not_found: "No se encontró el concierto.",
  error: "No se pudo cargar la información del artista."
};
function artistBioClear() {
  artistBioView.req++; artistBioView.controller?.abort(); artistBioView.controller = null; artistBioView.concertId = null; artistBioView.loading = false;
  const body = artistBioBody(), root = artistBioRoot(); if (body) { body.replaceChildren(); body.setAttribute("aria-busy", "false"); } if (root) root.hidden = true;
}
/* Solo https://es.wikipedia.org/wiki/... ; cualquier otra cosa devuelve null y no se muestra enlace */
function wikipediaUrl(value) {
  if (typeof value !== "string") return null;
  try { const u = new URL(value.trim()); return u.protocol === "https:" && u.hostname === "es.wikipedia.org" && !u.port && !u.username && !u.password && u.pathname.startsWith("/wiki/") ? u.href : null; } catch { return null; }
}
function artistBioNode(tag, className, text) { const el = document.createElement(tag); if (className) el.className = className; if (text !== undefined) el.textContent = text; return el; }
function renderArtistBio(kind, opts = {}) {
  const body = artistBioBody(); if (!body) return;
  body.setAttribute("aria-busy", kind === "loading" ? "true" : "false"); body.replaceChildren();
  if (kind === "loading") { body.append(artistBioNode("div", "ab-skel"), artistBioNode("p", "ab-status", ARTIST_BIO_MSG.loading)); body.classList.add("is-loading"); body.classList.remove("is-notice"); return; }
  body.classList.remove("is-loading");
  if (kind === "ok") {
    body.classList.remove("is-notice"); body.append(artistBioNode("p", "ab-text", opts.biography));
    if (opts.url) { const a = artistBioNode("a", "ab-source", "Fuente: Wikipedia · Leer más"); a.href = opts.url; a.target = "_blank"; a.rel = "noopener noreferrer"; const wrap = artistBioNode("p", "ab-source-row"); wrap.append(a); body.append(wrap); }
    return;
  }
  body.classList.add("is-notice"); body.append(artistBioNode("p", "ab-status", opts.text));
  if (opts.retry) { const b = artistBioNode("button", "btn btn--sm ab-retry", "Reintentar"); b.type = "button"; b.dataset.artistBioRetry = ""; body.append(b); }
}
async function loadArtistBio(id, force = false) {
  const root = artistBioRoot(); if (!root || !Number.isInteger(id) || id <= 0) return;
  if (!force && artistBioView.concertId === id) return; // ya cargada o en curso: sin peticiones duplicadas
  if (force && artistBioView.loading) return;
  artistBioClear(); artistBioView.concertId = id; artistBioView.loading = true;
  const req = artistBioView.req, controller = artistBioView.controller = new AbortController(), current = () => req === artistBioView.req && state.selectedConcertId === id;
  root.hidden = false; renderArtistBio("loading");
  try {
    const data = await api(`/concerts/${id}/artist-bio`, { signal: controller.signal });
    if (!current()) return; // llegó tarde: el usuario ya está en otro concierto o salió del detalle
    artistBioView.loading = false;
    if (!data || typeof data !== "object" || Number(data.concert_id) !== id) return renderArtistBio("error", { text: ARTIST_BIO_MSG.error, retry: true });
    const bio = typeof data.biography === "string" ? data.biography.trim() : "";
    if (data.status === "ok") bio ? renderArtistBio("ok", { biography: bio, url: wikipediaUrl(data.article_url) }) : renderArtistBio("notice", { text: ARTIST_BIO_MSG.not_found });
    else if (data.status === "not_found" || data.status === "ambiguous") renderArtistBio("notice", { text: ARTIST_BIO_MSG[data.status] });
    else if (data.status === "unavailable") renderArtistBio("notice", { text: ARTIST_BIO_MSG.unavailable, retry: true });
    else renderArtistBio("error", { text: ARTIST_BIO_MSG.error, retry: true });
  } catch (error) {
    if (error?.name === "AbortError" || !current()) return; // cancelar no es un error
    artistBioView.loading = false;
    if (error.status === 404) renderArtistBio("notice", { text: ARTIST_BIO_MSG.concert_not_found });
    else if (error.status === 503 || error.data?.status === "unavailable") renderArtistBio("notice", { text: ARTIST_BIO_MSG.unavailable, retry: true });
    else renderArtistBio("error", { text: ARTIST_BIO_MSG.error, retry: true });
  }
}
document.addEventListener("click", e => { const b = e.target.closest("[data-artist-bio-retry]"); if (!b || b.disabled) return; b.disabled = true; loadArtistBio(state.selectedConcertId, true); });
 
/* ===== Próximos conciertos del artista (Ticketmaster) =====
   GET /concerts/{id}/upcoming-events  (misma base y mismo api() que el resto)
   -> { concert_id, artist, source: "ticketmaster", status: "ok"|"no_events"|"not_found"|"ambiguous", events: [{ id, date, time, timezone, city, country, venue }], message? }
   Solo informativo: sin enlaces ni botones de compra; las fechas no implican entradas en SoundPass.
   La API key vive solo en el backend (que cachea 15 min): una consulta por apertura del detalle, sin sondeos.
   La hora ya es la local del evento: no se convierte a la zona del navegador. La fecha se formatea como día de calendario (fmtDate, UTC).
   Todo lo que viene de la API se inserta con textContent. */
var upcomingView = { concertId: null, req: 0, controller: null };
const upcomingRoot = () => document.getElementById("upcoming-events");
const upcomingBody = () => document.getElementById("upcoming-events-body");
const UPCOMING_MSG = {
  loading: "Cargando próximos conciertos…",
  no_events: "No hay próximos conciertos registrados para este artista.",
  not_found: "No encontramos información de fechas para este artista.",
  ambiguous: "No pudimos identificar con certeza a este artista para mostrar sus fechas.",
  unavailable: "La información de próximos conciertos no está disponible en este momento.",
  concert_not_found: "No se encontró el concierto.",
  error: "No se pudo cargar la información de próximos conciertos."
};
function upcomingClear() {
  upcomingView.req++; upcomingView.controller?.abort(); upcomingView.controller = null; upcomingView.concertId = null;
  const body = upcomingBody(), root = upcomingRoot(); if (body) { body.replaceChildren(); body.setAttribute("aria-busy", "false"); body.className = "ue-card"; } if (root) root.hidden = true;
}
const upcomingText = v => typeof v === "string" && v.trim() ? v.trim() : "";
function upcomingNode(tag, className, text) { const el = document.createElement(tag); if (className) el.className = className; if (text !== undefined) el.textContent = text; return el; }
function renderUpcoming(kind, opts = {}) {
  const body = upcomingBody(); if (!body) return;
  body.setAttribute("aria-busy", kind === "loading" ? "true" : "false"); body.replaceChildren(); body.className = "ue-card";
  if (kind === "loading") { body.classList.add("is-loading"); body.append(upcomingNode("div", "ue-skel"), upcomingNode("p", "ue-status", UPCOMING_MSG.loading)); return; }
  if (kind === "notice") { body.classList.add("is-notice"); body.append(upcomingNode("p", "ue-status", opts.text)); return; }
  const list = upcomingNode("ul", "ue-list");
  opts.events.forEach(ev => {
    const li = upcomingNode("li", "ue-item"), when = upcomingNode("div", "ue-when");
    when.append(upcomingNode("strong", "ue-date", fmtDate(ev.date, true)), upcomingNode("span", "ue-time", ev.time ? `${fmtTime(ev.time)} · hora local` : "Hora por confirmar"));
    li.append(when);
    const where = upcomingNode("div", "ue-where"), place = [upcomingText(ev.city), upcomingText(ev.country)].filter(Boolean).join(", "), venueName = upcomingText(ev.venue);
    if (venueName) where.append(upcomingNode("strong", "ue-venue", venueName));
    if (place) where.append(upcomingNode("span", "ue-place", place));
    if (where.childNodes.length) li.append(where);
    list.append(li);
  });
  body.append(list, upcomingNode("p", "ue-note", "Las fechas son informativas y no implican disponibilidad de entradas en SoundPass."), upcomingNode("p", "ue-source", "Fuente: Ticketmaster · Información de fechas"));
}
async function loadUpcomingEvents(id) {
  const root = upcomingRoot(); if (!root || !Number.isInteger(id) || id <= 0) return;
  if (upcomingView.concertId === id) return; // ya cargada o en curso: sin consultas duplicadas ni continuas
  upcomingClear(); upcomingView.concertId = id;
  const req = upcomingView.req, controller = upcomingView.controller = new AbortController(), current = () => req === upcomingView.req && state.selectedConcertId === id;
  root.hidden = false; renderUpcoming("loading");
  try {
    const data = await api(`/concerts/${id}/upcoming-events`, { signal: controller.signal });
    if (!current()) return; // respuesta tardía de otro concierto: se descarta
    if (!data || typeof data !== "object" || Number(data.concert_id) !== id) return renderUpcoming("notice", { text: UPCOMING_MSG.error });
    const msg = upcomingText(data.message);
    if (data.status === "ok") {
      const events = (Array.isArray(data.events) ? data.events : []).filter(ev => ev && typeof ev === "object" && /^\d{4}-\d{2}-\d{2}/.test(String(ev.date || ""))).slice(0, 10); // mismo orden recibido
      events.length ? renderUpcoming("list", { events }) : renderUpcoming("notice", { text: msg || UPCOMING_MSG.no_events });
    } else if (data.status === "no_events" || data.status === "not_found" || data.status === "ambiguous") renderUpcoming("notice", { text: msg || UPCOMING_MSG[data.status] });
    else renderUpcoming("notice", { text: UPCOMING_MSG.error });
  } catch (error) {
    if (error?.name === "AbortError" || !current()) return; // cancelar no es un error
    renderUpcoming("notice", { text: error.status === 404 ? UPCOMING_MSG.concert_not_found : error.status === 502 || error.status === 503 ? UPCOMING_MSG.unavailable : UPCOMING_MSG.error });
  }
}
 
