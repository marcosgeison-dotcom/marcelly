(() => {
  const chatBody = document.getElementById('chatBody');
  const form = document.getElementById('chatForm');
  const input = document.getElementById('messageInput');
  const sendBtn = document.getElementById('sendBtn');
  const micBtn = document.getElementById('micBtn');
  const typing = document.getElementById('typingIndicator');
  const moodEmoji = document.querySelector('.chat__mood-emoji');
  const moodLabel = document.getElementById('moodLabel');
  const autostartBtn = document.getElementById('autostartBtn');
  const debugBtn = document.getElementById('debugBtn');
  const debugPanel = document.getElementById('debugPanel');
  const debugList = document.getElementById('debugList');
  const debugClearBtn = document.getElementById('debugClearBtn');

  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(protocol + '://' + location.host + '/ws');

  let recorder = null;
  let chunks = [];
  let busy = false;

  function setBusy(value) {
    busy = value;
    sendBtn.disabled = value;
    micBtn.disabled = value;
  }

  ws.addEventListener('message', (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === 'typing') {
      typing.hidden = !data.value;
      if (!data.value) setBusy(false);
      return;
    }
    if (data.type === 'transcribing') {
      typing.hidden = !data.value;
      micBtn.disabled = data.value;
      return;
    }
    if (data.type === 'transcript') {
      addMessage('user', data.text);
      return;
    }
    if (data.type === 'debug') {
      addDebugEvent(data.event);
      return;
    }
    if (data.type === 'message') {
      addMessage('bot', data.text);
      if (data.meta && data.meta.mood) updateMood(data.meta.mood);
      setBusy(false);
    }
  });

  ws.addEventListener('close', () => {
    addMessage('bot', '\u26a0\ufe0f Conex\u00e3o encerrada. Recarregue a p\u00e1gina para reconectar.');
  });

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    if (busy) return;
    const text = input.value.trim();
    if (!text) return;
    addMessage('user', text);
    setBusy(true);
    ws.send(JSON.stringify({ message: text }));
    input.value = '';
    // ---------- Iniciar com o Windows ----------
  function updateAutostart(enabled) {
    if (!autostartBtn) return;
    autostartBtn.setAttribute('aria-pressed', String(enabled));
    autostartBtn.classList.toggle('chat__autostart--on', enabled);
    autostartBtn.title = enabled
      ? 'Marcelly j\u00e1 inicia junto com o Windows. Clique para desativar.'
      : 'Ativar inicializa\u00e7\u00e3o com o Windows';
  }

  if (autostartBtn) {
    fetch('/api/autostart')
      .then((r) => r.json())
      .then((data) => updateAutostart(data.enabled))
      .catch(() => {});

    autostartBtn.addEventListener('click', async () => {
      const enabled = autostartBtn.getAttribute('aria-pressed') !== 'true';
      autostartBtn.disabled = true;
      try {
        const res = await fetch('/api/autostart', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled }),
        });
        const data = await res.json();
        updateAutostart(data.enabled);
      } catch (err) {
        /* mant\u00e9m o estado atual */
      } finally {
        autostartBtn.disabled = false;
      }
    });
  }

  input.focus();
  });

  // ---------- Comando de voz ----------
  micBtn.addEventListener('click', async () => {
    if (busy) return;
    if (recorder && recorder.state === 'recording') {
      recorder.stop();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      chunks = [];
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        micBtn.classList.remove('recording');
        if (!chunks.length) return;
        const audio = await blobToBase64(new Blob(chunks, { type: 'audio/webm' }));
        setBusy(true);
        ws.send(JSON.stringify({ type: 'voice', audio, speak: true }));
      };
      recorder.start();
      micBtn.classList.add('recording');
    } catch (err) {
      addMessage('bot', '\u26a0\ufe0f N\u00e3o consegui acessar o microfone. Verifique as permiss\u00f5es do navegador.');
    }
  });

  function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(String(reader.result).split(',')[1]);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  function addMessage(role, text) {
    const wrap = document.createElement('div');
    wrap.className = 'msg msg--' + role;

    const avatar = document.createElement('div');
    avatar.className = 'msg__avatar';
    avatar.textContent = role === 'bot' ? 'M' : 'EU';

    const bubble = document.createElement('div');
    bubble.className = 'msg__bubble';
    bubble.innerHTML = formatText(text);

    wrap.append(avatar, bubble);
    chatBody.appendChild(wrap);
    chatBody.scrollTop = chatBody.scrollHeight;
  }

  function formatText(text) {
    let html = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/^[\u2022\-]\s(.+)$/gm, '<li>$1</li>')
      .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
      .replace(/\n/g, '<br>');
    return '<p>' + html + '</p>';
  }

  function updateMood(mood) {
    const map = {
      happy: '\U0001f60a', tired: '\U0001f634', stressed: '\U0001f630',
      excited: '\U0001f929', neutral: '\U0001f642', sad: '\U0001f614',
    };
    moodEmoji.textContent = map[mood] || '\U0001f642';
    moodLabel.textContent = mood;
  }

  // ---------- Modo de depuração ----------
  const KIND_LABEL = {
    request: 'entrada',
    response: 'resposta',
    routing: 'roteamento',
    mood: 'humor',
    module: 'm\u00f3dulo',
    agents: 'agente',
    error: 'erro',
    debug_mode: 'depura\u00e7\u00e3o',
  };

  function fmtTime(ts) {
    return new Date(ts * 1000).toLocaleTimeString('pt-BR');
  }

  function debugDetail(ev) {
    if (ev.kind === 'request') return (ev.source || '') + ': ' + (ev.message || '');
    if (ev.kind === 'response') {
      return 'intent=' + (ev.intent || '?') + ' \u00b7 ' + (ev.duration_ms || 0) + 'ms \u00b7 ' + (ev.chars || 0) + ' caracteres';
    }
    if (ev.kind === 'routing') return ev.intent + ' (' + Math.round((ev.confidence || 0) * 100) + '%)';
    if (ev.kind === 'mood') return ev.mood;
    if (ev.kind === 'agents') return ev.agent || '';
    if (ev.kind === 'error') return (ev.where || '') + ': ' + (ev.error || '');
    if (ev.kind === 'debug_mode') return ev.value ? 'ativado' : 'desativado';
    return JSON.stringify(ev);
  }

  function addDebugEvent(ev) {
    if (!debugPanel || debugPanel.hidden || !ev) return;
    const row = document.createElement('div');
    row.className = 'debug-panel__event debug-panel__event--' + ev.kind;

    const kind = document.createElement('span');
    kind.className = 'debug-panel__kind';
    kind.textContent = KIND_LABEL[ev.kind] || ev.kind;

    const detail = document.createElement('span');
    detail.className = 'debug-panel__detail';
    detail.textContent = debugDetail(ev);

    const time = document.createElement('span');
    time.className = 'debug-panel__time';
    time.textContent = fmtTime(ev.ts);

    row.append(kind, detail, time);
    debugList.appendChild(row);
    debugList.scrollTop = debugList.scrollHeight;
  }

  function setDebug(enabled) {
    if (!debugBtn) return;
    debugBtn.setAttribute('aria-pressed', String(enabled));
    debugBtn.classList.toggle('chat__debug--on', enabled);
    debugBtn.title = enabled
      ? 'Modo de depura\u00e7\u00e3o ativo. Clique para desativar.'
      : 'Ativar modo de depura\u00e7\u00e3o';
    if (debugPanel) debugPanel.hidden = !enabled;
  }

  if (debugBtn) {
    fetch('/api/debug')
      .then((r) => r.json())
      .then((data) => {
        setDebug(data.enabled);
        if (data.enabled) (data.events || []).forEach(addDebugEvent);
      })
      .catch(() => {});

    debugBtn.addEventListener('click', async () => {
      const enabled = debugBtn.getAttribute('aria-pressed') !== 'true';
      debugBtn.disabled = true;
      try {
        const res = await fetch('/api/debug', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled }),
        });
        const data = await res.json();
        setDebug(data.enabled);
        if (data.enabled) {
          debugList.innerHTML = '';
          (data.events || []).forEach(addDebugEvent);
        }
      } catch (err) {
        /* mant\u00e9m o estado atual */
      } finally {
        debugBtn.disabled = false;
      }
    });

    if (debugClearBtn) {
      debugClearBtn.addEventListener('click', () => {
        debugList.innerHTML = '';
      });
    }
  }

  input.focus();
})();