'use strict';
const $ = id => document.getElementById(id);
const pages = document.querySelectorAll('.page');
let audioEnabled = true;
let audioCtx = null;
let lastMotionEpoch = null;
let connectionBusy = false;
let lastSnapshot = null;

function notify(message) { const el = $('notice'); el.textContent = message; el.hidden = !message; }
function clock() { $('clock').textContent = new Date().toLocaleTimeString('en-GB', {hour12:false}); }
setInterval(clock, 1000); clock();

for (const button of document.querySelectorAll('[data-page]')) {
  button.addEventListener('click', () => {
    for (const b of document.querySelectorAll('[data-page]')) b.classList.toggle('active', b === button);
    for (const p of pages) p.classList.toggle('active', p.id === `page-${button.dataset.page}`);
    if (lastSnapshot) renderCharts(lastSnapshot);
  });
}

function unlockAudio() {
  try { if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)(); if (audioCtx.state === 'suspended') audioCtx.resume(); }
  catch(e) { notify('This browser cannot play audio. Check Windows sound settings.'); }
}
function beep() {
  if (!audioEnabled) return;
  try {
    unlockAudio();
    if (!audioCtx) return;
    const osc = audioCtx.createOscillator(), gain = audioCtx.createGain();
    osc.type = 'sine'; osc.frequency.setValueAtTime(760,audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(560,audioCtx.currentTime+.23);
    gain.gain.setValueAtTime(.0001,audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(.09,audioCtx.currentTime+.025);
    gain.gain.exponentialRampToValueAtTime(.0001,audioCtx.currentTime+.3);
    osc.connect(gain).connect(audioCtx.destination); osc.start(); osc.stop(audioCtx.currentTime+.33);
  } catch(e) { notify('Sound playback blocked. Click TEST BEEP to enable audio.'); }
}
$('audio-toggle').addEventListener('click', () => { audioEnabled = !audioEnabled; $('audio-toggle').textContent = audioEnabled ? 'AUDIO ON' : 'AUDIO OFF'; $('audio-toggle').classList.toggle('active', audioEnabled); if (audioEnabled) unlockAudio(); });
$('sound-test').addEventListener('click', () => { unlockAudio(); beep(); });

async function api(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw Error(body.error || `HTTP ${response.status}`);
  return body;
}
async function scanPorts(){
  try {
    const current = $('com-port').value;
    const data = await api('/api/ports');
    $('com-port').replaceChildren();
    let opt = new Option(data.ports.length ? 'SELECT USB COM PORT' : 'NO COM PORTS FOUND', '');
    $('com-port').add(opt);
    for (const item of data.ports) $('com-port').add(new Option(`${item.device} · ${item.description}`, item.device));
    if (data.ports.some(x => x.device === current)) $('com-port').value = current;
    else if (data.ports.length === 1) $('com-port').value = data.ports[0].device;
  } catch(e) { notify(String(e)); }
}
$('scan-btn').addEventListener('click',scanPorts);
$('connect-btn').addEventListener('click', async () => {
  const port = $('com-port').value;
  if (!port) return notify('Choose the ESP32-S3 COM port first.');
  unlockAudio();
  if (connectionBusy) return;
  connectionBusy=true;
  try { await api('/api/connect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({port})}); notify(''); lastMotionEpoch = 0; }
  catch(e){notify(e.message + ' — Close ESP-IDF Monitor if it is using this COM port.');}
  finally{connectionBusy=false;}
});
$('disconnect-btn').addEventListener('click',async()=>{
  try{await api('/api/disconnect',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});notify('');}
  catch(e){notify(e.message);}
});

function setBodyState(moving, presence){
  const stage = $('human-stage');
  stage.classList.remove('body-idle','body-still','body-moving');
  stage.classList.add(moving ? 'body-moving' : presence ? 'body-still' : 'body-idle');
}

function render(snapshot) {
  lastSnapshot=snapshot;
  const connected=snapshot.connected, ready=snapshot.radar_online;
  $('link-label').textContent = ready ? 'LINK ESTABLISHED' : connected ? 'USB OPEN / NO DATA' : 'OFFLINE';
  $('link-label').style.color = ready ? '#a6dbb0' : connected ? '#dab687' : '#697f6c';
  $('link-dot').classList.toggle('on',ready);
  $('connect-btn').disabled = connected || connectionBusy;
  $('disconnect-btn').disabled = !connected;
  $('com-port').disabled = connected;
  $('radar-status').textContent = ready ? 'RADAR REPORTING' : connected ? 'AWAITING SS24 FRAMES' : 'SENSOR OFFLINE';
  $('radar-status').classList.toggle('online',ready);
  $('frames').textContent = snapshot.frames.toLocaleString('en-US');
  $('packet-radar').textContent = snapshot.frames.toLocaleString('en-US');
  $('packet-gap').textContent = (snapshot.radar_seq_gaps || 0).toLocaleString('en-US');
  $('packet-csi').textContent = (snapshot.csi_frames || 0).toLocaleString('en-US');
  $('csi-rssi').textContent = snapshot.csi_online && snapshot.csi_last ? snapshot.csi_last.rssi : '--';
  $('csi-status').textContent = snapshot.csi_online ? `CSI ACTIVE / CH ${snapshot.csi_last.channel}` : 'AWAITING CSI FRAMES';
  const wifi=snapshot.wifi_status || {};
  $('wifi-link').textContent = wifi.connected ? 'ROUTER CONNECTED' : (snapshot.connected ? 'NO ROUTER LINK' : 'USB DISCONNECTED');
  $('wifi-ip').textContent = 'IP: ' + (wifi.ip || '--');
  $('wifi-channel').textContent = 'CH: ' + (wifi.channel || '--');
  $('csi-rate').textContent = snapshot.csi_online ? (snapshot.csi_rate_hz ?? 0).toFixed(1) : '--';
  $('age-value').textContent = snapshot.last_age_sec == null ? '--' : `${snapshot.last_age_sec.toFixed(1)} s`;
  const s=ready?snapshot.last:null, moving=!!s?.moving,presence=!!s?.presence;
  setBodyState(moving,presence);
  const state = $('presence-state');
  state.className = 'presence-status '+(moving?'moving':presence?'present':'idle');
  state.innerHTML = moving ? '<span class="status-emblem">●</span> MOTION DETECTED' : presence ? '<span class="status-emblem">◉</span> PRESENCE DETECTED' : ready ? '<span class="status-emblem">○</span> NO TARGET' : '<span class="status-emblem">○</span> WAITING FOR RADAR';
  $('state-description').textContent = moving ? (s.stationary?'MOVING + STATIONARY':'MOVING') : presence ? 'STATIONARY' : ready ? 'CLEAR' : 'NO VALID TELEMETRY';
  $('distance').textContent = s ? s.display_distance_cm : '--';
  $('moving-energy').textContent = s ? s.moving_energy : '--';
  $('still-energy').textContent = s ? s.stationary_energy : '--';
  $('event-log').replaceChildren(...snapshot.events.map(e=>{
    const div=document.createElement('div');div.className=`event ${e.type}`;
    const t=document.createElement('time');t.textContent=e.at;
    const m=document.createElement('span');m.textContent=e.message;
    div.append(t,m);return div;
  }));
  if (connected && lastMotionEpoch != null && snapshot.motion_epoch > lastMotionEpoch) beep();
  lastMotionEpoch=snapshot.motion_epoch;
  if (snapshot.error && !connected) notify(snapshot.error);
  renderClassifier(snapshot);
  renderCharts(snapshot);
}

function renderCharts(snapshot){
  $('chart-empty').hidden=snapshot.history.length>1;
  drawEnergyChart('energy-chart', snapshot.history, 55, true);
  drawRadar(snapshot.last, snapshot.radar_online);
  drawDSP(snapshot.history);
  drawCSI(snapshot);
  drawCSITemporalDSP(snapshot);
  drawMotionFeature(snapshot);
}

function drawAxes(ctx,w,h,maxY,labelRight){
  ctx.lineWidth=1;ctx.font='10px Consolas, monospace';
  for(let i=0;i<=4;i++){
    const y=8+i*(h-25)/4;
    ctx.strokeStyle='#2b4032';ctx.beginPath();ctx.moveTo(36,y);ctx.lineTo(w-8,y);ctx.stroke();
    ctx.fillStyle='#718d76';ctx.fillText(String(maxY-i*(maxY/4)),3,y+3);
  }
  if(labelRight) { ctx.font='9px Consolas,monospace'; ctx.fillStyle='#63806c'; ctx.fillText(labelRight,w-100,h-4); }
}

function drawEnergyChart(canvasId, history, secondsWindow, annotate){
  const canvas=$(canvasId), rect=canvas.getBoundingClientRect();
  if(rect.width<10 || rect.height<10) return;
  const dpr=Math.min(window.devicePixelRatio||1,2), w=rect.width,h=rect.height;
  canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
  const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.fillStyle='#101d17';ctx.fillRect(0,0,w,h);
  drawAxes(ctx,w,h,100, annotate ? `${secondsWindow} SEC WINDOW` : '');
  if(!history || history.length<2) return;
  const now=history[history.length-1].t;
  const pts=history.filter(p=>now-p.t<=secondsWindow);
  if(pts.length<2) return;
  const x=t=>36+(w-47)*Math.max(0,1-(now-t)/secondsWindow), y=v=>8+(h-25)*(1-Math.min(100,Math.max(0,v))/100);
  for(const [key,color] of [['moving','#9ccea6'],['still','#cda471']]){
    ctx.strokeStyle=color;ctx.lineWidth=1.8;ctx.beginPath();
    pts.forEach((p,i)=>{ if(i===0) ctx.moveTo(x(p.t),y(p[key])); else ctx.lineTo(x(p.t),y(p[key])); });
    ctx.stroke();
  }
}

function drawRadar(sample, online){
  const canvas=$('radar-canvas'), rect=canvas.getBoundingClientRect();
  if(rect.width<10 || rect.height<10) return;
  const dpr=Math.min(window.devicePixelRatio||1,2), w=rect.width,h=rect.height;
  canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
  const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,w,h);
  ctx.fillStyle='#0f1714'; ctx.fillRect(0,0,w,h);
  const cx=w/2, cy=h-18, maxR=Math.min(w*0.45,h-40);
  ctx.strokeStyle='rgba(145,214,159,.15)'; ctx.lineWidth=1;
  for(let i=1;i<=4;i++){
    const r=maxR*(i/4); ctx.beginPath(); ctx.arc(cx,cy,r,Math.PI,2*Math.PI); ctx.stroke();
  }
  for(let a=0;a<=180;a+=30){
    const rad=Math.PI + (a*Math.PI/180);
    ctx.beginPath(); ctx.moveTo(cx,cy); ctx.lineTo(cx+Math.cos(rad)*maxR, cy+Math.sin(rad)*maxR); ctx.strokeStyle='rgba(145,214,159,.08)'; ctx.stroke();
  }
  ctx.strokeStyle='rgba(145,214,159,.9)'; ctx.lineWidth=1.5; ctx.beginPath(); ctx.arc(cx,cy,maxR,Math.PI,2*Math.PI); ctx.stroke();
  ctx.font='10px Consolas, monospace'; ctx.fillStyle='#70907b';
  const rangeMarks=[50,100,150,200];
  rangeMarks.forEach((m,i)=>{ ctx.fillText(`${m}cm`, cx+6, cy-maxR*((i+1)/4)+3); });

  const sweepAngle = Math.PI + ((Date.now()/28)%180)*Math.PI/180;
  const grad = ctx.createLinearGradient(cx,cy,cx+Math.cos(sweepAngle)*maxR, cy+Math.sin(sweepAngle)*maxR);
  grad.addColorStop(0,'rgba(145,214,159,0.03)'); grad.addColorStop(1,'rgba(145,214,159,0.34)');
  ctx.strokeStyle=grad; ctx.lineWidth=2.2; ctx.beginPath(); ctx.moveTo(cx,cy); ctx.lineTo(cx+Math.cos(sweepAngle)*maxR, cy+Math.sin(sweepAngle)*maxR); ctx.stroke();

  if(!online || !sample || !sample.presence) {
    ctx.fillStyle='#6b8376'; ctx.fillText('NO TARGET', 16, 22); return;
  }
  const dist = Math.max(0, Number(sample.display_distance_cm || sample.detection_distance_cm || 0));
  const normalized = Math.max(0.08, Math.min(1, dist / 200));
  const r = normalized * maxR;
  const x = cx; const y = cy - r;
  const moving = !!sample.moving;
  const color = moving ? '#e94d4c' : '#93f0ad';
  ctx.strokeStyle=color; ctx.fillStyle=color;
  ctx.beginPath(); ctx.arc(x,y,7,0,Math.PI*2); ctx.fill();
  ctx.beginPath(); ctx.arc(x,y,16 + 2*Math.sin(Date.now()/190),0,Math.PI*2); ctx.globalAlpha=.5; ctx.stroke(); ctx.globalAlpha=1;
  ctx.font='11px Consolas, monospace'; ctx.fillStyle='#e9f5ea';
  const text = `${dist} cm`;
  const tw = ctx.measureText(text).width;
  ctx.fillText(text, x - tw/2, y - 12);
  ctx.fillStyle='#70907b';
  ctx.fillText(moving ? 'MOVING TARGET' : 'STATIONARY TARGET', 16, 22);
}

function mean(arr){ return arr.reduce((a,b)=>a+b,0) / arr.length; }
function std(arr,m){ return Math.sqrt(arr.reduce((a,b)=>a+(b-m)*(b-m),0) / arr.length); }

function drawDSP(history){
  $('dsp-time-empty').hidden = history.length > 6;
  $('dsp-fft-empty').hidden = history.length > 12;
  $('dsp-filter-empty').hidden = history.length > 6;
  drawFilteredChart(history);
  drawEnergyChart('dsp-time-chart', history, 80, false);
  const samples = history.slice(-64);
  if(samples.length < 8){
    ['stat-mean','stat-std','stat-peak','stat-rate'].forEach(id => $(id).textContent='--');
    clearCanvas('dsp-fft-chart');
    return;
  }
  const y = samples.map(p=>Number(p.moving||0));
  const m = mean(y), s = std(y,m), peak = Math.max(...y);
  const dt = [];
  for(let i=1;i<samples.length;i++) dt.push(samples[i].t - samples[i-1].t);
  const validDt = dt.filter(v=>v>0.0001);
  const sampleRate = validDt.length ? 1 / mean(validDt) : 0;
  $('stat-mean').textContent = m.toFixed(1);
  $('stat-std').textContent = s.toFixed(1);
  $('stat-peak').textContent = peak.toFixed(1);
  $('stat-rate').textContent = sampleRate ? sampleRate.toFixed(2) : '--';
  const resampled = resampleUniform(samples, Math.min(64,Math.max(16,samples.length)));
  if(resampled) drawFFT('dsp-fft-chart', resampled.y, resampled.sampleRate);
  else clearCanvas('dsp-fft-chart');
}

function clearCanvas(id){
  const canvas=$(id), rect=canvas.getBoundingClientRect();
  if(rect.width<10||rect.height<10) return;
  const dpr=Math.min(window.devicePixelRatio||1,2), w=rect.width,h=rect.height;
  canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
  const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.fillStyle='#101d17';ctx.fillRect(0,0,w,h);
}

function drawFFT(canvasId, values, sampleRate){
  const canvas=$(canvasId), rect=canvas.getBoundingClientRect();
  if(rect.width<10 || rect.height<10) return;
  const dpr=Math.min(window.devicePixelRatio||1,2), w=rect.width,h=rect.height;
  canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
  const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.fillStyle='#101d17';ctx.fillRect(0,0,w,h);

  const N = Math.min(64, values.length);
  const x = values.slice(-N);
  const avg = mean(x);
  // Detrend and apply a Hann window to reduce leakage.
  for(let i=0;i<N;i++) x[i] = (x[i]-avg) * .5 * (1-Math.cos(2*Math.PI*i/(N-1)));
  const mags=[];
  for(let k=0;k<Math.floor(N/2);k++){
    let re=0, im=0;
    for(let n=0;n<N;n++){
      const ang = -2*Math.PI*k*n/N;
      re += x[n]*Math.cos(ang);
      im += x[n]*Math.sin(ang);
    }
    mags.push(Math.sqrt(re*re+im*im)/N);
  }
  const maxMag = Math.max(1, ...mags);
  ctx.lineWidth=1;ctx.font='10px Consolas, monospace';
  for(let i=0;i<=4;i++){
    const yLine=8+i*(h-25)/4;
    ctx.strokeStyle='#2b4032';ctx.beginPath();ctx.moveTo(36,yLine);ctx.lineTo(w-8,yLine);ctx.stroke();
    ctx.fillStyle='#718d76';ctx.fillText((maxMag*(1-i/4)).toFixed(1),3,yLine+3);
  }
  const nyquist = sampleRate/2;
  ctx.fillStyle='#63806c'; ctx.font='9px Consolas,monospace'; ctx.fillText(`0 .. ${nyquist.toFixed(2)} Hz`, w-92, h-4);
  if(mags.length < 2) return;
  const barW = (w - 50) / mags.length;
  mags.forEach((mag, k)=>{
    const bh = (h-24) * (mag / maxMag);
    const bx = 38 + k*barW;
    const by = h - 12 - bh;
    ctx.fillStyle = '#8fcf9d';
    ctx.fillRect(bx, by, Math.max(1, barW-2), bh);
  });
}

async function poll(){
  try { const data=await api('/api/status'); render(data); }
  catch(e){$('radar-status').textContent='WINDOWS BACKEND DISCONNECTED';}
  setTimeout(poll,350);
}

window.addEventListener('resize',()=>{ if(lastSnapshot) renderCharts(lastSnapshot); });
scanPorts();poll();

// ─── Windows Wi-Fi survey: real BSSID data, NOT an RF spectrum ───
let wifiSurvey = null;
$('wifi-scan').addEventListener('click', async () => {
  $('wifi-scan').disabled = true;
  $('wifi-caption').textContent = 'SCANNING WINDOWS WLAN INTERFACE ...';
  try {
    wifiSurvey = await api('/api/wifi/scan');
    const rows = $('wireless-rows'); rows.replaceChildren();
    const networks = wifiSurvey.networks || [];
    if (!networks.length) {
      const tr=document.createElement('tr'),td=document.createElement('td');
      td.colSpan=5;td.textContent=wifiSurvey.reason || 'No Wi-Fi access points found';tr.append(td);rows.append(tr);
    }
    for(const item of networks){
      const tr=document.createElement('tr');
      for (const field of ['ssid','bssid','channel','signal_percent','radio_type']) {
        const td=document.createElement('td');
        td.textContent=field==='signal_percent' ? `${item[field] ?? '--'}%` : String(item[field] ?? '--');
        tr.append(td);
      }
      rows.append(tr);
    }
    $('wifi-caption').textContent=networks.length ? `${networks.length} BSSID(s) / WIFI CHANNEL SURVEY / NOT AN RF SPECTRUM` : (wifiSurvey.reason || 'NO WIFI SCAN RESULTS');
    drawChannelSurvey();
  } catch(e) { $('wifi-caption').textContent=e.message; }
  finally { $('wifi-scan').disabled=false; }
});
function drawChannelSurvey(){
  const canvas=$('channel-chart'),r=canvas.getBoundingClientRect();
  if(r.width<10||r.height<10)return;
  const dpr=Math.min(devicePixelRatio||1,2),w=r.width,h=r.height;
  canvas.width=Math.floor(w*dpr);canvas.height=Math.floor(h*dpr);
  const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.fillStyle='#0f1714';ctx.fillRect(0,0,w,h);
  const metrics=Array.from({length:13},()=>({count:0,peak:0}));
  for(const net of (wifiSurvey?.networks||[])) if(net.channel>=1&&net.channel<=13){
    const bin=metrics[net.channel-1];bin.count+=1;bin.peak=Math.max(bin.peak,net.signal_percent||0);
  }
  const bottom=h-35,top=18,left=33,usable=w-50;
  ctx.strokeStyle='#2b4335';ctx.font='10px Consolas,monospace';
  for(let n=0;n<=4;n++) {const y=bottom-(bottom-top)*n/4;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(w-10,y);ctx.stroke();ctx.fillStyle='#75947e';ctx.fillText(`${n*25}%`,3,y+3);}
  metrics.forEach((m,i)=>{
    const slot=usable/13,x=left+i*slot+slot*.14,height=(m.peak/100)*(bottom-top);
    ctx.fillStyle=m.count?'#8dcfa2':'#233d2d';ctx.fillRect(x,bottom-height,slot*.72,Math.max(1,height));
    if(m.count) {ctx.fillStyle='#e5d4a0';ctx.fillText(String(m.count),x+slot*.18,Math.max(12,bottom-height-5));}
    ctx.fillStyle='#92aa97';ctx.fillText(String(i+1),x+slot*.16,h-18);
  });
  ctx.fillStyle='#698b73';ctx.fillText('2.4 GHz CHANNEL',w-134,h-5);
}

// True CSI views are gated on event=csi frames from firmware.
function drawCSI(snapshot){
  const active=!!(snapshot.csi_online && snapshot.csi_last);
  const amps=active ? snapshot.csi_last.subcarrier_amplitude : [];
  $('csi-empty').hidden=amps.length>0;
  $('csi-history-empty').hidden=(snapshot.csi_history||[]).length>1;
  const c=$('csi-chart'),r=c.getBoundingClientRect();
  if(r.width>=10&&r.height>=10){
    const dpr=Math.min(devicePixelRatio||1,2),w=r.width,h=r.height;
    c.width=Math.floor(w*dpr);c.height=Math.floor(h*dpr);
    const ctx=c.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.fillStyle='#101d17';ctx.fillRect(0,0,w,h);
    ctx.strokeStyle='#30473a';ctx.lineWidth=1;
    for(let j=1;j<5;j++){const y=j*h/5;ctx.beginPath();ctx.moveTo(30,y);ctx.lineTo(w-10,y);ctx.stroke();}
    if(amps.length){
      const max=Math.max(1,...amps),dx=(w-46)/amps.length;
      ctx.strokeStyle='#8bcfa0';ctx.lineWidth=1.3;ctx.beginPath();
      amps.forEach((v,i)=>{const x=35+i*dx,y=h-20-(h-40)*v/max;if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);});ctx.stroke();
      ctx.fillStyle='#789480';ctx.font='10px Consolas,monospace';ctx.fillText('CSI AMPLITUDE / SUBCARRIER INDEX',35,h-5);
    }
  }
  const history=snapshot.csi_history||[],canvas=$('csi-history-chart'),r2=canvas.getBoundingClientRect();
  if(r2.width<10||r2.height<10)return;
  const dpr=Math.min(devicePixelRatio||1,2),w=r2.width,h=r2.height;
  canvas.width=Math.floor(w*dpr);canvas.height=Math.floor(h*dpr);
  const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.fillStyle='#101d17';ctx.fillRect(0,0,w,h);
  if(history.length<2)return;
  const now=history[history.length-1].t, recent=history.filter(p=>now-p.t<=60),max=Math.max(1,...recent.map(p=>p.mean_amplitude));
  ctx.strokeStyle='#88c5a2';ctx.lineWidth=1.5;ctx.beginPath();
  recent.forEach((p,i)=>{const x=35+(w-48)*(1-(now-p.t)/60),y=12+(h-30)*(1-p.mean_amplitude/max);if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);});ctx.stroke();
  ctx.fillStyle='#789480';ctx.font='10px Consolas,monospace';ctx.fillText('60 SEC WINDOW / CSI AMPLITUDE',35,h-5);
}

