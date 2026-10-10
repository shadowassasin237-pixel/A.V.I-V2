"""
A.V.I. - Artificial Voice Intelligence
A.V.I. HOLOGRAPHIC HUD — PyWebView Edition

High-performance native desktop HUD built with Edge Chromium / Three.js.
Fully non-blocking telemetry and state engine to prevent any UI freezes.

FIXES IN THIS VERSION
  * Crash / freeze on open: pywebview walks EVERY public attribute of the
    js_api object (recursively). Public attributes such as ``speaker``,
    ``brain``, ``voice_client`` and ``window`` made it dive into the LiveKit
    room and the native .NET window (-> "maximum recursion depth exceeded").
    All non-API state is now underscore-private, which pywebview skips.
  * Speech repeating 2-3x: all speech now goes through ONE queue + ONE worker
    thread, with duplicate suppression. send_message() is also de-duplicated.
  * Modes: sentinel = mask over orb, god = glow + lightning (colours never change).
  * Speaking: heartbeat lub-dub + vibration on the orb; orb spin frozen meanwhile.
"""

import json
import os
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# ============================================================
# OPTIONAL PROJECT IMPORTS
# ============================================================

try:
    from core.language import (
        detect_language,
        language_label,
        LANG_ENGLISH,
        LANG_HINDI,
        LANG_PUNJABI,
    )
except Exception:
    LANG_ENGLISH = "en"
    LANG_HINDI = "hi"
    LANG_PUNJABI = "pa"

    def detect_language(text):
        return LANG_ENGLISH

    def language_label(lang):
        return str(lang)


try:
    from config import (
        OPENROUTER_API_KEY,
        LLM_MODEL,
        LIVEKIT_URL,
        LIVEKIT_API_KEY,
        LIVEKIT_API_SECRET,
        AVI_VOICE,
        INWORLD_VOICES,
        POPULAR_MODELS,
    )
except Exception:
    OPENROUTER_API_KEY = ""
    LLM_MODEL = ""
    LIVEKIT_URL = ""
    LIVEKIT_API_KEY = ""
    LIVEKIT_API_SECRET = ""
    AVI_VOICE = "Arjun"
    INWORLD_VOICES = [
        "Arjun", "Priya", "Ashley", "Mark", "Sarah",
        "Brian", "Wendy", "Deborah", "Alex", "Emma",
    ]
    POPULAR_MODELS = [
        "openai/gpt-4o-mini",
        "openai/gpt-4o",
        "anthropic/claude-3.5-sonnet",
        "google/gemini-pro-1.5",
    ]


# ── Persistent config file ──
AVI_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".avi_config.json")

# Set AVI_GUI_SPEAK=0 if your brain.respond() already speaks by itself
# (then the GUI must NOT speak the reply a second time).
GUI_SPEAKS_REPLIES = os.environ.get("AVI_GUI_SPEAK", "1").strip() not in ("0", "false", "no")


