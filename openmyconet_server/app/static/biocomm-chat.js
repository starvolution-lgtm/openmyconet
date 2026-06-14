/**
 * biocomm-chat.js — OpenMycoNet Chatbot (schwebendes Widget, unten rechts)
 * Einbinden am Ende von index.html, vor </body>:
 *   <script src="/static/biocomm-chat.js"></script>
 * Kein <div> nötig — das Widget baut sich selbst auf.
 */

(function () {
  const API_URL = "/api/chat";
  let history = [];
  let isOpen = false;

  // -----------------------------------------------------------------------
  // Styles
  // -----------------------------------------------------------------------
  const style = document.createElement("style");
  style.textContent = `
    #omn-fab {
      position: fixed; bottom: 24px; right: 24px; z-index: 9999;
      width: 56px; height: 56px; border-radius: 50%;
      background: #1D9E75; color: #fff; border: none;
      font-size: 26px; cursor: pointer; box-shadow: 0 4px 16px rgba(0,0,0,0.25);
      display: flex; align-items: center; justify-content: center;
      transition: background 0.2s;
    }
    #omn-fab:hover { background: #178a63; }

    #omn-widget {
      position: fixed; bottom: 90px; right: 24px; z-index: 9998;
      width: 360px; max-width: calc(100vw - 48px);
      background: #fff; border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.18);
      display: none; flex-direction: column; overflow: hidden;
      font-family: sans-serif;
    }
    #omn-widget.omn-open { display: flex; }

    #omn-widget-header {
      background: #1D9E75; color: #fff;
      padding: 14px 16px; display: flex; align-items: center; gap: 10px;
    }
    #omn-widget-header .omn-hicon { font-size: 22px; }
    #omn-widget-header .omn-htitle { font-size: 15px; font-weight: 600; }
    #omn-widget-header .omn-hsub { font-size: 11px; opacity: 0.85; }
    #omn-widget-close {
      margin-left: auto; background: none; border: none;
      color: #fff; font-size: 20px; cursor: pointer; line-height: 1; padding: 0 2px;
    }

    #omn-messages {
      flex: 1; overflow-y: auto; padding: 14px;
      display: flex; flex-direction: column; gap: 10px;
      min-height: 220px; max-height: 320px;
      background: #f7f7f5;
    }
    .omn-msg { display: flex; flex-direction: column; max-width: 88%; }
    .omn-msg.omn-user { align-self: flex-end; align-items: flex-end; }
    .omn-msg.omn-bot  { align-self: flex-start; align-items: flex-start; }
    .omn-bubble {
      padding: 9px 13px; border-radius: 14px;
      font-size: 13.5px; line-height: 1.5;
    }
    .omn-msg.omn-user .omn-bubble {
      background: #1D9E75; color: #fff; border-bottom-right-radius: 3px;
    }
    .omn-msg.omn-bot .omn-bubble {
      background: #fff; border: 1px solid #e4e4e4; color: #222;
      border-bottom-left-radius: 3px;
    }
    .omn-sources { font-size: 10px; color: #1D9E75; margin-top: 3px; }
    .omn-thinking { opacity: 0.45; font-style: italic; }

    #omn-input-area {
      padding: 10px 12px; border-top: 1px solid #ececec;
      display: flex; gap: 8px; align-items: flex-end;
      background: #fff;
    }
    #omn-input {
      flex: 1; border: 1px solid #ccc; border-radius: 8px;
      padding: 8px 11px; font-size: 13.5px; resize: none;
      font-family: sans-serif; max-height: 80px;
    }
    #omn-send {
      background: #1D9E75; color: #fff; border: none;
      border-radius: 8px; padding: 8px 14px;
      font-size: 13.5px; cursor: pointer; white-space: nowrap;
    }
    #omn-send:hover { background: #178a63; }
    #omn-send:disabled { background: #aaa; cursor: default; }
  `;
  document.head.appendChild(style);

  // -----------------------------------------------------------------------
  // HTML aufbauen
  // -----------------------------------------------------------------------
  document.body.insertAdjacentHTML("beforeend", `
    <button id="omn-fab" aria-label="OpenMycoNet Assistent öffnen" title="Fragen zum Projekt?">🌿</button>

    <div id="omn-widget" role="dialog" aria-label="OpenMycoNet Chatbot">
      <div id="omn-widget-header">
        <span class="omn-hicon">🌿</span>
        <div>
          <div class="omn-htitle">OpenMycoNet Assistent</div>
          <div class="omn-hsub">DE · EN · NL · FR · ES</div>
        </div>
        <button id="omn-widget-close" aria-label="Schließen">×</button>
      </div>
      <div id="omn-messages">
        <div class="omn-msg omn-bot">
          <div class="omn-bubble">Hallo! Ich beantworte Fragen zu OpenMycoNet und BioComm — einfach losschreiben.</div>
        </div>
      </div>
      <div id="omn-input-area">
        <textarea id="omn-input" rows="1" placeholder="Frage stellen…"></textarea>
        <button id="omn-send">Senden</button>
      </div>
    </div>
  `);

  // -----------------------------------------------------------------------
  // Öffnen / Schließen
  // -----------------------------------------------------------------------
  const fab    = document.getElementById("omn-fab");
  const widget = document.getElementById("omn-widget");
  const closeBtn = document.getElementById("omn-widget-close");

  function toggleWidget() {
    isOpen = !isOpen;
    widget.classList.toggle("omn-open", isOpen);
    fab.textContent = isOpen ? "×" : "🌿";
    fab.style.fontSize = isOpen ? "22px" : "26px";
    if (isOpen) document.getElementById("omn-input").focus();
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
    bub.textContent = text;
    div.appendChild(bub);
    if (sources && sources.length) {
      const s = document.createElement("div");
      s.className = "omn-sources";
      s.textContent = "📄 " + sources.join(" · ");
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
        body: JSON.stringify({ message: msg, history: history.slice(0, -1) }),
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

})();