// Local temporal analysis of *real* CSI mean amplitudes from router packets.
// The time axis is actual received monotonic timestamps, uniformly interpolated for FFT.
function drawCSITemporalDSP(snapshot){
  const history=snapshot.csi_history || [];
  const active=!!snapshot.csi_online && history.length>1;
  $('dsp-csi-status').textContent=active ? 'REAL CSI RECEIVING' : 'NO LIVE CSI SIGNAL';
  $('dsp-csi-empty').hidden = active;
  const pts=history.map(p=>({t:p.t, moving:p.mean_amplitude}));
  const canvas=$('dsp-csi-time');
  const r=canvas.getBoundingClientRect();
  if(r.width>=10 && r.height>=10){
    const dpr=Math.min(devicePixelRatio||1,2),w=r.width,h=r.height;
    canvas.width=Math.floor(w*dpr);canvas.height=Math.floor(h*dpr);
    const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.fillStyle='#101d17';ctx.fillRect(0,0,w,h);
    if(pts.length>1){
      const now=pts[pts.length-1].t,recent=pts.filter(p=>now-p.t<=50);
      const minVal=Math.min(...recent.map(x=>x.moving));
      const maxVal=Math.max(...recent.map(x=>x.moving));
      const span=Math.max(3,maxVal-minVal);
      ctx.strokeStyle='#2b4032';ctx.lineWidth=1;
      for(let j=0;j<=4;j++){
        const y=10+(h-30)*j/4;ctx.beginPath();ctx.moveTo(40,y);ctx.lineTo(w-10,y);ctx.stroke();
        ctx.fillStyle='#718d76';ctx.font='9px Consolas, monospace';
        ctx.fillText((minVal+span*(1-j/4)).toFixed(1),3,y+3);
      }
      ctx.strokeStyle='#8edab0';ctx.lineWidth=1.6;ctx.beginPath();
      recent.forEach((p,i)=>{
        const x=40+(w-50)*(1-(now-p.t)/50);
        const y=10+(h-30)*(1-(p.moving-minVal)/span);
        if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
      });ctx.stroke();
      ctx.fillStyle='#789480';ctx.font='9px Consolas, monospace';ctx.fillText('MEAN CSI IQ MAGNITUDE · 50 SEC',40,h-5);
    }
  }
  const fftSamples=pts.slice(-64);
  const interpolation=fftSamples.length>=16 ? resampleUniform(fftSamples,64) : null;
  if(interpolation && active) drawFFT('dsp-csi-fft',interpolation.y,interpolation.sampleRate);
  else clearCanvas('dsp-csi-fft');
}

