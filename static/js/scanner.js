// Scanner QR code pour l'accueil concert

(function () {
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  let html5QrCode = null;
  let running = false;
  let currentToken = null;

  const btnToggle = document.getElementById('btn-toggle');
  const btnManual = document.getElementById('btn-manual');
  const btnCheckin = document.getElementById('btn-checkin');
  const btnUndo = document.getElementById('btn-undo');
  const btnReset = document.getElementById('btn-reset');

  const manualInput = document.getElementById('manual-token');
  const countInput = document.getElementById('checkin-count');

  const resultCard = document.getElementById('result-card');
  const placeholder = document.getElementById('placeholder');
  const resultLogo = document.getElementById('result-logo');
  const resultName = document.getElementById('result-name');
  const resultTier = document.getElementById('result-tier');
  const resultEntries = document.getElementById('result-entries');
  const resultTotal = document.getElementById('result-total');
  const resultProgress = document.getElementById('result-progress');
  const resultMessage = document.getElementById('result-message');

  function showMessage(type, text) {
    resultMessage.className = `alert alert-${type}`;
    resultMessage.textContent = text;
  }

  function clearMessage() {
    resultMessage.className = 'alert d-none';
    resultMessage.textContent = '';
  }

  function renderSponsor(sponsor) {
    resultCard.classList.remove('d-none');
    placeholder.classList.add('d-none');
    if (sponsor.logo_url) {
      resultLogo.src = sponsor.logo_url;
      resultLogo.style.display = '';
    } else {
      resultLogo.style.display = 'none';
    }
    resultName.textContent = sponsor.company_name;
    resultTier.textContent = sponsor.tier + ' — ' + sponsor.contact_name;
    resultEntries.textContent = sponsor.entries_count;
    resultTotal.textContent = sponsor.total_invitations;
    const pct = sponsor.total_invitations
      ? (sponsor.entries_count / sponsor.total_invitations) * 100
      : 0;
    resultProgress.style.width = pct + '%';
    resultProgress.classList.toggle('bg-success', sponsor.is_full);
    resultProgress.classList.toggle('bg-warning', !sponsor.is_full && pct >= 50);
  }

  async function apiPost(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
      },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, data };
  }

  async function verifyToken(token) {
    clearMessage();
    const { ok, data } = await apiPost('/scan/verify', { token });
    if (!ok || !data.ok) {
      placeholder.classList.remove('d-none');
      resultCard.classList.add('d-none');
      alert(data.error || 'QR code non reconnu.');
      currentToken = null;
      return;
    }
    currentToken = token;
    renderSponsor(data.sponsor);
    if (data.sponsor.is_full) {
      showMessage('warning', 'Toutes les invitations de ce sponsor ont déjà été utilisées.');
    }
  }

  async function checkIn() {
    if (!currentToken) return;
    const count = parseInt(countInput.value, 10) || 1;
    const { ok, data } = await apiPost('/scan/check-in', {
      token: currentToken,
      count,
    });
    if (!ok || !data.ok) {
      showMessage('danger', data.error || 'Erreur lors du pointage.');
      if (data.sponsor) renderSponsor(data.sponsor);
      return;
    }
    renderSponsor(data.sponsor);
    showMessage('success', `+${count} entrée(s) enregistrée(s).`);
  }

  async function undo() {
    if (!currentToken) return;
    const { ok, data } = await apiPost('/scan/undo', { token: currentToken });
    if (!ok || !data.ok) {
      showMessage('danger', data.error || 'Impossible d\'annuler.');
      return;
    }
    renderSponsor(data.sponsor);
    showMessage('info', 'Dernier pointage annulé.');
  }

  function resetView() {
    currentToken = null;
    resultCard.classList.add('d-none');
    placeholder.classList.remove('d-none');
    manualInput.value = '';
  }

  async function startScanner() {
    if (!html5QrCode) {
      html5QrCode = new Html5Qrcode('qr-reader');
    }
    try {
      await html5QrCode.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 260, height: 260 } },
        async (decodedText) => {
          await html5QrCode.pause(true);
          await verifyToken(decodedText.trim());
        },
        () => {}
      );
      running = true;
      btnToggle.textContent = 'Arrêter';
    } catch (err) {
      alert('Impossible d\'accéder à la caméra : ' + err);
    }
  }

  async function stopScanner() {
    if (html5QrCode && running) {
      try {
        await html5QrCode.stop();
      } catch (_) {}
      running = false;
      btnToggle.textContent = 'Démarrer';
    }
  }

  btnToggle.addEventListener('click', () => {
    if (running) stopScanner();
    else startScanner();
  });

  btnManual.addEventListener('click', () => {
    const token = (manualInput.value || '').trim();
    if (token) verifyToken(token);
  });
  manualInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      btnManual.click();
    }
  });

  btnCheckin.addEventListener('click', checkIn);
  btnUndo.addEventListener('click', undo);
  btnReset.addEventListener('click', async () => {
    resetView();
    if (html5QrCode && running) {
      try {
        await html5QrCode.resume();
      } catch (_) {}
    }
  });
})();
