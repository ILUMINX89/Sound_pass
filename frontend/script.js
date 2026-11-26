const API_URL = "/api";
let CONCERTS = [], TICKETS = [], HOME_CATALOG = [];
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
  if (id !== "detail") detailRequest++;
  if (id !== "detail" && typeof spotifyView !== "undefined" && spotifyView) spotifyClear();
  if (id !== "detail" && typeof artistBioView !== "undefined" && artistBioView) artistBioClear();
  if (id !== "detail" && typeof upcomingView !== "undefined" && upcomingView) upcomingClear();
  if (id !== "assistant" && typeof aiView !== "undefined" && aiView) aiLeave();
  document.querySelectorAll("[data-screen]").forEach(el => el.classList.toggle("is-active", el.id === `screen-${id}`));
  document.querySelectorAll(".primary-nav__link[data-active-on]").forEach(el => el.classList.toggle("is-active", el.dataset.activeOn.split(",").includes(id)));
  if (id === "checkout") renderCheckout(); if (id === "mytickets") loadTickets(); window.scrollTo({ top: 0, behavior: "smooth" });
}
function collectionMessage(text) { document.getElementById("featured-grid").innerHTML = `<div class="empty-state collection-message"><p>${esc(text)}</p></div>`; document.getElementById("concert-list").innerHTML = `<div class="empty-state"><p>${esc(text)}</p></div>`; document.getElementById("concert-count").textContent = "Conciertos (0)"; }
let catalogRequest = 0;
let catalogSearchTimer;
let detailRequest = 0;

async function loadConcerts(search = "") {
  const request = ++catalogRequest;
  CONCERTS = [];
  collectionMessage("Cargando conciertos de Ticketmaster...");
  try {
    const query = search.trim().slice(0, 100);
    const provider = await api(`/concerts/ticketmaster?q=${encodeURIComponent(query)}`,
      { signal: AbortSignal.timeout(25000) });
    if (request !== catalogRequest) return;
    const events = new Map();
    for (const item of provider.events) {
      if (item.source === "ticketmaster" && item.id && item.artist_id) events.set(concertKey(item), item);
    }
    CONCERTS = [...events.values()].sort((a, b) =>
      `${a.event_date}${a.event_time || ""}`.localeCompare(`${b.event_date}${b.event_time || ""}`));
    if (!query) HOME_CATALOG = CONCERTS;
    state.filters.city = "";
    state.filters.genres = [];
    populateFilters();
    renderCatalog();
  } catch (error) {
    if (request === catalogRequest) collectionMessage(error.message);
  }
}
function populateFilters() {
  const cities = [...new Set(CONCERTS.map(c => c.venue.city).filter(Boolean))].sort((a, b) => a.localeCompare(b, "es"));
  document.getElementById("f-city").innerHTML = `<option value="">Todas</option>${cities.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join("")}`;
  const genres = [...new Set(CONCERTS.map(c => c.genre).filter(Boolean))].sort((a, b) => a.localeCompare(b, "es"));
  document.getElementById("genre-filters").innerHTML = genres.map(v => `<label class="checkbox"><input type="checkbox" value="${esc(v)}"><span>${esc(v)}</span></label>`).join("");
}
const ADD_ON = /\b(vip|suites?|parking|estacionamiento|premium seats?|hospitality|meet[ -]and[ -]greet|add[ -]ons?|upgrades?|cannot split by day|2[ -]day tickets?)\b/i;
const INACTIVE_EVENT = new Set(["canceled", "cancelled", "postponed", "rescheduled", "inactive", "aplazado", "cancelado"]);
const artistName = value => (value || "").normalize("NFKC").trim().replace(/\s+/g, " ").toLocaleLowerCase("es");
const venueClocks = new Map();

function venueClock(instant, timezone) {
  if (!venueClocks.has(timezone)) {
    const options = { year:"numeric", month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit", second:"2-digit", hourCycle:"h23" };
    try { venueClocks.set(timezone, new Intl.DateTimeFormat("en-CA", { ...options, timeZone: timezone || undefined })); }
    catch { venueClocks.set(timezone, new Intl.DateTimeFormat("en-CA", options)); }
  }
  const fields = Object.fromEntries(venueClocks.get(timezone).formatToParts(instant).map(p => [p.type, p.value]));
  return `${fields.year}-${fields.month}-${fields.day}T${fields.hour}:${fields.minute}:${fields.second}`;
}

function eventInstant(c) {
  const explicit = c.event_time && Date.parse(c.starts_at);
  if (Number.isFinite(explicit)) return explicit;
  const wall = Date.parse(`${c.event_date}T${c.event_time || "23:59:59"}Z`);
  if (!Number.isFinite(wall)) return Infinity;
  const first = wall + (wall - Date.parse(venueClock(wall, c.timezone) + "Z"));
  return first + (wall - Date.parse(venueClock(first, c.timezone) + "Z"));
}

function validConcert(c, now) {
  return /^\d{4}-\d{2}-\d{2}$/.test(c.event_date || "")
    && !INACTIVE_EVENT.has(String(c.status || "").toLowerCase())
    && !ADD_ON.test(c.tour_name || c.name || "")
    && (c.event_time ? eventInstant(c) >= now : c.event_date >= venueClock(now, c.timezone).slice(0, 10));
}

function artistKeys(events) {
  const known = new Map();
  for (const c of events) {
    if (!c.artist_id) continue;
    const name = artistName(c.artist);
    if (!known.has(name)) known.set(name, new Set());
    known.get(name).add(c.artist_id);
  }
  return c => {
    if (c.artist_id) return `artist:${c.artist_id}`;
    const name = artistName(c.artist), candidates = known.get(name);
    if (candidates?.size === 1) return `artist:${candidates.values().next().value}`;
    return !name || candidates?.size > 1 ? `event:${concertKey(c)}` : `name:${name}`;
  };
}

const compareShows = (a, b) => eventInstant(a) - eventInstant(b) || concertKey(a).localeCompare(concertKey(b));

function selectArtistCards(events, filters, now = Date.now()) {
  const artistKey = artistKeys(events);
  const eligible = events.filter(c => {
    if (!validConcert(c, now)) return false;
    const venueToday = venueClock(now, c.timezone).slice(0, 10);
    const day = new Date(`${c.event_date}T00:00:00Z`);
    const three = new Date(`${venueToday}T00:00:00Z`);
    three.setUTCMonth(three.getUTCMonth() + 3);
    return (!filters.city || c.venue.city === filters.city)
      && (!filters.genres.length || filters.genres.includes(c.genre))
      && (filters.date === "month" ? c.event_date.startsWith(venueToday.slice(0, 7))
        : filters.date === "three_months" ? day <= three : true);
  });
  const selected = new Map();
  for (const c of eligible) {
    const key = artistKey(c);
    const previous = selected.get(key);
    if (!previous || compareShows(c, previous) < 0) selected.set(key, c);
  }
  return [...selected.values()].sort(compareShows);
}

function renderCatalog() {
  const rows = selectArtistCards(CONCERTS, state.filters);
  renderFeatured(rows.slice(0, 6));
  const sort = state.filters.sort;
  if (sort !== "date") {
    const price = c => c.source === "ticketmaster"
      ? c.price_ranges?.find(range => range.min != null || range.max != null)
      : { currency: "COP", min: Number(c.price_from) };
    rows.sort((a, b) => {
      const x = price(a), y = price(b);
      if (!x || !y) return Number(!x) - Number(!y);
      return x.currency.localeCompare(y.currency)
        || ((x.min ?? x.max) - (y.min ?? y.max)) * (sort === "price_desc" ? -1 : 1);
    });
  }
  renderListing(rows);
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
  if (btn) { btn.disabled = out; btn.textContent = t && out ? "Agotado" : c.source === "ticketmaster" ? "Comprar" : "Continuar"; }
}

const concertKey = c => c.source === "ticketmaster" ? `tm:${c.id}` : String(c.id);
const concertPath = key => key.startsWith("tm:")
  ? `/concerts/ticketmaster/${encodeURIComponent(key.slice(3))}`
  : `/concerts/${encodeURIComponent(key)}`;
const concertResponseId = id => String(id).replace(/^tm:/, "");
const SEATMAP_ORIGINS = new Set(["https://s1.ticketm.net", "https://media.ticketmaster.eu", "https://maps.ticketmaster.com"]);

function safeHttpsUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password ? url : null;
  } catch { return null; }
}

