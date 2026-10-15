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
      ? 'Marcelly já inicia junto com o Windows. Clique para desativar.'
      : 'Ativar inicialização com o Windows';
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
        /* mantém o estado atual */
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

  input.focus();
})();
