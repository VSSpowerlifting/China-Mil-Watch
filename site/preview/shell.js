/* Optional disclosure defaults. Reading and navigation remain native. */
(()=>{const wide=matchMedia('(min-width:1100px)');for(const d of document.querySelectorAll('[data-wide-open]'))d.open=wide.matches;for(const d of document.querySelectorAll('.shell-menu'))d.addEventListener('keydown',e=>{if(e.key==='Escape'){d.open=false;d.querySelector('summary').focus()}});})();
