"""Run the two existing intro checks, with separate scheduling negative controls.
No intro/test source is modified. Run serially per revision on the same host.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import unittest

TIMINGS = r"""
window.__introEvents=[];
const record=(kind)=>window.__introEvents.push({kind,t:performance.now()});
document.addEventListener('DOMContentLoaded',()=>record('domcontentloaded'));
new PerformanceObserver(list=>{for(const e of list.getEntries()) if(e.name==='first-contentful-paint')
 window.__introEvents.push({kind:'fcp',t:e.startTime});}).observe({type:'paint',buffered:true});
let seen=false, faded=false, gone=false;
new MutationObserver(()=>{
 const el=document.querySelector('div.ipr-intro');
 if(el&&!seen){seen=true;record('attached');
  el.querySelector('canvas').addEventListener('webglcontextlost',()=>record('contextlost'));
 }
 if(el&&el.classList.contains('is-out')&&!faded){faded=true;record('is-out');}
 if(seen&&!el&&!gone){gone=true;record('removed');}
}).observe(document,{subtree:true,childList:true,attributes:true,attributeFilter:['class']});
"""


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--repetitions',type=int,default=3)
    args=parser.parse_args()
    sys.path.insert(0,str(args.root.resolve()))
    from tests import test_homepage_intro as module
    original_page=module.IntroCase.page
    observations=[]
    current={}
    def observed_page(case,*pos,**kwargs):
        kwargs['extra']=kwargs.get('extra','')+TIMINGS
        page=original_page(case,*pos,**kwargs)
        if current['mode']=='delayed-script':
            def delay(route):
                time.sleep(2.1);route.continue_()
            page.route('**/intro.js',delay)
        original_evaluate=page.evaluate
        def evaluate(expression,*values,**options):
            if isinstance(expression,str) and 'WEBGL_lose_context' in expression:
                if current['mode']=='delayed-loss': page.wait_for_timeout(1850)
                original_evaluate("window.__introEvents.push({kind:'loss-request',t:performance.now()})")
            return original_evaluate(expression,*values,**options)
        page.evaluate=evaluate
        def collect():
            current['events']=original_evaluate('window.__introEvents || []')
            current['script']=original_evaluate("performance.getEntriesByType('resource').filter(e=>e.name.endsWith('/intro.js')).map(e=>({start:e.startTime,end:e.responseEnd}))")
        case.addCleanup(collect)
        return page
    module.IntroCase.page=observed_page
    module.IntroCase.setUpClass()
    try:
        checks=[(module.TestTheIntroPlaysOnceAndLeavesNothing,'test_first_visit_plays_then_restores_the_page'),
                (module.TestFailureNeverTraps,'test_a_lost_context_ends_it_at_once')]
        for repetition in range(args.repetitions):
            for cls,name in checks:
                current={'mode':'real-time','test':name,'repetition':repetition+1}
                result=unittest.TestResult();cls(name).run(result)
                current.update(passed=result.wasSuccessful(),failures=len(result.failures),errors=len(result.errors))
                if result.failures or result.errors:current['detail']=(result.failures+result.errors)[0][1].strip().splitlines()[-1]
                observations.append(current)
        for (cls,name),mode in zip(checks,('delayed-script','delayed-loss')):
            current={'mode':mode,'test':name,'repetition':1}
            result=unittest.TestResult();cls(name).run(result)
            current.update(passed=result.wasSuccessful(),failures=len(result.failures),errors=len(result.errors))
            if result.failures or result.errors:current['detail']=(result.failures+result.errors)[0][1].strip().splitlines()[-1]
            observations.append(current)
    finally:
        module.IntroCase.tearDownClass()
        module.IntroCase.page=original_page
    report={'revision':args.revision,'browser':'Chromium/SwiftShader via existing IntroCase',
            'intro_sha256':hashlib.sha256((args.root/'site/preview/intro.js').read_bytes()).hexdigest(),
            'test_sha256':hashlib.sha256((args.root/'tests/test_homepage_intro.py').read_bytes()).hexdigest(),
            'observations':observations,'negative_controls':'Deliberately delayed scheduling; expected failures, not production behaviour changes or verification passes'}
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2))
    real=[x for x in observations if x['mode']=='real-time']
    print(f"{args.revision}: {sum(x['passed'] for x in real)}/{len(real)} original real-time checks passed; negative controls recorded separately")


if __name__=='__main__':main()