// Cryptography experiment: genuine AES-256-GCM, local Python endpoint.
function setCryptoResult(text, bad=false){ const el=$('crypto-result');el.textContent=text;el.classList.toggle('bad',bad); }
function cryptoPayload(which){
  const password=$('crypto-password').value;
  if(password.length<8){setCryptoResult('ERROR: PASSPHRASE MUST HAVE AT LEAST 8 CHARACTERS',true);return null;}
  if(which==='encrypt')return {plaintext:$('crypto-plaintext').value,password};
  if(!$('crypto-token').value.trim()){setCryptoResult('ERROR: ENCRYPTED TOKEN IS EMPTY',true);return null;}
  return {token:$('crypto-token').value.trim(),password};
}
$('crypto-encrypt').addEventListener('click',async()=>{
  const payload=cryptoPayload('encrypt');if(!payload)return;
  try{
    const data=await api('/api/crypto/encrypt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    $('crypto-token').value=data.token;setCryptoResult('ENCRYPTION SUCCESSFUL · AES-256-GCM / AUTHENTICATED TOKEN GENERATED');
  }catch(e){setCryptoResult(e.message,true);}
});
$('crypto-decrypt').addEventListener('click',async()=>{
  const payload=cryptoPayload('decrypt');if(!payload)return;
  try{
    const data=await api('/api/crypto/decrypt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    $('crypto-plaintext').value=data.plaintext;
    setCryptoResult('AUTHENTICATION VERIFIED · PLAINTEXT RESTORED');
  }catch(e){setCryptoResult(e.message,true);}
});
$('crypto-tamper').addEventListener('click',()=>{
  try{
    const env=JSON.parse(atob($('crypto-token').value.trim()));
    if(!env.ciphertext||env.ciphertext.length<5)throw Error('First encrypt a plaintext');
    const ct=env.ciphertext;
    env.ciphertext=(ct[0]==='A'?'B':'A')+ct.slice(1);
    $('crypto-token').value=btoa(JSON.stringify(env));
    setCryptoResult('CIPHERTEXT MODIFIED · PRESS DECRYPT + VERIFY TO OBSERVE AUTHENTICATION FAILURE',true);
  }catch(e){setCryptoResult('Encrypt a plaintext first, then run TAMPER TEST.',true);}
});

// 5-point moving average, independent of the LD2410B internal filtering.
function drawFilteredChart(history){
  const canvas=$('dsp-filter-chart'),rect=canvas.getBoundingClientRect();
  if(rect.width<10||rect.height<10)return;
  const dpr=Math.min(devicePixelRatio||1,2),w=rect.width,h=rect.height;
  canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
  const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.fillStyle='#101d17';ctx.fillRect(0,0,w,h);drawAxes(ctx,w,h,100,'ENERGY / 0–100');
  if(history.length<2)return;
  const pts=history.slice(-120),last=pts[pts.length-1].t,first=pts[0].t,span=Math.max(1,last-first);
  const x=t=>36+(w-47)*(t-first)/span;
  const y=v=>8+(h-25)*(1-Math.max(0,Math.min(100,v))/100);
  const ma=pts.map((p,i)=>{
    const slice=pts.slice(Math.max(0,i-4),i+1);return slice.reduce((acc,item)=>acc+item.moving,0)/slice.length;
  });
  for(const [name,color,seq] of [['RAW','#c79c72',pts.map(p=>p.moving)],['FILTERED','#9cdfa8',ma]]){
    ctx.strokeStyle=color;ctx.lineWidth=name==='FILTERED'?2:1.1;ctx.beginPath();
    pts.forEach((p,i)=>{if(i===0)ctx.moveTo(x(p.t),y(seq[i]));else ctx.lineTo(x(p.t),y(seq[i]));});ctx.stroke();
  }
  ctx.fillStyle='#c79c72';ctx.font='9px Consolas,monospace';ctx.fillText('RAW',46,16);
  ctx.fillStyle='#9cdfa8';ctx.fillText('FILTERED',92,16);
}
function resampleUniform(samples,N){
  if(samples.length<8)return null;
  const sorted=samples.filter((p,i,a)=>i===0 || p.t>a[i-1].t);
  if(sorted.length<8)return null;
  const t0=sorted[0].t, t1=sorted[sorted.length-1].t,span=t1-t0;
  if(span<=0.1)return null;
  let j=0, result=[];
  for(let k=0;k<N;k++){
    const t=t0+span*k/(N-1);
    while(j<sorted.length-2 && sorted[j+1].t<t)j++;
    const a=sorted[j],b=sorted[j+1],ratio=(t-a.t)/Math.max(.0001,b.t-a.t);
    result.push(a.moving+(b.moving-a.moving)*Math.max(0,Math.min(1,ratio)));
  }
  return {y:result,sampleRate:(N-1)/span};
}

// v1.4 / quiet-noise calibration, live classifier, radar comparison.
function showMetric(x, decimals=2){return typeof x==='number' && Number.isFinite(x) ? x.toFixed(decimals) : '--';}
function renderClassifier(snapshot){
  const c=snapshot.classifier||{}, f=snapshot.fusion||{}, e=snapshot.evaluation||{};
  $('motion-class-status').textContent=c.state||'NO CSI';
  $('motion-class-status').classList.toggle('online',c.online && c.calibrated);
  $('motion-score').textContent=showMetric(c.score,0);
  $('noise-floor').textContent=showMetric(c.noise_floor,4);
  $('motion-threshold').textContent=showMetric(c.threshold,4);
  $('calibration-progress').style.width=`${c.calibration_percent||0}%`;
  $('calibration-note').textContent=c.note||'CSI calibration not started';
  $('fusion-radar').textContent=f.radar_motion===true?'MOVING':f.radar_presence===true?'STATIONARY':f.radar_presence===false?'NO TARGET':'OFFLINE';
  $('fusion-csi').textContent=c.motion===true?'MOTION':c.motion===false?'STABLE':(c.state||'CALIBRATING');
  $('fusion-score').textContent=showMetric(c.score,0);
  $('fusion-result').textContent=f.state||'WAITING FOR SENSORS';
  $('fusion-agreement').textContent=f.agreement||'NOT COMPARABLE';
  $('dsp-motion-label').textContent=c.state||'CSI OFFLINE';
  $('eval-phase').textContent=e.phase ? `${e.phase} / ${Math.ceil(e.remaining_sec||0)}S LEFT` : 'READY';
  $('eval-n').textContent=e.n||0;
  $('eval-accuracy').textContent= e.accuracy_pct==null?'--':`${e.accuracy_pct}%`;
  $('eval-recall').textContent=e.recall_pct==null?'--':`${e.recall_pct}%`;
  $('eval-fp').textContent=e.fp||0;
  $('eval-breakdown').textContent=`EMPTY ${e.samples_per_phase?.EMPTY||0} · STILL ${e.samples_per_phase?.STILL||0} · MOVING ${e.samples_per_phase?.MOVING||0}  |  TP ${e.tp||0} · FP ${e.fp||0} · TN ${e.tn||0} · FN ${e.fn||0}`;
  for(const b of document.querySelectorAll('[data-eval]')) b.disabled=!!e.phase || !c.calibrated || !c.online;
  $('calibrate-csi').disabled=!snapshot.connected;
}
async function command(path, body={}){
  try{ await api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});notify(''); }
  catch(e){notify(e.message);}
}
$('calibrate-csi').addEventListener('click',()=>command('/api/csi/calibrate'));
for(const b of document.querySelectorAll('[data-eval]')){
  b.addEventListener('click',()=>command('/api/evaluation/start',{label:b.dataset.eval}));
}
$('eval-reset').addEventListener('click',()=>{
  if(confirm('Clear recorded validation results?'))command('/api/evaluation/reset');
});
function drawMotionFeature(snapshot){
  const arr=snapshot.classifier?.history||[];
  const canvas=$('dsp-motion-chart'),rect=canvas.getBoundingClientRect();
  $('dsp-motion-empty').hidden=arr.length>2;
  if(rect.width<10||rect.height<10)return;
  const dpr=Math.min(devicePixelRatio||1,2),w=rect.width,h=rect.height;
  canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
  const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.fillStyle='#101d17';ctx.fillRect(0,0,w,h);
  if(arr.length<2)return;
  const pts=arr.slice(-150),t0=pts[0].t,t1=pts[pts.length-1].t, span=Math.max(.1,t1-t0);
  const top=Math.max(.025,...pts.map(p=>p.smoothed||0),...pts.map(p=>p.threshold||0))*1.15;
  const left=50,bottom=h-23,plotW=w-62,plotH=h-40;
  for(let k=0;k<=4;k++){
    const y=bottom-k*plotH/4;ctx.strokeStyle='#2b4032';ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(w-10,y);ctx.stroke();
    ctx.font='9px Consolas,monospace';ctx.fillStyle='#84a08a';ctx.fillText((top*k/4).toFixed(3),4,y+3);
  }
  const xx=t=>left+plotW*(t-t0)/span, yy=v=>bottom-Math.min(top,Math.max(0,v))/top*plotH;
  for(const [key,color,dashed] of [['smoothed','#9cdcb2',false],['threshold','#d1ac68',true]]){
    ctx.strokeStyle=color;ctx.lineWidth=1.8;ctx.setLineDash(dashed?[5,4]:[]);ctx.beginPath();
    let started=false;for(const p of pts){if(p[key]==null)continue;const x=xx(p.t),y=yy(p[key]);if(!started){ctx.moveTo(x,y);started=true;}else ctx.lineTo(x,y);}
    ctx.stroke();ctx.setLineDash([]);
  }
  ctx.font='10px Consolas,monospace';ctx.fillStyle='#80a188';ctx.fillText('RELATIVE CSI CHANGE / TIME (S)',w-235,h-5);
}

// Load measured telemetry into the authenticated-encryption experiment.
$('crypto-load-live').addEventListener('click',async()=>{
  try {
    const snap=await api('/api/status');
    if(!snap.radar_online && !snap.csi_online) return setCryptoResult('NO LIVE RADAR OR CSI FRAME AVAILABLE',true);
    const payload={device:'SECURESENSE-24',source:'LOCAL SENSOR SNAPSHOT',
      radar:snap.radar_online?snap.last:null,
      wifi:snap.wifi_status?.connected?snap.wifi_status:null,
      csi:snap.csi_online?{channel:snap.csi_last.channel,rssi:snap.csi_last.rssi,
        seq:snap.csi_last.seq,subcarrier_amplitude:snap.csi_last.subcarrier_amplitude}:null};
    $('crypto-plaintext').value=JSON.stringify(payload,null,2);
    setCryptoResult('LIVE SENSOR DATA LOADED · PRESS ENCRYPT + AUTHENTICATE');
  } catch(e){setCryptoResult(e.message,true);}
});
