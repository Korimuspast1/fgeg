const canvas=document.getElementById('game'),ctx=canvas.getContext('2d');
const W=1100,H=680; let keys={},selected=null,lastActivity=Date.now(),muted=false;
const people=[
 {id:'template',name:'TEMPLATE',role:'base character',initial:'T',ava:'ava-a',x:345,y:330,color:'#f08b65',shirt:'#e9e1d5',hair:'#442d28',mood:'bored',line:'Ого, тут тихо…'},
 {id:'max',name:'МАКС',role:'resident / 24',initial:'М',ava:'ava-b',x:600,y:350,color:'#5c8fe8',shirt:'#d9e7ff',hair:'#26252b',mood:'happy',line:'Хороший день, правда?'},
 {id:'lina',name:'ЛИНА',role:'resident / 22',initial:'Л',ava:'ava-c',x:780,y:265,color:'#d69b72',shirt:'#e85e4e',hair:'#4b2925',mood:'sad',line:'Мне немного одиноко…'}
];
const obstacles=[{x:205,y:160,w:170,h:40},{x:765,y:150,w:160,h:43},{x:480,y:445,w:180,h:40},{x:905,y:360,w:54,h:125},{x:160,y:440,w:55,h:110}];
function log(text,who='SYSTEM'){let el=document.createElement('div');el.className='log-item';el.innerHTML=`<b>${who}</b> ${text}<time>now</time>`;document.getElementById('log').prepend(el);while(document.getElementById('log').children.length>4)document.getElementById('log').lastChild.remove()}
function toast(t){let e=document.getElementById('toast');e.textContent=t;e.classList.add('show');setTimeout(()=>e.classList.remove('show'),1800)}
function rebuildRoster(){document.getElementById('roster').innerHTML=people.map(p=>`<div class="person ${selected===p?'active':''}" data-id="${p.id}"><div class="avatar ${p.ava}">${p.initial}</div><div class="person-info"><b>${p.name}</b><small>${p.role}</small></div><span class="status">${p.mood}</span></div>`).join('');document.querySelectorAll('.person').forEach(e=>e.onclick=()=>select(people.find(p=>p.id===e.dataset.id)))}
function select(p){selected=p;document.getElementById('selectedName').textContent=`${p.name}  /  текущий статус: ${p.mood}`;rebuildRoster();toast(`${p.name} выбран`)}
rebuildRoster();log('Симуляция запущена');log('Коллизии персонажей активны');log('Новый обитатель вошёл в лофт');log('Ожидание действий игрока');