function externalPrice(c) {
  const prices = (c.price_ranges || []).map(({ min, max, currency }) => {
    const format = new Intl.NumberFormat("es-CO", { style: "currency", currency, currencyDisplay: "code" });
    if (min == null) return `Hasta ${format.format(max)}`;
    if (max == null) return `Desde ${format.format(min)}`;
    return min === max ? format.format(min) : format.formatRange(min, max);
  });
  return prices.length && c.price_source ? `${prices.join(" · ")} · ${c.price_source}${c.price_kind === "resale" ? " · Reventa" : ""}` : "Precio no disponible";
}

function renderFeatured(rows, gridId = "featured-grid") {
  document.getElementById(gridId).innerHTML = rows.map(c =>
    `<article class="feature-card${soldClass(c)}" data-open="${esc(concertKey(c))}">${art(c, "feature-card__art", statusChips(c))}
      <div class="feature-card__body">
        <p class="feature-card__title"><button type="button" class="btn btn--sm" data-open="${esc(concertKey(c))}">${esc(c.artist)}</button></p>
        <p class="feature-card__meta">${esc(venue(c))} · ${fmtDate(c.event_date)}</p>
      </div>
    </article>`
  ).join("") || '<div class="empty-state"><p>No hay conciertos próximos disponibles.</p></div>';
}

function renderListing(rows) {
  document.getElementById("concert-count").textContent = `Conciertos (${rows.length})`;
  document.getElementById("concert-list").innerHTML = rows.map(c =>
    `<article class="concert-row${soldClass(c)}" data-open="${esc(concertKey(c))}">${art(c, "concert-row__art")}
      <div class="concert-row__body">
        <p class="concert-row__title">${esc(c.artist)}</p>
        <p class="concert-row__sub">${esc(c.tour_name)}</p>
        ${statusChips(c)}
        <div class="concert-row__meta">
          <span>${fmtDate(c.event_date)} · ${fmtTime(c.event_time)}</span>
          <span>${esc(venue(c))}</span>
        </div>
      </div>
      <div class="concert-row__price"><strong>${esc(c.source === "ticketmaster" ? externalPrice(c) : fmtCOP(c.price_from))}</strong></div>
      <button type="button" class="btn btn--primary btn--sm" data-open="${esc(concertKey(c))}">Ver evento</button>
    </article>`
  ).join("") || '<div class="empty-state"><p>No encontramos conciertos para esta búsqueda.</p></div>';
}

function setExternalTicketPanel(external) {
  const screen = document.getElementById("screen-detail");
  for (const selector of [".stage-map", ".panel-note"]) {
    const element = screen.querySelector(selector);
    element.style.display = external ? "none" : "";
  }
  screen.querySelector(".ticket-panel h3").textContent = external ? "Entradas" : "Tipos de boleto";
}

