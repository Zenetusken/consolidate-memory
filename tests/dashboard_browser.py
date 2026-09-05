#!/usr/bin/env python3
"""Optional real-browser UI regression checks (dev-only Playwright + Chromium).

python3 tests/dashboard_browser.py --out /tmp/cm-browser
Does not read stores, persist cycles, or launch the user's default browser.
"""
from __future__ import annotations

import argparse
import copy
import importlib
import json
from pathlib import Path

from dashboard_fixture import sample, write_preview, rh


def main(out):
    sync_playwright = importlib.import_module("playwright.sync_api").sync_playwright
    out.mkdir(parents=True, exist_ok=True)
    preview = write_preview(out)
    results = []

    def check(name, value):
        results.append({"check": name, "passed": bool(value)})
        # Preserve the exact failure and all completed checks for CI artifacts.
        (out / "browser-results.json").write_text(json.dumps(results, indent=2)+"\n", encoding="utf-8")
        print(("PASS " if value else "FAIL ") + name)
        if not value:
            raise AssertionError(name)

    record, history, diffs = sample()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce", color_scheme="light")
        page = context.new_page()
        errors, requests = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda req: requests.append(req.url) if req.url.startswith(("http:", "https:")) else None)

        def ready(url):
            page.goto(url)
            page.wait_for_function("document.querySelector('#boot').style.display === 'none'")

        ready(preview.as_uri()+"#sel=7")
        check("default palette is midnight even under a light system preference",
              page.locator("body").evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(8, 15, 27)"
              and page.locator("#theme-tog").inner_text() == "● Nocturne")
        page.locator(".skip").focus()
        page.keyboard.press("Enter")
        check("skip link focuses the report without changing the selected dream", page.url.endswith("#sel=7") and page.locator("#app").evaluate("e => e === document.activeElement"))
        check("all original evidence surfaces have rendered", all(page.locator("#"+s).is_visible() for s in
              ("traj", "kpis", "net", "m-index", "m-cmd", "m-global", "trend", "rigor", "audit", "verify", "distill-blk", "demotion-blk", "registrar-blk", "entries", "dream-arc")))
        check("chain evidence and skill usage are visible", page.locator("#dstl-chains-list").is_visible()
              and "tests/contracts.py" in page.locator("#dstl-chains-list").inner_text()
              and "check-release" in page.locator("#dstl-used-list").inner_text()
              and page.locator("#dstl-used-list").is_visible())
        check("diagram keeps seven projects and four observed edges", page.locator(".net-node").count() == 7 and page.locator(".fact-edge").count() == 4)
        check("fact routes do not cross unrelated project boxes", page.locator(".fact-edge").evaluate_all("""edges => edges.every(e => {
            const unrelated=[...document.querySelectorAll('.net-node')].filter(n => n.dataset.node!==e.dataset.a && n.dataset.node!==e.dataset.b).map(n=>n.querySelector('rect').getBBox());
            const length=e.getTotalLength();
            for(let i=1;i<100;i++){const p=e.getPointAtLength(length*i/100);if(unrelated.some(r=>p.x>r.x-1 && p.x<r.x+r.width+1 && p.y>r.y-1 && p.y<r.y+r.height+1))return false;}
            return true;
        })"""))
        check("three domains have visible containers", page.locator(".domain-zone").count() == 3)
        page.get_by_role("button", name="Group / release-kit", exact=True).click()
        check("group selects only three granted projects", page.locator(".net-node.selected").count() == 3 and page.locator(".net-node.dim").count() == 4)
        check("permission routes stay distinct from observed holdings", page.locator(".grant-edge").count() == 2
              and all(t in page.locator("#net-detail").inner_text() for t in ("permission only", "3 captured group members", "group show")))
        page.get_by_role("button", name="Group / api-contract", exact=True).click()
        check("same-domain group excludes the third work project", page.locator(".net-node.selected").count() == 2 and "team-docs" not in " ".join(page.locator(".net-node.selected").all_text_contents()))
        page.get_by_role("button", name="Shared facts", exact=True).click()
        node = page.locator('.net-node[data-current="true"]')
        node.focus()
        check("keyboard focus exposes the node's token evidence", "984 always-loaded tokens" in page.locator("#net-detail").inner_text())
        page.locator(".fact-edge").first.focus()
        check("unnamed production edges keep an explicit capture boundary", "fact names were not captured" in page.locator("#net-detail").inner_text())
        page.locator('.fact-edge[data-a="eval-lab"][data-b="release-tools"]').focus()
        check("named differential edge preserves its captured evidence", "benchmark-reproducibility" in page.locator("#net-detail").inner_text())
        page.locator("#network-data summary").click()
        check("complete network inventory preserves costs, grants and fact names", all(t in page.locator("#network-data-body").inner_text() for t in
              ("Mirror index", "Recall", "release-kit", "artifact-provenance", "eval-lab", "work")))
        group_table = page.locator("#network-data-body table").nth(1)
        check("group inventory labels the captured membership basis", "Captured group members" in group_table.inner_text()
              and "Granted members" not in group_table.inner_text())
        check("production group facts never invent holder measurements", all("held" not in f for gr in record["network"]["group_links"] for f in gr["facts"])
              and "work / release-checks" in group_table.inner_text() and "(0)" not in group_table.inner_text()
              and "Facts addressed to group" in group_table.inner_text())
        page.locator("#network-data summary").click()
        check("raw captured record retains every source subtree",
              all(json.loads(page.locator("#record-json").text_content())[key] == value for key, value in record.items()))
        page.locator(".nm-diff").first.click()
        check("diff opens with proper semantics and focus", page.get_by_role("dialog").is_visible()
              and page.locator("#dmodal-x").evaluate("e => e === document.activeElement")
              and page.locator("#app").evaluate("e => e.inert"))
        page.keyboard.press("Tab")
        check("diff traps keyboard focus", page.locator("#dmodal-x").evaluate("e => e === document.activeElement"))
        page.keyboard.press("Escape")
        check("diff closes and restores focus to its file", not page.get_by_role("dialog").is_visible()
              and page.locator(".nm-diff").first.evaluate("e => e === document.activeElement")
              and not page.locator("#app").evaluate("e => e.inert"))
        page.locator("#pass-blk > .shead").focus()
        page.keyboard.press("Enter")
        check("keyboard collapse hides the panel", not page.locator("#audit").is_visible())
        page.get_by_role("button", name="Verification & health", exact=True).first.click()
        check("section navigation expands a collapsed panel", page.locator("#audit").is_visible())
        page.locator("#dens-tog").click()
        page.keyboard.press("ArrowLeft")
        page.wait_for_function("location.hash === '#sel=6' && document.querySelector('#dreamnav .pos').textContent.includes('dream 7 /')")
        check("cycle navigation preserves density and resets grant overlays", page.locator("body").evaluate("e => e.classList.contains('compact')") and page.locator(".grant-edge").count() == 0)
        page.keyboard.press("ArrowRight")
        page.wait_for_function("location.hash === '#sel=7' && document.querySelector('#dreamnav .pos').textContent.includes('dream 8 /')")
        check("chain evidence survives cycle navigation", page.locator("#dstl-chains-list").is_visible())
        page.locator("#dens-tog").click()
        page.keyboard.press("Escape")
        page.wait_for_function("document.querySelector('#archive').style.display !== 'none'")
        check("archive retains all eight cycles", page.locator(".arch-row").count() == 8)
        page.locator("#f-sort").select_option("tsRaw:1")
        check("archive oldest-first order is functional", page.locator(".arch-row").first.get_attribute("href") == "#sel=0")
        page.locator("#f-rig").select_option("SUBSTANTIAL")
        check("archive rigor filter stays functional", "shown" in page.locator("#f-count").inner_text() and page.locator(".arch-row").count() == 8)
        page.screenshot(path=str(out / "archive-desktop.png"), full_page=True)
        for width in (320, 390, 768):
            page.set_viewport_size({"width": width, "height": 900})
            check("archive has no page overflow at %dpx" % width, page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            check("archive columns remain accessible at %dpx" % width, page.locator(".arch-row").first.locator(".hh").is_visible() and page.locator(".arch-row").first.locator(".en").is_visible())
        page.locator('a.arch-row[href="#sel=7"]').click()
        page.wait_for_function("location.hash === '#sel=7' && document.querySelector('#dreamnav .pos').textContent.includes('dream 8 /')")
        for width in (320, 390, 768, 1440):
            page.set_viewport_size({"width": width, "height": 1000})
            check("report has no page overflow at %dpx" % width, page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            check("all node labels fit their domain lane at %dpx" % width,
                  page.locator(".net-node text").evaluate_all("es => es.every(e => { const p=e.parentNode.querySelector('rect').getBBox(), b=e.getBBox(); return b.x>=p.x && b.x+b.width<=p.x+p.width; })"))
            if width in (390, 1440):
                page.screenshot(path=str(out / ("report-mobile.png" if width == 390 else "report-desktop.png")), full_page=True)
        page.evaluate("scrollTo(0,0)")
        page.screenshot(path=str(out / "report-cover.png"))
        page.locator("#theme-tog").click()
        original_palette = {
            "paper": "#15120d", "paper2": "#1e1913", "card": "#1c1711", "rule": "#332c22", "rule2": "#493f30",
            "ink": "#ece4d2", "ink2": "#b4a98e", "faint": "#9a8d74", "ghost": "#8e816a",
            "accent": "#d96a3f", "data": "#5fa996", "ok": "#7cae65", "warn": "#d4a24d", "crit": "#d96a3f", "glow": "#221b13",
            "tint-ok": "rgba(95,169,150,.16)", "tint-crit": "rgba(217,106,63,.12)",
            "tint-accent": "rgba(217,106,63,.09)", "tint-warn": "rgba(212,162,77,.10)"}
        check("Original visibly identifies the preserved dark palette", page.locator("html").get_attribute("data-theme") == "original"
              and page.locator("#theme-tog").inner_text() == "◒ Original"
              and page.locator("#theme-tog").get_attribute("aria-label") == "Color theme: Original. Switch to Light")
        check("Original preserves every previous production color and tint", page.locator("html").evaluate(
            "(e, expected) => Object.entries(expected).every(([k,v]) => getComputedStyle(e).getPropertyValue('--'+k).trim() === v)", original_palette))
        check("Original is dark under a light system preference", page.locator("body").evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(21, 18, 13)"
              and page.locator("html").evaluate("e => getComputedStyle(e).colorScheme") == "dark")
        page.screenshot(path=str(out / "report-original.png"), full_page=True)
        page.reload()
        page.wait_for_function("document.querySelector('#boot').style.display === 'none'")
        check("Original persists on reload", page.locator("html").get_attribute("data-theme") == "original"
              and page.evaluate("localStorage.getItem('cm-theme')") == "original")
        check("theme selection leaves captured evidence intact", all(json.loads(page.locator("#record-json").text_content())[key] == value for key, value in record.items()))
        for width in (320, 390):
            page.set_viewport_size({"width": width, "height": 900})
            check("Original control stays within the viewport at %dpx" % width, page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                  and page.locator("#theme-tog").evaluate("e => {const r=e.getBoundingClientRect(); return r.left>=0 && r.right<=innerWidth;}"))
        page.set_viewport_size({"width": 1440, "height": 1000})

        def check_print(mode):
            page.emulate_media(media="print")
            check(mode+" prints with readable text and white surfaces", page.locator("body").evaluate("e => getComputedStyle(e).color") == "rgb(23, 43, 67)"
                  and page.locator("html").evaluate("e => getComputedStyle(e).getPropertyValue('--paper').trim()") == "#ffffff"
                  and page.locator("html").evaluate("e => getComputedStyle(e).colorScheme") == "light")
            page.emulate_media(media="screen")

        check_print("Original")
        page.locator("#theme-tog").click()
        check("light theme works", page.locator("html").get_attribute("data-theme") == "light")
        page.screenshot(path=str(out / "report-light.png"))
        check_print("Light")
        page.locator("#theme-tog").click()
        check("System follows a light preference", page.locator("html").get_attribute("data-theme") == "auto"
              and page.locator("body").evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(237, 242, 247)")
        check_print("System light")
        page.emulate_media(color_scheme="dark")
        check("System responds to a changed dark preference", page.locator("body").evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(8, 15, 27)")
        check_print("System dark")
        page.locator("#theme-tog").click()
        check("four-mode toggle returns to Nocturne", page.locator("html").get_attribute("data-theme") == "dark"
              and page.locator("#theme-tog").inner_text() == "● Nocturne")
        check_print("Nocturne")
        check("reduced motion disables chart animation", page.locator(".draw").first.evaluate("e => getComputedStyle(e).animationName") == "none")

        # Isolate the head's bootstrap: these assertions cannot be rescued by the
        # later application script, so a saved palette is applied before paint.
        head_preview = out / "theme-before-paint.html"
        head_preview.write_text(preview.read_text(encoding="utf-8").split("</head>", 1)[0]+"</head><body></body></html>", encoding="utf-8")
        for saved, scheme, expected in (("original", "light", "rgb(21, 18, 13)"), ("dark", "light", "rgb(8, 15, 27)"),
                                        ("light", "dark", "rgb(237, 242, 247)"), ("auto", "light", "rgb(237, 242, 247)"),
                                        ("auto", "dark", "rgb(8, 15, 27)"), ("unknown", "light", "rgb(8, 15, 27)")):
            themed = browser.new_context(color_scheme=scheme)
            themed.add_init_script("localStorage.setItem('cm-theme', %s)" % json.dumps(saved))
            first_paint = themed.new_page()
            first_paint.goto(head_preview.as_uri())
            check("saved %s with %s system restores before application startup" % (saved, scheme),
                  first_paint.locator("body").evaluate("e => getComputedStyle(e).backgroundColor") == expected)
            themed.close()
        unavailable = browser.new_context()
        unavailable.add_init_script("Object.defineProperty(window, 'localStorage', {get(){throw new DOMException('Storage unavailable', 'SecurityError');}})")
        ephemeral = unavailable.new_page()
        ephemeral.goto(preview.as_uri()+"#sel=7")
        ephemeral.wait_for_function("document.querySelector('#boot').style.display === 'none'")
        ephemeral.locator("#theme-tog").click()
        check("Original works when browser persistence is unavailable", ephemeral.locator("html").get_attribute("data-theme") == "original"
              and ephemeral.locator("#net").is_visible())
        unavailable.close()

        cases = {}
        empty = copy.deepcopy(record); empty["network"]["nodes"] = []
        cases["empty-fleet"] = empty
        sparse = {"project": "legacy", "marker": {"commit": "abc", "timestamp": "2026-01-01"}}
        cases["sparse"] = sparse
        partial = copy.deepcopy(record)
        partial["verification"] = {"corrected": 2, "unverifiable": 3}
        partial["health"] = {"broken": ["missing-source-fact"], "dangling_links": []}
        cases["partial-evidence"] = partial
        confirmed_only = copy.deepcopy(record)
        confirmed_only["verification"] = {"confirmed": 4}
        cases["partial-confirmed"] = confirmed_only
        empty_measurements = copy.deepcopy(record)
        empty_measurements["budget"]["claude_md"] = {}
        for key in ("audit", "usage", "remediation"):
            empty_measurements[key] = {}
        cases["empty-measurements"] = empty_measurements
        legacy_lines = copy.deepcopy(record)
        legacy_lines["budget"]["claude_md"] = {"before": 12, "after": 10}
        cases["legacy-line-budget"] = legacy_lines
        partial_measurements = copy.deepcopy(record)
        partial_measurements["budget"]["claude_md"] = {"before_tokens": 1250}
        partial_measurements["audit"] = {"operations": [{"path": "retained-fact.md", "op": "modified"}]}
        partial_measurements["usage"] = {"mentions": 2}
        partial_measurements["remediation"] = {"over_ceiling": True}
        cases["partial-measurements"] = partial_measurements
        partial_audit = copy.deepcopy(record)
        partial_audit["audit"] = {"memory": {"created": 1}}
        partial_audit["remediation"] = {"pruned": 2}
        cases["partial-audit-counts"] = partial_audit
        measured_zero = copy.deepcopy(record)
        measured_zero["budget"]["claude_md"] = {"after_tokens": 0}
        measured_zero["budget"]["claude_md_hierarchy"] = {}
        measured_zero["audit"] = {key: dict(created=0, modified=0, deleted=0, token_delta=0) for key in ("memory", "claude_md", "repo_doc")}
        measured_zero["usage"] = {"reads": 0, "facts_read": 0, "transcripts": 0, "mentions": 0}
        measured_zero["remediation"] = {"required": False, "over_ceiling": False}
        cases["measured-zero"] = measured_zero
        legacy = copy.deepcopy(record); legacy["network"].pop("basis_scope")
        cases["legacy-network"] = legacy
        single = copy.deepcopy(record); single["network"]["nodes"] = single["network"]["nodes"][:1]
        cases["single-node"] = single
        large = copy.deepcopy(record)
        large["network"]["nodes"] = [dict(record["network"]["nodes"][0], node="project-%02d" % i, trigger=i==0) for i in range(25)]
        cases["large-fleet"] = large
        hostile = copy.deepcopy(record)
        hostile["network"]["nodes"][0]["node"] = '</script><img src=x onerror="window.PWNED=1">'
        hostile["entries"][0]["reason"] = '<img src=x onerror="window.PWNED=1">'
        cases["hostile"] = hostile
        warning = copy.deepcopy(record)
        warning["budget"]["index"]["after_tokens"] = 4100
        warning["budget"]["index"]["over"] = True
        warning["remediation"] = {"required": True, "over_ceiling": True}
        warning["verification"] = {"confirmed": 0, "corrected": 0, "unverifiable": 0}
        cases["warnings"] = warning
        local = copy.deepcopy(record); local.pop("network")
        local["identity"] = {"domain_id": "unknown", "enrolled": False, "cross_project_allowed": False, "registry_state": "healthy"}
        cases["local-only"] = local
        for name, rec in cases.items():
            path=out / (name+".html")
            path.write_text(rh.build_html(rec, [], "2026-09-05"), encoding="utf-8")
            ready(path.as_uri()+"#sel=0")
            check(name+" renders without exceptions", not errors)
            check(name+" stays contained", page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            if name == "empty-fleet":
                check("empty fleet distinguishes missing rows from zero holdings", "No project rows" in page.locator("#net").text_content())
            if name == "sparse":
                check("absent measurements do not claim healthy zeroes", "not measured" in page.locator("#lead-head").inner_text() and "Not captured" in page.locator("#verify").inner_text())
            if name == "partial-evidence":
                claims = page.locator("#verify .audit-ln").filter(has=page.locator('.s', has_text="claims verified")).inner_text()
                pointer = page.locator("#verify .audit-ln").filter(has=page.locator('.s', has_text="index pointers"))
                check("partial verification retains corrections and unverifiable claims", "2 corrected" in claims and "3 unverifiable" in claims
                      and "confirmed: not captured" in claims and "0 confirmed" not in claims)
                check("partial health retains known broken pointers and warning color", "missing-source-fact" in pointer.inner_text()
                      and "broken" in pointer.inner_text() and "all resolve" not in pointer.inner_text()
                      and pointer.locator(".nums").evaluate("e => getComputedStyle(e).color") == "rgb(240, 163, 166)")
            if name == "partial-confirmed":
                claims = page.locator("#verify .audit-ln").filter(has=page.locator('.s', has_text="claims verified")).inner_text()
                check("partial verification distinguishes missing counters from measured zero", "4 confirmed" in claims
                      and "corrected: not captured" in claims and "unverifiable: not captured" in claims
                      and "0 corrected" not in claims and "0 unverifiable" not in claims)
            if name == "empty-measurements":
                check("empty containers never claim measured budget or audit success", "not captured" in page.locator("#m-cmd").inner_text()
                      and "Within budget" not in page.locator("#m-cmd").inner_text()
                      and "not captured" in page.locator("#audit").inner_text() and "No file mutations" not in page.locator("#audit").inner_text())
                check("empty usage and remediation remain explicitly unknown", "Usage counts not captured" in page.locator("#verify").inner_text()
                      and "Prune requirement not captured" in page.locator("#verify").inner_text())
            if name == "legacy-line-budget":
                check("legacy line counts retain their units without inventing token cost", "12 → 10 lines" in page.locator("#m-cmd").inner_text()
                      and "Token budget not captured" in page.locator("#m-cmd").inner_text() and "Within budget" not in page.locator("#m-cmd").inner_text())
            if name == "partial-measurements":
                check("before-only token evidence does not imply an after-pass budget verdict", "Before pass: 1.3k estimated tokens" in page.locator("#m-cmd").inner_text()
                      and "not captured" in page.locator("#m-cmd").inner_text() and "Within budget" not in page.locator("#m-cmd").inner_text())
                check("operations survive missing aggregate audit counts", "retained-fact.md" in page.locator("#audit").inner_text()
                      and "modified" in page.locator("#audit").inner_text() and "token change not captured" in page.locator("#audit").inner_text()
                      and "No file mutations" not in page.locator("#audit").inner_text())
                usage = page.locator("#verify .audit-ln").filter(has=page.locator('.s', has_text="usage")).inner_text()
                check("mention-only usage never invents zero reads or transcripts", "2 mentions" in usage and "other usage counts not captured" in usage
                      and "0 organic reads" not in usage and "0 transcripts" not in usage)
                pressure = page.locator("#verify .audit-ln").filter(has=page.locator('.s', has_text="index pressure"))
                check("hard-ceiling evidence remains a warning without a required flag", "over hard ceiling" in pressure.inner_text()
                      and "clear" not in pressure.inner_text() and pressure.locator(".nums").evaluate("e => getComputedStyle(e).color") == "rgb(240, 163, 166)")
            if name == "partial-audit-counts":
                audit_row = page.locator("#audit .audit-row").nth(1)
                check("partial audit counts preserve known values and mark missing cells", audit_row.locator(".a-added").inner_text()=="1"
                      and audit_row.locator(".a-corrected").inner_text()=="—" and audit_row.locator(".a-deleted").inner_text()=="—"
                      and audit_row.locator(".tk").inner_text()=="—")
                pressure = page.locator("#verify .audit-ln").filter(has=page.locator('.s', has_text="index pressure")).inner_text()
                check("partial remediation preserves actions without inventing clearance", "Prune requirement not captured" in pressure and "2 pruned" in pressure and "clear" not in pressure)
            if name == "measured-zero":
                check("captured zero remains distinct from absent measurements", "0/4.0k" in page.locator("#m-cmd").inner_text()
                      and "Within budget" in page.locator("#m-cmd").inner_text() and "No file mutations detected" in page.locator("#audit").inner_text())
                check("measured zero usage and explicit clearance stay visible", "0 organic reads" in page.locator("#verify").inner_text()
                      and "0 mentions" in page.locator("#verify").inner_text()
                      and "clear" in page.locator("#verify .audit-ln").filter(has=page.locator('.s', has_text="index pressure")).inner_text())
            if name == "single-node":
                check("single-domain topology remains visible", page.locator(".domain-zone").count() == 1 and page.locator(".net-node").count() == 1)
            if name == "large-fleet":
                check("25-node payload has 16 drawn and 25 inventoried", page.locator(".net-node").count() == 16 and page.locator("#network-data-body table").first.locator("tbody tr").count() == 25)
            if name == "hostile":
                check("hostile strings stay inert", page.evaluate("!window.PWNED && !document.querySelector('img')"))
            if name == "warnings":
                check("hard ceiling and integrity warnings remain visible", "hard ceiling" in page.locator("#lead-head").inner_text() and "Procedure integrity" in page.locator("#verify").inner_text())
                page.screenshot(path=str(out / "warnings.png"), full_page=True)
            if name == "local-only":
                check("local-only state preserves enrollment guidance", "local-only" in page.locator("#h-banners").inner_text().lower() and "/cm-domain" in page.locator("#h-banners").inner_text())

        # A navigation regression requires different source arrays in adjacent
        # cycles; repeating the same rich fixture cannot expose stale DOM rows.
        no_workflows = copy.deepcopy(record)
        no_workflows["marker"] = {"commit": "earlier", "timestamp": "2026-09-04T14:30:00Z"}
        no_workflows["distill"]["top_chains"] = []
        no_workflows["distill"]["used"] = []
        no_workflows["distill"]["n_chains"] = 0
        transition = out / "workflow-transition.html"
        transition.write_text(rh.build_html(record, [no_workflows], "2026-09-05"), encoding="utf-8")
        ready(transition.as_uri()+"#sel=1")
        check("workflow navigation starts with captured chains and adoption", page.locator("#dstl-chains-list").is_visible()
              and page.locator("#dstl-used-list").is_visible())
        page.keyboard.press("ArrowLeft")
        page.wait_for_function("document.querySelector('#dreamnav .pos').textContent.includes('dream 1 /')")
        check("empty cycle clears preceding workflow evidence without hiding its recurring commands", page.locator("#dstl-top-list").is_visible()
              and not page.locator("#dstl-chains-list").is_visible() and not page.locator("#dstl-used-list").is_visible()
              and page.locator("#dstl-chains-list").text_content() == "" and page.locator("#dstl-used-list").text_content() == "")
        page.keyboard.press("ArrowRight")
        page.wait_for_function("document.querySelector('#dreamnav .pos').textContent.includes('dream 2 /')")
        check("returning to the populated cycle restores its own workflow evidence", page.locator("#dstl-chains-list").is_visible()
              and "tests/contracts.py" in page.locator("#dstl-chains-list").inner_text() and page.locator("#dstl-used-list").is_visible()
              and "check-release" in page.locator("#dstl-used-list").inner_text())

        # Exercise all 120 pairs, including distant diagonal edges, same-column
        # peers, adjacent cards, and multiple rows inside uneven domain lanes.
        collision_free = """edges => edges.every(e => {
            const boxes=[...document.querySelectorAll('.net-node')].filter(n => n.dataset.node!==e.dataset.a && n.dataset.node!==e.dataset.b).map(n=>n.querySelector('rect').getBBox());
            const length=e.getTotalLength();
            for(let distance=1;distance<length;distance+=2){const p=e.getPointAtLength(distance);if(boxes.some(r=>p.x>r.x && p.x<r.x+r.width && p.y>r.y && p.y<r.y+r.height))return false;}
            return true;
        })"""
        for topology, domain_of in (("four-domains", lambda i: "domain-%d" % (i//4)),
                                    ("one-domain-four-rows", lambda i: "work"),
                                    ("uneven-domains", lambda i: "work" if i<10 else "tools")):
            routing=copy.deepcopy(record)
            nodes=[dict(record["network"]["nodes"][0], node="project-%02d" % i, domain=domain_of(i),
                        groups=["routing-test"], trigger=i==0) for i in range(16)]
            routing["network"].update(nodes=nodes, domains=[{"domain": d} for d in sorted({n["domain"] for n in nodes})],
                stack_edges=[{"a": nodes[i]["node"], "b": nodes[j]["node"], "n": 1} for i in range(16) for j in range(i+1,16)],
                stack_edge_facts=[], group_links=[{"group": "routing-test", "home_domain": domain_of(0), "members_n": 16, "facts": []}])
            path=out / ("routing-"+topology+".html")
            path.write_text(rh.build_html(routing, [], "2026-09-05"), encoding="utf-8")
            ready(path.as_uri()+"#sel=0")
            check(topology+" keeps every observed route outside unrelated project cards", page.locator(".fact-edge").count()==120
                  and page.locator(".fact-edge").evaluate_all(collision_free))
            page.get_by_role("button", name="Group / routing-test", exact=True).click()
            check(topology+" keeps every group route outside unrelated project cards", page.locator(".grant-edge").count()==15
                  and page.locator(".grant-edge").evaluate_all(collision_free))
            page.screenshot(path=str(out / ("routing-"+topology+".png")), full_page=True)
        check("all report transitions finish without browser errors", not errors)
        check("no report makes external network requests", not requests)
        browser.close()
    (out / "browser-results.json").write_text(json.dumps(results, indent=2)+"\n", encoding="utf-8")
    print("%d browser checks passed" % len(results))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    main(parser.parse_args().out.resolve())
