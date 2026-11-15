(async()=>{
 const svgNS='http://www.w3.org/2000/svg',el=(tag,attrs,parent)=>{const n=document.createElementNS(svgNS,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);parent.append(n);return n;};
 const defs=[['contact',380,48,['First contact']],['nurse',190,150,['Nurse','assessment']],['gp',570,150,['GP','assessment']],['assessment',380,250,['Assessment','& referral']],['specialist',380,350,['Specialist','review']],['imaging',380,450,['Imaging']],['bronch',190,550,['Bronchoscopy']],['biopsy',570,550,['Needle biopsy']],['review',380,650,['Results','& review']],['treatment',190,780,['Treatment','planning']],['followup',650,780,['Discharge','& follow-up']]];
 const nodes=Object.fromEntries(defs.map(n=>[n[0],n]));
 let routes;
 try{const r=await fetch('routes.json');if(!r.ok)throw Error();routes=(await r.json()).routes;}catch{document.querySelector('.viewport').innerHTML='<p class="fallback">The patient routes could not be loaded. Reload to view the graph.</p>';return;}
 const edgePairs=new Set(routes.flatMap(r=>r.slice(1).map((id,i)=>r[i]+'|'+id))),paths={};
 for(const key of edgePairs){const[a,b]=key.split('|'),s=nodes[a],t=nodes[b];let x1=s[1],y1=s[2],x2=t[1],y2=t[2],d;
  if(y2<y1){d=`M${x1-76} ${y1} C65 ${y1} 65 ${y2} ${x2-80} ${y2}`;}
  else if(y1===y2){const sign=x2>x1?1:-1;d=`M${x1+sign*76} ${y1} H${x2-sign*80}`;}
  else{const exit=b==='followup'&&y2-y1>180;y1+=34;y2-=38;const mid=(y1+y2)/2;if(exit)d=`M${x1+55} ${y1} C770 ${y1+30} 770 ${y2-30} ${x2} ${y2}`;else d=`M${x1} ${y1} C${x1} ${mid} ${x2} ${mid} ${x2} ${y2}`;}
  const p=el('path',{d,class:'edge'+(t[2]<s[2]?' return':''),'marker-end':'url(#arrow)'},document.getElementById('edges'));paths[key]={path:p,length:p.getTotalLength()};
 }
 for(const [id,x,y,labels]of defs){const g=el('g',{class:'node'+(['review','specialist'].includes(id)?' review':'')},document.getElementById('nodes'));el('rect',{x:x-76,y:y-34,width:152,height:68,rx:5},g);labels.forEach((s,i)=>{el('text',{x,y:y+(i-(labels.length-1)/2)*21+5},g).textContent=s;});}
 const particles=routes.filter(r=>r.length>2).slice(0,95).map((r,i)=>({route:r,offset:i*.379,seconds:28+(i%7)*3,dot:el('circle',{r:3.4,class:'patient'},document.getElementById('patients'))}));
 let elapsed=0,last=performance.now(),visible=true;const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 function draw(now){const dt=Math.min(.1,(now-last)/1000);last=now;if(visible&&!document.hidden&&!reduced)elapsed+=dt;
 for(const p of particles){const phase=((elapsed+p.offset)%p.seconds)/p.seconds*(p.route.length-1),idx=Math.min(p.route.length-2,Math.floor(phase)),path=paths[p.route[idx]+'|'+p.route[idx+1]];if(!path)continue;const pos=path.path.getPointAtLength(path.length*(phase-idx));p.dot.setAttribute('cx',pos.x);p.dot.setAttribute('cy',pos.y);}
 requestAnimationFrame(draw);}
 window.addEventListener('message',e=>{if(e.origin===location.origin&&e.source===parent&&e.data?.type==='simulation-visibility')visible=!!e.data.visible;});requestAnimationFrame(draw);
})();