async function openConcert(id) {
  const key = String(id), external = key.startsWith("tm:"), request = ++detailRequest;
  spotifyClear(); artistBioClear(); upcomingClear();
  state.selectedConcertId = external ? key : Number(key);
  state.selectedConcert = external ? CONCERTS.find(item => concertKey(item) === key) || null : null;
  state.selectedTicketTypeId = null;
  state.qty = 1;
  const layout = document.querySelector(".detail-layout");
  const notice = document.getElementById("detail-load");
  layout.hidden = !state.selectedConcert;
  notice.textContent = "Cargando detalle del concierto...";
  goTo("detail");
  if (state.selectedConcert) renderDetail();
  try {
    const c = await api(concertPath(key), { signal: AbortSignal.timeout(15000) });
    if (request !== detailRequest) return;
    const summary = CONCERTS.find(item => concertKey(item) === key);
    state.selectedConcert = { ...summary, ...c };
    if (external && (!c.price_ranges || summary?.price_source === "Ticketmaster" && c.price_source !== "Ticketmaster")) {
      state.selectedConcert.price_ranges = summary?.price_ranges ?? null;
      state.selectedConcert.price_source = summary?.price_source ?? null;
      state.selectedConcert.price_kind = summary?.price_kind ?? null;
    }
    const types = c.ticket_types || [];
    state.selectedTicketTypeId = (types.find(t => t.quantity_available > 0) || types[0])?.id ?? null;
    layout.hidden = false;
    notice.textContent = "";
    renderDetail();
    loadSpotify(state.selectedConcert);
    loadUpcomingEvents(state.selectedConcertId);
    loadArtistBio(state.selectedConcertId);
  } catch (error) {
    if (request !== detailRequest) return;
    notice.textContent = state.selectedConcert
      ? `No se pudo completar el detalle: ${error.message}`
      : `No fue posible cargar el concierto: ${error.message}`;
  }
}
function renderDetail() {
  const c = concert(); if (!c) return; const poster = document.querySelector(".detail-poster"), url = imageUrl(c.image_url); poster.className = `detail-poster dynamic-art${url ? " has-image" : ""}`; poster.style.backgroundImage = url ? `linear-gradient(0deg,rgba(0,0,0,.62),transparent 60%),url("${url.replace(/"/g, "%22")}")` : ""; poster.querySelector(".poster__tag").textContent = c.artist; poster.querySelector(".poster__tag2").textContent = c.tour_name; document.querySelector(".detail-title").textContent = c.artist; document.querySelector(".detail-sub").textContent = [c.tour_name, c.genre].filter(Boolean).join(" · ");
  const external = c.source === "ticketmaster";
  setExternalTicketPanel(external);
  const map = document.getElementById("official-seatmap");
  const mapUrl = external && safeHttpsUrl(c.seatmap_url);
  map.hidden = !external;
  map.innerHTML = mapUrl && SEATMAP_ORIGINS.has(mapUrl.origin)
    ? `<h2>Plano del recinto</h2><a href="${esc(mapUrl.href)}" target="_blank" rel="noopener noreferrer"><img src="${esc(mapUrl.href)}" alt="Plano oficial de ${esc(c.venue.name || c.artist)}">Ampliar plano</a><p>Plano informativo de Ticketmaster.</p>`
    : external ? "<p>Plano del recinto no disponible.</p>" : "";
  if (external) {
    document.getElementById("detail-status").innerHTML = statusChips(c);
    document.querySelector(".meta-info").innerHTML =
      `<p>${fmtDate(c.event_date, true)} · ${fmtTime(c.event_time)}</p><p>${esc(venue(c))}</p>${c.venue.address ? `<p>${esc(c.venue.address)}</p>` : ""}`;
    document.querySelector(".detail-blurb").textContent = "Fuente del evento: Ticketmaster";
    const t = ticketType();
    document.getElementById("ticket-options").textContent = t
      ? "Entrada de demostración. Sin cobro ni validez para el evento."
      : "Compra de demostración no disponible para este evento.";
    document.getElementById("qty-val").textContent = state.qty;
    renderStatus(c);
    return;
  }
  document.querySelector(".meta-info").innerHTML = `<p><span class="dot">•</span> ${fmtDate(c.event_date, true)} · ${fmtTime(c.event_time)}</p><p><span class="dot">•</span> ${esc(venue(c))}</p>${c.venue.address ? `<p><span class="dot">•</span> ${esc(c.venue.address)}</p>` : ""}<p><span class="dot">•</span> Capacidad: ${Number(c.venue.capacity || 0).toLocaleString("es-CO")} personas</p>`; document.querySelector(".detail-blurb").textContent = c.description || "Información adicional no disponible.";
  document.getElementById("stage-zones").innerHTML = c.ticket_types.map((t, i) => `<div class="stage-zone" style="width:${Math.min(96, 42 + i * 18)}%">${esc(t.name)}</div>`).join(""); document.getElementById("ticket-options").innerHTML = c.ticket_types.length ? c.ticket_types.map(t => `<label class="ticket-option ${t.id === state.selectedTicketTypeId ? "is-selected" : ""} ${t.quantity_available < 1 ? "is-disabled" : ""}" data-ticket-type="${t.id}"><span class="ticket-option__left"><span class="radio-outer"><span class="radio-inner"></span></span><span>${esc(t.name)}<small class="${typeStock(t).cls}">${typeStock(t).text}</small></span></span><span class="ticket-option__price">${fmtCOP(t.price)}</span></label>`).join("") : `<p class="form-message is-error">No hay tipos de boleto disponibles.</p>`; document.getElementById("qty-val").textContent = state.qty; document.querySelector('[data-nav="checkout"]').disabled = !ticketType(); renderStatus(c); loadSpotify(c);
}
function renderCheckout() {
  const c = concert(), t = ticketType(); if (!c || !t) return goTo("listing"); const subtotal = Number(t.price) * state.qty, fee = c.source === "ticketmaster" ? 0 : 6000 * state.qty, total = subtotal + fee, box = document.querySelector(".summary-card"); box.querySelector(".summary-art").outerHTML = art(c, "thumb summary-art"); box.querySelector(".summary-item__title").textContent = c.artist; box.querySelector(".summary-item__sub").textContent = c.tour_name; const meta = box.querySelectorAll(".summary-item__meta"); meta[0].textContent = `${fmtDate(c.event_date)} · ${fmtTime(c.event_time)}`; meta[1].textContent = venue(c); const rows = box.querySelectorAll(".summary-rows div"); rows[0].querySelector("dd").textContent = t.name; document.getElementById("co-qty").textContent = state.qty; rows[2].querySelector("dd").textContent = fmtCOP(t.price); document.getElementById("co-subtotal").textContent = fmtCOP(subtotal); document.getElementById("co-service-fee").textContent = fmtCOP(fee); document.getElementById("co-total").textContent = fmtCOP(total); document.getElementById("pay-button-label").textContent = c.source === "ticketmaster" ? "Confirmar compra de demostración" : `Pagar ${fmtCOP(total)}`;
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
function renderAccount() { const b = document.getElementById("account-button"), logged = Boolean(state.currentUser); b.classList.toggle("is-signed-in", logged); b.title = logged ? `Cuenta de ${state.currentUser.full_name}` : "Iniciar sesión"; b.setAttribute("aria-label", b.title); if (logged) document.getElementById("account-greeting").textContent = `Hola, ${state.currentUser.full_name}`; const adm = document.getElementById("account-admin"); if (adm) adm.hidden = !(logged && state.currentUser.role === "admin"); if (typeof refreshForYou === "function") refreshForYou(); }
async function restoreSession() { if (!token()) return; try { state.currentUser = await api("/auth/me"); renderAccount(); } catch (error) { if (error.status === 401) localStorage.removeItem("soundpass_token"); } }
async function loadTickets() { if (!token()) return openAuth("mytickets"); const list = document.getElementById("ticket-list"); list.innerHTML = `<div class="empty-state"><p>Cargando tus boletos...</p></div>`; try { TICKETS = await api("/orders/me"); renderTickets(); } catch (error) { list.innerHTML = `<div class="empty-state"><p>${esc(error.message)}</p></div>`; } }
function renderTickets() { const now = new Date(), rows = TICKETS.filter(o => state.activeTicketTab === "proximos" ? o.status === "confirmed" && new Date(`${o.concert.event_date}T23:59:59`) >= now : o.status === "cancelled" || new Date(`${o.concert.event_date}T23:59:59`) < now), list = document.getElementById("ticket-list"); if (!rows.length) { list.innerHTML = `<div class="empty-state"><h3>No hay boletos en esta sección</h3><p>Explora los conciertos y encuentra tu próxima experiencia en vivo.</p><button class="btn btn--primary" data-nav="listing">Ver conciertos</button></div>`; return; } list.innerHTML = rows.map(o => { const c = o.concert, q = o.items.reduce((s, i) => s + i.quantity, 0), cancelled = o.status === "cancelled"; return `<article class="ticket-card">${art(c, "ticket-card__art")}<div class="ticket-card__body"><p class="ticket-card__title">${esc(c.artist)}</p><p class="ticket-card__sub">${esc(c.tour_name)}</p><div class="ticket-card__meta"><span>🗓 ${fmtDate(c.event_date)} · ${fmtTime(c.event_time)}</span><span>📍 ${esc(venue(c))}</span></div><div class="ticket-card__foot"><span>${q} boleto${q === 1 ? "" : "s"}</span><span>${o.items.map(i => esc(i.ticket_type_name)).join(", ")}</span><span>Orden #${esc(o.order_code)}</span></div></div><div class="ticket-card__actions"><span class="badge ${cancelled ? "badge--cancelled" : "badge--confirmed"}">${cancelled ? "Cancelado" : "Confirmado"}</span><button class="btn btn--outline btn--sm" data-order-detail="${o.id}">Ver detalle</button>${cancelled ? "" : `<button class="btn btn--danger-outline btn--sm" data-cancel-order="${o.id}">Cancelar compra</button>`}</div></article>`; }).join(""); }
function openCancelModal(id) { const o = TICKETS.find(x => x.id === Number(id)); if (!o) return; state.orderToCancel = o; const q = o.items.reduce((s, i) => s + i.quantity, 0); document.getElementById("cancel-ticket").innerHTML = `${art(o.concert, "thumb")}<div><p class="summary-item__title">${esc(o.concert.artist)}</p><p class="summary-item__meta">${fmtDate(o.concert.event_date)} · ${esc(o.concert.venue.name)}</p><p class="summary-item__meta">${q} boleto${q === 1 ? "" : "s"} · ${o.items.map(i => esc(i.ticket_type_name)).join(", ")}</p></div>`; document.getElementById("cancel-modal").hidden = false; }
async function confirmCancellation() { if (!state.orderToCancel) return; const b = document.getElementById("modal-confirm"); b.disabled = true; b.textContent = "Cancelando..."; try { const o = await api(`/orders/${state.orderToCancel.id}/cancel`, { method: "POST" }); document.getElementById("cancel-modal").hidden = true; document.getElementById("cancelled-order-code").textContent = `Orden #${o.order_code}`; document.getElementById("cancelled-order-date").textContent = `Cancelada: ${fmtDateTime(o.cancelled_at)}`; state.orderToCancel = null; goTo("cancelled"); } catch (e) { alert(e.message); } finally { b.disabled = false; b.textContent = "Sí, cancelar compra"; } }
 
document.addEventListener("click", e => { const nav = e.target.closest("[data-nav]"), open = e.target.closest("[data-open]"), type = e.target.closest("[data-ticket-type]"), view = e.target.closest("[data-auth-view]"), cancel = e.target.closest("[data-cancel-order]"); if (nav && nav.dataset.nav !== "checkout") goTo(nav.dataset.nav); if (open) openConcert(open.dataset.open); if (type && !type.classList.contains("is-disabled")) { state.selectedTicketTypeId = Number(type.dataset.ticketType); state.qty = Math.min(state.qty, ticketType()?.quantity_available || 1); renderDetail(); } if (view) setAuthView(view.dataset.authView); if (cancel) openCancelModal(cancel.dataset.cancelOrder); });
document.getElementById("f-city").onchange = e => { state.filters.city = e.target.value; renderCatalog(); }; document.getElementById("f-date").onchange = e => { state.filters.date = e.target.value; renderCatalog(); }; document.getElementById("genre-filters").onchange = () => { state.filters.genres = [...document.querySelectorAll("#genre-filters input:checked")].map(x => x.value); renderCatalog(); }; document.getElementById("concert-search").oninput = e => {
  const query = e.target.value;
  goTo("listing");
  ++catalogRequest;
  clearTimeout(catalogSearchTimer);
  catalogSearchTimer = setTimeout(() => loadConcerts(query), 350);
};
document.getElementById("sort-select").onchange = e => { state.filters.sort = e.target.value; renderCatalog(); };
window.setInterval(() => { if (CONCERTS.length) renderCatalog(); }, 30000);
document.getElementById("account-button").onclick = () => { if (!state.currentUser) return openAuth(); const m = document.getElementById("account-menu"); m.hidden = !m.hidden; }; document.getElementById("account-tickets").onclick = () => { document.getElementById("account-menu").hidden = true; goTo("mytickets"); }; document.getElementById("logout-button").onclick = () => { localStorage.removeItem("soundpass_token"); state.currentUser = null; document.getElementById("account-menu").hidden = true; renderAccount(); goTo("home"); }; document.addEventListener("click", e => { if (!e.target.closest(".topbar__right")) document.getElementById("account-menu").hidden = true; });
document.getElementById("auth-close").onclick = closeAuth; document.getElementById("auth-modal").onclick = e => { if (e.target.id === "auth-modal") closeAuth(); }; document.getElementById("qty-minus").onclick = () => { state.qty = Math.max(1, state.qty - 1); renderDetail(); }; document.getElementById("qty-plus").onclick = () => { state.qty = Math.min(10, ticketType()?.quantity_available || 1, state.qty + 1); renderDetail(); }; document.querySelector('[data-nav="checkout"]').onclick = e => { e.preventDefault(); if (!ticketType()) return; token() ? goTo("checkout") : openAuth("checkout"); };
document.querySelectorAll(".payment-option").forEach(o => o.onclick = () => { document.querySelectorAll(".payment-option").forEach(x => x.classList.remove("is-selected")); o.classList.add("is-selected"); o.querySelector("input").checked = true; });
document.getElementById("login-form").onsubmit = async e => { e.preventDefault(); const btn = e.currentTarget.querySelector("[type=submit]"); if (btn.disabled) return; btn.disabled = true; message("login-message", "", false); const f = new FormData(e.currentTarget); try { const r = await api("/auth/login", { method: "POST", body: JSON.stringify({ email: f.get("email"), password: f.get("password") }) }); localStorage.setItem("soundpass_token", r.access_token); state.currentUser = await api("/auth/me"); renderAccount(); const next = state.pendingScreen; closeAuth(); if (next) goTo(next); } catch (err) { message("login-message", err.message); } finally { btn.disabled = false; } };
document.getElementById("register-form").onsubmit = async e => { e.preventDefault(); const btn = e.currentTarget.querySelector("[type=submit]"); if (btn.disabled) return; btn.disabled = true; message("register-message", "", false); const f = new FormData(e.currentTarget); try { await api("/auth/register", { method: "POST", body: JSON.stringify({ full_name: f.get("full_name"), email: f.get("email"), password: f.get("password") }) }); try { const r = await api("/auth/login", { method: "POST", body: JSON.stringify({ email: f.get("email"), password: f.get("password") }) }); localStorage.setItem("soundpass_token", r.access_token); state.currentUser = await api("/auth/me"); renderAccount(); closeAuth(); openPrefs("onboarding"); } catch { document.getElementById("login-email").value = f.get("email"); setAuthView("login"); message("login-message", "Cuenta creada. Ahora inicia sesión.", false); } } catch (err) { message("register-message", err.message); } finally { btn.disabled = false; } };
document.getElementById("pay-button").onclick = async () => { if (!token()) return openAuth("checkout"); const b = document.getElementById("pay-button"), c = concert(), t = ticketType(), text = document.querySelector(".payment-option.is-selected").textContent, payment = text.includes("PSE") ? "pse" : text.includes("Nequi") ? "nequi" : "card"; b.disabled = true; document.getElementById("pay-button-label").textContent = "Procesando compra…"; try { state.lastOrder = await api("/orders", { method: "POST", body: JSON.stringify({ concert_id: c.checkout_concert_id ?? c.id, payment_method: payment, items: [{ ticket_type_id: t.id, quantity: state.qty }] }) }); renderSuccess(); goTo("success"); } catch (err) { alert(err.message); } finally { b.disabled = false; renderCheckout(); } };
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
const SPOTIFY_URL = /^https:\/\/open\.spotify\.com\/artist\/[A-Za-z0-9]{22}$/;
const SPOTIFY_EMBED = /^https:\/\/open\.spotify\.com\/embed\/(artist|track)\/[A-Za-z0-9]{22}$/;
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
  const key = concertKey(c);
  if (!force && spotifyView.concertId === key) return;
  spotifyClear(); spotifyView.concertId = key;
  const req = spotifyView.req, controller = spotifyView.controller = new AbortController();
  root.innerHTML = spotifyHead(c.artist) + `<div class="dm-card dm-loading" role="status" aria-live="polite"><div class="dm-skel"></div><p>Cargando reproductor de Spotify...</p></div>`;
  try {
    const data = await api(`${concertPath(key)}/spotify`, { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(25000)]) });
    if (req !== spotifyView.req) return; // el usuario ya cambió de concierto o salió del detalle
    const a = data?.artist || {}, name = a.name || c.artist;
    if (data?.status === "ok" && SPOTIFY_EMBED.test(a.embed_url || "")) {
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
  const root = artistBioRoot(); if (!root || id == null) return;
  if (!force && artistBioView.concertId === id) return; // ya cargada o en curso: sin peticiones duplicadas
  if (force && artistBioView.loading) return;
  artistBioClear(); artistBioView.concertId = id; artistBioView.loading = true;
  const req = artistBioView.req, controller = artistBioView.controller = new AbortController(), current = () => req === artistBioView.req && state.selectedConcertId === id;
  root.hidden = false; renderArtistBio("loading");
  try {
    const data = await api(`${concertPath(String(id))}/artist-bio`, { signal: controller.signal });
    if (!current()) return; // llegó tarde: el usuario ya está en otro concierto o salió del detalle
    artistBioView.loading = false;
    if (!data || typeof data !== "object" || String(data.concert_id) !== concertResponseId(id)) return renderArtistBio("error", { text: ARTIST_BIO_MSG.error, retry: true });
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
  body.append(list, upcomingNode("p", "ue-note", "Las fechas son informativas y no implican disponibilidad de entradas en SoundPass."));
}
function otherArtistShows(opened, catalog, providerEvents, now = Date.now()) {
  const artistKey = artistKeys([...catalog, opened]);
  const dateRow = c => ({
    ...c, date: c.event_date, time: c.event_time, city: c.venue.city, venue: c.venue.name,
  });
  const fingerprint = c => {
    const where = artistName(c.venue.name);
    return where ? [c.event_date, (c.event_time || "").slice(0, 5), where, artistName(c.venue.city)].join("|") : null;
  };
  const seenIds = new Set([concertKey(opened)]), seenShows = new Set([fingerprint(opened)].filter(Boolean));
  const rows = [
    ...providerEvents.map(ev => ({
      ...ev, source: "ticketmaster", event_date: ev.date, event_time: ev.time,
      venue: { name: ev.venue, city: ev.city }, provider: true,
    })),
    ...catalog.filter(c => c.source === "ticketmaster" && artistKey(c) === artistKey(opened)),
  ];
  const shows = [];
  for (const c of rows) {
    const key = concertKey(c), show = fingerprint(c);
    if (!validConcert(c, now) || seenIds.has(key) || (show && seenShows.has(show))) continue;
    seenIds.add(key);
    if (show) seenShows.add(show);
    shows.push(c);
  }
  return shows.sort(compareShows).map(dateRow);
}
async function loadUpcomingEvents(id) {
  const root = upcomingRoot(); if (!root || id == null) return;
  if (upcomingView.concertId === id) return; // ya cargada o en curso: sin consultas duplicadas ni continuas
  upcomingClear(); upcomingView.concertId = id;
  const req = upcomingView.req, controller = upcomingView.controller = new AbortController(), current = () => req === upcomingView.req && state.selectedConcertId === id;
  root.hidden = false; renderUpcoming("loading");
  try {
    const data = await api(`${concertPath(String(id))}/upcoming-events`, { signal: controller.signal });
    if (!current()) return; // respuesta tardía de otro concierto: se descarta
    if (!data || typeof data !== "object" || String(data.concert_id) !== concertResponseId(id)) return renderUpcoming("notice", { text: UPCOMING_MSG.error });
    const msg = upcomingText(data.message);
    const provider = data.status === "ok" && Array.isArray(data.events) ? data.events.filter(Boolean) : [];
    const events = otherArtistShows(concert(), CONCERTS, provider);
    if (events.length) renderUpcoming("list", { events });
    else if (["ok", "no_events", "not_found", "ambiguous"].includes(data.status)) renderUpcoming("notice", { text: msg || UPCOMING_MSG[data.status] || UPCOMING_MSG.no_events });
    else renderUpcoming("notice", { text: UPCOMING_MSG.error });
  } catch (error) {
    if (error?.name === "AbortError" || !current()) return; // cancelar no es un error
    const events = otherArtistShows(concert(), CONCERTS, []);
    if (events.length) return renderUpcoming("list", { events });
    renderUpcoming("notice", { text: error.status === 404 ? UPCOMING_MSG.concert_not_found : error.status === 502 || error.status === 503 ? UPCOMING_MSG.unavailable : UPCOMING_MSG.error });
  }
}
 

/* SoundPass AI usa el cliente autenticado de la aplicación.
   Los mensajes se insertan como texto plano. */
var AI_CONTRACT = {
  path: "/assistant/chat",
  method: "POST",
  body: message => ({ message }),
  reply: data => data.reply
};
const AI_MAX = 500;
const AI_ICON = `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" /></svg>`;
var aiView = { pending: false, controller: null, req: 0, last: "", started: false };
const aiEl = id => document.getElementById(id);
const aiMk = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
const aiTime = () => new Date().toLocaleTimeString("es-CO", { hour: "numeric", minute: "2-digit" });
function aiAppend(node) { const log = aiEl("ai-log"); log.append(node); log.scrollTop = log.scrollHeight; return node; }
function aiAddMessage(role, text) {
  const row = aiMk("div", `ai-msg ai-msg--${role}`);
  if (role === "bot") { const av = aiMk("span", "ai-avatar"); av.setAttribute("aria-hidden", "true"); av.innerHTML = AI_ICON; row.append(av); }
  const col = aiMk("div", "ai-msg__col");
  col.append(aiMk("div", "ai-msg__bubble", text), aiMk("span", "ai-msg__meta", `${role === "user" ? "Tú" : "SoundPass AI"} · ${aiTime()}`));
  row.append(col); return aiAppend(row);
}
function aiNote(kind, text, retry = false) {
  const n = aiMk("div", `ai-note ai-note--${kind}`); n.append(aiMk("p", "ai-note__text", text));
  if (retry) { const b = aiMk("button", "btn btn--sm ai-note__retry", "Reintentar"); b.type = "button"; b.dataset.aiRetry = ""; n.append(b); }
  return aiAppend(n);
}
function aiTyping() {
  const row = aiMk("div", "ai-msg ai-msg--bot ai-typing"); const av = aiMk("span", "ai-avatar"); av.setAttribute("aria-hidden", "true"); av.innerHTML = AI_ICON;
  const dots = aiMk("div", "ai-msg__bubble"); dots.setAttribute("aria-label", "SoundPass AI está escribiendo…"); dots.append(aiMk("i"), aiMk("i"), aiMk("i")); const col = aiMk("div", "ai-msg__col"); col.append(dots, aiMk("span", "ai-msg__meta", "Escribiendo…"));
  row.append(av, col); return aiAppend(row);
}
function aiSync() {
  const i = aiEl("ai-input"); aiEl("ai-send").disabled = aiView.pending || !i.value.trim();
  aiEl("ai-count").textContent = `${i.value.length}/${AI_MAX}`; i.style.height = "auto"; i.style.height = Math.min(i.scrollHeight, 140) + "px";
}
function aiBusy(on) { aiEl("ai-log").setAttribute("aria-busy", String(on)); aiEl("ai-form").classList.toggle("is-busy", on); aiSync(); }
function aiRenderStatus() {
  const el = aiEl("ai-status"), ok = Boolean(AI_CONTRACT.path);
  el.className = `ai-status ${ok ? "ai-status--ok" : "ai-status--pending"}`; el.textContent = ok ? "Asistente disponible" : "Interfaz lista · conexión con la IA pendiente";
}
async function askAssistant(message, signal) {
  const data = await api(AI_CONTRACT.path, { method: AI_CONTRACT.method, body: JSON.stringify(AI_CONTRACT.body(message)), signal });
  const reply = AI_CONTRACT.reply(data);
  if (typeof reply !== "string" || !reply.trim()) { const e = new Error("invalid"); e.code = "invalid"; throw e; }
  return reply.trim();
}
function aiShowError(error) { // nunca se muestran errores internos del servidor
  if (error?.status === 401) return aiNote("warn", "Inicia sesión para usar el asistente.");
  if (error?.status === 429) return aiNote("warn", "Hay muchas consultas en este momento. Espera un momento e inténtalo de nuevo.", true);
  if (error?.code === "invalid") return aiNote("warn", "Recibimos una respuesta que no pudimos mostrar. Inténtalo de nuevo.", true);
  aiNote("warn", "No pudimos obtener respuesta del asistente. Inténtalo de nuevo.", true);
}
async function aiSend(raw, retry = false) {
  const text = String(raw || "").trim(); if (!text || aiView.pending) return;
  if (!retry) { aiAddMessage("user", text); aiView.last = text; }
  if (!aiView.started) { aiView.started = true; aiEl("ai-suggest").hidden = true; }
  if (!AI_CONTRACT.path) return aiNote("info", "SoundPass AI todavía no está conectado al servicio de IA. Esta pantalla es solo la interfaz: tu mensaje no se envió.");
  const req = ++aiView.req; aiView.pending = true; aiView.controller = new AbortController(); aiBusy(true);
  const typing = aiTyping();
  try {
    const reply = await askAssistant(text, aiView.controller.signal);
    if (req !== aiView.req) return; // el usuario salió del chat: la respuesta tardía se descarta
    typing.remove(); aiAddMessage("bot", reply);
  } catch (error) {
    if (req !== aiView.req || error?.name === "AbortError") return; // cancelar no es un error
    typing.remove(); aiShowError(error);
  } finally { if (req === aiView.req) { aiView.pending = false; aiView.controller = null; aiBusy(false); } }
}
function aiLeave() { // al salir del chat con una consulta en curso: cancelar y dejar la conversación coherente
  if (!aiView.pending) return;
  aiView.req++; aiView.controller?.abort(); aiView.controller = null; aiView.pending = false;
  aiEl("ai-log").querySelector(".ai-typing")?.remove(); aiBusy(false);
  aiNote("info", "Se canceló la consulta porque saliste del chat. Puedes volver a preguntar.");
}
(function aiInit() {
  const input = aiEl("ai-input"), form = aiEl("ai-form"); if (!input || !form) return;
  aiRenderStatus(); aiSync();
  input.addEventListener("input", aiSync);
  input.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); } });
  form.addEventListener("submit", e => { e.preventDefault(); const v = input.value; if (!v.trim() || aiView.pending) return; input.value = ""; aiSync(); aiSend(v); });
  aiEl("ai-suggest").addEventListener("click", e => { const b = e.target.closest("[data-ai-suggest]"); if (b) aiSend(b.dataset.aiSuggest); });
  aiEl("ai-log").addEventListener("click", e => { const b = e.target.closest("[data-ai-retry]"); if (b && !aiView.pending) { b.closest(".ai-note").remove(); aiSend(aiView.last, true); } });
})();

