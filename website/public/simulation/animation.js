(async()=>{
 const svgNS='http://www.w3.org/2000/svg',el=(tag,attrs,parent)=>{const n=document.createElementNS(svgNS,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);parent.append(n);return n;};
 const defs=[['contact',100,320,['First contact']],['nurse',290,170,['Nurse','assessment']],['gp',290,470,['GP','assessment']],['assessment',490,320,['Assessment','& referral']],['specialist',690,320,['Specialist','review']],['imaging',890,320,['Imaging']],['bronch',1090,170,['Bronchoscopy']],['biopsy',1090,470,['Needle biopsy']],['review',1290,320,['Results','& review']],['treatment',1490,170,['Treatment','planning']],['followup',1490,470,['Discharge','& follow-up']]];
 const nodes=Object.fromEntries(defs.map(n=>[n[0],n]));
 let routes;
 try{const r=await fetch('routes.json');if(!r.ok)throw Error();routes=(await r.json()).routes;}catch{document.querySelector('.viewport').innerHTML='<p class="fallback">The patient routes could not be loaded. Reload to view the graph.</p>';return;}
 const edgePairs=new Set(routes.flatMap(r=>r.slice(1).map((id,i)=>r[i]+'|'+id))),paths={};
 for(const key of edgePairs){const[a,b]=key.split('|'),s=nodes[a],t=nodes[b];let x1=s[1],y1=s[2],x2=t[1],y2=t[2],d;
  if(x2<x1){d=`M${x1} ${y1+34} C${x1} 610 ${x2} 610 ${x2} ${y2+38}`;}
  else if(x1===x2){const sign=y2>y1?1:-1;d=`M${x1} ${y1+sign*34} V${y2-sign*38}`;}
  else{const isExit=b==='followup'&&x2-x1>420;x1+=76;x2-=80;const mid=(x1+x2)/2;if(isExit)d=`M${x1} ${y1} C${x1+50} 590 ${x2-40} 590 ${x2} ${y2}`;else d=`M${x1} ${y1} C${mid} ${y1} ${mid} ${y2} ${x2} ${y2}`;}
  const p=el('path',{d,class:'edge'+(t[1]<s[1]?' return':''),'marker-end':'url(#arrow)'},document.getElementById('edges'));paths[key]={path:p,length:p.getTotalLength()};
 }
 for(const [id,x,y,labels]of defs){const g=el('g',{class:'node'+(['review','specialist'].includes(id)?' review':'')},document.getElementById('nodes'));el('rect',{x:x-76,y:y-34,width:152,height:68,rx:5},g);labels.forEach((s,i)=>{el('text',{x,y:y+(i-(labels.length-1)/2)*21+5},g).textContent=s;});}
 const stageLabels=[['FIRST CONTACT',100],['PRIMARY CARE',390],['SPECIALIST CARE',790],['DIAGNOSIS & REVIEW',1190],['NEXT STEPS',1490]];
 for(const [text,x]of stageLabels)el('text',{x,y:58,class:'stage','text-anchor':'middle'},document.getElementById('scene')).textContent=text;
 const particles=routes.filter(r=>r.length>2).slice(0,95).map((r,i)=>({route:r,offset:i*.379,seconds:28+(i%7)*3,dot:el('circle',{r:3.4,class:'patient'},document.getElementById('patients'))}));
 let elapsed=0,last=performance.now(),visible=true;const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 function draw(now){const dt=Math.min(.1,(now-last)/1000);last=now;if(visible&&!document.hidden&&!reduced)elapsed+=dt;
 for(const p of particles){const phase=((elapsed+p.offset)%p.seconds)/p.seconds*(p.route.length-1),idx=Math.min(p.route.length-2,Math.floor(phase)),path=paths[p.route[idx]+'|'+p.route[idx+1]];if(!path)continue;const pos=path.path.getPointAtLength(path.length*(phase-idx));p.dot.setAttribute('cx',pos.x);p.dot.setAttribute('cy',pos.y);}
 requestAnimationFrame(draw);}
 window.addEventListener('message',e=>{if(e.origin===location.origin&&e.source===parent&&e.data?.type==='simulation-visibility')visible=!!e.data.visible;});requestAnimationFrame(draw);
})();
