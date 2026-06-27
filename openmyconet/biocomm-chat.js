/**
 * biocomm-chat.js — OpenMycoNet Wissensvermittler (schwebendes Widget, unten rechts)
 * Einbinden am Ende von index.html, vor </body>:
 *   <script src="/static/biocomm-chat.js"></script>
 * Kein <div> nötig — das Widget baut sich selbst auf.
 *
 * Avatar-Zustände (CSS-Klasse auf #omn-fab und #omn-widget):
 *   omn-state-offline   — heute: ruhiger Sensor-Knoten (Standard)
 *   omn-state-active    — später: Daten vorhanden, Lichtpulse
 *   omn-state-growing   — später: Netzwerk wächst, neue Myzelstränge
 */

(function () {
  const API_URL = "https://api.openmyconet.de/api/chat";
  let history = [];
  let isOpen = false;

  // Zustand: "offline" | "active" | "growing"
  const NETWORK_STATE = "offline";

  // -----------------------------------------------------------------------
  // Sprache — aus URL-Parameter oder Browser-Sprache
  // -----------------------------------------------------------------------
  function detectLang() {
    const params = new URLSearchParams(window.location.search);
    const urlLang = params.get("lang");
    if (urlLang && ["de","en","nl","fr","es"].includes(urlLang)) return urlLang;
    const browser = (navigator.language || "de").slice(0,2).toLowerCase();
    return ["de","en","nl","fr","es"].includes(browser) ? browser : "de";
  }
  const LANG = detectLang();

  const i18n = {
    de: {
      title:       "OpenMycoNet Wissensvermittler",
      state:       "Sensor-Netzwerk \u00b7 Offline-Modus",
      greeting:    "Hallo! Ich beantworte Fragen zu OpenMycoNet und BioComm \u2014 einfach losschreiben.",
      placeholder: "Frage stellen\u2026",
      send:        "Senden",
      aria:        "OpenMycoNet Wissensvermittler \u00f6ffnen",
      tooltip:     "Fragen zum Projekt?",
    },
    en: {
      title:       "OpenMycoNet Knowledge Guide",
      state:       "Sensor Network \u00b7 Offline Mode",
      greeting:    "Hello! I answer questions about OpenMycoNet and BioComm \u2014 just start typing.",
      placeholder: "Ask a question\u2026",
      send:        "Send",
      aria:        "Open OpenMycoNet Knowledge Guide",
      tooltip:     "Questions about the project?",
    },
    nl: {
      title:       "OpenMycoNet Kennisassistent",
      state:       "Sensornetwerk \u00b7 Offline-modus",
      greeting:    "Hallo! Ik beantwoord vragen over OpenMycoNet en BioComm \u2014 begin maar te typen.",
      placeholder: "Stel een vraag\u2026",
      send:        "Versturen",
      aria:        "OpenMycoNet Kennisassistent openen",
      tooltip:     "Vragen over het project?",
    },
    fr: {
      title:       "Guide de connaissances OpenMycoNet",
      state:       "R\u00e9seau de capteurs \u00b7 Mode hors ligne",
      greeting:    "Bonjour ! Je r\u00e9ponds aux questions sur OpenMycoNet et BioComm \u2014 \u00e9crivez simplement.",
      placeholder: "Poser une question\u2026",
      send:        "Envoyer",
      aria:        "Ouvrir le guide OpenMycoNet",
      tooltip:     "Des questions sur le projet ?",
    },
    es: {
      title:       "Gu\u00eda de conocimiento OpenMycoNet",
      state:       "Red de sensores \u00b7 Modo sin conexi\u00f3n",
      greeting:    "\u00a1Hola! Respondo preguntas sobre OpenMycoNet y BioComm \u2014 simplemente escribe.",
      placeholder: "Hacer una pregunta\u2026",
      send:        "Enviar",
      aria:        "Abrir gu\u00eda OpenMycoNet",
      tooltip:     "\u00bfPreguntas sobre el proyecto?",
    },
  };
  const T = i18n[LANG] || i18n.de;

  // -----------------------------------------------------------------------
  // SVG Avatar — Sensor-Knoten mit Myzelstruktur (Variante B)
  // -----------------------------------------------------------------------
  const avatarSVG = `
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 56 56" width="56" height="56" id="omn-avatar-svg">
    <defs>
      <!-- Cyan-Glühen für LED und Impulse -->
      <filter id="omn-glow" x="-40%" y="-40%" width="180%" height="180%">
        <feGaussianBlur stdDeviation="2.5" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
      <!-- Subtiles Myzel-Glühen -->
      <filter id="omn-glow-soft" x="-60%" y="-60%" width="220%" height="220%">
        <feGaussianBlur stdDeviation="1.5" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
      <!-- Radialer Gradient für Sensor-Kern -->
      <radialGradient id="omn-core-grad" cx="50%" cy="45%" r="55%">
        <stop offset="0%" stop-color="#013826"/>
        <stop offset="100%" stop-color="#013020"/>
      </radialGradient>
    </defs>

    <!-- Äußerer Ring — Sensor-Gehäuse -->
    <circle cx="28" cy="28" r="26" fill="#013020" stroke="#013826" stroke-width="1.5"/>

    <!-- Myzelstränge (dezent, Offline-Modus) -->
    <g id="omn-myzel" opacity="0.35" filter="url(#omn-glow-soft)">
      <line x1="28" y1="28" x2="10" y2="18" stroke="#d4a030" stroke-width="0.6" stroke-linecap="round"/>
      <line x1="28" y1="28" x2="46" y2="16" stroke="#d4a030" stroke-width="0.6" stroke-linecap="round"/>
      <line x1="28" y1="28" x2="8"  y2="38" stroke="#d4a030" stroke-width="0.5" stroke-linecap="round"/>
      <line x1="28" y1="28" x2="48" y2="40" stroke="#d4a030" stroke-width="0.5" stroke-linecap="round"/>
      <line x1="28" y1="28" x2="22" y2="50" stroke="#d4a030" stroke-width="0.4" stroke-linecap="round"/>
      <line x1="28" y1="28" x2="36" y2="50" stroke="#d4a030" stroke-width="0.4" stroke-linecap="round"/>
      <!-- Knotenpunkte an den Enden -->
      <circle cx="10" cy="18" r="1.2" fill="#d4a030" opacity="0.6"/>
      <circle cx="46" cy="16" r="1.2" fill="#d4a030" opacity="0.6"/>
      <circle cx="8"  cy="38" r="1.0" fill="#6ee87e" opacity="0.5"/>
      <circle cx="48" cy="40" r="1.0" fill="#6ee87e" opacity="0.5"/>
      <circle cx="22" cy="50" r="0.9" fill="#d4a030" opacity="0.4"/>
      <circle cx="36" cy="50" r="0.9" fill="#d4a030" opacity="0.4"/>
    </g>

    <!-- Sensor-Kern -->
    <circle cx="28" cy="28" r="14" fill="url(#omn-core-grad)" stroke="#0a6040" stroke-width="1"/>

    <!-- Innerer Kreis — Sensorring -->
    <circle cx="28" cy="28" r="10" fill="none" stroke="#0a7050" stroke-width="0.8" opacity="0.7"/>

    <!-- Kreuzmarkierung — Sensor-Mitte -->
    <line x1="24" y1="28" x2="32" y2="28" stroke="#0a7050" stroke-width="0.7" opacity="0.6"/>
    <line x1="28" y1="24" x2="28" y2="32" stroke="#0a7050" stroke-width="0.7" opacity="0.6"/>

    <!-- Status-LED (grün im Offline-Modus, pulsiert später) -->
    <circle id="omn-led" cx="28" cy="28" r="3" fill="#6ee87e" filter="url(#omn-glow)">
      <animate attributeName="opacity" values="0.7;1;0.7" dur="3s" repeatCount="indefinite"/>
      <animate attributeName="r" values="2.8;3.2;2.8" dur="3s" repeatCount="indefinite"/>
    </circle>

    <!-- Äußerer Pulse-Ring (sehr subtil) -->
    <circle cx="28" cy="28" r="20" fill="none" stroke="#d4a030" stroke-width="0.4" opacity="0">
      <animate attributeName="opacity" values="0;0.15;0" dur="4s" repeatCount="indefinite"/>
      <animate attributeName="r" values="16;22;16" dur="4s" repeatCount="indefinite"/>
    </circle>
  </svg>`;

  // FAB-Avatar (kleiner, nur Kern sichtbar)
  const fabSVG = `
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" width="36" height="36">
    <defs>
      <filter id="omn-fab-glow" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="2" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
      <filter id="omn-fab-glow-soft" x="-60%" y="-60%" width="220%" height="220%">
        <feGaussianBlur stdDeviation="1.2" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
      <radialGradient id="omn-fab-grad" cx="50%" cy="45%" r="55%">
        <stop offset="0%" stop-color="#013826"/>
        <stop offset="100%" stop-color="#013020"/>
      </radialGradient>
    </defs>
    <!-- Myzelstränge im FAB -->
    <g opacity="0.4" filter="url(#omn-fab-glow-soft)">
      <line x1="20" y1="20" x2="6"  y2="10" stroke="#d4a030" stroke-width="0.7" stroke-linecap="round"/>
      <line x1="20" y1="20" x2="34" y2="10" stroke="#d4a030" stroke-width="0.7" stroke-linecap="round"/>
      <line x1="20" y1="20" x2="5"  y2="30" stroke="#d4a030" stroke-width="0.5" stroke-linecap="round"/>
      <line x1="20" y1="20" x2="35" y2="30" stroke="#d4a030" stroke-width="0.5" stroke-linecap="round"/>
      <circle cx="6"  cy="10" r="1.2" fill="#d4a030" opacity="0.7"/>
      <circle cx="34" cy="10" r="1.2" fill="#d4a030" opacity="0.7"/>
      <circle cx="5"  cy="30" r="1.0" fill="#6ee87e" opacity="0.5"/>
      <circle cx="35" cy="30" r="1.0" fill="#6ee87e" opacity="0.5"/>
    </g>
    <circle cx="20" cy="20" r="13" fill="url(#omn-fab-grad)" stroke="#0a6040" stroke-width="1"/>
    <circle cx="20" cy="20" r="9"  fill="none" stroke="#0a7050" stroke-width="0.8" opacity="0.6"/>
    <circle cx="20" cy="20" r="3"  fill="#6ee87e" filter="url(#omn-fab-glow)">
      <animate attributeName="opacity" values="0.7;1;0.7" dur="3s" repeatCount="indefinite"/>
      <animate attributeName="r" values="2.6;3.2;2.6" dur="3s" repeatCount="indefinite"/>
    </circle>
    <circle cx="20" cy="20" r="16" fill="none" stroke="#d4a030" stroke-width="0.4" opacity="0">
      <animate attributeName="opacity" values="0;0.2;0" dur="4s" repeatCount="indefinite"/>
      <animate attributeName="r" values="12;18;12" dur="4s" repeatCount="indefinite"/>
    </circle>
  </svg>`;

  // -----------------------------------------------------------------------
  // Styles
  // -----------------------------------------------------------------------
  const style = document.createElement("style");
  style.textContent = `
    #omn-fab {
      position: fixed; bottom: 220px; right: 16px; z-index: 9999;
      width: 56px; height: 56px; border-radius: 50%;
      background: #013020; border: 1.5px solid #0a7050;
      cursor: pointer;
      box-shadow: 0 4px 20px rgba(110,232,126,0.12), 0 2px 8px rgba(0,0,0,0.5);
      display: flex; align-items: center; justify-content: center;
      transition: box-shadow 0.3s, border-color 0.3s;
      padding: 0;
    }
    #omn-fab:hover {
      box-shadow: 0 4px 28px rgba(110,232,126,0.25), 0 2px 8px rgba(0,0,0,0.5);
      border-color: #6ee87e;
    }
    #omn-fab.omn-open-fab {
      background: #013020;
      border-color: #6ee87e;
    }
    #omn-fab-close-icon {
      display: none;
      color: #d4a030; font-size: 22px; line-height: 1;
      font-family: sans-serif; font-weight: 300;
    }
    #omn-fab.omn-open-fab #omn-fab-svg-wrap { display: none; }
    #omn-fab.omn-open-fab #omn-fab-close-icon { display: flex; align-items: center; justify-content: center; }

    #omn-widget {
      position: fixed; bottom: 286px; right: 16px; z-index: 9998;
      width: 370px; max-width: calc(100vw - 32px);
      max-height: calc(100vh - 120px);
      background: #024530; border-radius: 0px;
      border: 1px solid #0a6040;
      box-shadow: 0 8px 40px rgba(0,0,0,0.6), 0 0 20px rgba(10,96,64,0.15);
      display: none; flex-direction: column; overflow: hidden;
      font-family: 'Lora', Georgia, serif;
    }
    #omn-widget.omn-open { display: flex; }

    #omn-widget-header {
      background: #013020;
      border-bottom: 1px solid #0a6040;
      padding: 12px 14px;
      display: flex; align-items: center; gap: 12px;
    }
    #omn-avatar-wrap {
      flex-shrink: 0; width: 44px; height: 44px;
      display: flex; align-items: center; justify-content: center;
    }
    .omn-header-text { flex: 1; }
    .omn-htitle {
      font-size: 14px; font-weight: 600;
      color: #e8f5e0; letter-spacing: 0.02em;
    }
    .omn-hsub {
      font-size: 10px; color: #6ee87e; opacity: 0.75;
      margin-top: 2px; letter-spacing: 0.05em;
    }
    .omn-hstate {
      font-size: 9px; color: #d4a030; opacity: 0.6;
      margin-top: 2px; letter-spacing: 0.08em; text-transform: uppercase;
    }
    #omn-widget-close {
      background: none; border: none;
      color: #d4a030; font-size: 20px; cursor: pointer;
      line-height: 1; padding: 4px; opacity: 0.6;
      transition: opacity 0.2s;
    }
    #omn-widget-close:hover { opacity: 1; }

    #omn-messages {
      flex: 1; overflow-y: auto; padding: 14px;
      display: flex; flex-direction: column; gap: 10px;
      min-height: 120px; max-height: min(320px, calc(100vh - 340px));
      background: #024530;
    }
    /* Scrollbar */
    #omn-messages::-webkit-scrollbar { width: 4px; }
    #omn-messages::-webkit-scrollbar-track { background: transparent; }
    #omn-messages::-webkit-scrollbar-thumb { background: #0a6040; border-radius: 2px; }

    .omn-msg { display: flex; flex-direction: column; max-width: 88%; }
    .omn-msg.omn-user { align-self: flex-end; align-items: flex-end; }
    .omn-msg.omn-bot  { align-self: flex-start; align-items: flex-start; }

    .omn-bubble {
      padding: 9px 13px; border-radius: 0px;
      font-size: 13px; line-height: 1.55;
    }
    .omn-msg.omn-user .omn-bubble {
      background: #0a7050; color: #fff;
      border-bottom-right-radius: 0px;
    }
    .omn-msg.omn-bot .omn-bubble {
      background: rgba(0,0,0,0.28);
      border: 1px solid #0a6040;
      color: #e8f5e0;
      border-bottom-left-radius: 0px;
    }
    .omn-sources {
      font-size: 10px; color: #d4a030;
      margin-top: 4px; opacity: 0.6;
    }
    .omn-thinking { opacity: 0.4; font-style: italic; color: #d4a030; }

    #omn-input-area {
      padding: 10px 12px;
      border-top: 1px solid #0a6040;
      display: flex; gap: 8px; align-items: flex-end;
      background: #013020;
    }
    #omn-input {
      flex: 1; border: 1px solid #0a6040; border-radius: 0px;
      padding: 8px 11px; font-size: 13px; resize: none;
      font-family: sans-serif; max-height: 60px;
      background: #024530; color: #e8f5e0;
      outline: none; transition: border-color 0.2s;
    }
    #omn-input:focus { border-color: #6ee87e; }
    #omn-input::placeholder { color: #5a8a6a; }
    #omn-send {
      background: #0a7050; color: #fff; border: none;
      border-radius: 0px; padding: 8px 14px;
      font-size: 13px; cursor: pointer; white-space: nowrap;
      transition: background 0.2s;
    }
    #omn-send:hover { background: #3a9e5a; }
    #omn-send:disabled { background: #0a6040; color: #5a8a6a; cursor: default; }

    /* Sprachauswahl */
    .omn-lang-btn {
      cursor: pointer; opacity: 0.5;
      transition: opacity 0.2s, color 0.2s;
    }
    .omn-lang-btn:hover { opacity: 0.9; }
    .omn-lang-btn.omn-lang-active {
      opacity: 1; color: #d4a030; font-weight: 700;
    }

    /* Zustandsvarianten — für spätere Aktivierung */
    .omn-state-active #omn-led { fill: #f0b84a; }
    .omn-state-growing #omn-myzel { opacity: 0.7; }

    @media (max-width: 480px) {
      #omn-widget {
        left: 8px; right: 8px; width: auto;
        bottom: 136px;
        max-height: calc(100vh - 100px);
        border-radius: 0px;
      }
      #omn-fab {
        bottom: 72px; right: 16px;
        width: 52px; height: 52px;
      }
      #omn-messages {
        min-height: 80px;
        max-height: min(200px, calc(100vh - 320px));
      }
      #omn-input-area {
        padding: 8px 10px;
      }
      #omn-input {
        font-size: 16px;
        height: 40px;
        max-height: 40px;
      }
      #omn-send {
        padding: 8px 12px;
        font-size: 13px;
        height: 40px;
      }
    }
    `;
  document.head.appendChild(style);

  // -----------------------------------------------------------------------
  // HTML aufbauen
  // -----------------------------------------------------------------------
  document.body.insertAdjacentHTML("beforeend", `
    <button id="omn-fab" aria-label="${T.aria}"
            title="${T.tooltip}" class="omn-state-${NETWORK_STATE}">
      <span id="omn-fab-svg-wrap">${fabSVG}</span>
      <span id="omn-fab-close-icon">×</span>
    </button>

    <div id="omn-widget" role="dialog" aria-label="${T.title}"
         class="omn-state-${NETWORK_STATE}">
      <div id="omn-widget-header">
        <div id="omn-avatar-wrap">${avatarSVG}</div>
        <div class="omn-header-text">
          <div class="omn-htitle">${T.title}</div>
          <div class="omn-hsub" id="omn-lang-bar">
            <span class="omn-lang-btn" data-lang="de">DE</span> ·
            <span class="omn-lang-btn" data-lang="en">EN</span> ·
            <span class="omn-lang-btn" data-lang="nl">NL</span> ·
            <span class="omn-lang-btn" data-lang="fr">FR</span> ·
            <span class="omn-lang-btn" data-lang="es">ES</span>
          </div>
          <div class="omn-hstate">${T.state}</div>
        </div>
        <button id="omn-widget-close" aria-label="×">×</button>
      </div>
      <div id="omn-messages">
        <div class="omn-msg omn-bot">
          <div class="omn-bubble">${T.greeting}</div>
        </div>
      </div>
      <div id="omn-input-area">
        <textarea id="omn-input" rows="1" placeholder="${T.placeholder}"></textarea>
        <button id="omn-send">${T.send}</button>
      </div>
    </div>
  `);

  // -----------------------------------------------------------------------
  // Öffnen / Schließen
  // -----------------------------------------------------------------------
  const fab     = document.getElementById("omn-fab");
  const widget  = document.getElementById("omn-widget");
  const closeBtn = document.getElementById("omn-widget-close");

  function toggleWidget() {
    isOpen = !isOpen;
    widget.classList.toggle("omn-open", isOpen);
    fab.classList.toggle("omn-open-fab", isOpen);
    if (isOpen) {
      // Beim Öffnen aktuelle Seitensprache prüfen und ggf. umschalten
      const params = new URLSearchParams(window.location.search);
      const pageLang = params.get("lang") || "de"; // kein Parameter = Deutsch
      if (i18n[pageLang] && pageLang !== currentLang) {
        setLang(pageLang);
      }
      document.getElementById("omn-input").focus();
    }
  }

  fab.addEventListener("click", toggleWidget);
  closeBtn.addEventListener("click", toggleWidget);

  // -----------------------------------------------------------------------
  // Nachrichten
  // -----------------------------------------------------------------------
  function addMessage(role, text, sources) {
    const box = document.getElementById("omn-messages");
    const div = document.createElement("div");
    div.className = "omn-msg " + (role === "user" ? "omn-user" : "omn-bot");
    const bub = document.createElement("div");
    bub.className = "omn-bubble";
    // URLs in klickbare Links umwandeln (nur für Bot-Nachrichten)
    if (role === "bot") {
      const escaped = text.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
      // URLs als klickbare Links
      let linked = escaped.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener" style="color:#d4a030;text-decoration:underline;">$1</a>');
      // E-Mail-Adressen als mailto-Links
      linked = linked.replace(/([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})/g, '<a href="mailto:$1" style="color:#d4a030;text-decoration:underline;">$1</a>');
      bub.innerHTML = linked;
    } else {
      bub.textContent = text;
    }
    div.appendChild(bub);
    if (sources && sources.length) {
      const s = document.createElement("div");
      s.className = "omn-sources";
      s.textContent = "📡 " + sources.join(" · ");
      div.appendChild(s);
    }
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
    return bub;
  }

  // -----------------------------------------------------------------------
  // Senden
  // -----------------------------------------------------------------------
  async function sendMessage() {
    const inp = document.getElementById("omn-input");
    const btn = document.getElementById("omn-send");
    const msg = inp.value.trim();
    if (!msg) return;

    inp.value = "";
    btn.disabled = true;

    addMessage("user", msg);
    history.push({ role: "user", content: msg });

    const box = document.getElementById("omn-messages");
    const thinkDiv = document.createElement("div");
    thinkDiv.className = "omn-msg omn-bot";
    const thinkBub = document.createElement("div");
    thinkBub.className = "omn-bubble omn-thinking";
    thinkBub.textContent = "…";
    thinkDiv.appendChild(thinkBub);
    box.appendChild(thinkDiv);
    box.scrollTop = box.scrollHeight;

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, history: history.slice(0, -1), lang: currentLang }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      const data = await res.json();
      thinkDiv.remove();
      addMessage("bot", data.answer, data.chunks_used);
      history.push({ role: "assistant", content: data.answer });
    } catch (e) {
      thinkBub.textContent = "Fehler: " + e.message;
      thinkBub.classList.remove("omn-thinking");
    }

    btn.disabled = false;
    inp.focus();
  }

  document.getElementById("omn-send").addEventListener("click", sendMessage);
  document.getElementById("omn-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });

  // -----------------------------------------------------------------------
  // Sprachumschaltung — nach DOM-Aufbau initialisieren
  // -----------------------------------------------------------------------
  let currentLang = LANG;

  function setLang(lang) {
    if (!i18n[lang]) return;
    currentLang = lang;
    const Tx = i18n[lang];

    document.querySelector(".omn-htitle").textContent = Tx.title;
    document.querySelector(".omn-hstate").textContent = Tx.state;
    document.getElementById("omn-input").placeholder = Tx.placeholder;
    document.getElementById("omn-send").textContent = Tx.send;
    document.getElementById("omn-fab").title = Tx.tooltip;
    document.getElementById("omn-fab").setAttribute("aria-label", Tx.aria);
    document.getElementById("omn-widget").setAttribute("aria-label", Tx.title);

    // Begrüßungstext aktualisieren (erste Bot-Nachricht)
    const firstBubble = document.querySelector("#omn-messages .omn-bot .omn-bubble");
    if (firstBubble) firstBubble.textContent = Tx.greeting;

    document.querySelectorAll(".omn-lang-btn").forEach(btn => {
      btn.classList.toggle("omn-lang-active", btn.dataset.lang === lang);
    });
  }

  // Initiale Markierung setzen (DOM ist jetzt bereit)
  setLang(currentLang);

  // Klick-Handler
  document.querySelectorAll(".omn-lang-btn").forEach(btn => {
    btn.addEventListener("click", () => setLang(btn.dataset.lang));
  });

})();
