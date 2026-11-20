/* ============================================================
   SoundPass — Panel de administración (admin.html)
   Reutiliza la sesión de la tienda (mismo token en localStorage).

   CONTRATO PENDIENTE CON BACKEND (hoy no existe):
   - /auth/me debe devolver el rol de la cuenta: { ..., "role": "admin" }.
   - Las rutas POST/PUT/DELETE de /concerts y /venues deben exigir ese rol.
   Mientras tanto, el panel NO se abre: sin el campo "role" no se puede
   confirmar que la cuenta sea administradora. Ocultar el panel en el
   navegador no protege nada por sí solo; la protección real es del backend.
   ============================================================ */
(function () {
  "use strict";
  var API_URL = "/api", TOKEN_KEY = "soundpass_token", ADMIN_ROLE = "admin", ROLE_FIELD = "role";
  var $ = function (id) { return document.getElementById(id); };
  var S = { user: null, concerts: [], venues: [], tab: "concerts", editingId: null, del: null, loadSeq: 0, busy: false };
  var lastFocus = null, toastTimer = null;

  function getToken() { try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; } }
  function setToken(t) { try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch (e) { /* sin almacenamiento */ } }

  /* ---------- API ---------- */
  function api(path, options) {
    options = options || {};
    var headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
    if (getToken()) headers.Authorization = "Bearer " + getToken();
    return fetch(API_URL + path, Object.assign({}, options, { headers: headers })).then(function (res) {
      return res.text().then(function (txt) {
        var data = {}; try { data = txt ? JSON.parse(txt) : {}; } catch (e) { data = {}; }
        if (!res.ok) {
          var d = data && data.detail, err = new Error(
            res.status === 401 && !path.indexOf("/auth/login") ? "Correo o contraseña incorrectos." :
            res.status === 401 ? "Tu sesión expiró. Inicia sesión de nuevo." :
            res.status === 403 ? "No tienes permisos para esta acción." :
            typeof d === "string" && d ? d :
            d && typeof d.message === "string" && d.message ? d.message :
            Array.isArray(d) ? "Revisa los datos ingresados." :
            "No fue posible completar la solicitud.");
          err.status = res.status; throw err;
        }
        return data;
      });
    }, function () { throw new Error("No fue posible conectar con la API. Verifica que el backend esté activo."); });
  }

  /* ---------- Utilidades ---------- */
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function show(id, on) { $(id).hidden = !on; }
  function setMsg(id, text) { $(id).textContent = text || ""; }
  function toast(text, isError) {
    var t = $("adm-toast"); t.textContent = text; t.classList.toggle("is-error", !!isError); t.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.hidden = true; }, 3800);
  }
  function fmtDate(iso) { var p = String(iso || "").slice(0, 10).split("-"); return p.length === 3 ? p[2] + "/" + p[1] + "/" + p[0] : "—"; }
  function isPast(iso) { var p = String(iso || "").slice(0, 10).split("-").map(Number), n = new Date(); return p.length === 3 && Date.UTC(p[0], p[1] - 1, p[2]) < Date.UTC(n.getFullYear(), n.getMonth(), n.getDate()); }
  function validImage(v) { return !v || /^https?:\/\/\S+$/i.test(v) || /^\/[^\s/]\S*$/.test(v); }
  function setBusy(btn, on, label) { btn.disabled = on; if (label) btn.textContent = on ? "Guardando…" : label; }

  /* ---------- Vistas de acceso ---------- */
  function showGate(mode, text) {
    show("adm-loading", false); show("adm-panel", false); show("adm-gate", true);
    show("adm-login", mode === "login"); show("adm-denied", mode === "denied"); show("adm-user", mode === "denied");
    $("adm-gate-title").textContent = mode === "denied" ? "Sin acceso al panel" : "Panel de administración";
    $("adm-gate-sub").textContent = mode === "denied" ? "" : "Inicia sesión con una cuenta de administrador.";
    $("adm-gate-sub").hidden = mode === "denied";
    setMsg("adm-denied-msg", mode === "denied" ? text : "");
    setMsg("adm-login-msg", mode === "login" ? text : "");
    if (mode === "login") { $("adm-user").hidden = true; $("adm-password").value = ""; }
  }
  function adminState(user) {
    if (!user || typeof user !== "object") return "none";
    if (!(ROLE_FIELD in user)) return "norole";
    return user[ROLE_FIELD] === ADMIN_ROLE ? "ok" : "other";
  }
  function enter(user) {
    S.user = user;
    var st = adminState(user);
    if (st === "ok") {
      $("adm-user-name").textContent = user.full_name || user.email || "Administrador";
      show("adm-user", true); show("adm-gate", false); show("adm-loading", false); show("adm-panel", true);
      loadAll(); return;
    }
    showGate("denied", st === "norole"
      ? "No se puede confirmar que tu cuenta sea de administrador: el servidor todavía no informa el rol de la cuenta. Pide al equipo de backend que agregue el campo «role» a /auth/me."
      : "Tu cuenta no tiene permisos de administrador.");
    $("adm-user-name").textContent = user.full_name || user.email || ""; show("adm-user", true);
  }
  function logout(message) {
    setToken(null); S.user = null; S.concerts = []; S.venues = []; S.loadSeq++;
    closeModals(); showGate("login", message || "");
  }
  function boot() {
    if (!getToken()) return showGate("login", "");
    api("/auth/me").then(enter, function (e) {
      if (e.status === 401) { setToken(null); showGate("login", ""); }
      else { show("adm-loading", false); showGate("login", e.message); }
    });
  }

  /* ---------- Carga de datos ---------- */
  function loadAll() {
    var seq = ++S.loadSeq; setMsg("c-empty", ""); showBanner("");
    $("c-empty").hidden = false; $("c-empty").textContent = "Cargando…"; $("v-empty").hidden = false; $("v-empty").textContent = "Cargando…";
    return Promise.all([api("/concerts?sort=date"), api("/venues")]).then(function (r) {
      if (seq !== S.loadSeq) return;
      S.concerts = Array.isArray(r[0]) ? r[0] : []; S.venues = Array.isArray(r[1]) ? r[1] : [];
      renderAll();
    }, function (e) {
      if (seq !== S.loadSeq) return;
      if (e.status === 401) return logout("Tu sesión expiró. Inicia sesión de nuevo.");
      $("c-body").textContent = ""; $("v-body").textContent = "";
      $("c-empty").hidden = true; $("v-empty").hidden = true;
      showBanner(e.message + " ");
      var b = el("button", "btn btn--outline btn--sm", "Reintentar"); b.type = "button"; b.onclick = loadAll; $("adm-banner").appendChild(b);
    });
  }
  function showBanner(text) { var b = $("adm-banner"); b.textContent = text || ""; b.hidden = !text; }

  /* ---------- Render ---------- */
  function renderAll() { renderStats(); renderConcerts(); renderVenues(); }
  function renderStats() {
    var up = S.concerts.filter(function (c) { return !isPast(c.event_date); }).length;
    var tk = S.concerts.reduce(function (s, c) { return s + (Number(c.tickets_available) || 0); }, 0);
    var known = S.concerts.some(function (c) { return c.tickets_available != null; });
    $("st-concerts").textContent = S.concerts.length.toLocaleString("es-CO");
    $("st-upcoming").textContent = up.toLocaleString("es-CO");
    $("st-venues").textContent = S.venues.length.toLocaleString("es-CO");
    $("st-tickets").textContent = known ? tk.toLocaleString("es-CO") : "—";
  }
  function norm(s) { return String(s || "").toLocaleLowerCase("es").normalize("NFD").replace(/[̀-ͯ]/g, ""); }
  function td(label, cls) { var c = el("td", cls || ""); if (label) c.setAttribute("data-l", label); return c; }
  function renderConcerts() {
    var q = norm($("c-search").value.trim()), body = $("c-body"); body.textContent = "";
    var rows = S.concerts.filter(function (c) {
      return !q || [c.artist, c.tour_name, c.genre, c.venue && c.venue.name, c.venue && c.venue.city].some(function (v) { return norm(v).indexOf(q) !== -1; });
    });
    rows.forEach(function (c) {
      var tr = el("tr"), a = td("");
      a.appendChild(el("div", "adm-cell-main", c.artist));
      a.appendChild(el("div", "adm-cell-sub", c.tour_name + (c.genre ? " · " + c.genre : "")));
      var v = td("Recinto"); v.textContent = c.venue ? c.venue.name + (c.venue.city ? " — " + c.venue.city : "") : "—";
      var d = td("Fecha"); d.appendChild(document.createTextNode(fmtDate(c.event_date) + (c.event_time ? " · " + String(c.event_time).slice(0, 5) : "")));
      if (isPast(c.event_date)) d.appendChild(el("span", "adm-pill adm-pill--past", "Finalizado"));
      var t = td("Boletos", "num");
      if (c.tickets_available == null) t.textContent = "—";
      else { t.textContent = Number(c.tickets_available).toLocaleString("es-CO"); if (Number(c.tickets_available) === 0) t.appendChild(el("span", "adm-pill adm-pill--out", "Agotado")); }
      var act = td("", "act"), e = el("button", "btn btn--outline btn--sm", "Editar"), x = el("button", "btn btn--danger-outline btn--sm", "Eliminar");
      e.type = x.type = "button"; e.setAttribute("aria-label", "Editar " + c.artist); x.setAttribute("aria-label", "Eliminar " + c.artist);
      e.onclick = function () { openConcert(c.id); };
      x.onclick = function () { askDelete("concert", c); };
      act.appendChild(e); act.appendChild(x);
      [a, v, d, t, act].forEach(function (n) { tr.appendChild(n); }); body.appendChild(tr);
    });
    var em = $("c-empty"); em.hidden = rows.length > 0;
    em.textContent = S.concerts.length ? "Ningún concierto coincide con la búsqueda." : "Todavía no hay conciertos. Crea el primero con «Nuevo concierto».";
  }
  function renderVenues() {
    var body = $("v-body"); body.textContent = "";
    S.venues.forEach(function (v) {
      var tr = el("tr"), n = td(""); n.appendChild(el("div", "adm-cell-main", v.name));
      var c = td("Ciudad"); c.textContent = v.city || "—";
      var a = td("Dirección"); a.textContent = v.address || "—";
      var k = td("Capacidad", "num"); k.textContent = v.capacity != null ? Number(v.capacity).toLocaleString("es-CO") : "—";
      var act = td("", "act"), x = el("button", "btn btn--danger-outline btn--sm", "Eliminar"); x.type = "button"; x.setAttribute("aria-label", "Eliminar " + v.name);
      x.onclick = function () { askDelete("venue", v); }; act.appendChild(x);
      [n, c, a, k, act].forEach(function (m) { tr.appendChild(m); }); body.appendChild(tr);
    });
    var em = $("v-empty"); em.hidden = S.venues.length > 0; em.textContent = "Todavía no hay recintos. Crea uno con «Nuevo recinto».";
  }

  /* ---------- Pestañas ---------- */
  function setTab(name) {
    S.tab = name;
    ["concerts", "venues"].forEach(function (t) {
      var on = t === name; $("tab-" + t).classList.toggle("is-active", on); $("tab-" + t).setAttribute("aria-selected", on ? "true" : "false"); show("pane-" + t, on);
    });
  }

  /* ---------- Modales ---------- */
  function openModal(id, focusId) { lastFocus = document.activeElement; $(id).hidden = false; var f = $(focusId); if (f) f.focus(); }
  function closeModals() {
    ["cm", "vm", "dm"].forEach(function (m) { $(m).hidden = true; });
    S.editingId = null; S.del = null; S.busy = false;
    if (lastFocus && lastFocus.focus && document.body.contains(lastFocus)) lastFocus.focus(); lastFocus = null;
  }
  function fillVenueSelect(sel) {
    var s = $("cm-venue"); s.textContent = "";
    var ph = el("option", "", "Selecciona un recinto"); ph.value = ""; s.appendChild(ph);
    S.venues.forEach(function (v) { var o = el("option", "", v.name + " — " + v.city); o.value = String(v.id); s.appendChild(o); });
    s.value = sel != null ? String(sel) : "";
  }
  function clearErrors(form) { Array.prototype.forEach.call(form.querySelectorAll(".has-error"), function (n) { n.classList.remove("has-error"); }); }
  function flag(input) { input.closest(".field").classList.add("has-error"); }

  function openConcert(id) {
    S.editingId = id || null; $("cm-form").reset(); clearErrors($("cm-form")); setMsg("cm-msg", "");
    $("cm-title").textContent = id ? "Editar concierto" : "Nuevo concierto";
    if (!id) { fillVenueSelect(null); return openModal("cm", "cm-artist"); }
    // El listado no trae descripción ni imagen: se pide el detalle.
    $("cm-save").disabled = true; openModal("cm", "cm-cancel"); setMsg("cm-msg", "");
    api("/concerts/" + encodeURIComponent(id)).then(function (c) {
      if (S.editingId !== id) return;
      $("cm-artist").value = c.artist || ""; $("cm-tour").value = c.tour_name || ""; $("cm-genre").value = c.genre || "";
      fillVenueSelect(c.venue && c.venue.id); $("cm-date").value = String(c.event_date || "").slice(0, 10);
      $("cm-time").value = String(c.event_time || "").slice(0, 5); $("cm-image").value = c.image_url || ""; $("cm-desc").value = c.description || "";
      $("cm-save").disabled = false; $("cm-artist").focus();
    }, function (e) {
      if (S.editingId !== id) return;
      if (e.status === 401) return logout("Tu sesión expiró. Inicia sesión de nuevo.");
      setMsg("cm-msg", e.message + " Cierra y vuelve a intentarlo.");
    });
  }
  function saveConcert(ev) {
    ev.preventDefault(); if (S.busy) return;
    var f = $("cm-form"), g = function (n) { return f.elements[n]; }, bad = [];
    clearErrors(f); setMsg("cm-msg", "");
    ["artist", "tour_name", "genre", "venue_id", "event_date", "event_time"].forEach(function (n) { if (!String(g(n).value).trim()) bad.push(g(n)); });
    if (!validImage(g("image_url").value.trim())) bad.push(g("image_url"));
    if (bad.length) {
      bad.forEach(flag); bad[0].focus();
      return setMsg("cm-msg", bad[0] === g("image_url") ? "La imagen debe ser una URL http(s) o una ruta que empiece por «/»." : "Completa los campos obligatorios.");
    }
    var body = {
      artist: g("artist").value.trim(), tour_name: g("tour_name").value.trim(), genre: g("genre").value.trim(),
      venue_id: Number(g("venue_id").value), event_date: g("event_date").value, event_time: g("event_time").value,
      description: g("description").value.trim() || null, image_url: g("image_url").value.trim() || null
    };
    var id = S.editingId, btn = $("cm-save"); S.busy = true; setBusy(btn, true, "Guardar");
    api(id ? "/concerts/" + encodeURIComponent(id) : "/concerts", { method: id ? "PUT" : "POST", body: JSON.stringify(body) }).then(function () {
      S.busy = false; setBusy(btn, false, "Guardar"); closeModals(); toast(id ? "Concierto actualizado." : "Concierto creado."); loadAll();
    }, function (e) {
      S.busy = false; setBusy(btn, false, "Guardar");
      if (e.status === 401) return logout("Tu sesión expiró. Inicia sesión de nuevo.");
      setMsg("cm-msg", e.message);
    });
  }

  function openVenue() { $("vm-form").reset(); clearErrors($("vm-form")); setMsg("vm-msg", ""); openModal("vm", "vm-name"); }
  function saveVenue(ev) {
    ev.preventDefault(); if (S.busy) return;
    var f = $("vm-form"), g = function (n) { return f.elements[n]; }, bad = [];
    clearErrors(f); setMsg("vm-msg", "");
    ["name", "city"].forEach(function (n) { if (!g(n).value.trim()) bad.push(g(n)); });
    var cap = g("capacity").value.trim(); if (cap && !/^[1-9]\d{0,8}$/.test(cap)) bad.push(g("capacity"));
    if (bad.length) { bad.forEach(flag); bad[0].focus(); return setMsg("vm-msg", bad[0] === g("capacity") ? "La capacidad debe ser un número entero mayor que 0." : "Completa los campos obligatorios."); }
    var body = { name: g("name").value.trim(), city: g("city").value.trim(), address: g("address").value.trim() || null, capacity: cap ? Number(cap) : null };
    var btn = $("vm-save"); S.busy = true; setBusy(btn, true, "Guardar");
    api("/venues", { method: "POST", body: JSON.stringify(body) }).then(function () {
      S.busy = false; setBusy(btn, false, "Guardar"); closeModals(); toast("Recinto creado."); loadAll();
    }, function (e) {
      S.busy = false; setBusy(btn, false, "Guardar");
      if (e.status === 401) return logout("Tu sesión expiró. Inicia sesión de nuevo.");
      setMsg("vm-msg", e.message);
    });
  }

  function askDelete(kind, item) {
    S.del = { kind: kind, id: item.id }; setMsg("dm-msg", ""); $("dm-confirm").disabled = false;
    $("dm-title").textContent = kind === "concert" ? "Eliminar concierto" : "Eliminar recinto";
    $("dm-text").textContent = kind === "concert"
      ? "¿Eliminar «" + item.artist + " — " + item.tour_name + "»? Esta acción no se puede deshacer."
      : "¿Eliminar el recinto «" + item.name + "»? Esta acción no se puede deshacer.";
    openModal("dm", "dm-cancel");
  }
  function confirmDelete() {
    if (!S.del || S.busy) return;
    var d = S.del, btn = $("dm-confirm"); S.busy = true; btn.disabled = true; setMsg("dm-msg", "");
    api((d.kind === "concert" ? "/concerts/" : "/venues/") + encodeURIComponent(d.id), { method: "DELETE" }).then(function () {
      S.busy = false; closeModals(); toast(d.kind === "concert" ? "Concierto eliminado." : "Recinto eliminado."); loadAll();
    }, function (e) {
      S.busy = false; btn.disabled = false;
      if (e.status === 401) return logout("Tu sesión expiró. Inicia sesión de nuevo.");
      setMsg("dm-msg", e.status >= 500 && d.kind === "concert"
        ? "No se pudo eliminar. Si el concierto ya tiene órdenes asociadas, el sistema no permite borrarlo."
        : e.message);
    });
  }

  /* ---------- Eventos ---------- */
  $("adm-login").addEventListener("submit", function (ev) {
    ev.preventDefault(); var f = ev.currentTarget, btn = f.querySelector("[type=submit]"); if (btn.disabled) return;
    var email = $("adm-email").value.trim(), pass = $("adm-password").value;
    if (!email || !pass) return setMsg("adm-login-msg", "Ingresa tu correo y tu contraseña.");
    btn.disabled = true; setMsg("adm-login-msg", "");
    api("/auth/login", { method: "POST", body: JSON.stringify({ email: email, password: pass }) }).then(function (r) {
      setToken(r.access_token); return api("/auth/me");
    }).then(function (u) { btn.disabled = false; enter(u); }, function (e) { btn.disabled = false; setToken(null); setMsg("adm-login-msg", e.message); });
  });
  $("adm-logout").onclick = function () { logout(""); };
  $("adm-denied-logout").onclick = function () { logout(""); };
  document.querySelectorAll(".adm-tab").forEach(function (b) { b.onclick = function () { setTab(b.dataset.tab); }; });
  $("c-search").addEventListener("input", renderConcerts);
  $("c-new").onclick = function () { openConcert(null); };
  $("v-new").onclick = openVenue;
  $("cm-form").addEventListener("submit", saveConcert); $("vm-form").addEventListener("submit", saveVenue);
  $("dm-confirm").onclick = confirmDelete;
  ["cm-close", "cm-cancel", "vm-close", "vm-cancel", "dm-cancel"].forEach(function (i) { $(i).onclick = function () { if (!S.busy) closeModals(); }; });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !S.busy && ["cm", "vm", "dm"].some(function (m) { return !$(m).hidden; })) closeModals();
  });
  boot();
})();
