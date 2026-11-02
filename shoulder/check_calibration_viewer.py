"""Optional offline Chromium smoke check for the generated calibration viewer."""
import argparse
import json
from pathlib import Path
import shutil
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--screenshot',type=Path,required=True)
    parser.add_argument('--chromium',default=shutil.which('chromium'))
    args=parser.parse_args()
    errors=[]; requests=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=args.chromium,headless=True,args=['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1500,'height':1200})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:requests.append(r.url))
        # Loads local generated content without a server or remote dependencies.
        page.set_content(args.html.read_text(),wait_until='load',timeout=60000)
        page.wait_for_function('window.calibrationReady===true',timeout=60000)
        assert page.locator('canvas').count()>0
        def check_equal_scale():
            ratios=page.evaluate('''(()=>{const s=document.getElementById("plot").layout.scene;return ["x","y","z"].map(a=>s.aspectratio[a]/(s[a+"axis"].range[1]-s[a+"axis"].range[0]));})()''')
            assert max(ratios)-min(ratios)<1e-10,ratios
        check_equal_scale()
        assert page.evaluate('document.getElementById("plot").data.filter(t=>t.visible===true).length')==21
        page.select_option('#pose','1')
        page.wait_for_function('document.getElementById("plot").layout.title.text.includes("Modelreferentie")')
        assert page.evaluate('document.getElementById("plot").data.slice(0,33).every(t=>t.visible===false)')
        assert page.evaluate('document.getElementById("plot").data.slice(33).every(t=>t.visible===true || t.visible==="legendonly")')
        page.select_option('#pose','0')
        page.wait_for_function('document.getElementById("plot").layout.title.text.includes("Beginhouding")')
        legend=page.locator('.legend .traces').filter(has_text='Vaste mesh-kalibratie').first
        legend.locator('.legendtoggle').click()
        page.wait_for_function('document.getElementById("plot").data.filter(t=>t.legendgroup==="mesh_fixed0").every(t=>t.visible===true)')
        legend.locator('.legendtoggle').click()
        page.wait_for_function('document.getElementById("plot").data.filter(t=>t.legendgroup==="mesh_fixed0").every(t=>t.visible==="legendonly")')
        for view in ['front','right','top','oblique']:
            page.click('[data-camera="'+view+'"]')
            page.wait_for_timeout(250)
        page.click('#whole')
        page.wait_for_function('document.getElementById("plot").layout.scene.zaxis.range[0]<-1')
        check_equal_scale()
        page.click('#shoulders')
        page.wait_for_function('document.getElementById("plot").layout.scene.zaxis.range[0]===-.25')
        check_equal_scale()
        before=page.evaluate('JSON.stringify(document.getElementById("plot").layout.scene.camera)')
        box=page.locator('#plot').bounding_box()
        page.mouse.move(box['x']+box['width']*.35,box['y']+box['height']*.4)
        page.mouse.down();page.mouse.move(box['x']+box['width']*.45,box['y']+box['height']*.5,steps=12);page.mouse.up()
        page.wait_for_timeout(500)
        after=page.evaluate('JSON.stringify(document.getElementById("plot").layout.scene.camera)')
        assert before!=after,'Mouse drag did not rotate the camera'
        page.click('[data-camera="oblique"]')
        page.wait_for_timeout(1000)
        args.screenshot.parent.mkdir(parents=True,exist_ok=True)
        page.locator('#plot').screenshot(path=str(args.screenshot))
        assert not errors,errors
        assert not [r for r in requests if r.startswith(('http:','https:'))],requests
        report=dict(status='passed',javascript_errors=errors,external_requests=0,
            checks=['WebGL canvas created','21 visible + 12 optional start traces','pose selector switches all 66 traces','mesh axis legend toggles both sides','four camera buttons','whole-body and shoulder zoom','mouse rotation','equal spatial scale in overview and shoulder zoom'],browser=browser.version)
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
        browser.close()


if __name__=='__main__':main()
