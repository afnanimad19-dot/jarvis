/* JARVIS HUD client: vision websocket, chat, voice in (Web Speech) / out (TTS). */

const $ = (id) => document.getElementById(id);
let botName = "JARVIS";
let ttsAvailable = false;

/* ---------- config ---------- */
fetch("/api/config").then(r => r.json()).then(cfg => {
  botName = cfg.bot_name || "JARVIS";
  ttsAvailable = cfg.tts_available;
  $("botName").textContent = botName.split("").join(".") + ".";
  $("coreName").textContent = botName.toUpperCase();
  document.title = botName;
  renderGesture(cfg.gesture_enabled);
  status("BRAIN: " + (cfg.provider || "?").toUpperCase() + " — SYSTEMS NOMINAL");
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

/* ---------- camera popup (opens only when asked) ---------- */
let camOpen = false;

function setCamera(on, silent) {
  camOpen = on;
  $("camModal").hidden = !on;
  if (silent) return;
  const reply = on
    ? "Camera view on screen."
    : "Camera view closed. Sensors are still running in the background.";
  addMsg(botName, reply);
  status(on ? "CAMERA VIEW OPEN" : "CAMERA VIEW CLOSED — SENSORS ACTIVE");
  if ($("speak").checked) speak(reply);
}

function parseCameraCommand(text) {
  const t = text.toLowerCase();
  if (!/\b(camera|cam|feed|yourself|myself|my face)\b/.test(t)) return null;
  if (/\b(hide|close|turn off|switch off|disable|stop showing)\b/.test(t)) return "hide";
  if (/\b(open|show|display|turn on|switch on|enable|see|view|pop)\b/.test(t)) return "show";
  return null;
}

$("core").onclick = () => setCamera(!camOpen);
$("camClose").onclick = () => setCamera(false);

/* ---------- speaking animation ---------- */
function setSpeaking(on) {
  $("core").classList.toggle("speaking", on);
}

/* ---------- vision websocket ---------- */
function connectVision() {
  const ws = new WebSocket(`ws://${location.host}/ws/vision`);
  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.frame) {
      $("cam").src = "data:image/jpeg;base64," + data.frame;
      $("coreMsg").style.display = "none";
    }
    renderTracking(data.tracking || {});
    if (typeof data.gesture === "boolean" && data.gesture !== gestureOn) renderGesture(data.gesture);
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

  // Console commands: /crawl <url> [question]   /post <text>
  if (message.startsWith("/crawl ")) return crawlCommand(message.slice(7).trim());
  if (message.startsWith("/post ")) return postCommand(message.slice(6).trim());

  // Spoken camera commands: "show me my camera", "hide the camera", ...
  const camCmd = parseCameraCommand(message);
  if (camCmd) return setCamera(camCmd === "show");

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
async function crawlCommand(rest) {
  const firstSpace = rest.indexOf(" ");
  const url = firstSpace === -1 ? rest : rest.slice(0, firstSpace);
  const question = firstSpace === -1 ? "" : rest.slice(firstSpace + 1);
  status("CRAWLING " + url.toUpperCase().slice(0, 40) + "…");
  try {
    const resp = await fetch("/api/crawl", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, question }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    addMsg(botName, data.answer);
    status("CRAWL COMPLETE — " + data.chars_crawled + " CHARS ANALYZED");
    if ($("speak").checked) speak(data.answer);
  } catch (err) {
    addMsg("SYSTEM", "Crawl error: " + err.message);
    status("CRAWL FAILED");
  }
}

async function postCommand(text) {
  status("DRAFTING SOCIAL POST…");
  try {
    const resp = await fetch("/api/social/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, channel_ids: [] }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    addMsg("SYSTEM", `Draft created in Postiz on ${data.channels.length} channel(s). Review and publish it there — nothing goes live automatically.`);
    status("DRAFT SAVED TO POSTIZ");
  } catch (err) {
    addMsg("SYSTEM", "Post error: " + err.message);
    status("DRAFT FAILED");
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
        const audio = new Audio(URL.createObjectURL(blob));
        audio.onplay = () => setSpeaking(true);
        audio.onended = () => setSpeaking(false);
        audio.onerror = () => setSpeaking(false);
        audio.play();
        return;
      }
    } catch (_) { /* fall through to browser voice */ }
  }
  const u = new SpeechSynthesisUtterance(text);
  const voice = speechSynthesis.getVoices().find(v => /en[-_]GB/i.test(v.lang));
  if (voice) u.voice = voice;
  u.rate = 1.05;
  u.onstart = () => setSpeaking(true);
  u.onend = () => setSpeaking(false);
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

/* ---------- gesture mouse control ---------- */
let gestureOn = false;
function renderGesture(on) {
  gestureOn = on;
  const btn = $("gestureBtn");
  btn.textContent = on ? "ON" : "OFF";
  btn.classList.toggle("on", on);
}
$("gestureBtn").onclick = async () => {
  try {
    const resp = await fetch("/api/gesture", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !gestureOn }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error);
    renderGesture(data.enabled);
    status(data.enabled ? "GESTURE CONTROL ENGAGED — PINCH TO GRAB" : "GESTURE CONTROL OFF");
  } catch (err) {
    status("GESTURE ERROR");
    addMsg("SYSTEM", err.message);
  }
};

/* ---------- scan mode ---------- */
$("scanBtn").onclick = async () => {
  const btn = $("scanBtn");
  btn.classList.add("busy");
  btn.textContent = "◈ SCANNING…";
  status("ANALYZING TARGET…");
  try {
    const resp = await fetch("/api/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hint: "" }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    showScan(data.frame, data.annotations);
    status("SCAN COMPLETE");
    if ($("speak").checked && data.annotations.length) {
      speak(data.annotations[0].label + ". " + (data.annotations[0].detail || ""));
    }
  } catch (err) {
    addMsg("SYSTEM", "Scan error: " + err.message);
    status("SCAN FAILED");
  } finally {
    btn.classList.remove("busy");
    btn.textContent = "◈ SCAN";
  }
};

function showScan(frameB64, annotations) {
  const overlay = $("scanOverlay");
  const img = $("scanFrame");
  overlay.hidden = false;
  $("scanLabels").innerHTML = "";
  $("scanLines").innerHTML = "";
  img.onload = () => drawAnnotations(annotations);
  img.src = "data:image/jpeg;base64," + frameB64;
}

function drawAnnotations(annotations) {
  const img = $("scanFrame");
  const W = img.clientWidth, H = img.clientHeight;
  const svg = $("scanLines");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const labels = $("scanLabels");

  annotations.forEach((a, i) => {
    const px = a.x * W, py = a.y * H;
    const left = a.x < 0.5;            // label goes on the opposite side
    const lx = left ? W - 8 : 8;
    const ly = (H / (annotations.length + 1)) * (i + 1);

    const ns = "http://www.w3.org/2000/svg";
    const dot = document.createElementNS(ns, "circle");
    dot.setAttribute("cx", px); dot.setAttribute("cy", py); dot.setAttribute("r", 4);
    svg.appendChild(dot);
    const elbowX = left ? px + (W - px) * 0.55 : px * 0.45;
    const l1 = document.createElementNS(ns, "line");
    l1.setAttribute("x1", px); l1.setAttribute("y1", py);
    l1.setAttribute("x2", elbowX); l1.setAttribute("y2", ly);
    svg.appendChild(l1);
    const l2 = document.createElementNS(ns, "line");
    l2.setAttribute("x1", elbowX); l2.setAttribute("y1", ly);
    l2.setAttribute("x2", lx); l2.setAttribute("y2", ly);
    svg.appendChild(l2);

    const card = document.createElement("div");
    card.className = "callout";
    card.style.top = ly + "px";
    if (left) card.style.right = "-260px"; else card.style.left = "-260px";
    card.innerHTML = "<b></b><span></span>";
    card.querySelector("b").textContent = a.label;
    card.querySelector("span").textContent = a.detail || "";
    labels.appendChild(card);
  });
}

$("scanClose").onclick = () => { $("scanOverlay").hidden = true; };
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    $("scanOverlay").hidden = true;
    if (camOpen) setCamera(false, true);
  }
});
