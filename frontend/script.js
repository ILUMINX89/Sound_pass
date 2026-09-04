/* ============================================================
   SoundPass — data
   ============================================================ */
const CONCERTS = [
  {
    id: "weeknd",
    artist: "The Weeknd",
    tour: "After Hours Tour",
    date: "15 Jun 2025",
    time: "8:00 p.m.",
    venue: "Movistar Arena, Bogotá",
    priceFrom: 120000,
    art: "art--weeknd",
    thumb: "thumb--weeknd",
    ticketTypes: [
      { id: "general", label: "General", price: 120000 },
      { id: "preferencial", label: "Preferencial", price: 180000 },
      { id: "vip", label: "VIP", price: 250000 },
    ],
  },
  {
    id: "dragons",
    artist: "Imagine Dragons",
    tour: "LOOM World Tour",
    date: "22 Jun 2025",
    time: "8:00 p.m.",
    venue: "El Campín, Bogotá",
    priceFrom: 150000,
    art: "art--dragons",
    thumb: "thumb--dragons",
    ticketTypes: [
      { id: "general", label: "General", price: 150000 },
      { id: "preferencial", label: "Preferencial", price: 210000 },
      { id: "vip", label: "VIP", price: 290000 },
    ],
  },
  {
    id: "dualipa",
    artist: "Dua Lipa",
    tour: "Radical Optimism Tour",
    date: "05 Jul 2025",
    time: "8:00 p.m.",
    venue: "Movistar Arena, Bogotá",
    priceFrom: 110000,
    art: "art--dualipa",
    thumb: "thumb--dualipa",
    ticketTypes: [
      { id: "general", label: "General", price: 110000 },
      { id: "preferencial", label: "Preferencial", price: 165000 },
      { id: "vip", label: "VIP", price: 230000 },
    ],
  },
];

// pre-existing confirmed order shown on "Mis boletos" (screen 6)
let TICKETS = [
  {
    orderId: "SP-458792",
    concertId: "dragons",
    type: "General",
    qty: 1,
    status: "confirmed",
  },
];

const fmtCOP = (n) => "$" + n.toLocaleString("es-CO");

/* ============================================================
   State
   ============================================================ */
const state = {
  screen: "home",
  selectedConcertId: "weeknd",
  selectedTicketTypeId: "preferencial",
  qty: 2,
  serviceFee: 12000,
};

/* ============================================================
   Navigation
   ============================================================ */
function goTo(screenId) {
  document.querySelectorAll("[data-screen]").forEach((el) => {
    el.classList.toggle("is-active", el.id === "screen-" + screenId);
  });
  state.screen = screenId;

  document.querySelectorAll(".primary-nav__link[data-active-on]").forEach((el) => {
    const targets = el.getAttribute("data-active-on").split(",");
    el.classList.toggle("is-active", targets.includes(screenId));
  });

  if (screenId === "checkout") renderCheckout();
  if (screenId === "mytickets") renderTickets();

  window.scrollTo({ top: 0, behavior: "smooth" });
}

document.addEventListener("click", (e) => {
  const navBtn = e.target.closest("[data-nav]");
  if (navBtn) {
    goTo(navBtn.getAttribute("data-nav"));
  }
});

/* ============================================================
   1. Home — featured concerts
   ============================================================ */
function renderFeatured() {
  const grid = document.getElementById("featured-grid");
  grid.innerHTML = CONCERTS.map(
    (c) => `
    <article class="feature-card" data-open="${c.id}">
      <div class="feature-card__art ${c.art}"></div>
      <div class="feature-card__body">
        <p class="feature-card__title">${c.artist}</p>
        <p class="feature-card__meta">${c.venue.split(",")[0]} — ${c.date}</p>
      </div>
    </article>`
  ).join("");
}

/* ============================================================
   2. Listing
   ============================================================ */