/* ===== Recomendaciones "Para ti" =====
   Cuestionario opcional (géneros, artistas, cuatro escalas). El backend valida, guarda por usuario y ordena.
   Aquí solo se muestra: para cada artista recomendado se usa la tarjeta con la fecha válida más cercana
   que ya calcula selectArtistCards sobre el catálogo completo. Sin respuestas, sin modelo o sin
   coincidencias, la portada conserva el catálogo general. */
const PREF_SCALES = [
  ["danceability", "Baile", "Para escuchar", "Para bailar"],
  ["energy", "Energía", "Suave", "Intensa"],
  ["acousticness", "Acústica", "Electrónica", "Acústica"],
  ["mood", "Ánimo", "Melancólico", "Alegre"],
];
let prefsOptions = null, forYou = null, forYouRequest = 0, prefsMode = "edit", prefsOpener = null;
const MAX_PREF_GENRES = 5, MAX_PREF_ARTISTS = 8, PREF_ARTIST_RESULTS_LIMIT = 12;
const CHECK_SVG = `<svg class="prefs-chip__check" width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M3.2 8.5l3 3 6.6-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
let prefsDraft = null;

function defaultPrefsDraft(saved) {
  const scales = saved?.scales
    ? { danceability: saved.scales.danceability, energy: saved.scales.energy, acousticness: saved.scales.acousticness, mood: saved.scales.mood }
    : { danceability: 3, energy: 3, acousticness: 3, mood: 3 };
  return {
    step: 1,
    genres: [...(saved?.genres || [])],
    artist_ids: [...(saved?.artist_ids || [])],
    useScales: Boolean(saved?.scales),
    scales,
    query: "",
  };
}

function artistPortraits() {
  const map = new Map();
  for (const c of HOME_CATALOG) {
    const url = safeHttpsUrl(c?.image_url);
    if (url && c?.artist) {
      const key = artistName(c.artist);
      if (!map.has(key)) map.set(key, url.href);
    }
  }
  return map;
}

function renderForYou() {
  const section = document.getElementById("for-you"), invite = document.getElementById("prefs-invite");
  const logged = Boolean(state.currentUser), status = state.prefs?.status;
  invite.hidden = !(logged && status === "unset");
  const cards = new Map(selectArtistCards(HOME_CATALOG, { city: "", genres: [], date: "all" }).map(c => [String(c.artist_id), c]));
  const rows = (forYou?.items || []).map(item => cards.get(String(item.artist_id))).filter(Boolean).slice(0, 6);
  section.hidden = !(logged && status === "answered" && forYou?.available && rows.length);
  if (section.hidden) return;
  document.getElementById("for-you-profile").textContent = forYou.profile ? `Tu perfil musical: ${forYou.profile.name}` : "";
  renderFeatured(rows, "for-you-grid");
}

async function refreshForYou() {
  const request = ++forYouRequest;
  if (!state.currentUser) { state.prefs = null; forYou = null; renderForYou(); return; }
  try {
    const prefs = await api("/preferences/me");
    if (request !== forYouRequest) return;
    state.prefs = prefs; forYou = null; renderForYou();
    if (prefs.status === "answered") await loadForYou(request);
  } catch (error) { if (request === forYouRequest) { state.prefs = null; forYou = null; renderForYou(); } }
}

async function loadForYou(request = ++forYouRequest) {
  try {
    const result = await api("/preferences/me/recommendations", { signal: AbortSignal.timeout(30000) });
    if (request !== forYouRequest) return;
    forYou = result;
  } catch { if (request !== forYouRequest) return; forYou = null; }
  renderForYou();
}

async function loadPrefsOptions() {
  if (!prefsOptions?.available) prefsOptions = await api("/preferences/options");
  return prefsOptions;
}

function renderPrefsGenres() {
  if (!prefsOptions || !prefsDraft) return;
  const selected = new Set(prefsDraft.genres), full = selected.size >= MAX_PREF_GENRES;
  document.getElementById("prefs-genres").innerHTML = prefsOptions.genres.map(g => {
    const active = selected.has(g.id);
    return `<button type="button" class="prefs-chip" data-pref-genre="${esc(g.id)}" aria-pressed="${active ? "true" : "false"}"${!active && full ? " disabled" : ""}>${active ? CHECK_SVG : ""}<span class="prefs-chip__text">${esc(g.label)}</span></button>`;
  }).join("");
  const n = selected.size;
  document.getElementById("prefs-genre-count").textContent = n === MAX_PREF_GENRES
    ? `${n} de ${MAX_PREF_GENRES} seleccionados`
    : `${n} ${n === 1 ? "seleccionado" : "seleccionados"}`;
}

function renderPrefsArtists() {
  if (!prefsOptions || !prefsDraft) return;
  const byId = new Map(prefsOptions.artists.map(a => [a.id, a]));
  const selected = new Set(prefsDraft.artist_ids), full = selected.size >= MAX_PREF_ARTISTS;
  document.getElementById("prefs-selected-artists").innerHTML = prefsDraft.artist_ids
    .map(id => byId.get(id)).filter(Boolean)
    .map(a => `<span class="prefs-selected-chip"><span>${esc(a.name)}</span><button type="button" class="prefs-selected-chip__remove" data-remove-artist="${esc(a.id)}" aria-label="Quitar ${esc(a.name)}">×</button></span>`)
    .join("");
  document.getElementById("prefs-artist-count").textContent = `${selected.size} de ${MAX_PREF_ARTISTS} seleccionados`;
  const q = artistName(prefsDraft.query), portraits = artistPortraits();
  const matches = prefsOptions.artists.filter(a => !selected.has(a.id) && (!q || artistName(a.name).includes(q)));
  const shown = matches.slice(0, PREF_ARTIST_RESULTS_LIMIT);
  document.getElementById("prefs-artists").innerHTML = shown.length
    ? shown.map(a => {
        const photo = portraits.get(artistName(a.name));
        return `<div class="prefs-artist-row" role="listitem">${photo ? `<img class="prefs-artist-avatar" src="${esc(photo)}" alt="" loading="lazy">` : ""}<span class="prefs-artist-name">${esc(a.name)}</span><button type="button" class="prefs-artist-add" data-add-artist="${esc(a.id)}" aria-label="Agregar ${esc(a.name)}"${full ? " disabled" : ""}>+</button></div>`;
      }).join("")
    : `<p class="prefs-empty">${q ? "No encontramos artistas con ese nombre." : "Ya elegiste todos los artistas disponibles."}</p>`;
}

function renderPrefsScales() {
  if (!prefsDraft) return;
  const use = document.getElementById("prefs-use-scales"), list = document.getElementById("prefs-scales");
  use.checked = prefsDraft.useScales;
  list.classList.toggle("is-disabled", !prefsDraft.useScales);
  list.innerHTML = PREF_SCALES.map(([key, label, low, high]) => {
    const val = prefsDraft.scales[key] ?? 3, fill = `${((val - 1) / 4) * 100}%`;
    return `<div class="prefs-scale-card">
      <div class="prefs-scale-card__head"><label class="prefs-scale-card__label" for="pref-scale-${key}">${label}</label><span class="prefs-scale-card__val" data-scale-val="${key}">${val} / 5</span></div>
      <input class="prefs-range" id="pref-scale-${key}" type="range" min="1" max="5" step="1" value="${val}" style="--fill:${fill}" data-scale="${key}" aria-label="${label}: de ${low} a ${high}"${prefsDraft.useScales ? "" : " disabled"}>
      <div class="prefs-scale-card__ends"><span>${low}</span><span>${high}</span></div>
    </div>`;
  }).join("");
}

function renderPrefsStep(focusHeading = false) {
  if (!prefsDraft) return;
  const step = prefsDraft.step;
  document.querySelectorAll("[data-prefs-step]").forEach(el => { el.hidden = Number(el.dataset.prefsStep) !== step; });
  document.getElementById("prefs-progress-fill").style.width = `${(step / 3) * 100}%`;
  document.getElementById("prefs-progress-label").textContent = `${step} de 3`;
  const bar = document.getElementById("prefs-progressbar");
  bar.setAttribute("aria-valuenow", String(step));
  document.getElementById("prefs-back").hidden = step === 1;
  document.getElementById("prefs-next").hidden = step === 3;
  document.getElementById("prefs-save").hidden = step !== 3;
  document.getElementById("prefs-body").scrollTop = 0;
  if (step === 1) renderPrefsGenres();
  else if (step === 2) { document.getElementById("prefs-artist-search").value = prefsDraft.query; renderPrefsArtists(); }
  else renderPrefsScales();
  if (focusHeading) {
    const heading = document.querySelector(`[data-prefs-step="${step}"] h2`);
    heading?.focus?.();
  }
}

async function openPrefs(mode = "edit") {
  prefsMode = mode;
  prefsOpener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const modal = document.getElementById("prefs-modal");
  message("prefs-message", "", false);
  document.getElementById("prefs-skip").textContent = mode === "onboarding" ? "Omitir" : "Cancelar";
  let options;
  try { options = await loadPrefsOptions(); } catch { options = { available: false }; }
  if (!options.available) {
    if (mode === "onboarding") return;
    alert("Las recomendaciones no están disponibles por ahora."); return;
  }
  let saved = state.prefs;
  if (!saved && state.currentUser) { try { saved = state.prefs = await api("/preferences/me"); } catch { saved = null; } }
  prefsDraft = defaultPrefsDraft(saved);
  modal.hidden = false;
  renderPrefsStep(true);
}

function closePrefs() {
  document.getElementById("prefs-modal").hidden = true;
  prefsDraft = null;
  message("prefs-message", "", false);
  if (prefsOpener && document.contains(prefsOpener)) prefsOpener.focus?.();
  prefsOpener = null;
}

document.getElementById("prefs-genres").addEventListener("click", e => {
  const btn = e.target.closest("[data-pref-genre]");
  if (!btn || !prefsDraft) return;
  const id = btn.dataset.prefGenre, idx = prefsDraft.genres.indexOf(id);
  if (idx >= 0) prefsDraft.genres.splice(idx, 1);
  else if (prefsDraft.genres.length < MAX_PREF_GENRES) prefsDraft.genres.push(id);
  message("prefs-message", "", false);
  renderPrefsGenres();
});

document.getElementById("prefs-artist-search").addEventListener("input", e => {
  if (!prefsDraft) return;
  prefsDraft.query = e.target.value;
  renderPrefsArtists();
});

document.getElementById("prefs-artists").addEventListener("click", e => {
  const btn = e.target.closest("[data-add-artist]");
  if (!btn || !prefsDraft) return;
  const id = btn.dataset.addArtist;
  if (!prefsDraft.artist_ids.includes(id) && prefsDraft.artist_ids.length < MAX_PREF_ARTISTS) {
    prefsDraft.artist_ids.push(id);
    message("prefs-message", "", false);
    renderPrefsArtists();
  }
});

document.getElementById("prefs-selected-artists").addEventListener("click", e => {
  const btn = e.target.closest("[data-remove-artist]");
  if (!btn || !prefsDraft) return;
  prefsDraft.artist_ids = prefsDraft.artist_ids.filter(id => id !== btn.dataset.removeArtist);
  renderPrefsArtists();
});

document.getElementById("prefs-use-scales").addEventListener("change", e => {
  if (!prefsDraft) return;
  prefsDraft.useScales = e.target.checked;
  message("prefs-message", "", false);
  renderPrefsScales();
});

document.getElementById("prefs-scales").addEventListener("input", e => {
  const input = e.target.closest("input[data-scale]");
  if (!input || !prefsDraft) return;
  const key = input.dataset.scale, val = Number(input.value);
  prefsDraft.scales[key] = val;
  input.style.setProperty("--fill", `${((val - 1) / 4) * 100}%`);
  const badge = document.querySelector(`[data-scale-val="${key}"]`);
  if (badge) badge.textContent = `${val} / 5`;
});

document.getElementById("prefs-next").addEventListener("click", () => {
  if (!prefsDraft || prefsDraft.step >= 3) return;
  message("prefs-message", "", false);
  prefsDraft.step += 1;
  renderPrefsStep(true);
});

document.getElementById("prefs-back").addEventListener("click", () => {
  if (!prefsDraft || prefsDraft.step <= 1) return;
  message("prefs-message", "", false);
  prefsDraft.step -= 1;
  renderPrefsStep(true);
});

document.getElementById("prefs-close").addEventListener("click", closePrefs);
document.getElementById("prefs-skip").addEventListener("click", async () => {
  if (prefsMode === "onboarding") {
    try { state.prefs = await api("/preferences/me/skip", { method: "POST" }); renderForYou(); } catch { /* se podrá responder después */ }
  }
  closePrefs();
});
document.getElementById("prefs-modal").addEventListener("keydown", e => {
  if (e.key === "Escape") { e.preventDefault(); closePrefs(); }
});

document.getElementById("prefs-form").onsubmit = async e => {
  e.preventDefault();
  if (!prefsDraft) return;
  if (prefsDraft.step < 3) { prefsDraft.step += 1; renderPrefsStep(true); return; }
  const btn = document.getElementById("prefs-save");
  if (btn.disabled) return;
  btn.disabled = true; message("prefs-message", "", false);
  const body = {
    genres: [...prefsDraft.genres],
    artist_ids: [...prefsDraft.artist_ids],
    scales: prefsDraft.useScales ? { ...prefsDraft.scales } : null,
  };
  try {
    state.prefs = await api("/preferences/me", { method: "PUT", body: JSON.stringify(body) });
    closePrefs(); forYou = null; renderForYou();
    await loadForYou();
  } catch (err) { message("prefs-message", err.message); } finally { btn.disabled = false; }
};
document.getElementById("account-prefs").onclick = () => { document.getElementById("account-menu").hidden = true; openPrefs("edit"); };
document.getElementById("for-you-edit").onclick = () => openPrefs("edit");
document.getElementById("prefs-invite-open").onclick = () => openPrefs("edit");
