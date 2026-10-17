(() => {
  const chatBody = document.getElementById('chatBody');
  const form = document.getElementById('chatForm');
  const input = document.getElementById('messageInput');
  const sendBtn = document.getElementById('sendBtn');
  const micBtn = document.getElementById('micBtn');
  const attachBtn = document.getElementById('attachBtn');
  const fileInput = document.getElementById('fileInput');
  const attachChip = document.getElementById('attachChip');
  const attachName = document.getElementById('attachName');
  const attachRemoveBtn = document.getElementById('attachRemoveBtn');

  let attachedFile = null;

  function clearAttachment() {
    attachedFile = null;
    if (attachChip) attachChip.hidden = true;
    if (attachBtn) attachBtn.classList.remove('has-file');
    if (fileInput) fileInput.value = '';
  }
  const statusChip = document.getElementById('statusChip');
  const statusText = document.getElementById('statusText');
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
    if (attachBtn) attachBtn.disabled = value;
  }

  // ---------- Streaming + agentes em ação ----------
  let streamWrap = null;
  let streamBubble = null;
  let streamBuf = '';

  function resetStream() {
    streamWrap = null;
    streamBubble = null;
    streamBuf = '';
  }

  function hideStatus() {
    if (statusChip) statusChip.hidden = true;
  }

  function createStreamingMessage() {
    const wrap = document.createElement('div');
    wrap.className = 'msg msg--bot';
    const avatar = document.createElement('div');
    avatar.className = 'msg__avatar';
    avatar.textContent = 'M';
    const bubble = document.createElement('div');
    bubble.className = 'msg__bubble msg__bubble--streaming';
    bubble.innerHTML = '<p><span class="stream-cursor">▌</span></p>';
    wrap.append(avatar, bubble);
    chatBody.appendChild(wrap);
    chatBody.scrollTop = chatBody.scrollHeight;
    return { wrap, bubble };
  }

  ws.addEventListener('message', (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === 'typing') {
      if (!data.value) { setBusy(false); hideStatus(); }
      return;
    }
    if (data.type === 'status') {
      if (statusChip) {
        statusText.textContent = data.value || '';
        statusChip.hidden = !data.value;
      }
      return;
    }
    if (data.type === 'token') {
      hideStatus();
      if (!streamWrap) {
        const m = createStreamingMessage();
        streamWrap = m.wrap;
        streamBubble = m.bubble;
      }
      streamBuf += data.token || '';
      streamBubble.innerHTML = formatText(streamBuf) + '<span class="stream-cursor">▌</span>';
      chatBody.scrollTop = chatBody.scrollHeight;
      return;
    }
    if (data.type === 'transcribing') {
      if (statusChip) {
        statusText.textContent = 'Transcrevendo áudio…';
        statusChip.hidden = !data.value;
      }
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
      hideStatus();
      if (streamBubble) {
        streamBubble.innerHTML = formatText(data.text) + timeHtml();
      } else {
        addMessage('bot', data.text);
      }
      resetStream();
      if (data.meta && data.meta.mood) updateMood(data.meta.mood);
      setBusy(false);
    }
  });

  ws.addEventListener('close', () => {
    hideStatus();
    addMessage('bot', '\u26a0\ufe0f Conex\u00e3o encerrada. Recarregue a p\u00e1gina para reconectar.');
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (busy) return;
    const text = input.value.trim();
    if (!text && !attachedFile) return;

    const payload = { message: text };
    let shown = text;
    if (attachedFile) {
      try {
        payload.attachment = { name: attachedFile.name, content_b64: await blobToBase64(attachedFile) };
      } catch (err) {
        addMessage('bot', '\u26a0\ufe0f N\u00e3o consegui ler o arquivo selecionado.');
        return;
      }
      shown = (text ? text + '\n' : '') + '\ud83d\udcce ' + attachedFile.name;
    }
    addMessage('user', shown);
    setBusy(true);
    ws.send(JSON.stringify(payload));
    resetStream();
    input.value = '';
    clearAttachment();
  });

  // ---------- Anexo de arquivos ----------
  if (attachBtn && fileInput) {
    attachBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      if (file.size > 2 * 1024 * 1024) {
        addMessage('bot', '\u26a0\ufe0f Arquivo muito grande. O limite para anexos \u00e9 2 MB.');
        clearAttachment();
        return;
      }
      attachedFile = file;
      if (attachName) attachName.textContent = file.name;
      if (attachChip) attachChip.hidden = false;
      attachBtn.classList.add('has-file');
    });
    if (attachRemoveBtn) {
      attachRemoveBtn.addEventListener('click', () => clearAttachment());
    }
  }

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

  // ---------- O que a Marcelly sabe (painel de memória) ----------
  const memoryBtn = document.getElementById('memoryBtn');
  const memoryPanel = document.getElementById('memoryPanel');
  const memoryCloseBtn = document.getElementById('memoryCloseBtn');
  const memoryList = document.getElementById('memoryList');

  function memEscape(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function closeMemoryPanel() {
    if (memoryPanel) memoryPanel.hidden = true;
    if (memoryBtn) {
      memoryBtn.setAttribute('aria-pressed', 'false');
      memoryBtn.classList.remove('chat__memory--on');
    }
  }

  async function openMemoryPanel() {
    memoryBtn.setAttribute('aria-pressed', 'true');
    memoryBtn.classList.add('chat__memory--on');
    memoryPanel.hidden = false;
    memoryList.innerHTML = '<p class="memory-panel__empty">Carregando...</p>';
    try {
      const data = await fetch('/api/memory').then((r) => r.json());
      const parts = [];
      if (data.name) {
        parts.push('<h3>Seu nome</h3><ul class="memory-panel__items"><li><span>' + memEscape(data.name) + '</span></li></ul>');
      }
      if (data.profile) {
        const rows = [
          ['Gênero', data.profile.gender],
          ['Telefone', data.profile.phone],
          ['WhatsApp', data.profile.whatsapp],
          ['E-mail', data.profile.email],
        ].filter((row) => row[1]);
        if (rows.length) {
          parts.push('<h3>Seu perfil</h3><ul class="memory-panel__items">' + rows.map((row) =>
            '<li><span><strong>' + memEscape(row[0]) + '</strong> ' + memEscape(row[1]) + '</span></li>'
          ).join('') + '</ul>');
        }
      }
      if (data.facts && data.facts.length) {
        parts.push('<h3>Fatos que aprendi</h3><ul class="memory-panel__items">' + data.facts.map((f) =>
          '<li><span><strong>' + memEscape(f.key) + '</strong> ' + memEscape(f.value) + '</span>' +
          '<button type="button" class="memory-panel__forget" data-key="' + memEscape(f.key) + '" title="Esquecer este fato">✕</button></li>'
        ).join('') + '</ul>');
      }
      if (data.preferences && data.preferences.length) {
        parts.push('<h3>Preferências</h3><ul class="memory-panel__items">' + data.preferences.map((p) =>
          '<li><span><strong>' + memEscape(p.key) + '</strong> ' + memEscape(p.value) + '</span></li>'
        ).join('') + '</ul>');
      }
      if (data.patterns && data.patterns.length) {
        parts.push('<h3>Padrões observados</h3><ul class="memory-panel__items">' + data.patterns.map((p) =>
          '<li><span>' + memEscape(p) + '</span></li>'
        ).join('') + '</ul>');
      }
      memoryList.innerHTML = parts.join('') || '<p class="memory-panel__empty">Ainda não aprendi nada sobre você. Converse comigo!</p>';
    } catch (err) {
      memoryList.innerHTML = '<p class="memory-panel__empty">Não consegui carregar agora.</p>';
    }
  }

  if (memoryBtn) {
    memoryBtn.addEventListener('click', () => {
      if (memoryPanel.hidden) openMemoryPanel();
      else closeMemoryPanel();
    });
  }
  if (memoryCloseBtn) memoryCloseBtn.addEventListener('click', closeMemoryPanel);
  if (memoryList) {
    memoryList.addEventListener('click', async (e) => {
      const btn = e.target.closest('.memory-panel__forget');
      if (!btn) return;
      await fetch('/api/memory/forget', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: btn.dataset.key }),
      });
      openMemoryPanel();
    });
  }

  input.focus();

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


  function timeHtml() {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    return '<span class="msg__time">' + hh + ':' + mm + '</span>';
  }

  function addMessage(role, text) {
    const wrap = document.createElement('div');
    wrap.className = 'msg msg--' + role;

    const avatar = document.createElement('div');
    avatar.className = 'msg__avatar';
    avatar.textContent = role === 'bot' ? 'M' : 'EU';

    const bubble = document.createElement('div');
    bubble.className = 'msg__bubble';
    bubble.innerHTML = formatText(text) + timeHtml();

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

  // ---------- Histórico por dia + busca por assunto ----------
  const historyBtn = document.getElementById('historyBtn');
  const historyPanel = document.getElementById('historyPanel');
  const historyCloseBtn = document.getElementById('historyCloseBtn');
  const historySearchForm = document.getElementById('historySearchForm');
  const historySearch = document.getElementById('historySearch');
  const historyList = document.getElementById('historyList');

  function openHistory() {
    if (!historyPanel) return;
    historyPanel.hidden = false;
    if (historyBtn) historyBtn.setAttribute('aria-pressed', 'true');
    historySearch.focus();
    loadHistoryDays();
  }

  function closeHistory() {
    if (!historyPanel) return;
    historyPanel.hidden = true;
    if (historyBtn) historyBtn.setAttribute('aria-pressed', 'false');
  }

  function loadHistoryDays() {
    fetch('/api/history')
      .then((r) => r.json())
      .then((data) => renderDays(data.days || []))
      .catch(() => {});
  }

  function labelDay(day) {
    const now = new Date();
    const iso = (d) => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    const yesterday = new Date();
    yesterday.setDate(now.getDate() - 1);
    if (day === iso(now)) return 'Hoje';
    if (day === iso(yesterday)) return 'Ontem';
    return day.split('-').reverse().join('/');
  }

  function renderDays(days) {
    if (!historyList) return;
    if (!days.length) {
      historyList.innerHTML = '<p class="history-empty">Nenhuma conversa registrada ainda.</p>';
      return;
    }
    historyList.innerHTML = '';
    days.forEach((d) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'history-day';
      btn.innerHTML = '<span>' + labelDay(d.day) + '</span><span class="history-day__count">' + d.n + '</span>';
      btn.addEventListener('click', () => loadDay(d.day));
      historyList.appendChild(btn);
    });
  }

  function loadDay(day) {
    fetch('/api/history?day=' + encodeURIComponent(day))
      .then((r) => r.json())
      .then((data) => {
        if (!historyList) return;
        historyList.innerHTML = '';
        const back = document.createElement('button');
        back.type = 'button';
        back.className = 'history-back';
        back.textContent = '\u2190 ' + labelDay(day);
        back.addEventListener('click', loadHistoryDays);
        historyList.appendChild(back);
        const items = data.items || [];
        items.forEach((it) => {
          const when = new Date(it.ts * 1000).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
          const wrap = document.createElement('div');
          wrap.className = 'history-item';
          const head = document.createElement('div');
          head.className = 'history-item__head';
          head.innerHTML = '<span class="history-item__time">' + when + '</span><span class="history-item__intent">' + (it.intent || 'chat') + '</span>';
          const q = document.createElement('p');
          q.className = 'history-item__q';
          q.textContent = it.user_message;
          const a = document.createElement('details');
          a.className = 'history-item__a';
          const sum = document.createElement('summary');
          sum.textContent = 'ver resposta';
          const body = document.createElement('p');
          body.textContent = it.response || '';
          a.append(sum, body);
          wrap.append(head, q, a);
          historyList.appendChild(wrap);
        });
        if (!items.length) {
          historyList.innerHTML = '<p class="history-empty">Nenhuma conversa neste dia.</p>';
        }
      })
      .catch(() => {});
  }

  function renderSearchResults(items, q) {
    if (!historyList) return;
    if (!items.length) {
      historyList.innerHTML = '<p class="history-empty">Nada encontrado sobre "' + q + '".</p>';
      return;
    }
    historyList.innerHTML = '';
    const title = document.createElement('p');
    title.className = 'history-title';
    title.textContent = items.length + ' resultado(s) para "' + q + '"';
    historyList.appendChild(title);
    items.forEach((it) => {
      const when = new Date(it.ts * 1000).toLocaleString('pt-BR');
      const wrap = document.createElement('div');
      wrap.className = 'history-item';
      const head = document.createElement('div');
      head.className = 'history-item__head';
      head.innerHTML = '<span class="history-item__time">' + when + '</span>';
      const qt = document.createElement('p');
      qt.className = 'history-item__q';
      qt.textContent = it.user_message;
      wrap.append(head, qt);
      historyList.appendChild(wrap);
    });
  }

  if (historyBtn && historyPanel) {
    historyBtn.addEventListener('click', () => {
      if (historyPanel.hidden) openHistory();
      else closeHistory();
    });
    if (historyCloseBtn) historyCloseBtn.addEventListener('click', closeHistory);

    historySearchForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const q = historySearch.value.trim();
      if (!q) { loadHistoryDays(); return; }
      fetch('/api/search?q=' + encodeURIComponent(q))
        .then((r) => r.json())
        .then((data) => renderSearchResults(data.items || [], q))
        .catch(() => {
          historyList.innerHTML = '<p class="history-empty">Não consegui buscar agora.</p>';
        });
    });
  }

  // ---------- Liberação de espaço (ciclo de 120 dias) ----------
  const storageBanner = document.getElementById('storageBanner');
  const storageCount = document.getElementById('storageCount');
  const storageSaveBtn = document.getElementById('storageSaveBtn');
  const storageLaterBtn = document.getElementById('storageLaterBtn');

  if (storageBanner) {
    fetch('/api/storage')
      .then((r) => r.json())
      .then((data) => {
        if (!data.due) return;
        if (storageCount) storageCount.textContent = String(data.old_records);
        storageBanner.hidden = false;
      })
      .catch(() => {});

    if (storageLaterBtn) {
      storageLaterBtn.addEventListener('click', () => {
        fetch('/api/storage/postpone', { method: 'POST' }).catch(() => {});
        storageBanner.hidden = true;
      });
    }
    if (storageSaveBtn) {
      storageSaveBtn.addEventListener('click', () => {
        storageSaveBtn.disabled = true;
        fetch('/api/storage/archive', { method: 'POST' })
          .then((r) => r.json())
          .then((data) => {
            storageBanner.hidden = true;
            const msg = data.archived
              ? '💾 Pronto! Salvei ' + data.archived + ' conversa(s) antigas em "' + (data.file || 'arquivo local') + '" e liberei espaço no banco.'
              : '💾 Nada a arquivar — seu histórico já está enxuto.';
            addMessage('bot', msg);
          })
          .catch(() => { storageSaveBtn.disabled = false; });
      });
    }
  }

  // ---------- Monitor de recursos ----------
  const statsToggle = document.getElementById('statsToggle');
  const statsBody = document.getElementById('statsBody');
  const statsCpu = document.getElementById('statsCpu');
  const statsCpuVal = document.getElementById('statsCpuVal');
  const statsRam = document.getElementById('statsRam');
  const statsRamVal = document.getElementById('statsRamVal');
  const statsNote = document.getElementById('statsNote');

  async function refreshStats() {
    try {
      const s = await fetch('/api/stats').then((r) => r.json());
      if (statsCpu) statsCpu.style.width = Math.min(100, Math.round(s.cpu)) + '%';
      if (statsCpuVal) statsCpuVal.textContent = Math.round(s.cpu) + '%';
      if (statsRam) statsRam.style.width = Math.round(s.ram_percent) + '%';
      if (statsRamVal) statsRamVal.textContent = Math.round(s.ram_percent) + '%';
      if (statsNote) {
        statsNote.textContent = 'Marcelly: ' + s.app_ram_mb + ' MB \u00b7 RAM '
          + s.ram_used_gb + '/' + s.ram_total_gb + ' GB';
      }
    } catch (e) { /* servidor indisponível: tenta de novo no próximo ciclo */ }
  }
  if (statsToggle) {
    statsToggle.addEventListener('click', () => {
      const abrir = statsBody.hidden;
      statsBody.hidden = !abrir;
      statsToggle.setAttribute('aria-expanded', String(abrir));
    });
  }
  refreshStats();
  setInterval(refreshStats, 2000);

  // ---------- Boas-vindas: perfil do usuário (salvo só neste computador) ----------
  const onboarding = document.getElementById('onboarding');
  const onboardingForm = document.getElementById('onboardingForm');
  const onboardingSkip = document.getElementById('onboardingSkip');
  const onboardingSave = document.getElementById('onboardingSave');

  function closeOnboarding() {
    if (onboarding) onboarding.hidden = true;
  }

  function openOnboarding() {
    if (!onboarding) return;
    onboarding.hidden = false;
    const nameField = document.getElementById('obName');
    if (nameField) nameField.focus();
  }

  if (onboarding && onboardingForm) {
    let dismissed = false;
    try { dismissed = localStorage.getItem('marcelly_onboarding') === 'done'; } catch (e) { /* sem localStorage */ }
    fetch('/api/profile')
      .then((r) => r.json())
      .then((profile) => {
        if (profile && profile.name) return; // já preenchido: não pergunta de novo
        if (dismissed) return; // usuário optou por preencher depois
        openOnboarding();
      })
      .catch(() => { /* servidor ainda aquecendo: tenta no próximo uso */ });

    onboardingForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (onboardingSave) onboardingSave.disabled = true;
      const fields = {
        name: (document.getElementById('obName') || {}).value || '',
        gender: (document.getElementById('obGender') || {}).value || '',
        phone: (document.getElementById('obPhone') || {}).value || '',
        whatsapp: (document.getElementById('obWhats') || {}).value || '',
        email: (document.getElementById('obEmail') || {}).value || '',
      };
      try {
        await fetch('/api/profile', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(fields),
        });
        try { localStorage.setItem('marcelly_onboarding', 'done'); } catch (e) { /* sem localStorage */ }
        closeOnboarding();
        addMessage('bot', 'Olá! Anotado — vou te tratar pelo nome, do jeito certo. Tudo salvo apenas neste computador. 🙌');
      } catch (err) {
        if (onboardingSave) onboardingSave.disabled = false;
      }
    });

    onboardingSkip.addEventListener('click', () => {
      try { localStorage.setItem('marcelly_onboarding', 'done'); } catch (e) { /* sem localStorage */ }
      closeOnboarding();
    });
  }

  input.focus();
})();