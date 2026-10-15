(() => {
  const chatBody = document.getElementById('chatBody');
  const form = document.getElementById('chatForm');
  const input = document.getElementById('messageInput');
  const sendBtn = document.getElementById('sendBtn');
  const typing = document.getElementById('typingIndicator');
  const moodEmoji = document.querySelector('.chat__mood-emoji');
  const moodLabel = document.getElementById('moodLabel');

  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(protocol + '://' + location.host + '/ws');

  ws.addEventListener('message', (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === 'typing') {
      typing.hidden = !data.value;
      sendBtn.disabled = data.value;
      return;
    }
    if (data.type === 'message') {
      addMessage('bot', data.text);
      if (data.meta && data.meta.mood) updateMood(data.meta.mood);
    }
  });

  ws.addEventListener('close', () => {
    addMessage('bot', '⚠️ Conexão encerrada. Recarregue a página para reconectar.');
  });

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    addMessage('user', text);
    ws.send(JSON.stringify({ message: text }));
    input.value = '';
    input.focus();
  });

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
    // Converte **negrito**, *itálico*, listas e quebras
    let html = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/^[•\-]\s(.+)$/gm, '<li>$1</li>')
      .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
      .replace(/\n/g, '<br>');
    return '<p>' + html + '</p>';
  }

  function updateMood(mood) {
    const map = {
      happy: '😊', tired: '😴', stressed: '😰',
      excited: '🤩', neutral: '🙂', sad: '😔',
    };
    moodEmoji.textContent = map[mood] || '🙂';
    moodLabel.textContent = mood;
  }

  input.focus();
})();
