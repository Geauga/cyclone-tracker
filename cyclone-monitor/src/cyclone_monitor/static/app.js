// app.js
// User request: interactive official-cyclone map, automatic checks, replay, and scientific downloads.
"use strict";
const el = (id) => document.getElementById(id);
const esc = (value) => String(value == null ? "Unavailable" : value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt = (value) => value ? value.replace("T"," ").replace("Z","").slice(0,16) : "Unavailable";
const val = (v, unit) => v == null ? "Unavailable" : v + " " + unit;
const session = crypto.randomUUID();
let state = {}, selected = null, advisory = null, compared = null, versions = [], live = true, playing = null, loading = false, requestSerial = 0;
const map = L.map("map", {worldCopyJump:true, minZoom:2, maxZoom:8}).setView([18,0],2);
map.createPane("basemap"); map.getPane("basemap").style.zIndex=200;
map.attributionControl.addAttribution('<a href="https://www.naturalearthdata.com">Natural Earth</a> · offline basemap');
for(let lat=-60;lat<=60;lat+=30)L.polyline([[lat,-360],[lat,360]],{pane:"basemap",color:"#c9dde2",weight:1,interactive:false}).addTo(map);
for(let lon=-360;lon<=360;lon+=30)L.polyline([[-85,lon],[85,lon]],{pane:"basemap",color:"#c9dde2",weight:1,interactive:false}).addTo(map);
fetch("/static/countries.geojson").then(r=>{if(!r.ok)throw new Error("Offline basemap could not load");return r.json()}).then(data=>{
  for(const offset of [-360,0,360])L.geoJSON(data,{pane:"basemap",style:{color:"#bacdcf",weight:1,fillColor:"#f2f4ee",fillOpacity:1},
    coordsToLatLng:c=>L.latLng(c[1],c[0]+offset),onEachFeature:(f,l)=>l.bindTooltip(esc(f.properties.name))}).addTo(map);
}).catch(showError);
const dataLayer = L.layerGroup().addTo(map);

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error("Local API " + response.status + ": " + (await response.text()).slice(0,160));
  return response.json();
}
function showError(error) { el("errors").textContent = String(error.message || error); }
function stopReplay() { if (playing) clearInterval(playing); playing = null; el("play").textContent = "▶ Replay"; }
async function heartbeat() { await api("/api/session?session=" + session, {method:"POST"}); }
function visibleStorms() {
  const query = el("search").value.toLowerCase();
  return (state.storms || []).filter(s => (el("archived").checked || s.in_latest_index !== false) &&
    [s.name,s.storm_id,s.issuer].join(" ").toLowerCase().includes(query));
}
function renderDirectory() {
  const storms = visibleStorms();
  el("count").textContent = storms.length;
  el("storms").replaceChildren();
  if (!storms.length) {
    const p = document.createElement("p"); p.className="empty-note";
    p.textContent = state.busy ? "Retrieving official advisories…" :
      state.errors && state.errors.length ? "Data retrieval is incomplete. See status below." :
      state.index_count === 0 ? "No storms listed in the retrieved WMO index. Coverage limitations still apply." :
      !state.retrieved_at ? "No local advisories yet. Opening this dashboard starts retrieval." : "No matching archived advisories.";
    el("storms").append(p);
  }
  for (const s of storms) {
    const b = document.createElement("button"); b.className = "storm" + (selected === s.key ? " selected" : "");
    b.innerHTML = '<span class="storm-top"><strong>' + esc(s.name) + '</strong><span class="badge">' + esc(s.latest.intensity || "TC") + '</span></span><small>' + esc(s.storm_id) + " · " + esc(s.issuer) + '</small><span class="storm-meta"><span>' + esc(val(s.latest.wind_kt,"kt")) + '</span><span class="' + (s.age_hours > 12 ? "old" : "") + '">' + (s.in_latest_index === false ? "Archived" : s.age_hours > 12 ? "Older than 12 h" : fmt(s.analysis_time).slice(11) + " UTC") + "</span></span>";
    b.onclick = () => selectStorm(s.key, true);
    el("storms").append(b);
  }
}
function popup(point) {
  return "<strong>" + esc(point.kind) + "</strong><br>" + esc(fmt(point.valid_time)) + " UTC<br>" +
    esc(val(point.wind_kt,"kt")) + " · " + esc(val(point.pressure_hpa,"hPa")) +
    "<br>" + esc(point.issuer);
}
function trackCoordinates(points) {
  const result = [];
  for (const point of points) {
    let lon = point.longitude;
    if (result.length) {
      while (lon-result[result.length-1][1]>180) lon-=360;
      while (lon-result[result.length-1][1]<-180) lon+=360;
    }
    result.push([point.latitude,lon]);
  }
  return result;
}
function addTracks(p, comparison) {
  const obs=p.points.filter(v=>v.kind==="observed"), fc=p.points.filter(v=>v.kind==="forecast");
  const color=comparison?"#9569ac":"#087f8c";
  if (!comparison && obs.length>1) L.polyline(trackCoordinates(obs),{color,weight:3}).addTo(dataLayer);
  if (fc.length) L.polyline(trackCoordinates(obs.slice(-1).concat(fc)),{color:comparison?color:"#22668e",weight:3,dashArray:"6 7"}).addTo(dataLayer);
  for (const pnt of (comparison ? fc : p.points)) {
    L.circleMarker([pnt.latitude,pnt.longitude],{radius:pnt.kind==="forecast"?3:4,color,weight:1.5,fillColor:pnt.kind==="forecast"?"white":color,fillOpacity:1}).bindPopup(popup(pnt)).addTo(dataLayer);
  }
  if (!comparison && obs.length) {
    const last=obs[obs.length-1];
    L.circleMarker([last.latitude,last.longitude],{radius:9,color:"#fff",weight:3,fillColor:color,fillOpacity:1}).bindPopup("<strong>"+esc(p.name)+"</strong><br>"+popup(last)).addTo(dataLayer);
  }
}
function drawMap(fit=false) {
  dataLayer.clearLayers();
  if (!advisory) {
    for(const s of visibleStorms()) {
      const q=s.latest;
      L.circleMarker([q.latitude,q.longitude],{radius:8,color:"#fff",weight:2,fillColor:"#087f8c",fillOpacity:1})
        .bindTooltip(esc(s.name)+" · "+esc(val(q.wind_kt,"kt"))).on("click",()=>selectStorm(s.key,true)).addTo(dataLayer);
    }
    return;
  }
  for(const f of advisory.overlays) {
    const kind=f.properties.kind;
    if(kind==="cone"&&!el("cones").checked || kind==="wind"&&!el("winds").checked) continue;
    if(kind==="wind"&&el("wind-time").value&&f.properties.valid_time!==el("wind-time").value) continue;
    const threshold=f.properties.threshold_kt;
    const color=kind==="cone"?"#377fa5":threshold>=64?"#b74d35":threshold>=50?"#cf852d":"#d8ab43";
    L.geoJSON(f,{style:{color,weight:1.2,fillOpacity:kind==="cone"?.13:.18}}).bindPopup(
      "<strong>"+esc(kind==="cone"?"Official uncertainty cone":val(threshold,"kt wind extent"))+"</strong><br>"+
      esc(f.properties.issuer)+"<br>Issued: "+esc(fmt(f.properties.issue_time))+" UTC<br>Valid: "+
      esc(fmt(f.properties.valid_time))+"<br>"+esc(f.properties.meaning)).addTo(dataLayer);
  }
  if(el("tracks").checked) { addTracks(advisory,false); if(compared) addTracks(compared,true); }
  if(fit) {
    const pts=trackCoordinates(advisory.points);
    if(pts.length>1) map.fitBounds(L.latLngBounds(pts).pad(.2),{maxZoom:6});
    else if(pts.length) map.setView(pts[0],5);
  }
}
function renderDetail(fit=false) {
  el("empty").hidden=!!advisory; el("detail").hidden=!advisory;
  if(!advisory) { el("map-label").textContent="Global overview"; drawMap(); return; }
  const p=advisory, last=p.points.filter(q=>q.kind==="observed").slice(-1)[0];
  el("storm-title").textContent=p.name+" · "+p.storm_id;
  el("map-label").textContent=p.name;
  el("issuer").textContent=p.issuer+" · "+(last.intensity||"Classification unavailable");
  el("mode").textContent=live?"LATEST RETRIEVED":"ARCHIVE REPLAY · "+fmt(p.analysis_time)+" UTC";
  el("wind-value").textContent=val(last.wind_kt,"kt");
  el("averaging").textContent=last.wind_averaging_minutes ? last.wind_averaging_minutes+"-minute averaging" : "Averaging period not supplied";
  el("pressure-value").textContent=val(last.pressure_hpa,"hPa");
  el("analysis").textContent=fmt(p.analysis_time);
  el("issued").textContent=fmt(p.issue_time);
  el("issued").title=p.issue_time_note;
  el("overlay-status").textContent="Cone: "+p.overlay_status.cone+" · Wind polygons: "+p.overlay_status.wind;
  el("wind-text").textContent=last.wind_radii_text?"Published wind radii: "+last.wind_radii_text:"Wind-radius text: unavailable in this advisory.";
  el("provenance").textContent="First retrieved "+fmt(p.retrieved_at)+" UTC · Last seen "+fmt(p.last_seen)+" UTC · "+p.source_url;
  for(const type of ["csv","geojson","nc","raw"]) el(type).href="/api/export/"+p.version+"/"+type;
  const times=[...new Set(p.overlays.filter(f=>f.properties.kind==="wind").map(f=>f.properties.valid_time).filter(Boolean))].sort();
  const prior=el("wind-time").value;
  el("wind-time").innerHTML='<option value="">All published times</option>'+times.map(t=>'<option value="'+esc(t)+'">'+esc(fmt(t))+' UTC</option>').join("");
  if(times.includes(prior))el("wind-time").value=prior;
  el("records").innerHTML='<div class="records-row"><span>Type</span><span>Valid time · UTC</span><span>Wind · kt</span><span>Pressure · hPa</span><span>Position</span></div>'+
    p.points.map(q=>'<div class="records-row"><span>'+esc(q.kind)+'</span><span>'+esc(fmt(q.valid_time))+'</span><span>'+esc(q.wind_kt)+'</span><span>'+esc(q.pressure_hpa)+'</span><span>'+q.latitude.toFixed(1)+', '+q.longitude.toFixed(1)+'</span></div>').join("");
  drawMap(fit);
}
async function selectStorm(key,fit=false) {
  stopReplay(); const serial=++requestSerial; selected=key; live=true; compared=null;
  const fetchedVersions=await api("/api/archive/"+encodeURIComponent(key));
  if(serial!==requestSerial || !fetchedVersions.length)return;
  versions=fetchedVersions;
  el("versions").innerHTML=versions.map((v,i)=>'<option value="'+v.version+'">'+(i===0?"Latest · ":"")+esc(fmt(v.analysis_time))+" · "+v.version.slice(0,6)+"</option>").join("");
  el("compare").innerHTML='<option value="">None</option>'+versions.map(v=>'<option value="'+v.version+'">'+esc(fmt(v.analysis_time))+" · "+v.version.slice(0,6)+"</option>").join("");
  el("comparison").textContent="";
  const p=await api("/api/advisory/"+versions[0].version);
  if(serial!==requestSerial)return;
  advisory=p; renderDirectory(); renderDetail(fit);
}
async function loadVersion(id) {
  const serial=++requestSerial;
  const p=await api("/api/advisory/"+id);
  if(serial!==requestSerial)return;
  advisory=p; live=id===(versions[0]||{}).version; compared=null;
  el("compare").value=""; el("comparison").textContent="";
  renderDetail();
}
async function updateState() {
  if(loading)return; loading=true;
  try {
    state=await api("/api/state");
    const prefix=state.busy?"Retrieving official data…":state.retrieved_at?"Last check "+fmt(state.retrieved_at)+" UTC":"Waiting for the first retrieval";
    el("status").textContent=prefix+(state.errors.length?" · Partial / failed retrieval":"")+
      (!state.busy&&state.next_refresh_seconds!=null?" · Next check in "+Math.ceil(state.next_refresh_seconds/60)+" min":"");
    el("refresh").disabled=state.busy;
    el("interval").value=String(state.interval);
    el("coverage").innerHTML=state.coverage.map(t=>"<p>"+esc(t)+"</p>").join("")+
      "<p>Feed timestamp: "+esc(fmt(state.index_time))+" UTC. Records older than 12 hours are highlighted; this is a display threshold.</p>";
    el("errors").innerHTML=state.errors.concat((state.missing_keys||[]).map(k=>"No archived data for indexed storm "+k)).map(e=>"<p>"+esc(e)+"</p>").join("");
    renderDirectory();
    if(selected&&live) {
      const latest=state.storms.find(s=>s.key===selected);
      if(latest&&advisory&&latest.version!==advisory.version) await selectStorm(selected);
    }
    if(!advisory)drawMap();
  }catch(e){showError(e)}finally{loading=false}
}
el("refresh").onclick=async()=>{try{const r=await api("/api/refresh?session="+session,{method:"POST"});if(!r.started)el("status").textContent="A refresh is already running or was requested less than 30 seconds ago.";await updateState()}catch(e){showError(e)}};
el("interval").onchange=async()=>{try{await api("/api/settings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({interval:Number(el("interval").value)})});await updateState()}catch(e){showError(e)}};
el("search").oninput=()=>{renderDirectory();if(!advisory)drawMap()};
el("archived").onchange=()=>{renderDirectory();if(!advisory)drawMap()};
el("global").onclick=()=>{stopReplay();++requestSerial;selected=null;advisory=null;compared=null;map.setView([18,0],2);renderDirectory();renderDetail()};
for(const id of ["tracks","cones","winds","wind-time"])el(id).onchange=()=>drawMap();
el("versions").onchange=()=>{stopReplay();loadVersion(el("versions").value).catch(showError)};
el("play").onclick=()=>{
  if(playing){stopReplay();return}
  if(versions.length<2){el("comparison").textContent="Replay needs at least two distinct locally retrieved advisories.";return}
  const sequence=versions.slice().reverse();let i=0;el("play").textContent="Ⅱ Pause";
  const next=()=>{const v=sequence[i++];if(!v){stopReplay();return}el("versions").value=v.version;loadVersion(v.version).catch(showError)};
  next();playing=setInterval(next,2500);
};
el("compare").onchange=async()=>{
  try {
    const id=el("compare").value, selectedVersion=advisory && advisory.version;
    const fetched=id?await api("/api/advisory/"+id):null;
    if(!advisory || advisory.version!==selectedVersion || el("compare").value!==id)return;
    compared=fetched;
    let text="";
    if(compared&&advisory){
      const a=advisory.points.filter(p=>p.kind==="observed").slice(-1)[0], b=compared.points.filter(p=>p.kind==="observed").slice(-1)[0];
      text="Purple = comparison forecast";
      if(a.wind_kt!=null&&b.wind_kt!=null)text+=" · Selected minus comparison wind: "+(a.wind_kt-b.wind_kt)+" kt";
    }
    el("comparison").textContent=text;drawMap();
  }catch(e){showError(e)}
};
window.addEventListener("pagehide",()=>navigator.sendBeacon("/api/close?session="+session,""));
window.addEventListener("pageshow",()=>heartbeat().catch(showError));
setInterval(()=>heartbeat().catch(showError),15000);
setInterval(updateState,5000);
setInterval(()=>{el("clock").textContent=new Date().toISOString().slice(0,16).replace("T"," ")+" UTC"},1000);
heartbeat().then(updateState).catch(showError);
// Purpose: dashboard interaction; upstream: local server API returns official/archived advisories.
// Environment: modern browser with Leaflet. Generated: 2026-09-28 America/New_York.
// Change record: new UI lines 1-213; line 201: label selected advisory accurately during replay. Finalized 2026-09-29 America/New_York.