def load_saved_config():
    """Load all user settings from the local config file."""
    global OPENROUTER_API_KEY, LLM_MODEL
    global LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, AVI_VOICE
    try:
        if not os.path.exists(AVI_CONFIG_PATH):
            return
        with open(AVI_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return

        def _pick(key, current):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
            return current

        OPENROUTER_API_KEY = _pick("openrouter_api_key", OPENROUTER_API_KEY)
        LLM_MODEL = _pick("llm_model", LLM_MODEL)
        LIVEKIT_URL = _pick("livekit_url", LIVEKIT_URL)
        LIVEKIT_API_KEY = _pick("livekit_api_key", LIVEKIT_API_KEY)
        LIVEKIT_API_SECRET = _pick(
            "livekit_api_secret", LIVEKIT_API_SECRET
        )
        AVI_VOICE = _pick("avi_voice", AVI_VOICE)

        # Mirror to the config module so app.py sees the latest values
        try:
            import config as _cfg
            _cfg.OPENROUTER_API_KEY = OPENROUTER_API_KEY
            _cfg.LLM_MODEL = LLM_MODEL
            _cfg.LIVEKIT_URL = LIVEKIT_URL
            _cfg.LIVEKIT_API_KEY = LIVEKIT_API_KEY
            _cfg.LIVEKIT_API_SECRET = LIVEKIT_API_SECRET
            _cfg.AVI_VOICE = AVI_VOICE
        except Exception:
            pass

        # Mirror to os.environ so the agent subprocess inherits them
        os.environ["OPENROUTER_API_KEY"] = OPENROUTER_API_KEY
        os.environ["AVI_LLM_MODEL"] = LLM_MODEL
        os.environ["LIVEKIT_URL"] = LIVEKIT_URL
        os.environ["LIVEKIT_API_KEY"] = LIVEKIT_API_KEY
        os.environ["LIVEKIT_API_SECRET"] = LIVEKIT_API_SECRET
        os.environ["AVI_VOICE"] = AVI_VOICE
    except Exception as exc:
        print("Config load error:", exc)


def save_config_to_file(
    api_key,
    model,
    livekit_url="",
    livekit_api_key="",
    livekit_api_secret="",
    voice="",
):
    """Persist every setting the user can change in the GUI."""
    try:
        data = {
            "openrouter_api_key": api_key,
            "llm_model": model,
            "livekit_url": livekit_url,
            "livekit_api_key": livekit_api_key,
            "livekit_api_secret": livekit_api_secret,
            "avi_voice": voice,
        }
        with open(AVI_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        print("Config save error:", exc)


def _write_env_value(env_path, key, value):
    """Update a single KEY=value line in the .env file, or append it."""
    if not env_path:
        return
    p = Path(env_path)
    lines = []
    if p.exists():
        with p.open("r", encoding="utf-8") as f:
            lines = f.readlines()

    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}\n")

    with p.open("w", encoding="utf-8") as f:
        f.writelines(lines)


# Load saved config on import
load_saved_config()


try:
    from voice.listener import AVIListener
except Exception:
    AVIListener = None


# ============================================================
# ORB / MODE EFFECTS  (injected into the page once it has loaded)
# ============================================================
# Colours are NEVER changed per mode:
#   tactical   - plain orb, nothing added
#   sentinel   - hex-mesh "mask" + scan bar + shield ring over the orb
#   god        - orb glows/saturates harder + lightning crackling around it
# While speaking: heartbeat "lub-dub" pulse + vibration + shock rings.
# The orb's own spin is frozen while speaking / listening / thinking.
#
# Optional tuning (env vars):  AVI_ORB_SELECTOR (CSS selector of the orb canvas)
#                              AVI_ORB_RADIUS   (orb radius in CSS pixels)

MODES_OK = ("tactical", "sentinel", "focus", "diagnostic", "god")

AVIFX_JS = r'''
(function(){
if(window.AVIFX&&window.AVIFX.__v){return;}
var CFG={selector:__SEL__,radius:__RAD__};
var S={mode:'tactical',py:false,st:false,orbState:'idle',level:0,col:[0,229,255],cv:null,ov:null,cx:null,
 amp:0,gA:0,sA:0,lastBeat:-1,lastDub:-1,rings:[],bolts:[],nextBolt:0,cT:0,fT:-9999,hex:null,hexKey:'',lock:{},t0:performance.now(),d:1,tx:false,lastF:null,hover:false,touchUntil:0};
var P=0.9;
function bump(p,c,w){var d=(p-c)/w;return Math.exp(-d*d);}
function C(a,l){var c=S.col;l=l||0;return 'rgba('+Math.min(255,c[0]+l)+','+Math.min(255,c[1]+l)+','+Math.min(255,c[2]+l)+','+Math.max(0,Math.min(1,a)).toFixed(3)+')';}
function size(){var d=window.devicePixelRatio||1;S.d=d;S.ov.width=Math.round(innerWidth*d);S.ov.height=Math.round(innerHeight*d);}
function mk(){
  if(S.ov&&S.ov.isConnected)return;
  var o=document.createElement('canvas');o.id='avi-fx-overlay';
  o.style.cssText='position:fixed;left:0;top:0;width:100vw;height:100vh;pointer-events:none;z-index:30;';
  document.body.appendChild(o);S.ov=o;S.cx=o.getContext('2d');size();
}
window.addEventListener('resize',function(){if(S.ov)size();});
function find(){
  if(CFG.selector){var e=document.querySelector(CFG.selector);if(e)return e;}
  var best=null,ba=0;
  [].slice.call(document.querySelectorAll('canvas')).forEach(function(c){
    if(c===S.ov)return;var r=c.getBoundingClientRect();var a=r.width*r.height;
    if(a>ba){ba=a;best=c;}
  });
  return best;
}
function sample(){
  try{
    var c=S.cv;if(!c||c.tagName!=='CANVAS')return;
    var t=S.tc||(S.tc=document.createElement('canvas'));t.width=t.height=24;
    var x=t.getContext('2d',{willReadFrequently:true});x.drawImage(c,0,0,24,24);
    var d=x.getImageData(0,0,24,24).data,r=0,g=0,b=0,w=0;
    for(var i=0;i<d.length;i+=4){
      var m=Math.max(d[i],d[i+1],d[i+2]),n=Math.min(d[i],d[i+1],d[i+2]),s=m-n;
      if(m>90&&s>60){r+=d[i]*s;g+=d[i+1]*s;b+=d[i+2]*s;w+=s;}
    }
    if(w>0){r/=w;g/=w;b/=w;var k=255/(Math.max(r,g,b)||1);S.col=[r*k|0,g*k|0,b*k|0];}
  }catch(e){}
}
function geo(){
  var r=S.cv.getBoundingClientRect();
  var full=r.width>innerWidth*0.8&&r.height>innerHeight*0.8;
  var m=Math.min(r.width,r.height);
  return {cx:r.left+r.width/2,cy:r.top+r.height/2,R:CFG.radius||(full?m*0.28:m*0.42)};
}
function hexLayer(R){
  var key=Math.round(R)+'|'+S.col.join(',');
  if(S.hexKey===key)return;S.hexKey=key;
  var n=Math.ceil(2*R),c=S.hex||(S.hex=document.createElement('canvas'));c.width=c.height=n;
  var x=c.getContext('2d');x.clearRect(0,0,n,n);
  var s=16,w=s*1.5,h=s*Math.sqrt(3),seed=7;
  function rnd(){seed=(seed*9301+49297)%233280;return seed/233280;}
  for(var i=-1;i<n/w+1;i++){for(var j=-1;j<n/h+1;j++){
    var px=i*w,py=j*h+(i%2?h/2:0);
    x.beginPath();
    for(var k=0;k<6;k++){var a=k*Math.PI/3;var vx=px+s*0.95*Math.cos(a),vy=py+s*0.95*Math.sin(a);k?x.lineTo(vx,vy):x.moveTo(vx,vy);}
    x.closePath();x.strokeStyle=C(0.5);x.lineWidth=1;x.stroke();
    if(rnd()<0.1){x.fillStyle=C(0.14);x.fill();}
  }}
}
function mask(ctx,cx,cy,R,t,a){
  ctx.save();ctx.beginPath();ctx.arc(cx,cy,R,0,6.2832);ctx.clip();
  var g=ctx.createRadialGradient(cx,cy,R*0.3,cx,cy,R);
  g.addColorStop(0,'rgba(0,0,0,0)');g.addColorStop(1,'rgba(0,6,10,'+(0.62*a).toFixed(3)+')');
  ctx.fillStyle=g;ctx.fillRect(cx-R,cy-R,2*R,2*R);
  hexLayer(R);ctx.globalAlpha=0.6*a;ctx.drawImage(S.hex,cx-R,cy-R,2*R,2*R);ctx.globalAlpha=1;
  var y=cy-R+((t*0.35)%1)*2*R;
  var sg=ctx.createLinearGradient(0,y-20,0,y+20);
  sg.addColorStop(0,C(0));sg.addColorStop(0.5,C(0.4*a));sg.addColorStop(1,C(0));
  ctx.fillStyle=sg;ctx.fillRect(cx-R,y-20,2*R,40);
  ctx.restore();
  ctx.save();ctx.strokeStyle=C(0.75*a);ctx.lineWidth=2;
  ctx.beginPath();ctx.arc(cx,cy,R,0,6.2832);ctx.stroke();
  ctx.setLineDash([14,10]);ctx.lineDashOffset=-t*22;ctx.lineWidth=1.5;ctx.strokeStyle=C(0.55*a);
  ctx.beginPath();ctx.arc(cx,cy,R*1.06,0,6.2832);ctx.stroke();ctx.setLineDash([]);
  ctx.lineWidth=3;ctx.strokeStyle=C(0.9*a);
  for(var q=0;q<4;q++){var an=Math.PI/4+q*Math.PI/2;ctx.beginPath();ctx.arc(cx,cy,R*1.12,an-0.12,an+0.12);ctx.stroke();}
  ctx.restore();
}
function mkBolt(g,speaking){
  var inner=Math.random()<0.25,a=Math.random()*6.2832,x1,y1,x2,y2;
  if(inner){var o=Math.random()*g.R*0.3,oa=Math.random()*6.2832;x1=g.cx+Math.cos(oa)*o;y1=g.cy+Math.sin(oa)*o;x2=g.cx+Math.cos(a)*g.R*0.98;y2=g.cy+Math.sin(a)*g.R*0.98;}
  else{var r1=g.R*(0.92+Math.random()*0.08),r2=g.R*(1.4+Math.random()*0.9);x1=g.cx+Math.cos(a)*r1;y1=g.cy+Math.sin(a)*r1;x2=g.cx+Math.cos(a+(Math.random()-.5)*0.5)*r2;y2=g.cy+Math.sin(a+(Math.random()-.5)*0.5)*r2;}
  function path(ax,ay,bx,by,n,j){
    var dx=bx-ax,dy=by-ay,len=Math.hypot(dx,dy)||1,nx=-dy/len,ny=dx/len,pts=[[ax,ay]];
    for(var i=1;i<n;i++){var f=i/n,o=(Math.random()-.5)*len*j;pts.push([ax+dx*f+nx*o,ay+dy*f+ny*o]);}
    pts.push([bx,by]);return pts;
  }
  var main=path(x1,y1,x2,y2,10,0.24),paths=[main],nb=1+(Math.random()*2|0);
  for(var b=0;b<nb;b++){
    var p=main[2+(Math.random()*4|0)],ba=Math.random()*6.2832,bl=Math.hypot(x2-x1,y2-y1)*(0.25+Math.random()*0.2);
    paths.push(path(p[0],p[1],p[0]+Math.cos(ba)*bl,p[1]+Math.sin(ba)*bl,5,0.3));
  }
  return {paths:paths,born:performance.now(),life:170+Math.random()*160};
}
function strokePaths(ctx,paths){
  paths.forEach(function(pts){ctx.beginPath();pts.forEach(function(p,i){i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]);});ctx.stroke();});
}
var CAND=['group','orb','core','sphere','mesh','mainGroup','orbGroup','reactor','coreGroup'];
function freezeSpin(active){
  var rc=window.ReactorCore;if(!rc)return;
  CAND.forEach(function(k){
    var o=rc[k];if(!o||!o.rotation||typeof o.rotation.y!=='number')return;
    if(active){
      if(!S.lock[k])S.lock[k]=[o.rotation.x,o.rotation.y,o.rotation.z];
      var l=S.lock[k];o.rotation.x=l[0];o.rotation.y=l[1];o.rotation.z=l[2];
    }else{delete S.lock[k];}
  });
}
function hook(){
  var rc=window.ReactorCore;if(!rc||rc.__avifx)return;rc.__avifx=1;
  if(typeof rc.setState==='function'){var o=rc.setState;rc.setState=function(s){S.orbState=String(s);return o.apply(this,arguments);};}
  if(typeof rc.setVoiceLevel==='function'){var v=rc.setVoiceLevel;rc.setVoiceLevel=function(l){S.level=+l||0;return v.apply(this,arguments);};}
}
setInterval(hook,400);
function frame(now){
  requestAnimationFrame(frame);
  if(!document.body)return;
  mk();
  if(!S.cv||!S.cv.isConnected||now-S.fT>2000){
    var nc=find();S.fT=now;
    if(nc&&nc!==S.cv){S.cv=nc;S.origT=nc.style.transform;S.origF=nc.style.filter;nc.style.transition='filter .5s ease';}
  }
  if(!S.cv)return;
  if(now-S.cT>800){S.cT=now;sample();}
  var t=(now-S.t0)/1000,speaking=S.py,beating=speaking||S.hover||now<S.touchUntil,active=speaking||S.orbState==='listening'||S.orbState==='thinking'||S.orbState==='processing';
  freezeSpin(active);
  S.amp+=((beating?1:0)-S.amp)*0.12;
  S.gA+=((S.mode==='god'?1:0)-S.gA)*0.06;
  S.sA+=((S.mode==='sentinel'?1:0)-S.sA)*0.08;
  var ph=t%P,beatIdx=Math.floor(t/P),beat=bump(ph,0.10,0.05)+0.65*bump(ph,0.34,0.055);
  if(beating){
    if(ph>0.06&&S.lastBeat!==beatIdx){S.lastBeat=beatIdx;S.rings.push({t:now,k:1});}
    if(ph>0.30&&S.lastDub!==beatIdx){S.lastDub=beatIdx;S.rings.push({t:now,k:0.6});}
  }
  var cv=S.cv;
  if(S.amp>0.003){
    var lv=Math.min(1,S.level*1.5),sc=1+0.045*S.amp*beat*(0.8+0.4*lv),j=S.amp*(0.5+beat)*1.3;
    cv.style.transformOrigin='50% 50%';
    cv.style.transform='translate('+((Math.random()-.5)*2*j).toFixed(2)+'px,'+((Math.random()-.5)*2*j).toFixed(2)+'px) rotate('+((Math.random()-.5)*0.3*S.amp).toFixed(3)+'deg) scale('+sc.toFixed(4)+')';
    S.tx=true;
  }else if(S.tx){cv.style.transform=S.origT||'';S.tx=false;}
  var f=S.gA>0.02?'saturate('+(1+0.7*S.gA).toFixed(2)+') brightness('+(1+0.22*S.gA).toFixed(2)+') contrast('+(1+0.08*S.gA).toFixed(2)+')':(S.origF||'');
  if(f!==S.lastF){cv.style.filter=f;S.lastF=f;}
  var ctx=S.cx,d=S.d;
  ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,S.ov.width,S.ov.height);ctx.setTransform(d,0,0,d,0,0);
  var g=geo();
  if(S.gA>0.02){
    var pulse=0.85+0.15*Math.sin(t*3),gr=ctx.createRadialGradient(g.cx,g.cy,g.R*0.5,g.cx,g.cy,g.R*2);
    gr.addColorStop(0,C(0.3*S.gA*pulse));gr.addColorStop(0.5,C(0.12*S.gA*pulse));gr.addColorStop(1,C(0));
    ctx.save();ctx.globalCompositeOperation='lighter';ctx.fillStyle=gr;ctx.fillRect(g.cx-g.R*2,g.cy-g.R*2,g.R*4,g.R*4);ctx.restore();
    if(S.gA>0.5&&now>S.nextBolt){
      S.nextBolt=now+(speaking?70:110)+Math.random()*(speaking?160:280);
      S.bolts.push(mkBolt(g,speaking));if(S.bolts.length>8)S.bolts.shift();
    }
  }
  S.bolts=S.bolts.filter(function(b){return now-b.born<b.life;});
  if(S.bolts.length){
    ctx.save();ctx.globalCompositeOperation='lighter';ctx.lineJoin='round';ctx.lineCap='round';
    S.bolts.forEach(function(b){
      var a=(1-(now-b.born)/b.life)*(Math.random()>0.25?1:0.45)*Math.max(S.gA,0.3);
      ctx.shadowColor=C(1);ctx.shadowBlur=30;ctx.strokeStyle=C(0.5*a);ctx.lineWidth=9;strokePaths(ctx,b.paths);
      ctx.shadowBlur=8;ctx.strokeStyle=C(0.95*a,160);ctx.lineWidth=2.4;strokePaths(ctx,b.paths);
    });
    ctx.restore();
  }
  if(S.sA>0.02)mask(ctx,g.cx,g.cy,g.R,t,S.sA);
  S.rings=S.rings.filter(function(r){return now-r.t<750;});
  S.rings.forEach(function(r){
    var age=(now-r.t)/750;ctx.save();ctx.strokeStyle=C((1-age)*0.55*r.k);ctx.lineWidth=2.5*(1-age)+0.5;
    ctx.beginPath();ctx.arc(g.cx,g.cy,g.R*(1+0.45*age),0,6.2832);ctx.stroke();ctx.restore();
  });
}
function near(e,k){
  if(!S.cv)return false;var g=geo(),dx=e.clientX-g.cx,dy=e.clientY-g.cy;return Math.hypot(dx,dy)<g.R*(k||1.1);
}
function pt(e){return (e.touches&&e.touches[0])||e;}
window.addEventListener('pointermove',function(e){S.hover=(e.pointerType==='touch')?S.hover:near(e);},{passive:true});
window.addEventListener('pointerdown',function(e){if(near(e,1.25)){S.touchUntil=performance.now()+1800;if(e.pointerType!=='mouse')S.hover=true;}},{passive:true});
window.addEventListener('pointerup',function(e){if(e.pointerType==='touch'){S.hover=false;S.touchUntil=performance.now()+1200;}},{passive:true});
window.addEventListener('touchstart',function(e){var t=pt(e);if(near(t,1.25))S.touchUntil=performance.now()+1800;},{passive:true});
document.addEventListener('mouseleave',function(){S.hover=false;});
window.addEventListener('blur',function(){S.hover=false;});
window.AVIFX={__v:1,
  setMode:function(m){
    S.mode=m;document.documentElement.setAttribute('data-avi-mode',m);
    if(document.body){['tactical','sentinel','focus','diagnostic','god'].forEach(function(x){document.body.classList.remove('mode-'+x);});document.body.classList.add('mode-'+m);}
  },
  setSpeaking:function(b){S.py=!!b;},
  setLevel:function(l){S.level=+l||0;},
  config:function(o){for(var k in o)CFG[k]=o[k];S.fT=-9999;S.hexKey='';}
};
requestAnimationFrame(frame);
})();
'''

def _js_str(value):
    """Safely embed a Python value in JS source (handles quotes/newlines/unicode)."""
    return json.dumps(value, ensure_ascii=True)


# ============================================================
# PYWEBVIEW API CLASS — exposed to JavaScript
# ============================================================

class AVIWebAPI:
    """Python API exposed to the web frontend via pywebview.

    IMPORTANT: pywebview recursively inspects every PUBLIC attribute of this
    object. Anything that is not a JS-callable API method MUST start with an
    underscore, otherwise pywebview walks into the LiveKit room / native
    window objects and crashes with "maximum recursion depth exceeded".
    """

    def __init__(self, brain, speaker, voice_client=None, agent_launcher=None):
        # ---- all private (underscore) so pywebview does NOT introspect them ----
        self._brain = brain
        self._speaker = speaker
        self._voice_client = voice_client
        self._agent_launcher = agent_launcher
        self._window = None
        self._loaded = threading.Event()
        self._running = True
        self._current_mode = "tactical"
        self._mic_active = False
        self._mic_lock = threading.Lock()
        self._boot_time = time.time()

        # ---- de-duplication for chat messages ----
        self._msg_lock = threading.Lock()
        self._last_msg = ("", 0.0, "")  # (text, time, response)

        # ---- single speech pipeline (prevents the reply being read 2-3x) ----
        self._speech_q = queue.Queue()
        self._speech_lock = threading.Lock()
        self._pending_speech = set()
        self._last_spoken = ("", 0.0)
        self._speech_thread = threading.Thread(
            target=self._speech_worker, daemon=True
        )
        self._speech_thread.start()
        self._busy = False
        self._busy_end = 0.0
        self._speak_until = 0.0
        threading.Thread(target=self._speaking_watcher, daemon=True).start()

        # Cached telemetry stats for instantaneous non-blocking retrieval
        self._cached_stats = {
            "cpu": 0.0,
            "ram": 0.0,
            "ram_used": "0",
            "ram_total": "0",
            "gpu": "N/A",
            "gpu_percent": 0,
            "disk": 0.0,
            "processes": 0,
        }

        # Start non-blocking telemetry background daemon
        self._telemetry_thread = threading.Thread(
            target=self._telemetry_worker,
            daemon=True,
        )
        self._telemetry_thread.start()

    # ────────────────────────────────────────────
    # INTERNAL HELPERS (private -> invisible to JS)
    # ────────────────────────────────────────────

    def _attach_window(self, window):
        self._window = window

    def _on_loaded(self):
        """Fired by pywebview once the page has finished loading."""
        self._loaded.set()
        self._inject_fx()
        self._apply_mode_theme(self._current_mode)

    def _js(self, code):
        """Run JS safely. Never raises, never runs before the page is ready."""
        win = self._window
        if win is None or not self._running or not self._loaded.is_set():
            return None
        try:
            return win.evaluate_js(code)
        except Exception as exc:
            print("[A.V.I.] evaluate_js error:", exc)
            return None

    def _set_orb_idle(self):
        self._js("if(window.ReactorCore){window.ReactorCore.setState('idle')}")
        self._js("if(window.HUD&&window.HUD._updateOrbState){window.HUD._updateOrbState('idle')}")

    def _apply_mode_theme(self, mode):
        """Switch orb effects (mask / glow+lightning). Colours never change."""
        if mode not in MODES_OK:
            mode = "tactical"
        self._js(
            "if(window.AVIFX){window.AVIFX.setMode(%s)}" % _js_str(mode)
        )

    def _inject_fx(self):
        """Inject the orb effects script (heartbeat, mask, glow, lightning)."""
        sel = os.environ.get("AVI_ORB_SELECTOR", "").strip() or None
        try:
            rad = float(os.environ.get("AVI_ORB_RADIUS", "")) or None
        except ValueError:
            rad = None
        code = AVIFX_JS.replace("__SEL__", json.dumps(sel)).replace(
            "__RAD__", json.dumps(rad)
        )
        self._js(code)

    def _speaking_watcher(self):
        """Tell the orb effects when A.V.I. is speaking (works even if speak() is async)."""
        last = None
        while self._running:
            now = bool(self._busy) or time.time() < self._speak_until
            if now != last and self._loaded.is_set():
                last = now
                self._js("if(window.AVIFX){window.AVIFX.setSpeaking(%s)}" % ("true" if now else "false"))
            time.sleep(0.12)

    def _telemetry_worker(self):
        """Background thread updating stats once per second without blocking the GUI."""
        try:
            import psutil
        except Exception as exc:
            print("[A.V.I.] psutil not available, telemetry disabled:", exc)
            return
        # Prime psutil once
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

        while self._running:
            try:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory()
                disk_path = "C:\\" if os.name == "nt" else "/"
                disk_val = 0.0
                try:
                    disk_val = psutil.disk_usage(disk_path).percent
                except Exception:
                    pass

                self._cached_stats = {
                    "cpu": round(cpu, 1),
                    "ram": round(mem.percent, 1),
                    "ram_used": f"{mem.used / (1024**3):.1f}",
                    "ram_total": f"{mem.total / (1024**3):.1f}",
                    "gpu": "N/A",
                    "gpu_percent": 0,
                    "disk": round(disk_val, 1),
                    "processes": len(psutil.pids()),
                }
            except Exception:
                pass
            time.sleep(1.2)

    # ────────────────────────────────────────────
    # SPEECH — single queue, single worker, de-duplicated
    # ────────────────────────────────────────────

    def _enqueue_speech(self, text):
        """Queue text for speech unless it is already queued / just spoken."""
        text = (text or "").strip()
        if not text or not GUI_SPEAKS_REPLIES:
            return
        with self._speech_lock:
            last_text, last_time = self._last_spoken
            if text == last_text and (time.time() - last_time) < 8.0:
                print("[A.V.I.] Duplicate speech suppressed (just spoken).")
                return
            if text in self._pending_speech:
                print("[A.V.I.] Duplicate speech suppressed (already queued).")
                return
            self._pending_speech.add(text)
        self._speech_q.put(text)

    def _speech_worker(self):
        """The ONLY place that ever calls speak(). Runs one utterance at a time."""
        while self._running:
            try:
                text = self._speech_q.get(timeout=0.5)
            except queue.Empty:
                continue
            self._busy = True
            t_start = time.time()
            est = max(1.5, len(text) / 13.0 + 0.8)  # rough speaking time (s)
            self._speak_until = t_start + est
            try:
                self._speak_blocking(text)
                # If speak() blocked until the audio finished, stop right away;
                # if it returned instantly (async TTS), beat for the estimated time only.
                if time.time() - t_start >= est * 0.7:
                    self._speak_until = 0.0
            except Exception as exc:
                print("Speech error:", exc)
            finally:
                self._busy = False
                self._busy_end = time.time()
                with self._speech_lock:
                    self._pending_speech.discard(text)
                    self._last_spoken = (text, time.time())
                if self._speech_q.empty():
                    self._set_orb_idle()

    def _speak_blocking(self, text):
        """Speak via voice client OR speaker — never both."""
        vc = self._voice_client
        if vc is not None and hasattr(vc, "speak"):
            vc.speak(text)
            return
        if self._speaker is not None:
            self._speaker.speak(text)

    # ────────────────────────────────────────────
    # CHAT / BRAIN
    # ────────────────────────────────────────────

    def send_message(self, text):
        """Send a user message to A.V.I.'s brain and return the response."""
        if not text or not text.strip():
            return ""
        text = text.strip()

        # Prevent audio echo / feedback loop from computer speakers
        lower_t = text.lower()
        boot_echo_phrases = ["created by arnav kumar", "awaiting your command", "all systems operational", "a.v.i. online"]
        if any(p in lower_t for p in boot_echo_phrases) and (time.time() - self._boot_time < 8.0):
            print(f"[A.V.I.] Suppressed boot echo: {text}")
            return "A.V.I. Sentinel Core ready. Standing by for instructions."

        with self._msg_lock:
            # If the frontend fires the same message twice (Enter + voice result,
            # double click, ...) answer once and do NOT speak again.
            last_text, last_time, last_resp = self._last_msg
            if text == last_text and (time.time() - last_time) < 2.5:
                print(f"[A.V.I.] Duplicate message ignored: {text}")
                return last_resp

            try:
                start = time.time()
                response = self._brain.respond(text)
                elapsed = int((time.time() - start) * 1000)
                if response is None:
                    response = "I am unable to process that command."
                response = str(response)

                self._last_msg = (text, time.time(), response)

                # Update latency in frontend
                self._js(
                    f"if(window.updateLatency){{window.updateLatency({int(elapsed)})}}"
                )

                # One queued, de-duplicated utterance
                self._enqueue_speech(response)
                return response
            except Exception as exc:
                print("Brain error:", exc)
                return "I encountered an internal processing error."

    # ────────────────────────────────────────────
    # MICROPHONE / VOICE INPUT
    # ────────────────────────────────────────────

    def start_mic(self):
        """Start microphone listening in a background thread."""
        if AVIListener is None:
            return json.dumps({"error": "AVIListener not available"})
        with self._mic_lock:
            if self._mic_active:
                return json.dumps({"error": "Already listening"})
            self._mic_active = True
        threading.Thread(target=self._voice_worker, daemon=True).start()
        return json.dumps({"status": "listening"})

    def stop_mic(self):
        """Stop microphone."""
        self._mic_active = False
        return json.dumps({"status": "stopped"})

    def _voice_worker(self):
        """Background thread: listen for speech then push result to JS."""
        try:
            # Check speaker status
            if self._speaker and getattr(self._speaker, "is_speaking", False):
                print("[A.V.I.] Mic skipped: speaker is currently active.")
                self._send_voice_result(None)
                return

            listener = AVIListener(
                should_ignore=lambda: bool(
                    getattr(self._speaker, "is_speaking", False)
                )
            )
            result = listener.listen(auto_detect=True)
            if not result:
                self._send_voice_result(None)
                return
            if isinstance(result, tuple):
                text = result[0]
                lang = result[1] if len(result) > 1 else None
            else:
                text = result
                lang = None

            if not text or not text.strip():
                self._send_voice_result(None)
                return

            # Check if text is boot speech bleed from speakers
            lower = text.lower()
            boot_phrases = ["created by arnav kumar", "all systems operational", "awaiting your command"]
            if any(p in lower for p in boot_phrases) and (time.time() - self._boot_time < 8.0):
                print(f"[A.V.I.] Suppressed mic speaker bleed: {text}")
                self._send_voice_result(None)
                return

            # Detect language for speaker
            try:
                if lang is None:
                    lang = detect_language(text)
                if self._speaker is not None and hasattr(self._speaker, "set_language"):
                    self._speaker.set_language(lang)
            except Exception:
                pass

            self._send_voice_result(text)
        except Exception as exc:
            print("Voice listener error:", exc)
            self._send_voice_result(None)
        finally:
            self._mic_active = False

    def _send_voice_result(self, text):
        """Push recognized text to the frontend."""
        if text:
            self._js(
                f"if(window.voiceResult){{window.voiceResult({_js_str(text)})}}"
            )
        else:
            self._js("if(window.voiceResult){window.voiceResult(null)}")

    # ────────────────────────────────────────────
    # SYSTEM STATS (Instantaneous Non-blocking)
    # ────────────────────────────────────────────

    def get_system_stats(self):
        """Return live system telemetry as JSON in 0ms without blocking."""
        return json.dumps(self._cached_stats)

    # ────────────────────────────────────────────
    # SETTINGS
    # ────────────────────────────────────────────

    def load_settings(self):
        """Return current settings as JSON for the settings panel."""
        return json.dumps({
            "openrouter_api_key": OPENROUTER_API_KEY,
            "llm_model": LLM_MODEL,
            "livekit_url": LIVEKIT_URL,
            "livekit_api_key": LIVEKIT_API_KEY,
            "livekit_api_secret": LIVEKIT_API_SECRET,
            "avi_voice": AVI_VOICE,
            "voices_list": list(INWORLD_VOICES),
            "models_list": list(POPULAR_MODELS),
            "config_path": AVI_CONFIG_PATH,
        })

    def save_settings(self, data_json):
        """Save settings from the frontend."""
        global OPENROUTER_API_KEY, LLM_MODEL
        global LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, AVI_VOICE

        try:
            data = json.loads(data_json) if isinstance(data_json, str) else data_json
        except Exception:
            return json.dumps({"success": False, "error": "Invalid JSON"})

        key = data.get("openrouter_api_key", "").strip()
        model = data.get("llm_model", "").strip() or LLM_MODEL
        voice = data.get("avi_voice", "").strip() or AVI_VOICE
        lk_url = data.get("livekit_url", "").strip()
        lk_key = data.get("livekit_api_key", "").strip()
        lk_secret = data.get("livekit_api_secret", "").strip()
        restart_voice = data.get("restart_voice", False)

        original_voice = AVI_VOICE
        original_model = LLM_MODEL

        # Update globals
        OPENROUTER_API_KEY = key
        LLM_MODEL = model
        LIVEKIT_URL = lk_url
        LIVEKIT_API_KEY = lk_key
        LIVEKIT_API_SECRET = lk_secret
        AVI_VOICE = voice

        # Persist to JSON
        save_config_to_file(
            key, model,
            livekit_url=lk_url,
            livekit_api_key=lk_key,
            livekit_api_secret=lk_secret,
            voice=voice,
        )

        # Mirror into config.py
        try:
            import config
            config.OPENROUTER_API_KEY = key
            config.LLM_MODEL = model
            config.LIVEKIT_URL = lk_url
            config.LIVEKIT_API_KEY = lk_key
            config.LIVEKIT_API_SECRET = lk_secret
            config.AVI_VOICE = voice
        except Exception:
            pass

        # Write to .env
        try:
            env_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", ".env",
            )
            env_path = os.path.abspath(env_path)
            _write_env_value(env_path, "OPENROUTER_API_KEY", key)
            _write_env_value(env_path, "AVI_LLM_MODEL", model)
            _write_env_value(env_path, "LIVEKIT_URL", lk_url)
            _write_env_value(env_path, "LIVEKIT_API_KEY", lk_key)
            _write_env_value(env_path, "LIVEKIT_API_SECRET", lk_secret)
            _write_env_value(env_path, "AVI_VOICE", voice)
        except Exception as exc:
            print("A.V.I. .env write error:", exc)

        # Live brain reconfig
        voice_changed = (voice != original_voice)
        try:
            if model != original_model and self._brain is not None:
                if hasattr(self._brain, "configure_llm"):
                    self._brain.configure_llm(api_key=key, model=model)
        except Exception as exc:
            print("A.V.I. live brain reconfig error:", exc)

        # Update speaker voice
        try:
            if self._speaker is not None and hasattr(self._speaker, "voice"):
                self._speaker.voice = voice
        except Exception:
            pass

        # Restart voice agent if requested
        restart_msg = ""
        if restart_voice and voice_changed:
            try:
                if self._agent_launcher is not None:
                    self._agent_launcher.stop()
                    time.sleep(0.4)
                    ok = self._agent_launcher.start()
                    restart_msg = "Voice agent restarted." if ok else "Voice agent restart FAILED."
            except Exception as exc:
                restart_msg = f"Voice agent restart error: {exc}"
        elif voice_changed:
            restart_msg = "Voice saved; will take effect on next launch."

        return json.dumps({
            "success": True,
            "voice": voice or "(default Arjun)",
            "model": model or "NOT SET",
            "livekit": "SET" if (lk_url and lk_key and lk_secret) else "INCOMPLETE",
            "restart_msg": restart_msg,
        })

    def on_mode_change(self, mode):
        """Called from JS when user switches HUD mode — actually re-themes the HUD."""
        if mode not in MODES_OK:
            mode = "tactical"
        self._current_mode = mode
        # run off the API thread so the JS call returns instantly
        threading.Thread(
            target=self._apply_mode_theme, args=(mode,), daemon=True
        ).start()
        return json.dumps({"status": "ok", "mode": mode})

    def get_chat_history(self):
        """Return previous chat history."""
        return json.dumps([])


