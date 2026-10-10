/* One selection shared by HTML controls, real countries, seats and entries.
   Country/point anchors and the complete register work without this script. */
(()=>{'use strict';
const map=document.querySelector('.deskmap');if(!map)return;
const controls=map.querySelector('.deskmap-controls'),buttons=[...map.querySelectorAll('[data-select-desk]')],reset=map.querySelector('.deskmap-reset'),status=map.querySelector('[role=status]');
const entries=[...map.querySelectorAll('.deskmap-plate')];
function select(slug,fromMap=false,updateURL=false){
  const entry=entries.find(e=>e.dataset.desk===slug);if(slug&&!entry)return;
  for(const e of map.querySelectorAll('[data-desk]'))e.classList.toggle('is-selected',e.dataset.desk===slug);
  for(const b of buttons)b.setAttribute('aria-pressed',String(b.dataset.selectDesk===slug));
  reset.setAttribute('aria-pressed',String(!slug));
  for(const e of entries)e.querySelector('.deskmap-selected-label').hidden=e!==entry;
  map.classList.toggle('has-selection',!!entry);
  map.querySelector('.deskmap-context-default').hidden=!!entry;
  for(const c of map.querySelectorAll('[data-context-desk]'))c.hidden=c.dataset.contextDesk!==slug;
  status.textContent=entry?entry.querySelector('h2').textContent.trim()+' · '+entry.querySelector('.desk-state').textContent.trim()+' · Records: '+entry.querySelector('.deskmap-stats dd').textContent.trim(): 'All declared desks. Select a country, point or desk name.';
  if(updateURL)history.replaceState(null,'',location.pathname+location.search+(slug?'#desk-'+slug:''));
  if(fromMap&&matchMedia('(max-width:900px)').matches){
    const b=buttons.find(b=>b.dataset.selectDesk===slug);b.focus({preventScroll:true});
  }
}
controls.hidden=false;
buttons.forEach(b=>b.addEventListener('click',()=>select(b.dataset.selectDesk,false,true)));
reset.addEventListener('click',()=>select('',false,true));
map.querySelectorAll('.dm-country,.dm-anchor').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();select(a.dataset.desk,true,true)}));
controls.addEventListener('keydown',e=>{
  const all=[...buttons,reset],i=all.indexOf(e.target);if(i<0)return;
  let next;if(e.key==='ArrowRight'||e.key==='ArrowDown')next=(i+1)%all.length;
  if(e.key==='ArrowLeft'||e.key==='ArrowUp')next=(i+all.length-1)%all.length;
  if(e.key==='Home')next=0;if(e.key==='End')next=all.length-1;
  if(next!==undefined){e.preventDefault();all[next].focus()}
});
map.addEventListener('keydown',e=>{if(e.key==='Escape'){select('',false,true);reset.focus({preventScroll:true})}});
function fromHash(){if(location.hash.startsWith('#desk-'))select(location.hash.slice(6))}
addEventListener('hashchange',fromHash);fromHash();
})();
