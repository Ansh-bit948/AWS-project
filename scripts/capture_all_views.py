"""Capture full screenshots of every view in the IEAI-ALP application for the final report."""
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS = ROOT / "docs" / "screenshots"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)

def main():
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    log = (ROOT / ".local" / "screenshot-server.log").open("w", encoding="utf-8")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=flags
    )
    try:
        # Wait for server ready
        for _ in range(50):
            if server.poll() is not None:
                raise RuntimeError("Uvicorn failed to start")
            try:
                with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("Server not ready in time")

        print("Server is up, launching Playwright...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1050})
            page.goto("http://127.0.0.1:8000/?mode=local")
            page.wait_for_function("document.querySelector('#status').textContent.startsWith('Connected')", timeout=30000)

            # 1. Overview
            print("Capturing Overview...")
            page.wait_for_selector("#mUsers")
            page.screenshot(path=str(SCREENSHOTS / "view_overview.png"), full_page=False)

            # 2. Roles Catalog
            print("Capturing Roles Catalog...")
            page.locator("nav [data-view=roles]").click()
            page.wait_for_selector("#rolesBody tr")
            time.sleep(0.5)
            page.screenshot(path=str(SCREENSHOTS / "view_roles_catalog.png"), full_page=False)

            # 3. Role Modal
            print("Capturing Role Detail Modal...")
            page.locator("#rolesBody button").first.click()
            page.locator("#roleDialog").wait_for(state="visible")
            time.sleep(0.5)
            page.screenshot(path=str(SCREENSHOTS / "view_role_modal.png"), full_page=False)
            page.locator("#closeRole").click()
            page.locator("#roleDialog").wait_for(state="hidden")

            # 4. User Profiles & Permissions
            print("Capturing User Profiles & Permissions...")
            page.locator("nav [data-view=profiles]").click()
            page.wait_for_selector("#profilesBody tr")
            time.sleep(0.5)
            page.screenshot(path=str(SCREENSHOTS / "view_profiles.png"), full_page=False)

            # 5. Risk & Review
            print("Capturing Risk & Review...")
            page.locator("nav [data-view=risk]").click()
            page.wait_for_selector("#findings .finding")
            time.sleep(0.5)
            page.screenshot(path=str(SCREENSHOTS / "view_risk_review.png"), full_page=False)

            # 6. Policy & Governance
            print("Capturing Policy & Governance...")
            page.locator("nav [data-view=governance]").click()
            # Perform authorization check
            page.locator("#authorizationForm input[name=user_id]").fill("U0001")
            page.locator("#authorizationForm input[name=permission_id]").fill("P0001")
            page.locator("#authorizationForm button").click()
            page.wait_for_selector("#authResult")
            time.sleep(0.5)
            page.screenshot(path=str(SCREENSHOTS / "view_governance.png"), full_page=False)

            # 7. Learning Lab
            print("Capturing Learning Lab...")
            page.locator("nav [data-view=temporal]").click()
            time.sleep(0.5)
            page.screenshot(path=str(SCREENSHOTS / "view_learning_lab.png"), full_page=False)

            # 8. Data Provenance
            print("Capturing Data Provenance...")
            page.locator("nav [data-view=dataset]").click()
            time.sleep(0.5)
            page.screenshot(path=str(SCREENSHOTS / "view_provenance.png"), full_page=False)

            browser.close()
            print("All screenshots successfully captured!")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
        log.close()
        print("Server stopped.")

if __name__ == "__main__":
    main()
