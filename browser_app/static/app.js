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
  $('analyze').disabled=mode==='video'&&document.body.dataset.videoReady!=='true';
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
    let options;
    if(state.mode==='demo')options={method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})};
    else{
      const file=$('video-file').files[0];if(!file)throw new Error('Kies eerst een video.');
      const body=new FormData();body.append('video',file);body.append('duration',$('duration').value);body.append('start',$('start').value);
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
    if(parent<0||parent===i)return;
    const group=data.names[i].endsWith('_l')?'left':data.names[i].endsWith('_r')?'right':'trunk';
    groups[group].push(p[parent],p[i],[null,null,null]);
  });
  return Object.entries(groups).map(([group,values])=>({type:'scatter3d',mode:'lines',name:group,
    x:values.map(v=>v[0]),y:values.map(v=>v[1]),z:values.map(v=>v[2]),line:{color:colors[group],width:5},hoverinfo:'skip',showlegend:false}))
    .concat([{type:'scatter3d',mode:'markers',x:p.map(v=>v[0]),y:p.map(v=>v[1]),z:p.map(v=>v[2]),
      marker:{size:2.8,color:data.names.map(n=>n.endsWith('_l')?colors.left:n.endsWith('_r')?colors.right:colors.trunk)},
      text:data.names,hovertemplate:'%{text}<extra></extra>',showlegend:false}]);
}
const camera={eye:{x:.85,y:1.1,z:.4},up:{x:0,y:0,z:1}};
async function showResults(id){
  $('empty').hidden=true;$('skeleton').hidden=false;$('results').hidden=false;
  if(state.data.source!=='mujoco_myofullbody_fit')throw new Error('Resultaat komt niet uit de MyoFullBody-modelfit.');
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
  $('validation').textContent='MuJoCo-fit: '+data.validation.frames+' frames';
  const summaries=[['Frames',String(data.times.length)],['Modelgewrichten',String(data.validation.joints)],['Modelcoördinaten',String(data.coordinates.length)],['Clipduur',(data.times.at(-1)-data.times[0]+(data.times[1]-data.times[0])).toFixed(2).replace('.',',')+' s']];
  $('metrics').replaceChildren(...summaries.map(([label,value])=>{const card=document.createElement('div');card.className='metric';const strong=document.createElement('strong');strong.textContent=value;const span=document.createElement('span');span.textContent=label;card.append(strong,span);return card;}));
  const select=$('coordinate');select.replaceChildren();
  const groups=new Map();
  for(const coordinate of data.coordinates){
    if(!groups.has(coordinate.group)){const group=document.createElement('optgroup');group.label=coordinate.group;groups.set(coordinate.group,group);select.append(group);}
    const option=document.createElement('option');option.value=coordinate.name;
    option.textContent=coordinate.name+' — '+roleLabel(coordinate.role);groups.get(coordinate.group).append(option);
  }
  select.value='shoulder_elv_l';select.onchange=drawCharts;await drawCharts();
  $('fit-video').src=`/api/jobs/${id}/files/video`;$('fit-video').load();$('fit-video').hidden=false;
  $('toggle-view').hidden=false;$('skeleton').hidden=true;$('reset-camera').disabled=true;$('toggle-view').textContent='Draaibare modelstructuur';
  for(const type of ['csv','plot','report','zip'])$('download-'+type).href=`/api/jobs/${id}/files/${type}`;
  window.gemxResultReady=true;
}
const roleLabel=role=>({optimized:'geoptimaliseerd',coupled:'modelkoppeling',fixed_reference:'vaste referentie'})[role];
async function drawCharts(){
  const data=state.data, selected=data.coordinates.find(c=>c.name===$('coordinate').value);
  const names=[selected.name], paired=selected.name.replace(/_[lr]$/,x=>x==='_l'?'_r':'_l');
  if(paired!==selected.name&&data.coordinates.some(c=>c.name===paired))names.push(paired);
  const traces=names.map(name=>{const index=data.coordinates.findIndex(c=>c.name===name);return {type:'scatter',mode:'lines',x:data.times,y:data.values.map(row=>row[index]),name,
    line:{color:name.endsWith('_r')?colors.right:colors.left,width:2},hovertemplate:'%{x:.2f} s · %{y:.3f} '+selected.unit+'<extra>%{fullData.name}</extra>'};});
  $('coordinate-info').textContent=`${roleLabel(selected.role)} · qpos[${selected.qpos_address}] · eenheid ${selected.unit} · absolute modelwaarde, geen extra nulcorrectie`;
  await Plotly.react('charts',traces,{margin:{l:65,r:20,t:40,b:45},font:{family:'system-ui',size:12},title:{text:'Modelcoördinaat: '+selected.name},
    xaxis:{title:'Tijd (s)'},yaxis:{title:selected.unit},legend:{orientation:'h'},paper_bgcolor:'#fff',plot_bgcolor:'#fff'},
    {responsive:true,displaylogo:false,displayModeBar:false});
}
async function renderFrame(frame,seek=true){
  state.frame=frame;$('frame').value=frame;$('time').textContent=state.data.times[frame].toFixed(2).replace('.',',')+' s';
  if(seek)$('fit-video').currentTime=state.data.times[frame]-state.data.times[0];
  if(state.rendering)return;
  state.rendering=true;
  try{const values=traces(frame);await Plotly.restyle('skeleton',{x:values.map(t=>t.x),y:values.map(t=>t.y),z:values.map(t=>t.z)});}
  finally{state.rendering=false;}
}
$('toggle-view').onclick=()=>{
  const show=$('skeleton').hidden;$('reset-camera').disabled=!show;$('skeleton').hidden=!show;$('fit-video').hidden=show;
  $('toggle-view').textContent=show?'Wit MuJoCo-model':'Draaibare modelstructuur';
  if(show)Plotly.Plots.resize('skeleton');
};
function stop(){state.playing=false;$('fit-video').pause();$('play').textContent='▶︎';$('play').setAttribute('aria-label','Afspelen');}
$('frame').oninput=()=>{stop();renderFrame(Number($('frame').value));};
$('play').onclick=()=>{
  if(state.playing){stop();return;} if(!state.data)return;
  if(state.frame>=state.data.times.length-1)state.frame=0;
  state.playing=true;$('play').textContent='Ⅱ';$('play').setAttribute('aria-label','Pauzeren');
  $('fit-video').currentTime=state.data.times[state.frame]-state.data.times[0];
  $('fit-video').play().catch(error=>{stop();status('Modelvideo kon niet worden afgespeeld: '+error.message,'error');});
  function tick(now){
    if(!state.playing)return;
    const times=state.data.times,t=times[0]+$('fit-video').currentTime;
    let index=times.findIndex(value=>value>t);index=index<0?times.length-1:Math.max(0,index-1);
    if(index!==state.frame)renderFrame(index,false);
    if(t>=times.at(-1)){stop();return;}requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
};
$('reset-camera').onclick=()=>Plotly.relayout('skeleton',{'scene.camera':camera});
