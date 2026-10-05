/*
 * The opening title (docs/VISUAL_AND_MOTION_SYSTEM.md §1.1): ~2.4s over a
 * procedural ocean, homepage only, once per tab session. Loaded async, so
 * nothing waits for it; it waits only for the DOM and the title face, each
 * capped. Skipped once the page has painted, and for a query or hash, a
 * back/forward or same-site arrival, a hidden tab, reduced motion,
 * automation, or no storage or hardware WebGL.
 * Every exit ends in finish(), which runs once and undoes all of it.
 */
(function () {
  "use strict";
  var d = document, doc = d.documentElement, w = window, inerted = [],
      gl, cv, el, st, U, raf, t0, out, done, cap, late, tm;
  var VS = "attribute vec2 P;void main(){gl_Position=vec4(P,0,1);}";
  // Units are ship lengths. Waves: nine directional trains plus warped
  // noise. Wake, in the ship's frame: foam aft, an aged turquoise band,
  // faint Kelvin arms at 19.5deg, bow wash. Then hull, shadow, superstructure.
  var FS = "precision highp float;uniform vec2 R;uniform float T,K;uniform vec4 S;" +
    "float h(vec2 p){vec3 q=fract(p.xyx*.1031);q+=dot(q,q.yzx+33.33);return fract((q.x+q.y)*q.z);}" +
    "float n(vec2 p){vec2 i=floor(p),f=fract(p);f*=f*(3.-2.*f);return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+1.),f.x),f.y);}" +
    "float H(vec2 p){p+=.6*vec2(n(p*.4),n(p*.4+9.));float a=0.,k=2.6;" +
    "for(int i=0;i<9;i++){float r=h(vec2(i,3)),t=-.5+(r-.5)*3.2;a+=sin(dot(vec2(cos(t),sin(t)),p)*k-T*.9*sqrt(k)+r*6.28)/k;k*=1.23;}" +
    "mat2 m=mat2(1.68,1.26,-1.26,1.68);vec2 f=p*6.;float w=.09;" +
    "for(int i=0;i<3;i++){a+=w*n(f+T*vec2(1.2,-.8));f=m*f;w*=.5;}return a;}" +
    "float B(vec2 q,vec2 D,float a){float u=dot(q,D),v=abs(dot(q,vec2(-D.y,D.x))),b=.07*(u<.12?smoothstep(-.53,-.47,u):sqrt(max(0.,1.-pow((u-.12)/.38,2.))));return b>0.?clamp(.5-(v-b)/a,0.,1.):0.;}" +
    "void main(){vec2 c=gl_FragCoord.xy,p=c/K,q=(c-S.xy)/K,D=S.zw,uv=c/R;" +
    "float u=dot(q,D),v=abs(dot(q,vec2(-D.y,D.x))),s=-u-.5,b=.5-u,z=max(s,0.),w=.065+.06*sqrt(z)," +
    "g=step(-.2,s)*exp(-z/26.)*(1.-smoothstep(.5*w,2.2*w+.1,v)),e=.01,h0=H(p),m=1.-.7*g;" +
    "vec3 N=normalize(vec3((h0-H(p+vec2(e,0)))*m,(h0-H(p+vec2(0,e)))*m,e*11.))," +
    "V=normalize(vec3((.5-uv)*vec2(R.x/R.y,1.),1.25)),L=normalize(vec3(.62,.55,.72));" +
    "float y=n(p*.03+vec2(T*.01,0))*.6+n(p*.08)*.4;" +
    "vec3 C=mix(vec3(.02,.11,.15),vec3(.035,.28,.33),smoothstep(.1,1.,y*.7+uv.x*.3+uv.y*.25))*(.6+.6*max(dot(N,L),0.))" +
    "+vec3(.5,.7,.75)*1.3*(.02+.98*pow(1.-max(dot(N,V),0.),5.))" +
    "+vec3(1,.97,.9)*1.5*pow(max(dot(reflect(-L,N),V),0.),1400.)*smoothstep(.2,1.3,uv.x+uv.y*.8)*m;" +
    "C=mix(C,vec3(.12,.42,.44),.5*g);" +
    "float f=n(p*6.+3.)*.55+n(p*15.)*.45,k=abs(v-.3536*b),x=.06+.025*b," +
    "o=step(0.,s)*(1.-smoothstep(.35*w,w,v))*smoothstep(-.02,.08,s)*exp(-z/10.)*smoothstep(.15+.55*(1.-exp(-z/4.)),.85,f+.5*exp(-z/2.));" +
    "o=max(o,.32*step(0.,b)*exp(-k*k/(x*x))*exp(-b/2.5)*(.35+.65*smoothstep(.3,.8,n(p*4.)))*(.6+.4*sin(b*9.+v*22.)));" +
    "o=max(o,.8*f*(1.-smoothstep(0.,.04,abs(v-.08)))*smoothstep(.2,.45,u)*step(u,.52));" +
    "C=mix(C,vec3(.88,.94,.93),clamp(o,0.,1.));" +
    "float a=1./K,l=B(q,D,a);C*=1.-.4*B(q+vec2(.05,.04),D,a*3.);" +
    "C=mix(C,mix(vec3(.5,.52,.52),vec3(.93,.94,.92),clamp(.5-(abs(u+.27)-.09)/a,0.,1.)*clamp(.5-(v-.05)/a,0.,1.)),l);" +
    "C=mix(C,vec3(.16,.18,.19),.7*clamp(l-B(q*1.12,D,a),0.,1.));" +
    "gl_FragColor=vec4(C*(1.-.3*dot(uv-.5,uv-.5)),1);}";
  var E = "cubic-bezier(.16,1,.3,1)", INK = "rgba(5,28,35,";
  var CSS = "html.ipr-intro{overflow:hidden}" +
    "html.ipr-intro-hide{background:#072a33}html.ipr-intro-hide body{visibility:hidden}" +
    ".ipr-intro{visibility:visible;position:fixed;inset:0;z-index:2147483000;overflow:hidden;color:#EDEAE2;" +
    "background:linear-gradient(160deg,#0d4049,#072a33);transition:opacity .65s cubic-bezier(.4,0,.2,1)}" +
    ".ipr-intro.is-out{opacity:0}" +
    ".ipr-intro canvas{position:absolute;inset:0;width:100%;height:100%;opacity:0;transition:opacity .3s}" +
    ".ipr-intro canvas.is-on{opacity:1}" +
    ".ipr-intro-scrim{position:absolute;inset:0;background:radial-gradient(ellipse 75% 70% at 0 100%," + INK + ".72)," + INK + ".32) 55%," + INK + "0) 80%)}" +
    ".ipr-intro-copy{position:absolute;left:max(6vw,32px,env(safe-area-inset-left));bottom:max(14vh,48px);max-width:min(60vw,52rem)}" +
    ".ipr-intro-copy p{margin:0;opacity:0}" +
    ".ipr-intro-title{font:600 min(clamp(2.1rem,1.2rem + 3.4vw,4.1rem),9.5vh)/1.04 var(--serif);letter-spacing:.07em;text-transform:uppercase}" +
    ".ipr-intro-title span{white-space:nowrap}" +
    ".ipr-intro .ipr-intro-sub{margin-top:.85em;font:italic 400 clamp(1.05rem,.95rem + .45vw,1.35rem)/1.4 var(--serif);color:#D6D2C8}" +
    ".ipr-intro.is-text p{animation:ipr-in .9s " + E + " .05s both}" +
    ".ipr-intro.is-text .ipr-intro-sub{animation-delay:.28s}" +
    "@keyframes ipr-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}" +
    ".ipr-intro-skip{position:absolute;top:max(16px,env(safe-area-inset-top));right:max(16px,env(safe-area-inset-right));" +
    "min-height:44px;padding:0 1rem;font:500 .8125rem/1 var(--sans);letter-spacing:.02em;color:inherit;cursor:pointer;" +
    "background:" + INK + ".45);border:1px solid rgba(237,234,226,.5);border-radius:var(--radius)}" +
    ".ipr-intro-skip:hover{background:" + INK + ".75)}" +
    ".ipr-intro-skip:focus-visible{outline:2px solid #8FC9DE;outline-offset:3px}" +
    "@media (orientation:portrait){.ipr-intro-copy{left:max(24px,env(safe-area-inset-left));right:max(24px,env(safe-area-inset-right));" +
    "bottom:max(16vh,calc(56px + env(safe-area-inset-bottom)));max-width:none}" +
    ".ipr-intro-scrim{background:linear-gradient(to top," + INK + ".75)," + INK + ".3) 45%," + INK + "0) 70%)}}";

  function finish() {
    if (done) return;
    done = true;
    clearTimeout(cap); clearTimeout(late); clearTimeout(tm);
    cancelAnimationFrame(raf);
    d.removeEventListener("keydown", key);
    w.removeEventListener("pagehide", finish);
    d.removeEventListener("visibilitychange", finish);
    for (var i = 0; i < inerted.length; i++) inerted[i].inert = false;
    doc.classList.remove("ipr-intro", "ipr-intro-hide");
    try {
      // Keyboard on Skip: continue from the top of the page, not from <body>.
      var a = d.activeElement;
      if (el && el.contains(a) && a.matches(":focus-visible")) d.querySelector(".skip").focus();
    } catch (e) {}
    if (el) el.parentNode.removeChild(el);
    if (st) st.parentNode.removeChild(st);
    var x = gl && gl.getExtension("WEBGL_lose_context");
    if (x) x.loseContext();
  }
  function guard(f) {
    return function () { try { f.apply(this, arguments); } catch (e) { finish(); } };
  }
  function dismiss(ms) {
    if (!el) return finish();
    if (out || done) return;
    out = true;
    doc.classList.remove("ipr-intro-hide");
    el.style.transitionDuration = ms + "ms";
    el.className += " is-out";
    clearTimeout(tm);
    tm = setTimeout(finish, ms + 40);
  }
  function key(e) {
    if (e.key === "Escape" || e.key === "Esc") dismiss(250);
  }
  function frame(now) {
    var W = el.clientWidth, Hh = el.clientHeight, port = Hh > W,
        s = Math.min(w.devicePixelRatio || 1, 1.5, Math.sqrt(1.6e6 / (W * Hh))),
        bw = Math.round(W * s), bh = Math.round(Hh * s), t = Math.max(0, now - t0) / 1000,
        L = Math.max(13, Math.min(20, .0135 * Math.max(W, Hh))),
        a = (port ? 118 : 158) * Math.PI / 180, dx = Math.cos(a), dy = Math.sin(a), run = .42 * L * t;
    if (cv.width !== bw || cv.height !== bh) { cv.width = bw; cv.height = bh; gl.viewport(0, 0, bw, bh); }
    gl.uniform2f(U.R, bw, bh);
    gl.uniform1f(U.T, t + 7);
    gl.uniform1f(U.K, L * s);
    // The ship's course, in buffer pixels (y up): clear of the copy and Skip.
    gl.uniform4f(U.S, ((port ? .66 : .7) * W + dx * run) * s,
                 ((port ? .74 : .7) * Hh + dy * run) * s, dx, dy);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    cv.className = "is-on";
    raf = requestAnimationFrame(guard(frame));
  }
  // A page already on screen is never covered (nor after 2s with nothing painted).
  function stale() {
    return performance.getEntriesByName("first-contentful-paint").length > 0 || performance.now() > 2000;
  }
  function build() {
    clearTimeout(late);
    if (done) return;
    if (stale()) return finish();
    doc.classList.add("ipr-intro");
    el = d.createElement("div");
    el.className = "ipr-intro";
    el.innerHTML = '<div class="ipr-intro-scrim"></div><div class="ipr-intro-copy">' +
      '<p class="ipr-intro-title"><span>Indo-Pacific</span> Record</p>' +
      '<p class="ipr-intro-sub">Defense records. Regional context.</p></div>' +
      '<button type="button" class="ipr-intro-skip">Skip intro</button>';
    el.insertBefore(cv, el.firstChild);
    el.lastChild.addEventListener("click", guard(function () { dismiss(250); }));
    cv.addEventListener("webglcontextlost", finish);
    var kids = d.body.children;
    for (var i = 0; i < kids.length; i++) if (!kids[i].inert) { kids[i].inert = true; inerted.push(kids[i]); }
    d.body.insertBefore(el, d.body.firstChild);
    t0 = performance.now();
    raf = requestAnimationFrame(guard(frame));
    // The copy waits for the title face, at most 300ms, so it does not swap mid-fade.
    var go = guard(function () { if (!done) el.classList.add("is-text"); });
    setTimeout(go, 300);
    if (d.fonts) Promise.all([d.fonts.load('600 1em "Source Serif 4"'),
                              d.fonts.load('italic 400 1em "Source Serif 4"')]).then(go, go);
    tm = setTimeout(guard(function () { dismiss(650); }), 1750);
  }

  try {
    if (location.search || location.hash || navigator.webdriver ||
        d.visibilityState === "hidden" ||
        d.referrer.indexOf(location.origin + "/") === 0 ||
        w.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    var nav = performance.getEntriesByType("navigation")[0];
    if (nav && nav.type === "back_forward" || stale()) return;
    if (sessionStorage.getItem("ipr-intro")) return;
    sessionStorage.setItem("ipr-intro", "1");
    cv = d.createElement("canvas");
    gl = cv.getContext("webgl", { alpha: false, antialias: false, failIfMajorPerformanceCaveat: true });
    var pr = gl.createProgram();
    [[gl.VERTEX_SHADER, VS], [gl.FRAGMENT_SHADER, FS]].forEach(function (x) {
      var o = gl.createShader(x[0]);
      gl.shaderSource(o, x[1]); gl.compileShader(o); gl.attachShader(pr, o);
    });
    gl.linkProgram(pr);
    if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) return;
    gl.useProgram(pr);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    U = {};
    "RTKS".replace(/./g, function (k) { U[k] = gl.getUniformLocation(pr, k); });
  } catch (e) { return; }

  cap = setTimeout(finish, 5000);
  try {
    doc.classList.add("ipr-intro", "ipr-intro-hide");
    st = d.createElement("style");
    st.textContent = CSS;
    d.head.appendChild(st);
    d.addEventListener("keydown", key);
    w.addEventListener("pagehide", finish);
    d.addEventListener("visibilitychange", finish);
    // The DOM has 1.5s to arrive; a page that slow gets no introduction.
    late = setTimeout(finish, 1500);
    if (d.readyState === "loading") d.addEventListener("DOMContentLoaded", guard(build));
    else guard(build)();
  } catch (e) { finish(); }
})();
