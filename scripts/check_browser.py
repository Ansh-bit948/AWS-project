"""Real-browser verification; no mocked analytics and no fabricated review feedback."""
import argparse
import json
from pathlib import Path
import sys
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--skip-upload',action='store_true')
    args=parser.parse_args()
    modes=['local','aws']
    report={}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        for mode in modes:
            page=browser.new_page(viewport={'width':1440,'height':1000})
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1:8000/?mode='+mode)
            if mode=='aws':
                creds=json.loads((ROOT/'.local/demo-login.json').read_text(encoding='utf-8'))
                page.locator('#loginOpen').click()
                page.locator('#loginForm input[name=username]').fill(creds['username'])
                page.locator('#loginForm input[name=password]').fill(creds['password'])
                page.locator('#loginForm button[type=submit],#loginForm button.btn.full').click()
            page.wait_for_function("document.querySelector('#status').textContent.startsWith('Connected to')",timeout=60000)
            if mode=='aws' and not args.skip_upload:
                page.locator('#importOpen').click()
                page.locator('#uploadForm input[name=name]').fill('Firewall1 browser-verified demo')
                page.locator('#uploadForm input[name=source_url]').fill('https://onlinerbacfixing.github.io/cybersecurity2019/')
                page.locator('#uploadForm input[name=license_note]').fill('CC BY 4.0; published RBAC Maintenance variant')
                page.locator('#uploadForm input[name=file]').set_input_files(str(ROOT/'data/processed/firewall1_upa.csv'))
                page.locator('#uploadForm button[type=submit]').click()
                page.locator('#importDialog').wait_for(state='hidden',timeout=120000)
                page.wait_for_function("document.querySelector('#status').textContent.startsWith('Connected to')",timeout=60000)

            assert page.locator('#mUsers').inner_text()=='365'
            assert page.locator('#mEdges').inner_text()=='31,919'
            assert page.locator('#wOpt').inner_text()=='4,512'
            page.locator('nav [data-view=roles]').click()
            assert page.locator('#viewTitle').inner_text().startswith('Role catalog')
            page.locator('#rolesNext').click()
            page.wait_for_function("document.querySelector('#rolesPage').textContent.startsWith('26')",timeout=15000)
            page.locator('#rolesBody button').first.click()
            page.locator('#roleDialog').wait_for(state='visible')
            page.locator('#roleDialog .raw-evidence summary').click()
            role=json.loads(page.locator('#roleDetail').inner_text())
            assert role['users'] and role['permissions']
            page.locator('#closeRole').click()
            page.locator('nav [data-view=governance]').click()
            page.locator('#authorizationForm input[name=user_id]').fill(role['users'][0])
            page.locator('#authorizationForm input[name=permission_id]').fill(role['permissions'][0])
            page.locator('#authorizationForm button').click()
            page.wait_for_function("document.querySelector('#authResult').textContent.startsWith('ALLOWED')",timeout=15000)
            page.locator('nav [data-view=dataset]').click()
            assert page.locator('#license').inner_text()
            assert len(page.locator('#hash').inner_text())==64
            page.locator('nav [data-view=temporal]').click()
            assert page.locator('#train').is_visible()
            page.locator('nav [data-view=overview]').click()
            assert page.locator('#wCohort').inner_text()=='9,787'
            assert page.locator('#baseBar').evaluate('e=>e.style.width')=='100%'
            assert not errors,errors
            screenshots=ROOT/'docs/screenshots';screenshots.mkdir(exist_ok=True)
            page.wait_for_function("getComputedStyle(document.querySelector('#overview')).opacity === '1'")
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(screenshots/(mode+'-desktop.png')),full_page=True)
            if mode=='local':page.screenshot(path=str(screenshots/'frontend-preview.png'))
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+2')
            page.locator('#menuOpen').click()
            assert page.locator('#menuOpen').get_attribute('aria-expanded')=='true'
            page.locator('nav [data-view=profiles]').click()
            assert page.locator('#menuOpen').get_attribute('aria-expanded')=='false'
            assert page.locator('#sidebar').evaluate('e=>e.inert')
            assert page.locator('#profiles').is_visible()
            page.locator('#menuOpen').click()
            page.locator('nav [data-view=overview]').click()
            page.go_back()
            assert page.locator('#profiles').is_visible()
            page.go_forward()
            assert page.locator('#overview').is_visible()
            page.wait_for_function("document.querySelector('#sidebar').getBoundingClientRect().right <= 1 && getComputedStyle(document.querySelector('#overview')).opacity === '1'")
            page.screenshot(path=str(screenshots/(mode+'-mobile.png')),full_page=True)
            report[mode]={'login':mode=='aws','browser_s3_upload':None if args.skip_upload else mode=='aws','read_only_frontend_check':args.skip_upload,'dedicated_view_navigation':True,'mobile_navigation':True,'keyboard_safe_mobile_sidebar':True,'source_based_wsc_chart':True,'measured_data_visible':True,'catalog_pagination':True,'role_evidence':True,
                          'authorization_check':True,'mobile_no_horizontal_overflow':True,'page_errors':errors}
            page.close()
        browser.close()
    (ROOT/'docs/browser-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()

\n