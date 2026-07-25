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

/* ---------- speaking animation (also mutes the mic while talking) ---------- */
let speakingNow = false;
function setSpeaking(on) {
  speakingNow = on;
  $("core").classList.toggle("speaking", on);
  if (recognizer && wakeEnabled) {
    if (on) { try { recognizer.stop(); } catch (_) {} }
    else { setTimeout(() => { if (wakeEnabled && recognizer) { try { recognizer.start(); } catch (_) {} } }, 350); }
  }
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
    if (data.reminders_due) {
      for (const text of data.reminders_due) {
        addMsg(botName, "⏰ Reminder: " + text);
        speak("Reminder: " + text);
      }
    }
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

  // Spoken commands, checked in order:
  const lower = message.toLowerCase();

  // Pending outbound message confirmation comes first.
  if (pendingSend) {
    if (/^(confirm|yes|send it|go ahead|do it)\b/i.test(lower)) {
      const p = pendingSend; pendingSend = null;
      return executeSend(p);
    }
    if (/^(cancel|no|never mind|don'?t)\b/i.test(lower)) {
      pendingSend = null;
      addMsg(botName, "Cancelled. Nothing was sent.");
      if ($("speak").checked) speak("Cancelled.");
      return;
    }
    // Anything else falls through and also cancels the pending send.
    pendingSend = null;
  }

  // Daily brief: "daily brief", "good morning", "brief me"
  if (/\b(daily brief|morning brief|brief me|good morning)\b/.test(lower)) return briefCommand();

  // Weather: "what's the weather", "weather in dubai"
  if (/\bweather\b/.test(lower)) {
    const cm = lower.match(/weather\s+(?:in|for)\s+(.+?)(?:\?|$)/);
    return weatherCommand(cm ? cm[1].trim() : "");
  }

  // Reminders
  const remindMatch = message.match(/^remind me\s+(?:to\s+|that\s+)?(.+)/i);
  if (remindMatch) return reminderCommand("add", remindMatch[1]);
  if (/\b(what are my reminders|list (my )?reminders|show (my )?reminders)\b/.test(lower)) {
    return reminderCommand("list", "");
  }
  if (/^(clear|cancel) all reminders$/i.test(message.trim())) return reminderCommand("clear", "");
  const cancelRem = message.match(/^cancel (?:the )?reminder\s+(?:about\s+|to\s+)?(.+)/i);
  if (cancelRem) return reminderCommand("cancel", cancelRem[1]);

  // Messaging: "telegram: buy milk" / "whatsapp to mom: on my way"
  const msgMatch = message.match(/^(?:send\s+(?:a\s+)?)?(whatsapp|telegram)(?:\s+message)?(?:\s+to\s+([^:,]+?))?\s*[:,-]\s*(.+)/i);
  if (msgMatch) return prepareSend(msgMatch[1].toLowerCase(), (msgMatch[2] || "").trim(), msgMatch[3].trim());

  // Virtual keyboard: "bring up the keyboard" / "hide the keyboard"
  if (/\bkeyboard\b/.test(lower)) {
    if (/\b(hide|close|remove|put away)\b/.test(lower)) return setKeyboard(false);
    if (/\b(bring|show|open|display|pop|up)\b/.test(lower)) return setKeyboard(true);
  }

  // Camera: "show me my camera", "hide the camera", ...
  const camCmd = parseCameraCommand(message);
  if (camCmd) return setCamera(camCmd === "show");

  // Screen awareness: "what's on my screen / monitor 2 / my tabs"
  if (/\b(screen|monitor|tabs?)\b/.test(lower) &&
      /\b(what|see|look|read|check|describe|show me what|open on)\b/.test(lower)) {
    const m = lower.match(/monitor\s+(\d)/);
    return screenCommand(message, m ? parseInt(m[1], 10) : 0);
  }

  // Web search: "search for iron man suit", "google best mediapipe tutorial"
  const searchMatch = message.match(/^(?:search(?:\s+(?:the\s+web|google|online))?(?:\s+for)?|google(?:\s+for)?|look\s+up)\s+(.+)/i);
  if (searchMatch) return searchCommand(searchMatch[1]);

  // System report: "system status", "how's the system"
  if (/\bsystem\s+(status|report|check)\b/.test(lower) || /\bhow('s| is) (the )?system\b/.test(lower)) {
    return systemCommand();
  }

  // Window control: "maximize/minimize this window"
  const winMatch = lower.match(/\b(maximize|minimize|restore)\b.*\b(window|this|tab)\b/);
  if (winMatch) return windowCommand(winMatch[1]);

  // Volume / media: "volume up", "mute the sound", "pause the music", "next song"
  if (/\b(volume|sound|audio)\b/.test(lower)) {
    if (/\b(up|higher|louder|increase|raise)\b/.test(lower)) return mediaCommand("volume_up", 3, "Volume up.");
    if (/\b(down|lower|quieter|decrease|reduce)\b/.test(lower)) return mediaCommand("volume_down", 3, "Volume down.");
    if (/\b(mute|unmute)\b/.test(lower)) return mediaCommand("mute", 1, "Toggled mute.");
  }
  if (/\b(pause|play|resume|stop)\b.*\b(music|song|media|video|playback)\b/.test(lower) ||
      /\b(music|song|media|video)\b.*\b(pause|play|resume|stop)\b/.test(lower)) {
    return mediaCommand("play_pause", 1, "Done.");
  }
  if (/\b(next|skip)\b.*\b(song|track)\b/.test(lower)) return mediaCommand("next", 1, "Skipping.");
  if (/\b(previous|last|back)\b.*\b(song|track)\b/.test(lower)) return mediaCommand("previous", 1, "Going back.");

  // App launching: "open notepad", "launch spotify", "start chrome"
  const appMatch = message.match(/^(?:open|launch|start)\s+(?:the\s+|my\s+)?(.+)/i);
  if (appMatch) return appCommand(appMatch[1]);

  // Memory: "remember that ...", "what do you remember", "forget ..."
  const remMatch = message.match(/^remember\s+(?:that\s+)?(.+)/i);
  if (remMatch) return memoryCommand("add", remMatch[1]);
  if (/\b(what do you (remember|know) about me|show (your |me your )?memory|list memories)\b/.test(lower)) {
    return memoryCommand("list", "");
  }
  if (/^forget everything$/i.test(message.trim())) return memoryCommand("clear", "");
  const forgetMatch = message.match(/^forget\s+(?:about\s+)?(.+)/i);
  if (forgetMatch) return memoryCommand("remove", forgetMatch[1]);

  status("PROCESSING…");
  // If the brain takes more than ~2.5s, acknowledge out loud so it never
  // feels dead while the model chain works.
  const fillerTimer = setTimeout(() => {
    status("STILL WORKING — MODEL CHAIN BUSY…");
    if ($("speak").checked && speechQueue.length === 0 && !speechBusy) speak(pickFiller());
  }, 2500);
  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, attach_frame: $("attachFrame").checked }),
    });
    clearTimeout(fillerTimer);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    addMsg(botName, data.reply);
    const modelName = data.model ? data.model.split("/").pop().replace(":free", "") : "";
    status(modelName ? "ONLINE — VIA " + modelName.toUpperCase() : "SYSTEMS NOMINAL");
    if ($("speak").checked) speak(data.reply);
  } catch (err) {
    clearTimeout(fillerTimer);
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

async function screenCommand(question, monitor) {
  status("ANALYZING SCREEN…");
  try {
    const resp = await fetch("/api/screen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, monitor }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    addMsg(botName, data.answer);
    status("SCREEN ANALYSIS COMPLETE");
    if ($("speak").checked) speak(data.answer);
  } catch (err) {
    addMsg("SYSTEM", "Screen error: " + err.message);
    status("SCREEN ANALYSIS FAILED");
  }
}

async function searchCommand(query) {
  try {
    const resp = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    const reply = "Searching for " + data.query + ". It's open in your browser.";
    addMsg(botName, reply);
    status("BROWSER SEARCH LAUNCHED");
    if ($("speak").checked) speak(reply);
  } catch (err) {
    addMsg("SYSTEM", "Search error: " + err.message);
  }
}

async function systemCommand() {
  try {
    const resp = await fetch("/api/system");
    const s = await resp.json();
    if (!resp.ok) throw new Error(s.error || resp.statusText);
    let reply = `CPU at ${s.cpu_percent} percent. RAM at ${s.ram_percent} percent — ` +
      `${s.ram_used_gb} of ${s.ram_total_gb} gigabytes. Disk ${s.disk_percent} percent full.`;
    if (s.battery) reply += ` Battery ${s.battery.percent} percent${s.battery.plugged ? ", charging" : ""}.`;
    addMsg(botName, reply);
    if ($("speak").checked) speak(reply);
  } catch (err) {
    addMsg("SYSTEM", "System report error: " + err.message);
  }
}

async function windowCommand(action) {
  try {
    const resp = await fetch("/api/window", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    const reply = action + "d " + data.title + ".";
    addMsg(botName, reply);
    if ($("speak").checked) speak(reply);
  } catch (err) {
    addMsg("SYSTEM", "Window error: " + err.message);
  }
}

/* ---------- weather / brief / reminders / messaging ---------- */
let pendingSend = null;

async function weatherCommand(city) {
  status("CHECKING WEATHER…");
  try {
    const resp = await fetch("/api/weather" + (city ? "?city=" + encodeURIComponent(city) : ""));
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    addMsg(botName, data.spoken);
    status("SYSTEMS NOMINAL");
    if ($("speak").checked) speak(data.spoken);
  } catch (err) {
    addMsg("SYSTEM", "Weather error: " + err.message);
    status("WEATHER FAILED");
  }
}

async function briefCommand() {
  status("COMPILING DAILY BRIEF…");
  try {
    const resp = await fetch("/api/brief", { method: "POST" });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    addMsg(botName, data.brief);
    status("BRIEF DELIVERED");
    if ($("speak").checked) speak(data.brief);
  } catch (err) {
    addMsg("SYSTEM", "Brief error: " + err.message);
    status("BRIEF FAILED");
  }
}

async function reminderCommand(action, text) {
  try {
    if (action === "list") {
      const resp = await fetch("/api/reminders");
      const data = await resp.json();
      const items = data.reminders || [];
      const reply = items.length
        ? "Your reminders:\n" + items.map(r => "• " + r.text + " — " + r.at).join("\n")
        : "No reminders set.";
      addMsg(botName, reply);
      if ($("speak").checked) speak(items.length ? "You have " + items.length + " reminders. They're on screen." : reply);
      return;
    }
    const resp = await fetch("/api/reminders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, text }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    let reply;
    if (action === "add") reply = "Reminder set for " + data.at + ": " + data.text + ".";
    else if (action === "cancel") reply = data.removed ? "Cancelled " + data.removed + " reminder(s)." : "No matching reminder found.";
    else reply = "All reminders cleared (" + data.cleared + ").";
    addMsg(botName, reply);
    if ($("speak").checked) speak(reply);
  } catch (err) {
    addMsg("SYSTEM", "Reminder error: " + err.message);
    if ($("speak").checked) speak(err.message);
  }
}

function prepareSend(channel, to, text) {
  if (channel === "whatsapp" && !to) {
    addMsg(botName, "WhatsApp to whom? Say: whatsapp to <name>: <message>.");
    if ($("speak").checked) speak("WhatsApp to whom?");
    return;
  }
  pendingSend = { channel, to, text };
  const target = channel === "telegram" ? (to || "your Telegram") : to;
  const ask = `Send via ${channel} to ${target}: "${text}" — say "confirm" to send or "cancel".`;
  addMsg(botName, ask);
  if ($("speak").checked) speak(`Sending to ${target}: ${text}. Say confirm, or cancel.`);
  status("AWAITING SEND CONFIRMATION");
}

async function executeSend(p) {
  status("SENDING…");
  try {
    const resp = await fetch("/api/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel: p.channel, to: p.to, text: p.text }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    const reply = p.channel === "whatsapp"
      ? "Sent. Your browser opened WhatsApp Web to deliver it — give it a few seconds."
      : "Sent to Telegram.";
    addMsg(botName, reply);
    status("MESSAGE SENT");
    if ($("speak").checked) speak(reply);
  } catch (err) {
    addMsg("SYSTEM", "Send error: " + err.message);
    status("SEND FAILED");
    if ($("speak").checked) speak("Sending failed. " + err.message);
  }
}

async function mediaCommand(action, times, sayText) {
  try {
    const resp = await fetch("/api/media", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, times }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    addMsg(botName, sayText);
    if ($("speak").checked && action.indexOf("volume") === -1) speak(sayText);
  } catch (err) {
    addMsg("SYSTEM", "Media error: " + err.message);
  }
}

async function appCommand(name) {
  try {
    const resp = await fetch("/api/app", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    const reply = "Opening " + data.app + ".";
    addMsg(botName, reply);
    if ($("speak").checked) speak(reply);
  } catch (err) {
    addMsg("SYSTEM", "App error: " + err.message);
  }
}

async function memoryCommand(action, text) {
  try {
    if (action === "list") {
      const resp = await fetch("/api/memory");
      const data = await resp.json();
      const facts = data.facts || [];
      const reply = facts.length
        ? "Here's what I remember:\n" + facts.map(f => "• " + f).join("\n")
        : "My long-term memory is empty so far. Tell me things with 'remember that…'.";
      addMsg(botName, reply);
      if ($("speak").checked) speak(facts.length ? "I remember " + facts.length + " things. They're on screen." : reply);
      return;
    }
    const resp = await fetch("/api/memory", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, text }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    let reply;
    if (action === "add") reply = data.added ? "Noted. I'll remember that." : "I already knew that.";
    else if (action === "remove") reply = data.removed ? "Forgotten — removed " + data.removed + " memory item(s)." : "I had nothing matching that.";
    else reply = "Memory wiped clean — " + data.cleared + " item(s) gone.";
    addMsg(botName, reply);
    if ($("speak").checked) speak(reply);
  } catch (err) {
    addMsg("SYSTEM", "Memory error: " + err.message);
  }
}

/* ---------- virtual keyboard (types into the console input) ---------- */
let vkShift = false;

function buildKeyboard() {
  const kb = $("vkeyboard");
  kb.innerHTML = "";
  const rows = ["1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm"];
  rows.forEach((row) => {
    const div = document.createElement("div");
    div.className = "krow";
    row.split("").forEach((ch) => {
      const b = document.createElement("button");
      b.textContent = vkShift ? ch.toUpperCase() : ch;
      b.onclick = () => { $("chatInput").value += vkShift ? ch.toUpperCase() : ch; };
      div.appendChild(b);
    });
    kb.appendChild(div);
  });
  const last = document.createElement("div");
  last.className = "krow";
  const mk = (label, cls, fn) => {
    const b = document.createElement("button");
    b.textContent = label; b.className = cls; b.onclick = fn;
    last.appendChild(b);
  };
  mk("⇧", "wide", () => { vkShift = !vkShift; buildKeyboard(); });
  mk("SPACE", "wide space", () => { $("chatInput").value += " "; });
  mk("⌫", "wide", () => { const i = $("chatInput"); i.value = i.value.slice(0, -1); });
  mk("SEND ⏎", "wide", () => send());
  mk("✕", "wide", () => setKeyboard(false));
  kb.appendChild(last);
}

function setKeyboard(on) {
  if (on) buildKeyboard();
  $("vkeyboard").hidden = !on;
  const reply = on ? "Keyboard up." : "Keyboard away.";
  addMsg(botName, reply);
  if ($("speak").checked) speak(reply);
}

$("sendBtn").onclick = send;
$("chatInput").addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });

/* ---------- voice output (queued: one voice at a time, in order) ---------- */
let ttsWarned = false;
const speechQueue = [];
let speechBusy = false;

function speak(text) {
  speechQueue.push(text);
  pumpSpeech();
}

async function pumpSpeech() {
  if (speechBusy || speechQueue.length === 0) return;
  speechBusy = true;
  const text = speechQueue.shift();
  try { await speakNow(text); } catch (_) {}
  speechBusy = false;
  pumpSpeech();
}

async function speakNow(text) {
  if (ttsAvailable) {
    try {
      const resp = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (resp.ok) {
        const blob = await resp.blob();
        await new Promise((resolve) => {
          const audio = new Audio(URL.createObjectURL(blob));
          audio.onplay = () => setSpeaking(true);
          audio.onended = () => { setSpeaking(false); resolve(); };
          audio.onerror = () => { setSpeaking(false); resolve(); };
          audio.play().catch(resolve);
        });
        return;
      }
      if (!ttsWarned) {
        ttsWarned = true;
        let why = "HTTP " + resp.status;
        try { why = (await resp.json()).error || why; } catch (_) {}
        addMsg("SYSTEM", "ElevenLabs voice failed (" + why + ") — using the browser voice instead. Check ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID and your elevenlabs.io quota.");
      }
    } catch (_) { /* fall through to browser voice */ }
  }
  await new Promise((resolve) => {
    const u = new SpeechSynthesisUtterance(text);
    const voice = speechSynthesis.getVoices().find(v => /en[-_]GB/i.test(v.lang));
    if (voice) u.voice = voice;
    u.rate = 1.05;
    u.onstart = () => setSpeaking(true);
    u.onend = () => { setSpeaking(false); resolve(); };
    u.onerror = () => { setSpeaking(false); resolve(); };
    speechSynthesis.speak(u);
  });
}

/* Instant acknowledgment while the brain works */
const FILLERS = ["On it.", "One moment.", "Checking that now.", "Working on it, Boss."];
function pickFiller() { return FILLERS[Math.floor(Math.random() * FILLERS.length)]; }

/* ---------- always-on voice input with "Hey Jarvis" wake word ---------- */
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognizer = null;
let wakeEnabled = false;
let awaitingCommand = false;
let awaitTimer = null;

// Conversation mode: after you address JARVIS once, he keeps answering
// WITHOUT the wake word for this long (refreshed on every exchange).
const CONVO_WINDOW_MS = 60000;
let convoUntil = 0;

function inConversation() {
  return Date.now() < convoUntil;
}

function extendConversation() {
  convoUntil = Date.now() + CONVO_WINDOW_MS;
}

function endConversation() {
  convoUntil = 0;
  awaitingCommand = false;
  clearTimeout(awaitTimer);
}

function wakeWords() {
  const n = (botName || "jarvis").toLowerCase();
  return ["hey " + n, "hi " + n, "okay " + n, "ok " + n, "alright " + n, n];
}

function handleUtterance(raw) {
  const text = raw.trim();
  if (!text || speakingNow) return;
  const lower = text.toLowerCase();

  // "Go to sleep" / "that's all" ends conversation mode explicitly.
  if (/\b(go to sleep|that'?s all|stop listening|stand down|standby)\b/.test(lower)) {
    if (inConversation() || awaitingCommand) {
      endConversation();
      addMsg(botName, "Standing by. Say my name when you need me.");
      if ($("speak").checked) speak("Standing by.");
      status("STANDBY — WAKE WORD REQUIRED");
    }
    return;
  }

  if (awaitingCommand) {
    clearTimeout(awaitTimer);
    awaitingCommand = false;
    extendConversation();
    $("chatInput").value = text;
    send();
    return;
  }

  for (const w of wakeWords()) {
    const idx = lower.indexOf(w);
    if (idx === -1) continue;
    extendConversation();
    const rest = text.slice(idx + w.length).replace(/^[\s,.!?:;-]+/, "");
    if (rest.length > 1) {
      $("chatInput").value = rest;
      send();
    } else {
      // Just "Hey Jarvis" — acknowledge and wait for the actual command.
      awaitingCommand = true;
      addMsg(botName, "Yes?");
      if ($("speak").checked) speak("Yes?");
      status("LISTENING FOR YOUR COMMAND…");
      awaitTimer = setTimeout(() => {
        awaitingCommand = false;
        status("SYSTEMS NOMINAL");
      }, 9000);
    }
    return;
  }

  // No wake word — but we're mid-conversation, so treat it as a command.
  if (inConversation()) {
    extendConversation();
    $("chatInput").value = text;
    send();
  }
  // Otherwise: not addressed to JARVIS — stay quiet.
}

function startListening() {
  recognizer = new SR();
  recognizer.lang = "en-US";
  recognizer.continuous = true;
  recognizer.interimResults = false;
  recognizer.onresult = (e) => {
    for (let i = e.resultIndex; i < e.results.length; i++) {
      if (e.results[i].isFinal) handleUtterance(e.results[i][0].transcript);
    }
  };
  recognizer.onend = () => {
    // Chrome stops recognition periodically — restart to stay always-on.
    if (wakeEnabled && !speakingNow) {
      setTimeout(() => { try { recognizer.start(); } catch (_) {} }, 400);
    }
  };
  recognizer.onerror = (e) => {
    if (e.error === "not-allowed" || e.error === "service-not-allowed") {
      wakeEnabled = false;
      renderMic();
      addMsg("SYSTEM",
        "Microphone blocked. Click the camera/mic icon in Chrome's address bar, allow the microphone, then click the ◉ button.");
      status("MICROPHONE BLOCKED");
    }
  };
  try { recognizer.start(); } catch (_) {}
}

function renderMic() {
  $("micBtn").classList.toggle("listening", wakeEnabled);
  $("micBtn").title = wakeEnabled
    ? "Always listening for 'Hey " + botName + "' — click to mute"
    : "Click to enable 'Hey " + botName + "' listening";
}

function setWake(on) {
  wakeEnabled = on;
  if (on) {
    startListening();
  } else {
    // Full mute: kill recognition AND any active conversation window, so
    // nothing — not even "Jarvis" — triggers until unmuted.
    endConversation();
    if (recognizer) {
      recognizer.onend = null;  // prevent the auto-restart handler
      try { recognizer.stop(); } catch (_) {}
      recognizer = null;
    }
  }
  renderMic();
  status(on
    ? 'WAKE WORD ACTIVE — SAY "HEY ' + (botName || "JARVIS").toUpperCase() + '"'
    : "MICROPHONE MUTED");
}

if (SR) {
  $("micBtn").onclick = () => setWake(!wakeEnabled);
  // Auto-arm on load; Chrome will ask for mic permission the first time.
  setTimeout(() => setWake(true), 1200);
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
