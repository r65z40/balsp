// Scanner QR code — Bal des Pompiers d'Auxerre
// Chaque QR code correspond à une invitation unique.

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
  const currentCard = document.getElementById('current-invitation');
  const currentNumber = document.getElementById('current-number');
  const currentName = document.getElementById('current-name');
  const currentStatus = document.getElementById('current-status');
  const invitationList = document.getElementById('invitation-list');

  // Check-in controls
  const guestNameInput = document.getElementById('guest-name');
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
    if (guestNameInput) guestNameInput.value = '';
    clearMessage();
  }

  function showResultView() {
    scannerSection.classList.add('d-none');
    resultSection.classList.remove('d-none');
  }

  // --- Rendering ---

  function renderInvitations(invitations, currentId) {
    invitationList.innerHTML = '';
    invitations.forEach(inv => {
      const li = document.createElement('li');
      const isCurrent = inv.id === currentId;
      li.className = 'list-group-item d-flex justify-content-between align-items-center'
        + (isCurrent ? ' border-danger border-2' : '');
      const badge = inv.scanned
        ? '<span class="badge text-bg-success me-2">Arrivé</span>'
        : '<span class="badge text-bg-light text-dark me-2">Attendu</span>';
      const nameHtml = inv.guest_name
        ? `<strong>${inv.guest_name}</strong>`
        : '<span class="text-muted">Sans nom</span>';
      const scannedBy = inv.scanned_by ? ` <small class="text-muted">par ${inv.scanned_by}</small>` : '';
      li.innerHTML = `
        <span>${badge}<span class="me-2">#${inv.number}</span>${nameHtml}${scannedBy}</span>
        <button class="btn btn-sm ${inv.scanned ? 'btn-outline-secondary' : 'btn-outline-success'} inv-toggle" data-id="${inv.id}">
          ${inv.scanned ? 'Annuler' : 'Pointer'}
        </button>
      `;
      invitationList.appendChild(li);
    });

    invitationList.querySelectorAll('.inv-toggle').forEach(btn => {
      btn.addEventListener('click', () => toggleInvitation(parseInt(btn.dataset.id)));
    });
  }

  function renderCurrentInvitation(inv) {
    if (!inv) {
      currentCard.classList.add('d-none');
      return;
    }
    currentCard.classList.remove('d-none');
    currentNumber.textContent = inv.number;
    currentName.textContent = inv.guest_name || '';
    if (inv.scanned) {
      currentStatus.className = 'badge text-bg-success';
      currentStatus.textContent = 'Déjà pointée';
      btnCheckin.disabled = true;
      btnUndo.classList.remove('d-none');
    } else {
      currentStatus.className = 'badge text-bg-warning text-dark';
      currentStatus.textContent = 'En attente';
      btnCheckin.disabled = false;
      btnUndo.classList.add('d-none');
    }
  }

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
    renderInvitations(sponsor.invitations, sponsor.current_invitation_id);
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

    await stopScanner();
    showResultView();
    renderSponsor(data.sponsor);
    renderCurrentInvitation(data.invitation);

    if (data.invitation.scanned) {
      showMessage('warning', `⚠️ Invitation n°${data.invitation.number} déjà utilisée.`);
    } else {
      showMessage('info', `Invitation n°${data.invitation.number} — prête à être pointée.`);
    }
  }

  async function checkIn() {
    if (!currentToken) return;
    const guestName = (guestNameInput.value || '').trim();

    const { ok, data } = await apiPost('/scan/check-in', {
      token: currentToken,
      guest_name: guestName,
    });
    if (!ok || !data.ok) {
      showMessage('danger', data.error || 'Erreur lors du pointage.');
      if (data.sponsor) {
        renderSponsor(data.sponsor);
        renderCurrentInvitation(data.invitation);
      }
      return;
    }
    renderSponsor(data.sponsor);
    renderCurrentInvitation(data.invitation);
    const name = data.invitation.guest_name ? ` (${data.invitation.guest_name})` : '';
    showMessage('success', `✓ Invitation n°${data.invitation.number} pointée${name}.`);
    guestNameInput.value = '';
  }

  async function undo() {
    if (!currentToken) return;
    const { ok, data } = await apiPost('/scan/undo', { token: currentToken });
    if (!ok || !data.ok) {
      showMessage('danger', data.error || 'Impossible d\'annuler.');
      return;
    }
    renderSponsor(data.sponsor);
    renderCurrentInvitation(data.invitation);
    showMessage('info', `Pointage de l'invitation n°${data.invitation.number} annulé.`);
  }

  async function toggleInvitation(invitationId) {
    const { ok, data } = await apiPost('/scan/toggle-invitation', { invitation_id: invitationId });
    if (!ok || !data.ok) {
      showMessage('danger', data.error || 'Erreur.');
      return;
    }
    renderSponsor(data.sponsor);
    if (data.invitation.id === data.sponsor.current_invitation_id) {
      renderCurrentInvitation(data.invitation);
    }
    const action = data.invitation.scanned ? 'pointée' : 'dépointée';
    showMessage('info', `Invitation n°${data.invitation.number} ${action}.`);
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
    await startScanner();
  });
})();
