/* JARVIS HUD client: vision websocket, chat, voice in (Web Speech) / out (TTS). */

const $ = (id) => document.getElementById(id);
let botName = "JARVIS";
let ttsAvailable = false;

/* ---------- config ---------- */
fetch("/api/config").then(r => r.json()).then(cfg => {
  botName = cfg.bot_name || "JARVIS";
  ttsAvailable = cfg.tts_available;
  $("botName").textContent = botName.split("").join(".") + ".";
  document.title = botName;
});

/* ---------- clock + binary ticker ---------- */
setInterval(() => {
  $("clock").textContent = new Date().toLocaleTimeString("en-GB");
}, 500);
setInterval(() => {
  let s = "";
  for (let i = 0; i < 96; i++) s += Math.random() > 0.5 ? "1" : "0";
  $("binaryTicker").textContent = s;
}, 900);

/* ---------- vision websocket ---------- */
function connectVision() {
  const ws = new WebSocket(`ws://${location.host}/ws/vision`);
  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.frame) {
      const img = $("cam");
      img.src = "data:image/jpeg;base64," + data.frame;
      img.classList.add("live");
      $("coreMsg").style.display = "none";
    }
    renderTracking(data.tracking || {});
  };
  ws.onclose = () => {
    $("coreMsg").style.display = "";
    $("coreMsg").textContent = "RECONNECTING…";
    setTimeout(connectVision, 1500);
  };
}
connectVision();

function renderTracking(t) {
  $("tCamera").textContent = t.camera ? "ONLINE" : "OFFLINE";
  $("tFps").textContent = t.fps ?? 0;
  const hands = t.hands || [];
  $("tHands").textContent = hands.length;
  const left = hands.find(h => h.label === "Left");
  const right = hands.find(h => h.label === "Right");
  $("tLeft").textContent = left ? `${left.fingers_up} ↑ ${left.gesture}` : "—";
  $("tRight").textContent = right ? `${right.fingers_up} ↑ ${right.gesture}` : "—";
  const f = t.face;
  $("tFace").textContent = f ? "LOCKED" : "—";
  $("tYaw").textContent = f ? `${f.yaw_deg}°` : "—";
  $("tPitch").textContent = f ? `${f.pitch_deg}°` : "—";
  const objs = (t.objects || []).filter(o => o.held).map(o => o.label);
  $("tObjects").textContent = objs.length ? objs.join(", ") : "—";
  if (t.error) status(t.error.toUpperCase());
}

/* ---------- chat ---------- */
function addMsg(who, text) {
  const div = document.createElement("div");
  div.className = "msg " + (who === "YOU" ? "user" : "jarvis");
  div.innerHTML = `<div class="who">${who}</div><div class="body"></div>`;
  div.querySelector(".body").textContent = text;
  $("chatLog").appendChild(div);
  $("chatLog").scrollTop = $("chatLog").scrollHeight;
}

async function send() {
  const input = $("chatInput");
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  addMsg("YOU", message);
  status("PROCESSING…");
  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, attach_frame: $("attachFrame").checked }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    addMsg(botName, data.reply);
    status("SYSTEMS NOMINAL");
    if ($("speak").checked) speak(data.reply);
  } catch (err) {
    addMsg("SYSTEM", "Error: " + err.message);
    status("ERROR");
  }
}
$("sendBtn").onclick = send;
$("chatInput").addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });

/* ---------- voice output ---------- */
async function speak(text) {
  if (ttsAvailable) {
    try {
      const resp = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (resp.ok) {
        const blob = await resp.blob();
        new Audio(URL.createObjectURL(blob)).play();
        return;
      }
    } catch (_) { /* fall through to browser voice */ }
  }
  const u = new SpeechSynthesisUtterance(text);
  const voice = speechSynthesis.getVoices().find(v => /en[-_]GB/i.test(v.lang));
  if (voice) u.voice = voice;
  u.rate = 1.05;
  speechSynthesis.speak(u);
}

/* ---------- voice input (Web Speech API — Chrome/Edge) ---------- */
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SR) {
  const rec = new SR();
  rec.lang = "en-US";
  rec.interimResults = false;
  let listening = false;
  rec.onresult = (e) => {
    $("chatInput").value = e.results[0][0].transcript;
    send();
  };
  rec.onend = () => { listening = false; $("micBtn").classList.remove("listening"); };
  $("micBtn").onclick = () => {
    if (listening) { rec.stop(); return; }
    listening = true;
    $("micBtn").classList.add("listening");
    rec.start();
  };
} else {
  $("micBtn").disabled = true;
  $("micBtn").title = "Voice input needs Chrome or Edge";
}

function status(text) { $("statusLine").textContent = text; }
