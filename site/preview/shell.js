/* Optional disclosure defaults. Anchors and content remain native without JS. */
(()=>{
  const wide=matchMedia('(min-width:1100px)'),reading=matchMedia('(min-width:901px)');
  const disclosures=[...document.querySelectorAll('[data-wide-open]')];
  const sync=()=>{for(const d of disclosures)d.open=(d.matches('.brief-reading-navigation')?reading:wide).matches};
  sync();wide.addEventListener('change',sync);reading.addEventListener('change',sync);
  for(const d of document.querySelectorAll('.shell-menu'))d.addEventListener('keydown',e=>{if(e.key==='Escape'){d.open=false;d.querySelector('summary').focus()}});
})();
