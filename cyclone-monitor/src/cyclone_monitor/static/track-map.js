// track-map.js
// User request: standalone interactive tracks, source popups and official overlay controls.
"use strict";
const data = JSON.parse(document.getElementById("track-data").textContent);
const basemap = JSON.parse(document.getElementById("basemap-data").textContent);
const longitudes = data.features.filter(f=>f.geometry?.type==="Point").map(f=>f.geometry.coordinates[0]);
// Use the midpoint of the smallest longitude arc, so date-line tracks stay together.
function centerLongitude(values) {
  if(!values.length)return 0;
  const sorted=values.map(x=>(x+360)%360).sort((a,b)=>a-b);
  let gap=-1,start=sorted[0];
  for(let i=0;i<sorted.length;i++){
    const next=sorted[(i+1)%sorted.length]+(i+1===sorted.length?360:0);
    if(next-sorted[i]>gap){gap=next-sorted[i];start=next%360;}
  }
  return ((start+(360-gap)/2+180)%360)-180;
}
const center=centerLongitude(longitudes);
const longitude=x=>center+((x-center+540)%360)-180;
const map=L.map("map",{minZoom:1,maxZoom:10}).setView([15,center],2);
map.createPane("basemap");map.getPane("basemap").style.zIndex=200;
map.attributionControl.addAttribution("Natural Earth · offline basemap");
for(const offset of [-360,0,360])L.geoJSON(basemap,{pane:"basemap",interactive:false,
  coordsToLatLng:c=>L.latLng(c[1],c[0]+offset),
  style:{color:"#b2c6cc",weight:1,fillColor:"#f2f4ee",fillOpacity:1}}).addTo(map);
const groups={observed:L.layerGroup().addTo(map),forecast:L.layerGroup().addTo(map),cone:L.layerGroup().addTo(map),wind:L.layerGroup().addTo(map)};
const colors={observed:"#087f86",forecast:"#376b91",cone:"#669ab5",wind:"#bd902a"};
const overlays=data.features.filter(f=>["wind","cone"].includes(f.properties?.kind));
document.getElementById("overlay-metadata").textContent=overlays.length ? JSON.stringify(overlays.map(f=>f.properties),null,2) : "No cone or wind features supplied.";
const times=[...new Set(overlays.filter(f=>f.properties.kind==="wind").map(f=>f.properties.valid_time).filter(Boolean))].sort();
for(const time of times){const option=document.createElement("option");option.value=time;option.textContent=time;document.getElementById("wind-time").append(option);}
function draw(){
  Object.values(groups).forEach(g=>g.clearLayers());
  const time=document.getElementById("wind-time").value;
  for(const f of data.features){
    if(!f.geometry)continue;
    const kind=f.properties?.kind || "observed";
    const category=kind.startsWith("forecast")?"forecast":["cone","wind"].includes(kind)?kind:"observed";
    if(category==="wind"&&time&&f.properties.valid_time!==time)continue;
    const color=colors[category];
    L.geoJSON(f,{coordsToLatLng:c=>L.latLng(c[1],longitude(c[0])),
      style:{color,weight:category==="cone"||category==="wind"?1.5:3,fillOpacity:.18,dashArray:category==="forecast"?"7 5":null},
      pointToLayer:(feature,ll)=>L.circleMarker(ll,{radius:5,color,fillColor:category==="forecast"?"white":color,fillOpacity:1,weight:2}),
      onEachFeature:(feature,layer)=>{const text=document.createElement("div");text.textContent=JSON.stringify(feature.properties,null,2);layer.bindPopup(text);}
    }).addTo(groups[category]);
  }
}
function fit(){
  const points=data.features.filter(f=>f.geometry?.type==="Point").map(f=>[f.geometry.coordinates[1],longitude(f.geometry.coordinates[0])]);
  if(points.length)map.fitBounds(L.latLngBounds(points).pad(.25),{maxZoom:6});
  else {const bounds=L.featureGroup(Object.values(groups).flatMap(g=>g.getLayers())).getBounds();if(bounds.isValid())map.fitBounds(bounds,{maxZoom:6});}
}
for(const key of Object.keys(groups))document.getElementById(key).addEventListener("change",e=>{if(e.target.checked)groups[key].addTo(map);else map.removeLayer(groups[key]);});
document.getElementById("wind-time").addEventListener("change",draw);
document.getElementById("fit").addEventListener("click",fit);
document.getElementById("world-view").addEventListener("click",()=>map.setView([15,0],2));
draw();fit();
// Purpose: render safely embedded GeoJSON without network requests or live updates.
// Upstream: track_map.py template/data; upstream purpose: preserve archived tracks and provenance.
// Environment: modern browser, bundled Leaflet. Generated: 2026-10-09 America/New_York.
// Change record: new file, lines 1-60; finalized 2026-10-10 America/New_York.