# ============================================================
# AVIGUI — drop-in replacement for the old Tkinter class
# ============================================================

class AVIGUI:
    """PyWebView-based A.V.I. Holographic HUD.

    Preserves the same constructor signature as legacy Tkinter ``AVIGUI``.
    """

    MODES = ("tactical", "sentinel", "focus", "diagnostic", "god")

    def __init__(self, brain, speaker, voice_client=None, agent_launcher=None):
        self.brain = brain
        self.speaker = speaker
        self.voice_client = voice_client
        self.agent_launcher = agent_launcher

        # Build the API bridge
        self.api = AVIWebAPI(
            brain=brain,
            speaker=speaker,
            voice_client=voice_client,
            agent_launcher=agent_launcher,
        )

        self._window = None
        self._running = True

    def mainloop(self):
        """Start the PyWebView window (blocks until closed)."""
        import webview

        web_hud_dir = Path(__file__).parent / "web_hud"
        index_path = web_hud_dir / "index.html"

        if not index_path.exists():
            print(f"A.V.I. ERROR: HUD not found at {index_path}")
            return

        # Create the window
        self._window = webview.create_window(
            title="A.V.I. // ARTIFICIAL VOICE INTELLIGENCE",
            url=index_path.as_uri(),
            js_api=self.api,
            width=1440,
            height=900,
            min_size=(1050, 700),
            resizable=True,
            frameless=False,
            easy_drag=False,
            text_select=False,
            confirm_close=False,
        )

        # Give the API a reference to the window for evaluate_js
        self.api._attach_window(self._window)

        # Only touch the page once it has loaded; clean up when it closes
        try:
            self._window.events.loaded += self.api._on_loaded
            self._window.events.closing += self.on_close
        except Exception as exc:
            print("A.V.I. window event hook error:", exc)
            self.api._loaded.set()

        # Start the voice client if provided
        if self.voice_client is not None:
            try:
                if hasattr(self.voice_client, "start"):
                    threading.Thread(
                        target=self.voice_client.start, daemon=True
                    ).start()
            except Exception as exc:
                print("Voice client start error:", exc)

        # Launch webview (blocks)
        webview.start(debug=False)

        # After window closes
        self._running = False
        self.api._running = False

    def set_orb_state(self, state):
        if state not in ("idle", "listening", "thinking", "speaking", "processing"):
            state = "idle"
        self.api._js(
            f"if(window.ReactorCore){{window.ReactorCore.setState({_js_str(state)})}}"
        )

    def set_voice_level(self, level):
        try:
            level = float(level)
        except Exception:
            return
        self.api._js(
            f"if(window.ReactorCore){{window.ReactorCore.setVoiceLevel({level})}}"
        )

    def add_chat(self, speaker_name, text, tag="system"):
        self.api._js(
            "if(window.HUD){window.HUD.addMessage(%s,%s,%s)}"
            % (_js_str(speaker_name), _js_str(text), _js_str(tag))
        )

    def on_close(self, *args):
        self._running = False
        self.api._running = False
        try:
            if self.speaker is not None and hasattr(self.speaker, "stop"):
                self.speaker.stop()
        except Exception:
            pass
        try:
            if self.voice_client is not None and hasattr(self.voice_client, "stop"):
                self.voice_client.stop()
        except Exception:
            pass


# ============================================================
# DIRECT TEST
# ============================================================

class DummyBrain:
    def respond(self, text):
        return f"A.V.I. Core acknowledged: {text}"


class DummySpeaker:
    def speak(self, text):
        print("A.V.I. SPEAK:", text)

    def stop(self):
        pass


if __name__ == "__main__":
    app = AVIGUI(DummyBrain(), DummySpeaker())
    app.mainloop()