'use strict';
const $ = id => document.getElementById(id);
const clp = n => new Intl.NumberFormat('es-CL',{style:'currency',currency:'CLP',maximumFractionDigits:0}).format(n);
const labels = {pending:'Pendiente',approved:'Aprobada',credited:'Acreditada',activated:'Activada',declined:'Rechazada',expired:'Expirada',reversed:'Reversada',review_required:'En revisión',rejected:'Rechazada',cancelled:'Cancelada'};
function el(tag,text,cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
async function get(url){const r=await fetch(url,{headers:{Accept:'application/json'},cache:'no-store'});if(!r.ok||r.redirected)throw new Error('connection');return r.json();}
if($('wallet-page')){
 let signature='',preloadSignature='',updating=false,queued=false,live=false,pendingDeadlines=[];
 document.querySelectorAll('a[href="#my-card"]').forEach(a=>a.addEventListener('click',()=>{$('my-card').open=true;}));
 async function update(){
  if(updating){queued=true;return;}
  updating=true;
  try{
   const d=await get('/api/state/');$('balance').textContent=clp(d.balance);$('updated').textContent='Ledger actualizado: '+new Date(d.updated_at).toLocaleTimeString('es-CL');$('connection').textContent='';$('frozen').hidden=!d.frozen;
   pendingDeadlines=d.pending.map(op=>Date.parse(op.expires_at));
   const preloadNext=JSON.stringify([d.frozen,d.preloads||[]]);
   if(preloadNext!==preloadSignature){
    preloadSignature=preloadNext;$('preloads').replaceChildren();
    const ready=(d.preloads||[]).filter(p=>p.status==='ready');
    if(!ready.length)$('preloads').append(el('p','No tienes prerecargas pendientes.','muted'));
    for(const preload of ready){
     const item=el('div',undefined,'preload-item');item.append(el('strong',clp(preload.amount)+' CLP'),el('small','Fondos OGPASS reservados · Sin vencimiento'));
     const button=el('button','Activar '+clp(preload.amount));button.disabled=d.frozen;
     button.onclick=async()=>{button.disabled=true;$('preload-message').textContent='Activando…';try{
      const csrf=document.querySelector('[name=csrfmiddlewaretoken]').value;
      const response=await fetch('/api/preloads/'+preload.id+'/activate/',{method:'POST',headers:{'X-CSRFToken':csrf}});
      if(!response.ok)throw new Error();
      $('preload-message').textContent='Prerecarga activada. Tus fondos ya están disponibles.';await update();
     }catch(error){$('preload-message').textContent='No se pudo confirmar. Puedes reintentar: la activación no se duplica.';button.disabled=false;}};
     item.append(button);$('preloads').append(item);
    }
   }
   $('linked-cards').replaceChildren();
   for(const c of d.cards||[]){const row=el('div',undefined,'linked-card');row.append(el('strong','Tarjeta '+c.number),el('p',c.active?'Asociada':'Desactivada'));$('linked-cards').append(row);}
   $('association-status').textContent=(d.association_pending||[]).map(n=>'Tarjeta '+n+' · Vinculación al lector OGPASS pendiente.').join(' ');
   const readers=d.readers||[];
   $('reader-status').textContent=readers.length?readers.map(r=>r.name+' · '+(r.online?'En línea':'Sin conexión')).join(' / '):'No hay lectores configurados. La asociación se completará cuando un lector envíe una lectura real.';
   const scan=d.last_scan;
   $('scan-status').replaceChildren();
   if(scan){
    $('scan-status').append(el('strong',scan.card_number?'Tarjeta '+scan.card_number:'Tarjeta detectada'));
    if(scan.available_balance!==null){$('scan-status').append(el('p','Disponible OGPASS: '+clp(scan.available_balance)+' CLP'));}
    if(scan.status==='disabled')$('scan-status').append(el('p','Tarjeta desactivada. No se muestra saldo en el lector.'));
    if(scan.frozen)$('scan-status').append(el('p','Cuenta en revisión. Fondos no disponibles para operar.'));
    $('scan-status').append(el('small','Última lectura: '+new Date(scan.scanned_at).toLocaleString('es-CL')+' · '+scan.reader),el('small','Fuente: ledger OGPASS. Consultar no descuenta fondos.'));
   }else{$('scan-status').append(el('p','Escanea tu tarjeta asociada para consultar tus fondos OGPASS.'));}
   const next=JSON.stringify(d.pending);
   if(next!==signature){signature=next;$('pending').replaceChildren();for(const op of d.pending){const card=el('section',undefined,'card pending-card');card.append(el('p','CONFIRMA TU OPERACIÓN','eyebrow'),el('h2',clp(op.amount)+' CLP'),el('p',op.reader+' · Confirma antes de '+new Date(op.expires_at).toLocaleTimeString('es-CL')));const actions=el('div',undefined,'actions');for(const [approve,title] of [[true,'Confirmar pago'],[false,'Rechazar']]){const b=el('button',title,approve?'':'secondary');b.onclick=async()=>{for(const btn of actions.children)btn.disabled=true;try{const csrf=document.querySelector('[name=csrfmiddlewaretoken]').value;const r=await fetch('/api/operations/'+op.id+'/confirm/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify({approve})});if(!r.ok)throw new Error();signature='';await update();}catch(e){$('connection').textContent='No se recibió confirmación. Consultando el estado…';signature='';}};actions.append(b);}card.append(actions);$('pending').append(card);}}
   const rows=[...(d.preloads||[]).filter(p=>p.status==='activated').map(p=>({...p,created_at:p.activated_at,type:'Prerecarga',signed:p.amount})),...d.operations.map(o=>({...o,type:'Operación',signed:o.status==='approved'?-o.amount:0})),...d.topups.map(t=>({...t,type:'Recarga',signed:t.status==='credited'?t.amount:0}))].sort((a,b)=>b.created_at.localeCompare(a.created_at));$('movements').replaceChildren();if(!rows.length)$('movements').append(el('p','Tu primer movimiento aparecerá aquí.','muted'));for(const row of rows){const n=el('div',undefined,'movement');const detail=el('div',row.type+' · '+(labels[row.status]||row.status));detail.append(el('small',new Date(row.created_at).toLocaleString('es-CL')),el('small',row.id));n.append(detail,el('strong',row.signed?clp(row.signed):clp(row.amount)+' · sin débito',row.signed>0?'positive':''));$('movements').append(n);}
  }catch(e){$('connection').textContent='Sin conexión. El saldo mostrado puede estar desactualizado.';$('reader-status').textContent='No se puede verificar la conexión del lector en este momento.';}
  finally{updating=false;if(queued){queued=false;queueMicrotask(update);}}
 }
 async function external(){try{const d=await get('/api/external/');$('stellar').replaceChildren();if(!d.stellar.length)$('stellar').append(el('p','Stellar Testnet: cuenta pendiente de crear. Sin saldo consultado.','muted'));for(const a of d.stellar){$('stellar').append(el('h3',a.network==='testnet'?'Stellar Testnet · Activos de prueba':'Stellar Mainnet · Activos en red pública'),el('small',a.address));if(a.network==='testnet')$('stellar').append(el('p','Sin valor monetario real. No es saldo CLP.','muted'));if(a.status!=='connected')$('stellar').append(el('p','Estado: '+a.status+' · saldo no disponible'));else{for(const b of a.balances){$('stellar').append(el('p',b.balance+' '+(b.asset_type==='native'?'XLM':b.asset_code)),el('small',b.asset_issuer||'Activo nativo'));}const link=el('a','Ver fuente en Horizon ↗');link.href=a.source_url;link.target='_blank';link.rel='noopener';$('stellar').append(link,el('small','Consultado: '+new Date(a.updated_at).toLocaleString('es-CL')));}}}catch(e){$('stellar').textContent='Stellar: conexión no disponible. Sin saldo verificado.';}}
 async function transport(){
  const target=$('transport-result');
  try{
   const data=await get('/api/transport/');target.replaceChildren();
   if(!data.cards.length){target.append(el('p',data.message));return;}
   for(const card of data.cards){
    const row=el('div',undefined,'linked-card');row.append(el('strong','Tarjeta '+card.card_number),el('p','Saldo: no disponible en OGPASS'),el('small','Fuente: '+data.source));
    const copy=el('button','Copiar número','secondary');copy.type='button';copy.onclick=async()=>{try{await navigator.clipboard.writeText(card.card_number);copy.textContent='Número copiado';}catch(error){copy.textContent='Número: '+card.card_number;}};const monitor=el('button','Monitor NFC / Copiar a llavero','secondary');monitor.type='button';monitor.onclick=()=>openNfcMonitor(card.card_number,monitor);const actions=el('div',undefined,'card-tools');actions.append(copy,monitor);row.append(actions);target.append(row);
   }
   target.append(el('p',data.message));
   const link=el('a','Consultar saldo en bip! ↗','button');link.href=data.source_url;link.target='_blank';link.rel='noopener noreferrer';target.append(link);
   if(data.checked_at)target.append(el('small','Disponibilidad del portal comprobada: '+new Date(data.checked_at).toLocaleString('es-CL')+' · Esto no es una actualización de saldo.'));
  }catch(error){target.replaceChildren(el('p','No se pudo comprobar la consulta de transporte. No hay saldo verificado.'));}
 }
 update();external();transport();
 if(window.EventSource){
  const stream=new EventSource('/api/events/');
  stream.onopen=()=>{live=true;$('live-status').textContent='● Fondos OGPASS en vivo';};
  stream.addEventListener('wallet',()=>{if(!document.hidden)update();});
  stream.onerror=()=>{live=false;$('live-status').textContent='Reconectando… Consulta de respaldo cada 5 s.';};
  window.addEventListener('pagehide',()=>stream.close(),{once:true});
 }else{$('live-status').textContent='Consulta automática cada 5 s.';}
 document.addEventListener('visibilitychange',()=>{if(!document.hidden){update();external();transport();}});
 setInterval(()=>{if(!live&&!document.hidden)update();},5000);
 setInterval(()=>{if(pendingDeadlines.some(deadline=>deadline<=Date.now())){pendingDeadlines=[];update();}},1000);
 // External providers have independent refresh intervals, not OGPASS event guarantees.
 setInterval(()=>{if(!document.hidden)external();},60000);
 setInterval(()=>{if(!document.hidden)transport();},300000);
}

if($('ops-page')){
 let running=false,again=false,connected=false,preloadsVersion='';
 async function refreshOps(){
  if(running){again=true;return;}running=true;
  try{const data=await get('/api/ops/state/');for(const node of document.querySelectorAll('[data-ops-value]'))node.textContent=clp(data.report[node.dataset.opsValue]);$('funding-balance').textContent=clp(data.funding_balance);
   const next=JSON.stringify(data.preloads);
   if(next!==preloadsVersion){preloadsVersion=next;const tbody=$('ops-preload-rows');tbody.replaceChildren();
    for(const p of data.preloads){const row=el('tr');row.append(el('td',new Date(p.created_at).toLocaleString('es-CL')),el('td',p.recipient),el('td',clp(p.amount)),el('td',p.label));const action=el('td');
     if(p.cancellable){const form=el('form');form.method='post';form.action='/ops/preloads/'+p.id+'/cancel/';const csrf=el('input');csrf.type='hidden';csrf.name='csrfmiddlewaretoken';csrf.value=document.querySelector('[name=csrfmiddlewaretoken]').value;form.append(csrf,el('button','Cancelar y recuperar fondos','secondary'));action.append(form);}
     row.append(action);tbody.append(row);
    }
    if(!data.preloads.length){const row=el('tr');const cell=el('td','Sin prerecargas.');cell.colSpan=5;row.append(cell);tbody.append(row);}
   }
  }
  catch(error){$('ops-live-status').textContent='Sin conexión: los saldos mostrados pueden estar desactualizados.';}
  finally{running=false;if(again){again=false;queueMicrotask(refreshOps);}}
 }
 if(window.EventSource){const stream=new EventSource('/api/ops/events/');stream.onopen=()=>{connected=true;$('ops-live-status').textContent='● Saldos y resultado OGPASS en vivo';};stream.addEventListener('wallet',refreshOps);stream.onerror=()=>{connected=false;$('ops-live-status').textContent='Reconectando saldos…';};window.addEventListener('pagehide',()=>stream.close(),{once:true});}
 refreshOps();setInterval(()=>{if(!connected&&!document.hidden)refreshOps();},5000);
}


if($('ops-readers')){
 let reading=false,version='';
 async function readers(){
  if(reading||document.hidden)return;reading=true;
  try{
   const data=await get('/api/ops/readers/');
   const next=JSON.stringify(data);
   if(next===version)return;
   const selected={};document.querySelectorAll('[data-reader-select]').forEach(n=>selected[n.dataset.readerSelect]=n.value);
   version=next;$('ops-readers').replaceChildren();
   if(!data.readers.length)$('ops-readers').append(el('p','No hay lectores configurados. Conecta y provisiona el ESP32 para comenzar.'));
   for(const r of data.readers){
    const box=el('div',undefined,'reader-item');box.append(el('h3',r.name),el('span',r.online?'● En línea':r.active?'○ Sin conexión':'○ Deshabilitado','pill'),el('small','Última señal: '+(r.last_seen?new Date(r.last_seen).toLocaleString('es-CL'):'Nunca')));
    const scan=r.scan;
    if(scan){
     box.append(el('p',scan.card_number?'Tarjeta '+scan.card_number+' · '+(scan.active?'Asociada a '+scan.owner:'Desactivada'):'Tarjeta detectada · Sin asociación'),el('small','UID leído: '+scan.uid),el('small','Lectura: '+new Date(scan.at).toLocaleString('es-CL')));
     if(scan.card_number&&scan.active){const button=el('button','Copiar y reescribir en la próxima tarjeta NFC','secondary');button.onclick=()=>{$('copy-card').textContent='Origen: '+scan.card_number+' · UID '+scan.uid;$('copy-dialog').showModal();};box.append(button,el('small','Pendiente de habilitar escritura y verificación en el lector.'));}
     if(scan.pairable&&data.requests.length){
      const label=el('label','Solicitud de asociación');const select=el('select');select.dataset.readerSelect=r.id;select.id='reader-request-'+r.id;label.htmlFor=select.id;
      const placeholder=el('option','Selecciona usuario e ID');placeholder.value='';select.append(placeholder);
      for(const request of data.requests){const option=el('option',request.user+' · '+request.number);option.value=request.id;select.append(option);}
      select.value=selected[r.id]||'';
      const button=el('button','Vincular tarjeta detectada');button.disabled=!select.value;select.onchange=()=>button.disabled=!select.value;
      button.onclick=async()=>{
       const item=data.requests.find(x=>String(x.id)===select.value);if(!item)return;
       if(!window.confirm('¿Vincular el UID '+scan.uid+' con la tarjeta '+item.number+' de '+item.user+'? Comprueba ambos datos en el punto de atención.'))return;
       button.disabled=true;
       try{const body=new URLSearchParams({request_id:item.id,number:item.number,scan_key:scan.key});const response=await fetch('/ops/cards/associate/',{method:'POST',headers:{'X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value},body});const result=await response.json();if(!response.ok)throw new Error(result.error||'No se pudo vincular.');$('ops-reader-message').textContent='Tarjeta '+result.number+' asociada. No se escribieron datos en el chip.';version='';await readers();}
       catch(error){$('ops-reader-message').textContent=error.message;button.disabled=false;}
      };
      box.append(label,select,el('small','Comprueba que el número impreso y el titular corresponden a la tarjeta detectada.'),button);
     }
    }else box.append(el('p','Acerca una tarjeta NFC para ver su lectura.'));
    $('ops-readers').append(box);
   }
   if(data.requests.length)$('ops-readers').append(el('p',data.requests.length+' solicitud(es) pendiente(s) de vinculación.'));
  }catch(error){version='';$('ops-readers').replaceChildren(el('p','Sin conexión con el servidor. No se puede verificar el estado del lector.'));}
  finally{reading=false;}
 }
 readers();setInterval(readers,2000);
}


// Read-only monitor. Demo never sends a command to a reader or changes a card/account.
let openNfcMonitor=()=>{};
if($('nfc-monitor')){
 const dialog=$('nfc-monitor');let epoch=0,pollTimer=null,demoTimers=[],opener=null;
 function stop(){epoch++;clearTimeout(pollTimer);demoTimers.forEach(clearTimeout);demoTimers=[];}
 function line(text){const log=$('nfc-log');log.append(el('p','['+new Date().toLocaleTimeString('es-CL')+'] '+text));while(log.children.length>40)log.firstElementChild.remove();log.scrollTop=log.scrollHeight;}
 openNfcMonitor=(number,button)=>{
  stop();opener=button;const current=epoch;let lastReaders='',lastScan='',busy=false;
  $('nfc-source').textContent='Número guardado: '+number;
  $('nfc-log').replaceChildren();$('nfc-demo').hidden=true;$('nfc-demo-start').disabled=false;$('nfc-demo-result').textContent='';
  $('nfc-live').textContent='Comprobando lector…';dialog.showModal();
  line('Monitor iniciado. Consultas de solo lectura.');
  line('Referencia guardada: '+number+'. No es una copia de la memoria NFC.');
  async function poll(){
   if(current!==epoch||!dialog.open||busy)return;busy=true;
   try{
    const data=await get('/api/state/');if(current!==epoch||!dialog.open)return;
    const summary=data.readers.length?data.readers.map(r=>r.name+': '+(r.online?'en línea':'sin conexión')).join(' · '):'No hay lectores configurados';
    $('nfc-live').textContent=summary+' · Consultado '+new Date().toLocaleTimeString('es-CL');
    if(summary!==lastReaders){line(summary);lastReaders=summary;}
    const associated=(data.cards||[]).some(c=>c.number===number&&c.active);
    const scan=data.last_scan;
    const stamp=JSON.stringify([associated,scan&&scan.card_number===number?scan.key:null]);
    if(stamp!==lastScan){
     lastScan=stamp;
     if(!associated)line('Número guardado; vinculación NFC pendiente.');
     else if(scan&&scan.card_number===number){line('Última lectura de esta tarjeta: '+new Date(scan.scanned_at).toLocaleString('es-CL')+' · '+scan.reader);line('Datos disponibles: referencia de cuenta OGPASS. Memoria y metadatos completos: no disponibles.');}
     else line('Tarjeta vinculada. Esperando una lectura de esta tarjeta.');
    }
   }catch(error){if(current===epoch){$('nfc-live').textContent='Sin conexión con el servidor. Estado del lector no verificado.';if(lastReaders!=='unavailable'){line('No se pudo actualizar el monitor. Reintentando…');lastReaders='unavailable';}}}
   finally{busy=false;if(current===epoch&&dialog.open)pollTimer=setTimeout(poll,2000);}
  }
  poll();
 };
 $('nfc-close').onclick=()=>dialog.close();dialog.addEventListener('close',()=>{stop();if(opener&&opener.isConnected)opener.focus();});
 window.addEventListener('pagehide',stop);
 $('nfc-demo-start').onclick=()=>{
  demoTimers.forEach(clearTimeout);demoTimers=[];const current=epoch;
  $('nfc-demo').hidden=false;$('nfc-demo-start').disabled=true;$('nfc-demo-log').textContent='[DEMO] Referencia ficticia: OGPASS-EJEMPLO-001\n';$('nfc-demo-result').textContent='Demostración en curso. Ninguna escritura real.';
  for(let i=1;i<=3;i++)$('nfc-step-'+i).classList.remove('done');
  const steps=[
   [400,1,'[DEMO] Datos de aplicación de ejemplo preparados.'],
   [1400,2,'[DEMO] Llavero de ejemplo presentado. No es detección del lector.'],
   [2400,3,'[DEMO] Copia virtual comparada con el ejemplo: coincide.']
  ];
  for(const [delay,step,text] of steps)demoTimers.push(setTimeout(()=>{if(current!==epoch||!dialog.open)return;$('nfc-step-'+step).classList.add('done');$('nfc-demo-log').textContent+=text+'\n';if(step===3){$('nfc-demo-result').textContent='Demostración terminada. No se escribió ningún dato en una tarjeta o llavero.';$('nfc-demo-start').disabled=false;}},delay));
 };
}
