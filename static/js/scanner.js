// Scanner QR code — Bal des Pompiers d'Auxerre

(function () {
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  let html5QrCode = null;
  let running = false;
  let currentToken = null;

  // Sections
  const scannerSection = document.getElementById('scanner-section');
  const resultSection = document.getElementById('result-section');

  // Scanner controls
  const btnToggle = document.getElementById('btn-toggle');
  const btnManual = document.getElementById('btn-manual');
  const manualInput = document.getElementById('manual-token');

  // Result elements
  const resultLogo = document.getElementById('result-logo');
  const resultName = document.getElementById('result-name');
  const resultTier = document.getElementById('result-tier');
  const resultEntries = document.getElementById('result-entries');
  const resultTotal = document.getElementById('result-total');
  const resultProgress = document.getElementById('result-progress');
  const resultMessage = document.getElementById('result-message');
  const resultGuests = document.getElementById('result-guests');
  const guestList = document.getElementById('guest-list');

  // Check-in controls
  const guestNameInput = document.getElementById('guest-name');
  const countInput = document.getElementById('checkin-count');
  const btnCheckin = document.getElementById('btn-checkin');
  const btnUndo = document.getElementById('btn-undo');
  const btnRescan = document.getElementById('btn-rescan');

  // --- UI helpers ---

  function showMessage(type, text) {
    resultMessage.className = `alert alert-${type}`;
    resultMessage.textContent = text;
  }

  function clearMessage() {
    resultMessage.className = 'alert d-none';
    resultMessage.textContent = '';
  }

  function showScannerView() {
    scannerSection.classList.remove('d-none');
    resultSection.classList.add('d-none');
    currentToken = null;
    guestNameInput.value = '';
    countInput.value = '1';
    clearMessage();
  }

  function showResultView() {
    scannerSection.classList.add('d-none');
    resultSection.classList.remove('d-none');
  }

  // --- Guests ---

  function renderGuests(guests) {
    guestList.innerHTML = '';
    if (!guests || guests.length === 0) {
      resultGuests.classList.add('d-none');
      return;
    }
    resultGuests.classList.remove('d-none');
    guests.forEach(g => {
      const li = document.createElement('li');
      li.className = 'list-group-item d-flex justify-content-between align-items-center';
      const badge = g.checked_in
        ? '<span class="badge text-bg-success me-2">Arrivé</span>'
        : '<span class="badge text-bg-light me-2">Attendu</span>';
      li.innerHTML = `
        <span>${badge}${g.name}</span>
        <button class="btn btn-sm ${g.checked_in ? 'btn-outline-secondary' : 'btn-outline-success'} guest-toggle" data-id="${g.id}">
          ${g.checked_in ? 'Annuler' : 'Pointer'}
        </button>
      `;
      guestList.appendChild(li);
    });

    guestList.querySelectorAll('.guest-toggle').forEach(btn => {
      btn.addEventListener('click', () => toggleGuest(parseInt(btn.dataset.id)));
    });
  }

  async function toggleGuest(guestId) {
    const { ok, data } = await apiPost('/scan/guest-toggle', { guest_id: guestId });
    if (!ok || !data.ok) {
      showMessage('danger', data.error || 'Erreur.');
      return;
    }
    renderSponsor(data.sponsor);
    const action = data.guest.checked_in ? 'pointé' : 'dépointé';
    showMessage('info', `${data.guest.name} ${action}.`);
  }

  // --- Sponsor display ---

  function renderSponsor(sponsor) {
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
    renderGuests(sponsor.guests);
  }

  // --- API ---

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

  // --- Actions ---

  async function verifyToken(token) {
    clearMessage();
    const { ok, data } = await apiPost('/scan/verify', { token });
    if (!ok || !data.ok) {
      alert(data.error || 'QR code non reconnu.');
      currentToken = null;
      return;
    }
    currentToken = token;

    // Arrêter la caméra et basculer vers le formulaire
    await stopScanner();
    showResultView();
    renderSponsor(data.sponsor);

    if (data.sponsor.is_full) {
      showMessage('warning', 'Toutes les invitations de ce sponsor ont déjà été utilisées.');
    }
  }

  async function checkIn() {
    if (!currentToken) return;
    const count = parseInt(countInput.value, 10) || 1;
    const guestName = (guestNameInput.value || '').trim();

    const { ok, data } = await apiPost('/scan/check-in', {
      token: currentToken,
      count,
      guest_name: guestName,
    });
    if (!ok || !data.ok) {
      showMessage('danger', data.error || 'Erreur lors du pointage.');
      if (data.sponsor) renderSponsor(data.sponsor);
      return;
    }
    renderSponsor(data.sponsor);
    let msg = `+${count} entrée(s) enregistrée(s).`;
    if (guestName) msg += ` (${guestName})`;
    showMessage('success', msg);

    // Reset du formulaire pour le prochain invité
    guestNameInput.value = '';
    countInput.value = '1';
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

  // --- Camera ---

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

  // --- Event listeners ---

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

  btnRescan.addEventListener('click', async () => {
    showScannerView();
    // Relancer la caméra automatiquement
    await startScanner();
  });
})();