function renderListing() {
  const list = document.getElementById("concert-list");
  list.innerHTML = CONCERTS.map(
    (c) => `
    <article class="concert-row" data-open="${c.id}">
      <div class="concert-row__art ${c.art}"></div>
      <div class="concert-row__body">
        <p class="concert-row__title">${c.artist}</p>
        <p class="concert-row__sub">${c.tour}</p>
        <div class="concert-row__meta">
          <span>🗓 ${c.date} · ${c.time}</span>
          <span>📍 ${c.venue}</span>
        </div>
      </div>
      <div class="concert-row__price">
        <small>Desde</small>
        <strong>${fmtCOP(c.priceFrom)}</strong>
      </div>
      <button class="btn btn--primary btn--sm" data-open="${c.id}">Ver evento</button>
    </article>`
  ).join("");
}

document.addEventListener("click", (e) => {
  const openBtn = e.target.closest("[data-open]");
  if (openBtn) {
    state.selectedConcertId = openBtn.getAttribute("data-open");
    const concert = CONCERTS.find((c) => c.id === state.selectedConcertId);
    state.selectedTicketTypeId = concert.ticketTypes[1]?.id || concert.ticketTypes[0].id;
    state.qty = 2;
    renderDetail();
    goTo("detail");
  }
});

/* ============================================================
   3. Detail
   ============================================================ */
function renderDetail() {
  const concert = CONCERTS.find((c) => c.id === state.selectedConcertId);
  if (!concert) return;

  document.querySelector(".detail-title").textContent = concert.artist;
  document.querySelector(".detail-sub").textContent = concert.tour;

  const poster = document.querySelector(".detail-poster");
  poster.className = "detail-poster poster--" + concert.id;
  poster.querySelector(".poster__tag").textContent = concert.artist.toUpperCase();
  poster.querySelector(".poster__tag2").textContent = concert.tour.toUpperCase();

  const metaInfo = document.querySelector(".meta-info");
  metaInfo.innerHTML = `
    <p><span class="dot">•</span> ${concert.date} · ${concert.time}</p>
    <p><span class="dot">•</span> ${concert.venue}</p>
    <p><span class="dot">•</span> Capacidad: 14.000 personas</p>`;

  const optionsWrap = document.getElementById("ticket-options");
  optionsWrap.innerHTML = concert.ticketTypes
    .map(
      (t) => `
    <label class="ticket-option ${t.id === state.selectedTicketTypeId ? "is-selected" : ""}" data-ticket-type="${t.id}">
      <span class="ticket-option__left">
        <span class="radio-outer"><span class="radio-inner"></span></span>
        ${t.label}
      </span>
      <span class="ticket-option__price">${fmtCOP(t.price)}</span>
    </label>`
    )
    .join("");

  document.getElementById("qty-val").textContent = state.qty;
}

document.addEventListener("click", (e) => {
  const opt = e.target.closest("[data-ticket-type]");
  if (opt) {
    state.selectedTicketTypeId = opt.getAttribute("data-ticket-type");
    renderDetail();
  }
});

document.getElementById("qty-minus").addEventListener("click", () => {
  state.qty = Math.max(1, state.qty - 1);
  document.getElementById("qty-val").textContent = state.qty;
});
document.getElementById("qty-plus").addEventListener("click", () => {
  state.qty = Math.min(10, state.qty + 1);
  document.getElementById("qty-val").textContent = state.qty;
});

/* ============================================================
   4. Checkout
   ============================================================ */
function renderCheckout() {
  const concert = CONCERTS.find((c) => c.id === state.selectedConcertId);
  const type = concert.ticketTypes.find((t) => t.id === state.selectedTicketTypeId);
  const subtotal = type.price * state.qty;
  const total = subtotal + state.serviceFee;

  document.querySelector(".summary-item__title").textContent = concert.artist;
  document.querySelector(".summary-item__sub").textContent = concert.tour;
  const metas = document.querySelectorAll(".summary-item__meta");
  metas[0].textContent = `${concert.date} · ${concert.time}`;
  metas[1].textContent = concert.venue;
  document.querySelector(".summary-card .thumb").className = "thumb " + concert.thumb;

  document.querySelectorAll(".summary-rows div")[0].querySelector("dd").textContent = type.label;
  document.getElementById("co-qty").textContent = state.qty;
  document.querySelectorAll(".summary-rows div")[2].querySelector("dd").textContent = fmtCOP(type.price);
  document.getElementById("co-subtotal").textContent = fmtCOP(subtotal);
  document.getElementById("co-total").textContent = fmtCOP(total);

  const payBtn = document.querySelector('#screen-checkout .btn--primary');
  payBtn.lastChild.textContent = " Pagar " + fmtCOP(total);
}

