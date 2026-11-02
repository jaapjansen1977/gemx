'use strict';
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="gemx-token"]').content;
const state = {mode:'demo', busy:false, job:null, data:null, playing:false, frame:0, rendering:false};
const colors = {left:'#208fcb', right:'#e28c3e', trunk:'#758b83'};
function status(text, kind='') {$('status').textContent=text; $('status').className='status '+kind;}
function choose(mode) {
  if(state.busy)return;
  state.mode=mode;
  for(const key of ['demo','video']){
    $(key+'-tab').classList.toggle('active',key===mode);
    $(key+'-tab').setAttribute('aria-selected',String(key===mode));
    $(key+'-panel').hidden=key!==mode;
  }
  $('analyze').disabled=mode==='video'&&!document.querySelector('.engine.ready');
  status(mode==='video'&&$('analyze').disabled?'Eigen videoanalyse is nog niet ingesteld. Kies de proefclip om direct te testen.':'Klaar om te beginnen.');
}
$('demo-tab').onclick=()=>choose('demo'); $('video-tab').onclick=()=>choose('video');
async function api(url,options={}){
  const response=await fetch(url,{...options,headers:{'X-GEMX-Token':token,...options.headers}});
  const body=await response.json().catch(()=>({error:'De server kon het verzoek niet verwerken.'}));
  if(!response.ok)throw new Error(body.error||`Verzoek mislukt (${response.status}).`);
  return body;
}
function busy(value){state.busy=value;$('analyze').disabled=value;$('cancel').hidden=!value;$('demo-tab').disabled=value;$('video-tab').disabled=value;}
$('analyze').onclick=async()=>{
  try{
    const neutral=Number($('neutral').value);
    if(!Number.isFinite(neutral)||neutral<=0)throw new Error('Vul een geldige neutrale beginperiode in.');
    let options;
    if(state.mode==='demo')options={method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({neutral_seconds:neutral})};
    else{
      const file=$('video-file').files[0];if(!file)throw new Error('Kies eerst een video.');
      const body=new FormData();body.append('video',file);body.append('neutral_seconds',neutral);body.append('duration',$('duration').value);body.append('start',$('start').value);
      options={method:'POST',body};
    }
    busy(true);$('download-log').hidden=true;stop();status('Analyse wordt gestart…','running');$('log').textContent='';
    const job=await api('/api/jobs/'+state.mode,options);state.job=job.id;
    await poll(job.id);
  }catch(error){busy(false);status(error.message,'error');}
};
$('cancel').onclick=async()=>{
  try{await api(`/api/jobs/${state.job}/cancel`,{method:'POST'});status('Analyse wordt gestopt…','running');}
  catch(error){status(error.message,'error');}
};
async function poll(id){
  const job=await api('/api/jobs/'+id);
  status(job.message,job.status==='failed'?'error':job.status==='completed'?'':'running');$('log').textContent=job.log.join('\n');
  if(job.status==='completed'){
    state.data=await api(`/api/jobs/${id}/data`);await showResults(id);busy(false);return;
  }
  if(job.status==='failed'||job.status==='cancelled'){busy(false);if(job.status==='failed'&&state.mode==='video'){$('download-log').href=`/api/jobs/${id}/files/log`;$('download-log').hidden=false;}return;}
  await new Promise(resolve=>setTimeout(resolve,650));return poll(id);
}
function points(frame){return state.data.positions[frame];}
function traces(frame){
  const data=state.data, p=points(frame), groups={left:[],right:[],trunk:[]};
  data.parents.forEach((parent,i)=>{
    if(parent<0)return;
    const group=data.names[i].startsWith('Left')?'left':data.names[i].startsWith('Right')?'right':'trunk';
    groups[group].push(p[parent],p[i],[null,null,null]);
  });
  return Object.entries(groups).map(([group,values])=>({type:'scatter3d',mode:'lines',name:group,
    x:values.map(v=>v[0]),y:values.map(v=>v[1]),z:values.map(v=>v[2]),line:{color:colors[group],width:5},hoverinfo:'skip',showlegend:false}))
    .concat([{type:'scatter3d',mode:'markers',x:p.map(v=>v[0]),y:p.map(v=>v[1]),z:p.map(v=>v[2]),
      marker:{size:2.8,color:data.names.map(n=>n.startsWith('Left')?colors.left:n.startsWith('Right')?colors.right:colors.trunk)},
      text:data.names,hovertemplate:'%{text}<extra></extra>',showlegend:false}]);
}
const camera={eye:{x:.85,y:1.1,z:.4},up:{x:0,y:0,z:1}};
async function showResults(id){
  $('empty').hidden=true;$('skeleton').hidden=false;$('results').hidden=false;
  const data=state.data, all=data.positions.flat(), lower=[0,1,2].map(k=>Math.min(...all.map(p=>p[k]))-.08), upper=[0,1,2].map(k=>Math.max(...all.map(p=>p[k]))+.08);
  const spans=upper.map((x,i)=>x-lower[i]),scale=Math.max(...spans);
  await Plotly.newPlot('skeleton',traces(0),{margin:{l:0,r:0,t:0,b:0},paper_bgcolor:'#fff',uirevision:'motion',
    scene:{camera,aspectmode:'manual',aspectratio:{x:spans[0]/scale,y:spans[1]/scale,z:spans[2]/scale},
      xaxis:{title:{text:'X (m)',font:{size:10}},range:[lower[0],upper[0]],backgroundcolor:'#f4f7f3',tickfont:{size:9}},
      yaxis:{title:{text:'Y (m)',font:{size:10}},range:[lower[1],upper[1]],backgroundcolor:'#f4f7f3',tickfont:{size:9}},
      zaxis:{title:{text:'Z omhoog (m)',font:{size:10}},range:[lower[2],upper[2]],backgroundcolor:'#f4f7f3',tickfont:{size:9}}}},
    {responsive:true,displaylogo:false,displayModeBar:false});
  $('frame').max=data.times.length-1;$('frame').value=0;$('frame').disabled=false;$('play').disabled=false;$('reset-camera').disabled=false;
  state.frame=0;$('time').textContent=data.times[0].toFixed(2).replace('.',',')+' s';
  $('validation').textContent='MuJoCo: '+data.validation.frames+' frames gecontroleerd';
  const summaries=[['Frames',String(data.times.length)],['MuJoCo-gewrichten',String(data.validation.joints)],['Nulreferentie',String(data.report.reference_frames)+' frames'],['Clipduur',(data.times.at(-1)-data.times[0]+(data.times[1]-data.times[0])).toFixed(2).replace('.',',')+' s']];
  $('metrics').replaceChildren(...summaries.map(([label,value])=>{const card=document.createElement('div');card.className='metric';const strong=document.createElement('strong');strong.textContent=value;const span=document.createElement('span');span.textContent=label;card.append(strong,span);return card;}));
  const chartTraces=[];
  for(const [index,measure] of ['elevation','axial','twist'].entries())for(const side of ['left','right'])chartTraces.push({x:data.times,y:data.angles[side][measure],
    type:'scatter',mode:'lines',connectgaps:false,name:side==='left'?'Links':'Rechts',legendgroup:side,showlegend:index===0,
    line:{color:colors[side],width:2},xaxis:index?'x'+(index+1):'x',yaxis:index?'y'+(index+1):'y',hovertemplate:'%{x:.2f} s · %{y:.1f}°<extra>%{fullData.name}</extra>'});
  const layout={margin:{l:55,r:20,t:35,b:40},paper_bgcolor:'#fff',plot_bgcolor:'#fff',font:{family:'system-ui',size:11,color:'#63766f'},legend:{orientation:'h',x:1,xanchor:'right',y:1.08},
    xaxis:{domain:[0,1],anchor:'y',showticklabels:false},yaxis:{domain:[.73,1],title:'Graden',gridcolor:'#e8eee9'},
    xaxis2:{domain:[0,1],anchor:'y2',matches:'x',showticklabels:false},yaxis2:{domain:[.37,.64],title:'Graden',gridcolor:'#e8eee9'},
    xaxis3:{domain:[0,1],anchor:'y3',matches:'x',title:'Tijd (s)'},yaxis3:{domain:[0,.27],title:'Graden',gridcolor:'#e8eee9'},
    annotations:[['Armheffing · aangenomen nulreferentie',1.06],['YXY-axiale rotatie · onderbrekingen bij instabiliteit',.70],['Aanvullende swing-twist · andere definitie',.33]].map(([text,y])=>({text,x:0,y,xref:'paper',yref:'paper',showarrow:false,xanchor:'left',font:{size:12,color:'#183731'}}))};
  await Plotly.newPlot('charts',chartTraces,layout,{responsive:true,displaylogo:false,displayModeBar:false});
  for(const type of ['csv','plot','report','zip'])$('download-'+type).href=`/api/jobs/${id}/files/${type}`;
  window.gemxResultReady=true;
}
async function renderFrame(frame){
  state.frame=frame;$('frame').value=frame;$('time').textContent=state.data.times[frame].toFixed(2).replace('.',',')+' s';
  if(state.rendering)return;
  state.rendering=true;
  try{const values=traces(frame);await Plotly.restyle('skeleton',{x:values.map(t=>t.x),y:values.map(t=>t.y),z:values.map(t=>t.z)});}
  finally{state.rendering=false;}
}
function stop(){state.playing=false;$('play').textContent='▶︎';$('play').setAttribute('aria-label','Afspelen');}
$('frame').oninput=()=>{stop();renderFrame(Number($('frame').value));};
$('play').onclick=()=>{
  if(state.playing){stop();return;} if(!state.data)return;
  if(state.frame>=state.data.times.length-1)state.frame=0;
  state.playing=true;$('play').textContent='Ⅱ';$('play').setAttribute('aria-label','Pauzeren');
  const start=performance.now(),offset=state.data.times[state.frame];
  function tick(now){
    if(!state.playing)return;
    const t=offset+(now-start)/1000, times=state.data.times;
    let index=times.findIndex(value=>value>t);index=index<0?times.length-1:Math.max(0,index-1);
    if(index!==state.frame)renderFrame(index);
    if(t>=times.at(-1)){stop();return;}requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
};
$('reset-camera').onclick=()=>Plotly.relayout('skeleton',{'scene.camera':camera});
