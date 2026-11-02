import argparse,json,shutil,zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8765');parser.add_argument('--output',type=Path,default=Path('outputs/browser-e2e'));parser.add_argument('--chromium',default=shutil.which('chromium'));args=parser.parse_args()
    output=args.output;output.mkdir(parents=True,exist_ok=True)
    errors=[];remote=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=args.chromium,headless=True,args=['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1440,'height':1100})
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda r:remote.append(r.url) if not r.url.startswith(args.url.rstrip('/')+'/') else None)
        page.goto(args.url,wait_until='networkidle')
        page.screenshot(path=str(output/'empty.png'),full_page=True)
        page.click('#analyze')
        page.wait_for_function('window.gemxResultReady===true || document.getElementById("status").classList.contains("error")',timeout=60000)
        assert page.evaluate('window.gemxResultReady===true'),page.locator('#status').inner_text()
        assert '60 frames' in page.locator('#validation').inner_text()
        page.wait_for_function('document.getElementById("fit-video").readyState>=1')
        assert page.evaluate('state.data.source')=='mujoco_myofullbody_fit'
        assert page.evaluate('state.data.coordinates.length')==122
        page.select_option('#coordinate','knee_angle_l')
        page.wait_for_function('document.getElementById("charts").data[0].name==="knee_angle_l"')
        page.select_option('#coordinate','cmc_flexion')
        assert 'vaste referentie' in page.locator('#coordinate-info').inner_text()
        page.click('#toggle-view')
        page.locator('#frame').evaluate("e=>{e.value=30;e.dispatchEvent(new Event('input'));}")
        page.wait_for_function('state.frame===30 && document.getElementById("skeleton").data[3].x[state.data.names.indexOf("ulna_l")]===state.data.positions[30][state.data.names.indexOf("ulna_l")][0]')
        page.click('#play');page.wait_for_function('state.frame>30',timeout=15000);page.click('#play')
        assert page.evaluate('state.frame')>30
        page.click('#reset-camera')
        with page.expect_download() as event:page.click('#download-zip')
        download=event.value;download.save_as(str(output/'resultaten.zip'))
        with zipfile.ZipFile(output/'resultaten.zip') as archive:
            assert archive.testzip() is None
            assert 'review/angles.csv' in archive.namelist()
            assert json.loads(archive.read('review/validation.json'))['frames']==60
        page.click('#toggle-view')
        page.select_option('#coordinate','shoulder_elv_l')
        page.screenshot(path=str(output/'complete.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(500)
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'),page.evaluate('document.documentElement.scrollWidth')
        page.screenshot(path=str(output/'mobile.png'),full_page=True)
        page.click('#video-tab')
        assert page.locator('#analyze').is_disabled()
        assert not errors,errors
        assert not remote,remote
        report={'status':'passed','checks':['actual MyoFullBody qpos source','60-frame MuJoCo validation','fitted model body coordinates update','play/pause','download ZIP integrity and CSV','mobile layout without overflow','video disabled when engine absent'],'javascript_errors':errors,'external_requests':remote,'browser':browser.version}
        (output/'browser-validation.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
        browser.close()

if __name__=='__main__':main()
