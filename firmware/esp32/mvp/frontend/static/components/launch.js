(() => {
  const devices = document.getElementById('platform-devices');
  if (!devices) return;
  const events = document.getElementById('platform-events');
  const credentials = document.getElementById('platform-credentials');
  const status = document.getElementById('platform-status');
  const panel = document.getElementById('platform-devices-section');
  const developer = panel.dataset.developer === 'true';
  const staff = panel.dataset.staff === 'true';
  const node = (tag, text) => { const el = document.createElement(tag); el.textContent = text; return el; };
  let busy = false, queued = false;
  async function get(path) {
    const response = await fetch('/api/v1/' + path, {headers: {'Accept': 'application/json'}});
    if (!response.ok) throw new Error('No se pudo actualizar');
    return response.json();
  }
  async function refresh() {
    if (document.hidden) return;
    if (busy) { queued = true; return; }
    busy = true;
    try {
      const [deviceState, eventState, credentialState] = await Promise.all([
        get('devices/'), get('events/recent/'), credentials ? get('credentials/') : Promise.resolve(null)
      ]);
      devices.replaceChildren();
      for (const device of deviceState.devices) {
        const card = node('article', ''); card.className = 'device-tile';
        card.append(node('h3', device.name), node('strong', device.status),
          node('p', device.device_type), node('small', 'Última señal: ' + (device.last_seen ? new Date(device.last_seen).toLocaleString() : 'Sin señal registrada')));
        const details = node('details', ''); details.append(node('summary', developer ? 'Ver dispositivo y diagnóstico' : 'Ver dispositivo'));
        details.append(node('small', 'Dispositivo: ' + device.device_id));
        if (developer) details.append(node('pre', JSON.stringify({driver: device.driver, role: device.role, firmware: device.firmware_version, capabilities: device.capabilities, health: device.health}, null, 2)));
        card.append(details);
        if (staff && device.status !== 'DISABLED') {
          const disable = node('button', 'Desactivar'); disable.className = 'secondary';
          disable.onclick = async () => {
            if (!window.confirm('¿Desactivar ' + device.name + '? Dejará de enviar lecturas autorizadas.')) return;
            disable.disabled = true;
            try {
              const token = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
              const response = await fetch('/api/v1/devices/' + device.device_id + '/disable/', {method: 'POST', headers: {'X-CSRFToken': token || ''}});
              if (!response.ok) throw new Error();
              refresh();
            } catch { disable.disabled = false; status.textContent = 'No se pudo desactivar el dispositivo.'; }
          };
          card.append(disable);
        }
        devices.append(card);
      }
      if (!deviceState.devices.length) devices.append(node('p', 'Aún no hay dispositivos vinculados a tu cuenta.'));
      if (events) {
        events.replaceChildren();
        for (const event of eventState.events) {
          const item = node('article', ''); item.className = 'activity-item';
          item.append(node('strong', event.status === 'detected' ? 'Credencial detectada' : 'Tecnología sin soporte activo'),
            node('p', event.device_name + ' · ' + event.technology), node('small', new Date(event.timestamp).toLocaleString()));
          if (developer) { const detail = node('details', ''); detail.append(node('summary', 'Diagnóstico del evento'), node('pre', JSON.stringify(event, null, 2))); item.append(detail); }
          events.append(item);
        }
        if (!eventState.events.length) events.append(node('p', 'Sin lecturas registradas.'));
      }
      if (credentials && credentialState) {
        credentials.replaceChildren();
        for (const credential of credentialState.credentials) credentials.append(node('p', credential.technology + ' · ' + credential.status + ' · ' + credential.credential_id));
        if (!credentialState.credentials.length) credentials.append(node('p', 'Asocia tu primera tarjeta para comenzar.'));
      }
      if (status) status.textContent = 'Actualizado: ' + new Date().toLocaleTimeString();
    } catch {
      if (status) status.textContent = 'Sin conexión. Los datos anteriores pueden estar desactualizados.';
    } finally {
      busy = false;
      if (queued) { queued = false; queueMicrotask(refresh); }
    }
  }
  refresh();
  window.addEventListener('ogpass:refresh', refresh);
  const timer = setInterval(refresh, 5000);
  window.addEventListener('pagehide', () => clearInterval(timer), {once: true});
})();