document.querySelectorAll('.moods button').forEach(b=>b.onclick=()=>{if(!selected)return toast('Сначала выбери персонажа');let mood=b.dataset.mood;selected.mood=mood;selected.line={happy:'Мне нравится этот момент.',sad:'Не хочется никуда идти…',angry:'Эй, осторожнее!',bored:'Оооой, как скучно…'}[mood];select(selected);log(`настроение → ${mood}`,selected.name);toast(`${selected.name}: настроение изменено`)})
document.getElementById('soundBtn').onclick=()=>{muted=!muted;document.getElementById('soundBtn').textContent=muted?'○':'◒';toast(muted?'Звук выключен':'Звук включён')};
window.addEventListener('keydown',e=>{keys[e.key.toLowerCase()]=true;if(e.code==='Space'&&selected){selected.line='Привет! Рада тебя видеть.';selected.mood='happy';say(selected);}});window.addEventListener('keyup',e=>keys[e.key.toLowerCase()]=false);
function collides(x,y,r=18){if(x<95+r||x>990-r||y<105+r||y>570-r)return true;return obstacles.some(o=>x+r>o.x&&x-r<o.x+o.w&&y+r>o.y&&y-r<o.y+o.h)}
function movePlayer(){let p=people[0],dx=(keys.d?1:0)-(keys.a?1:0),dy=(keys.s?1:0)-(keys.w?1:0);if(dx||dy){let len=Math.hypot(dx,dy),speed=2.5;dx=dx/len*speed;dy=dy/len*speed;if(!collides(p.x+dx,p.y))p.x+=dx;if(!collides(p.x,p.y+dy))p.y+=dy;lastActivity=Date.now()}}
function say(p){p.bubble=performance.now()+3400;log(p.line,p.name);}
function idle(){if(Date.now()-lastActivity>7000){let p=people[Math.floor((Date.now()/9000)%people.length)];if(!p.bubble)say(p);lastActivity=Date.now()}}
canvas.addEventListener('click',e=>{let r=canvas.getBoundingClientRect(),x=(e.clientX-r.left)*W/r.width,y=(e.clientY-r.top)*H/r.height;let p=people.find(a=>Math.hypot(a.x-x,a.y-y)<35);if(p){select(p);say(p)}});
function rounded(x,y,w,h,r,fill,stroke){ctx.beginPath();ctx.roundRect(x,y,w,h,r);ctx.fillStyle=fill;ctx.fill();if(stroke){ctx.strokeStyle=stroke;ctx.stroke()}}
function drawRoom(){let g=ctx.createLinearGradient(0,0,0,H);g.addColorStop(0,'#181b20');g.addColorStop(1,'#0d0f12');ctx.fillStyle=g;ctx.fillRect(0,0,W,H);ctx.fillStyle='#25282d';ctx.beginPath();ctx.moveTo(70,105);ctx.lineTo(1010,105);ctx.lineTo(1038,570);ctx.lineTo(72,570);ctx.closePath();ctx.fill();ctx.strokeStyle='#3d4249';ctx.stroke();
 for(let x=90;x<1020;x+=55){ctx.strokeStyle='#30343a';ctx.beginPath();ctx.moveTo(x,105);ctx.lineTo(x+7,570);ctx.stroke()}for(let y=145;y<570;y+=48){ctx.strokeStyle='#30343a';ctx.beginPath();ctx.moveTo(70,y);ctx.lineTo(1038,y);ctx.stroke()}
 // back wall panels
 ctx.fillStyle='#1c1f24';ctx.fillRect(72,105,938,38);ctx.fillStyle='#121417';ctx.fillRect(111,122,170,4);ctx.fillRect(744,122,186,4);ctx.strokeStyle='#4c5159';ctx.strokeRect(70,105,940,465);
 // windows
 ctx.fillStyle='#10161c';ctx.fillRect(420,128,150,110);ctx.fillStyle='#263744';ctx.fillRect(429,137,132,91);ctx.strokeStyle='#79828a';ctx.strokeRect(420,128,150,110);ctx.strokeStyle='#49535d';ctx.beginPath();ctx.moveTo(495,128);ctx.lineTo(495,238);ctx.moveTo(420,182);ctx.lineTo(570,182);ctx.stroke();
 // rugs
 ctx.fillStyle='#31353a';ctx.beginPath();ctx.ellipse(575,344,198,95,0,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#454a50';ctx.stroke();ctx.fillStyle='#202328';ctx.beginPath();ctx.ellipse(573,342,175,79,0,0,Math.PI*2);ctx.fill();
 // objects
 drawSofa(205,160,170);drawKitchen(765,150);drawTable(480,445);drawPlant(160,440);drawShelf(905,360);
}
function drawSofa(x,y,w){rounded(x,y,w,40,6,'#a74b3e','#c96b58');ctx.fillStyle='#7b3932';ctx.fillRect(x+10,y+39,w-20,12);ctx.fillStyle='#d67b66';ctx.fillRect(x+13,y+7,50,25);ctx.fillRect(x+70,y+7,50,25);ctx.fillStyle='#eb8d75';ctx.fillRect(x+128,y+7,31,25)}
function drawKitchen(x,y){ctx.fillStyle='#d3d0c7';ctx.fillRect(x,y,160,43);ctx.fillStyle='#555b60';ctx.fillRect(x+8,y+8,50,27);ctx.fillStyle='#15181c';ctx.fillRect(x+82,y+8,59,27);ctx.fillStyle='#b8bfbd';ctx.fillRect(x+12,y+12,42,4);ctx.fillRect(x+92,y+18,36,3)}
function drawTable(x,y){ctx.fillStyle='#8c5d42';ctx.fillRect(x,y,180,38);ctx.fillStyle='#5c3d31';ctx.fillRect(x+12,y+35,10,42);ctx.fillRect(x+158,y+35,10,42);ctx.fillStyle='#d59c68';ctx.beginPath();ctx.arc(x+145,y+18,8,0,7);ctx.fill()}
function drawPlant(x,y){ctx.fillStyle='#b96c48';ctx.fillRect(x+16,y+35,26,32);ctx.fillStyle='#70a66d';for(let i=0;i<6;i++){ctx.beginPath();ctx.ellipse(x+27+Math.cos(i)*22,y+15+Math.sin(i)*17,10,22,i,0,7);ctx.fill()}}
function drawShelf(x,y){ctx.fillStyle='#a57a54';ctx.fillRect(x,y,54,125);ctx.fillStyle='#402e27';ctx.fillRect(x+6,y+10,42,4);ctx.fillRect(x+6,y+44,42,4);ctx.fillRect(x+6,y+78,42,4);ctx.fillStyle='#ffce78';ctx.fillRect(x+15,y+20,10,18);ctx.fillStyle='#84a5c6';ctx.fillRect(x+31,y+54,10,22)}
function drawCharacter(p){let bob=Math.sin(performance.now()/420+p.x)*1.5;let x=p.x,y=p.y+bob;ctx.save();ctx.globalAlpha=.3;ctx.fillStyle='#000';ctx.beginPath();ctx.ellipse(x,y+27,26,9,0,0,7);ctx.fill();ctx.globalAlpha=1;
 // legs and shoes
 ctx.fillStyle='#24252a';ctx.fillRect(x-14,y+10,11,24);ctx.fillRect(x+3,y+10,11,24);ctx.fillStyle='#14161a';ctx.fillRect(x-17,y+30,16,6);ctx.fillRect(x+2,y+30,16,6);
 // torso
 ctx.fillStyle=p.shirt;ctx.beginPath();ctx.roundRect(x-21,y-28,42,42,12);ctx.fill();ctx.fillStyle=p.color;ctx.fillRect(x-21,y-9,42,24);ctx.strokeStyle='#111';ctx.globalAlpha=.18;ctx.stroke();ctx.globalAlpha=1;
 // arms
 ctx.strokeStyle='#e2a47f';ctx.lineWidth=8;ctx.lineCap='round';ctx.beginPath();ctx.moveTo(x-19,y-14);ctx.lineTo(x-27,y+8);ctx.moveTo(x+19,y-14);ctx.lineTo(x+27,y+8);ctx.stroke();
 // neck/head hair
 ctx.fillStyle='#e2a47f';ctx.fillRect(x-6,y-37,12,10);ctx.fillStyle='#e2a47f';ctx.beginPath();ctx.arc(x,y-47,17,0,7);ctx.fill();ctx.fillStyle=p.hair;ctx.beginPath();ctx.arc(x,y-51,18,Math.PI,Math.PI*2);ctx.fill();ctx.fillRect(x-17,y-51,8,12);ctx.fillStyle='#2a2020';ctx.fillRect(x-7,y-48,3,3);ctx.fillRect(x+6,y-48,3,3);
 // selected ring
 if(selected===p){ctx.strokeStyle='#c7f36b';ctx.lineWidth=2;ctx.beginPath();ctx.ellipse(x,y+36,32,9,0,0,7);ctx.stroke()}
 // nametag
 rounded(x-34,y-78,68,18,3,'#15171bd9',selected===p?'#c7f36b':'#343940');ctx.fillStyle='#eeece5';ctx.font='10px DM Mono';ctx.textAlign='center';ctx.fillText(p.name,x,y-66);
 if(p.bubble&&p.bubble>performance.now()){let text=p.line;ctx.font='11px Space Grotesk';let tw=Math.min(190,ctx.measureText(text).width+24);let bx=x-tw/2,by=y-115;rounded(bx,by,tw,28,8,'#f1eee7');ctx.fillStyle='#17181b';ctx.fillText(text,x,by+18);ctx.fillStyle='#f1eee7';ctx.beginPath();ctx.moveTo(x-5,by+28);ctx.lineTo(x+5,by+28);ctx.lineTo(x,by+34);ctx.fill()}
 ctx.restore()}
function render(){movePlayer();idle();drawRoom();people.slice().sort((a,b)=>a.y-b.y).forEach(drawCharacter);requestAnimationFrame(render)}
setInterval(()=>{let d=new Date();document.getElementById('clock').textContent=d.toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'})},1000);render();