document.querySelectorAll(".payment-option").forEach((opt) => {
  opt.addEventListener("click", () => {
    document.querySelectorAll(".payment-option").forEach((o) => o.classList.remove("is-selected"));
    opt.classList.add("is-selected");
    opt.querySelector("input").checked = true;
  });
});

document.querySelector('#screen-checkout .btn--primary').addEventListener("click", () => {
  // register the newly purchased order
  const concert = CONCERTS.find((c) => c.id === state.selectedConcertId);
  const type = concert.ticketTypes.find((t) => t.id === state.selectedTicketTypeId);
  TICKETS.unshift({
    orderId: "SP-458792",
    concertId: concert.id,
    type: type.label,
    qty: state.qty,
    status: "confirmed",
  });
});

/* ============================================================
   6/9. My tickets
   ============================================================ */
function renderTickets() {
  const list = document.getElementById("ticket-list");
  list.innerHTML = TICKETS.map((t, idx) => {
    const concert = CONCERTS.find((c) => c.id === t.concertId);
    const isCancelled = t.status === "cancelled";
    return `
    <article class="ticket-card">
      <div class="ticket-card__art ${concert.art}"></div>
      <div class="ticket-card__body">
        <div class="ticket-card__title-row">
          <p class="ticket-card__title">${concert.artist}</p>
        </div>
        <p class="ticket-card__sub">${concert.tour}</p>
        <div class="ticket-card__meta">
          <span>🗓 ${concert.date} · ${concert.time}</span>
          <span>📍 ${concert.venue}</span>
        </div>
        <div class="ticket-card__foot">
          <span>${t.qty} boleto${t.qty > 1 ? "s" : ""}</span>
          <span>${t.type}</span>
          <span>Orden #${t.orderId}</span>
        </div>
      </div>
      <div class="ticket-card__actions">
        <span class="badge ${isCancelled ? "badge--cancelled" : "badge--confirmed"}">${isCancelled ? "Cancelado" : "Confirmado"}</span>
        ${
          isCancelled
            ? `<button class="btn btn--outline btn--sm" data-details="${idx}">Ver detalles</button>`
            : `<button class="btn btn--outline btn--sm" data-details="${idx}">Ver boletos</button>
               <button class="btn btn--danger-outline btn--sm" data-cancel="${idx}">Cancelar compra</button>`
        }
      </div>
    </article>`;
  }).join("");
}

let cancelTargetIdx = null;

document.addEventListener("click", (e) => {
  const cancelBtn = e.target.closest("[data-cancel]");
  if (cancelBtn) {
    cancelTargetIdx = Number(cancelBtn.getAttribute("data-cancel"));
    const t = TICKETS[cancelTargetIdx];
    const concert = CONCERTS.find((c) => c.id === t.concertId);
    const modal = document.getElementById("cancel-modal");
    modal.querySelector(".modal-ticket .thumb").className = "thumb " + concert.thumb;
    modal.querySelector(".summary-item__title").textContent = concert.artist;
    modal.querySelectorAll(".summary-item__meta")[0].textContent = `${concert.date} · ${concert.venue}`;
    modal.querySelectorAll(".summary-item__meta")[1].textContent = `${t.qty} boletos · ${t.type}`;
    modal.hidden = false;
  }
});

document.getElementById("modal-close").addEventListener("click", closeModal);
document.getElementById("modal-cancel").addEventListener("click", closeModal);
function closeModal() {
  document.getElementById("cancel-modal").hidden = true;
}

document.getElementById("modal-confirm").addEventListener("click", () => {
  if (cancelTargetIdx !== null) {
    TICKETS[cancelTargetIdx].status = "cancelled";
  }
  closeModal();
  goTo("cancelled");
});

document.addEventListener("click", (e) => {
  const tab = e.target.closest(".tab");
  if (tab) {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("is-active"));
    tab.classList.add("is-active");
  }
});

/* ============================================================
   Init
   ============================================================ */
renderFeatured();
renderListing();
renderDetail();
goTo("home");