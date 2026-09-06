const API_URL = "http://127.0.0.1:8000";
const CONCERTS = [
  { id: "weeknd", apiId: 1, artist: "The Weeknd", tour: "After Hours Tour", date: "15 Jun 2025", time: "8:00 p.m.", venue: "Movistar Arena, Bogotá", priceFrom: 120000, art: "art--weeknd", thumb: "thumb--weeknd", ticketTypes: [{ id: "general", apiId: 1, label: "General", price: 120000 }, { id: "preferencial", apiId: 2, label: "Preferencial", price: 180000 }, { id: "vip", apiId: 3, label: "VIP", price: 250000 }] },
  { id: "dragons", apiId: 2, artist: "Imagine Dragons", tour: "LOOM World Tour", date: "22 Jun 2025", time: "8:00 p.m.", venue: "El Campín, Bogotá", priceFrom: 150000, art: "art--dragons", thumb: "thumb--dragons", ticketTypes: [{ id: "general", apiId: 4, label: "General", price: 150000 }, { id: "preferencial", apiId: 5, label: "Preferencial", price: 210000 }, { id: "vip", apiId: 6, label: "VIP", price: 290000 }] },
  { id: "dualipa", apiId: 3, artist: "Dua Lipa", tour: "Radical Optimism Tour", date: "05 Jul 2025", time: "8:00 p.m.", venue: "Movistar Arena, Bogotá", priceFrom: 110000, art: "art--dualipa", thumb: "thumb--dualipa", ticketTypes: [{ id: "general", apiId: 7, label: "General", price: 110000 }, { id: "preferencial", apiId: 8, label: "Preferencial", price: 165000 }, { id: "vip", apiId: 9, label: "VIP", price: 230000 }] },
];
let TICKETS = [];
const state = { selectedConcertId: "weeknd", selectedTicketTypeId: "preferencial", qty: 2, serviceFee: 12000, currentUser: null, pendingScreen: null };
const fmtCOP = (n) => "$" + Number(n).toLocaleString("es-CO");
const token = () => localStorage.getItem("soundpass_token");
const concert = () => CONCERTS.find((c) => c.id === state.selectedConcertId);
const ticketType = () => concert().ticketTypes.find((t) => t.id === state.selectedTicketTypeId);

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token()) headers.Authorization = `Bearer ${token()}`;
  const response = await fetch(API_URL + path, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "No fue posible completar la solicitud.");
  return data;
}
function goTo(id) {
  document.querySelectorAll("[data-screen]").forEach((el) => el.classList.toggle("is-active", el.id === `screen-${id}`));
  document.querySelectorAll(".primary-nav__link[data-active-on]").forEach((el) => el.classList.toggle("is-active", el.dataset.activeOn.split(",").includes(id)));
  if (id === "checkout") renderCheckout(); if (id === "mytickets") loadTickets(); window.scrollTo({ top: 0, behavior: "smooth" });
}
function renderFeatured() { document.getElementById("featured-grid").innerHTML = CONCERTS.map((c) => `<article class="feature-card" data-open="${c.id}"><div class="feature-card__art ${c.art}"></div><div class="feature-card__body"><p class="feature-card__title">${c.artist}</p><p class="feature-card__meta">${c.venue.split(",")[0]} — ${c.date}</p></div></article>`).join(""); }
function renderListing() { document.getElementById("concert-list").innerHTML = CONCERTS.map((c) => `<article class="concert-row" data-open="${c.id}"><div class="concert-row__art ${c.art}"></div><div class="concert-row__body"><p class="concert-row__title">${c.artist}</p><p class="concert-row__sub">${c.tour}</p><div class="concert-row__meta"><span>🗓 ${c.date} · ${c.time}</span><span>📍 ${c.venue}</span></div></div><div class="concert-row__price"><small>Desde</small><strong>${fmtCOP(c.priceFrom)}</strong></div><button class="btn btn--primary btn--sm" data-open="${c.id}">Ver evento</button></article>`).join(""); }
function renderDetail() {
  const c = concert(), poster = document.querySelector(".detail-poster"); document.querySelector(".detail-title").textContent = c.artist; document.querySelector(".detail-sub").textContent = c.tour;
  poster.className = `detail-poster poster--${c.id}`; poster.querySelector(".poster__tag").textContent = c.artist.toUpperCase(); poster.querySelector(".poster__tag2").textContent = c.tour.toUpperCase();
  document.querySelector(".meta-info").innerHTML = `<p><span class="dot">•</span> ${c.date} · ${c.time}</p><p><span class="dot">•</span> ${c.venue}</p><p><span class="dot">•</span> Capacidad: 14.000 personas</p>`;
  document.getElementById("ticket-options").innerHTML = c.ticketTypes.map((t) => `<label class="ticket-option ${t.id === state.selectedTicketTypeId ? "is-selected" : ""}" data-ticket-type="${t.id}"><span class="ticket-option__left"><span class="radio-outer"><span class="radio-inner"></span></span>${t.label}</span><span class="ticket-option__price">${fmtCOP(t.price)}</span></label>`).join(""); document.getElementById("qty-val").textContent = state.qty;
}
function renderCheckout() {
  const c = concert(), t = ticketType(), subtotal = t.price * state.qty, total = subtotal + state.serviceFee, summary = document.querySelector(".summary-card"), metas = summary.querySelectorAll(".summary-item__meta"), rows = summary.querySelectorAll(".summary-rows div");
  summary.querySelector(".summary-item__title").textContent = c.artist; summary.querySelector(".summary-item__sub").textContent = c.tour; metas[0].textContent = `${c.date} · ${c.time}`; metas[1].textContent = c.venue; summary.querySelector(".thumb").className = `thumb ${c.thumb}`; rows[0].querySelector("dd").textContent = t.label; document.getElementById("co-qty").textContent = state.qty; rows[2].querySelector("dd").textContent = fmtCOP(t.price); document.getElementById("co-subtotal").textContent = fmtCOP(subtotal); document.getElementById("co-total").textContent = fmtCOP(total); document.getElementById("pay-button").lastChild.textContent = ` Pagar ${fmtCOP(total)}`;
}
function setAuthView(view) { const register = view === "register"; document.getElementById("login-form").hidden = register; document.getElementById("register-form").hidden = !register; document.getElementById("auth-title").textContent = register ? "Crea tu cuenta" : "Inicia sesión para continuar"; }
function openAuth(next = null) { state.pendingScreen = next; setAuthView("login"); document.getElementById("auth-modal").hidden = false; document.getElementById("login-email").focus(); }
function closeAuth() { document.getElementById("auth-modal").hidden = true; state.pendingScreen = null; }
function message(id, text, error = true) { const el = document.getElementById(id); el.textContent = text; el.classList.toggle("is-error", error); }
function renderAccount() {
  const button = document.getElementById("account-button");
  const loggedIn = Boolean(state.currentUser);
  button.classList.toggle("is-signed-in", loggedIn);
  button.title = loggedIn ? `Cuenta de ${state.currentUser.full_name}` : "Iniciar sesión";
  button.setAttribute("aria-label", loggedIn ? `Cuenta de ${state.currentUser.full_name}` : "Iniciar sesión");
  if (loggedIn) document.getElementById("account-greeting").textContent = `Hola, ${state.currentUser.full_name}`;
}
async function restoreSession() { if (!token()) return; try { state.currentUser = await api("/auth/me"); renderAccount(); } catch { localStorage.removeItem("soundpass_token"); } }
async function loadTickets() {
  if (!token()) return openAuth("mytickets");
  try { const orders = await api("/orders/me"); TICKETS = orders.map((o) => ({ orderId: o.order_code, concertId: CONCERTS.find((c) => c.apiId === o.concert.id)?.id || "weeknd", type: o.items.map((i) => i.ticket_type_name).join(", "), qty: o.items.reduce((sum, i) => sum + i.quantity, 0), status: o.status })); renderTickets(); } catch (err) { alert(err.message); }
}
function renderTickets() {
  const list = document.getElementById("ticket-list"); if (!TICKETS.length) { list.innerHTML = `<div class="empty-state"><h3>Aún no tienes boletos</h3><p>Explora los conciertos y encuentra tu próxima experiencia en vivo.</p><button class="btn btn--primary" data-nav="listing">Ver conciertos</button></div>`; return; }
  list.innerHTML = TICKETS.map((t) => { const c = CONCERTS.find((x) => x.id === t.concertId) || CONCERTS[0], cancelled = t.status === "cancelled"; return `<article class="ticket-card"><div class="ticket-card__art ${c.art}"></div><div class="ticket-card__body"><p class="ticket-card__title">${c.artist}</p><p class="ticket-card__sub">${c.tour}</p><div class="ticket-card__meta"><span>🗓 ${c.date} · ${c.time}</span><span>📍 ${c.venue}</span></div><div class="ticket-card__foot"><span>${t.qty} boleto${t.qty > 1 ? "s" : ""}</span><span>${t.type}</span><span>Orden #${t.orderId}</span></div></div><div class="ticket-card__actions"><span class="badge ${cancelled ? "badge--cancelled" : "badge--confirmed"}">${cancelled ? "Cancelado" : "Confirmado"}</span></div></article>`; }).join("");
}
document.addEventListener("click", (e) => { const nav = e.target.closest("[data-nav]"), open = e.target.closest("[data-open]"), type = e.target.closest("[data-ticket-type]"), view = e.target.closest("[data-auth-view]"); if (nav && nav.dataset.nav !== "checkout") goTo(nav.dataset.nav); if (open) { state.selectedConcertId = open.dataset.open; state.selectedTicketTypeId = concert().ticketTypes[1]?.id || concert().ticketTypes[0].id; state.qty = 2; renderDetail(); goTo("detail"); } if (type) { state.selectedTicketTypeId = type.dataset.ticketType; renderDetail(); } if (view) setAuthView(view.dataset.authView); });
document.getElementById("account-button").addEventListener("click", () => {
  if (!state.currentUser) return openAuth();
  const menu = document.getElementById("account-menu");
  menu.hidden = !menu.hidden;
});
document.getElementById("account-tickets").addEventListener("click", () => { document.getElementById("account-menu").hidden = true; goTo("mytickets"); });
document.getElementById("logout-button").addEventListener("click", () => {
  localStorage.removeItem("soundpass_token"); state.currentUser = null;
  document.getElementById("account-menu").hidden = true; renderAccount(); goTo("home");
});
document.addEventListener("click", (e) => { if (!e.target.closest(".topbar__right")) document.getElementById("account-menu").hidden = true; });
document.getElementById("auth-close").addEventListener("click", closeAuth); document.getElementById("auth-modal").addEventListener("click", (e) => { if (e.target.id === "auth-modal") closeAuth(); });
document.getElementById("qty-minus").onclick = () => { state.qty = Math.max(1, state.qty - 1); renderDetail(); }; document.getElementById("qty-plus").onclick = () => { state.qty = Math.min(10, state.qty + 1); renderDetail(); };
document.querySelector('[data-nav="checkout"]').addEventListener("click", (e) => { e.preventDefault(); token() ? goTo("checkout") : openAuth("checkout"); });
document.querySelectorAll(".payment-option").forEach((o) => o.onclick = () => { document.querySelectorAll(".payment-option").forEach((x) => x.classList.remove("is-selected")); o.classList.add("is-selected"); o.querySelector("input").checked = true; });
document.getElementById("login-form").addEventListener("submit", async (e) => { e.preventDefault(); const f = new FormData(e.currentTarget); try { const r = await api("/auth/login", { method: "POST", body: JSON.stringify({ email: f.get("email"), password: f.get("password") }) }); localStorage.setItem("soundpass_token", r.access_token); state.currentUser = await api("/auth/me"); renderAccount(); const next = state.pendingScreen; closeAuth(); if (next) goTo(next); } catch (err) { message("login-message", err.message); } });
document.getElementById("register-form").addEventListener("submit", async (e) => { e.preventDefault(); const f = new FormData(e.currentTarget); try { await api("/auth/register", { method: "POST", body: JSON.stringify({ full_name: f.get("full_name"), email: f.get("email"), password: f.get("password") }) }); document.getElementById("login-email").value = f.get("email"); setAuthView("login"); message("login-message", "Cuenta creada. Ahora inicia sesión.", false); } catch (err) { message("register-message", err.message); } });
document.getElementById("pay-button").addEventListener("click", async () => { if (!token()) return openAuth("checkout"); const b = document.getElementById("pay-button"), c = concert(), t = ticketType(), selectedPay = document.querySelector(".payment-option.is-selected").textContent; const payment = selectedPay.includes("PSE") ? "pse" : selectedPay.includes("Nequi") ? "nequi" : "card"; b.disabled = true; b.textContent = "Procesando compra…"; try { await api("/orders", { method: "POST", body: JSON.stringify({ concert_id: c.apiId, payment_method: payment, items: [{ ticket_type_id: t.apiId, quantity: state.qty }] }) }); goTo("success"); } catch (err) { alert(err.message); } finally { b.disabled = false; renderCheckout(); } });
document.querySelectorAll(".tab").forEach((t) => t.onclick = () => { document.querySelectorAll(".tab").forEach((x) => x.classList.remove("is-active")); t.classList.add("is-active"); });
renderFeatured(); renderListing(); renderDetail(); restoreSession(); goTo("home");
