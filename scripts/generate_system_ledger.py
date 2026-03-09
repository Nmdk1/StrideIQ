import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
WEB_ROOT = ROOT / "apps" / "web"


ROUTER_ENDPOINT_RE = re.compile(r'@router\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)')
ROUTER_PREFIX_RE = re.compile(r'APIRouter\([^\)]*prefix\s*=\s*["\']([^"\']+)')
DEF_RE = re.compile(r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
FRONTEND_API_REF_RE = re.compile(r'[`"\'](/v[12]/[^`"\']*)[`"\']')
HREF_RE = re.compile(r'href=["\'](/[^"\']*)["\']')
ROUTER_PUSH_RE = re.compile(r'router\.push\(["\'](/[^"\']*)["\']\)')
HOOK_DEF_RE = re.compile(r"export\s+function\s+(use[A-Z][a-zA-Z0-9_]*)\s*\(")


@dataclass
class RouteEntry:
    method: str
    path: str
    file: str
    function: Optional[str]
    runtime_registered: bool
    frontend_consumed: bool
    status: str
    failure_reason: str
    owner: str
    fix_priority: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _normalize_dynamic_path(path: str) -> str:
    base = path.split("?")[0]
    base = re.sub(r"\$\{[^}]+\}", "SEG", base)
    base = base.replace("*", "SEG")
    base = (
        base.replace("[id]", "SEG")
        .replace("[activityId]", "SEG")
        .replace("[slug]", "SEG")
        .replace("[distance]", "SEG")
        .replace("[conversion]", "SEG")
    )
    return base


def _route_pattern(path: str) -> re.Pattern:
    p = path.split("?")[0]
    p = re.sub(r"\{[^}]+\}", "[^/]+", p)
    return re.compile("^" + p + "$")


def _collect_backend_routes() -> List[Dict]:
    routes: List[Dict] = []
    for router_file in sorted((API_ROOT / "routers").glob("*.py")):
        if router_file.name == "__init__.py":
            continue
        text = _read_text(router_file)
        prefix_match = ROUTER_PREFIX_RE.search(text)
        prefix = prefix_match.group(1) if prefix_match else ""
        defs = [(m.start(), m.group(1)) for m in DEF_RE.finditer(text)]

        for endpoint in ROUTER_ENDPOINT_RE.finditer(text):
            method, sub_path = endpoint.group(1).upper(), endpoint.group(2)
            full_path = (prefix.rstrip("/") + "/" + sub_path.lstrip("/")).replace("//", "/")
            fn = None
            ep_pos = endpoint.end()
            for dpos, dname in defs:
                if dpos > ep_pos:
                    fn = dname
                    break
            routes.append(
                {
                    "method": method,
                    "path": full_path,
                    "file": _rel(router_file),
                    "function": fn,
                    "router_symbol": router_file.stem,
                }
            )
    return routes


def _collect_runtime_paths() -> Set[str]:
    sys.path.insert(0, str(API_ROOT))
    import main  # type: ignore

    return {getattr(r, "path", "") for r in main.app.routes if getattr(r, "path", None)}


def _collect_frontend_api_refs() -> List[Dict]:
    refs: List[Dict] = []
    for ts_file in sorted(WEB_ROOT.rglob("*.ts*")):
        rel = _rel(ts_file)
        if "/__tests__/" in rel or rel.endswith(".test.ts") or rel.endswith(".test.tsx"):
            continue
        text = _read_text(ts_file)
        for m in FRONTEND_API_REF_RE.finditer(text):
            raw = m.group(1)
            if raw.startswith("/v1/") or raw.startswith("/v2/"):
                refs.append({"file": rel, "path": raw})
    # de-dup
    seen = set()
    deduped = []
    for ref in refs:
        key = (ref["file"], ref["path"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped


def _collect_pages() -> List[Dict]:
    pages: List[Dict] = []
    app_dir = WEB_ROOT / "app"
    for page_file in sorted(app_dir.rglob("page.tsx")):
        rel = str(page_file.relative_to(app_dir)).replace("\\", "/")
        route = "/" if rel == "page.tsx" else "/" + rel[:-9]
        pages.append({"route": route, "file": _rel(page_file)})
    return pages


def _route_regex_from_next_route(route: str) -> re.Pattern:
    escaped = re.escape(route)
    escaped = escaped.replace(r"\[id\]", "[^/]+")
    escaped = escaped.replace(r"\[activityId\]", "[^/]+")
    escaped = escaped.replace(r"\[slug\]", "[^/]+")
    escaped = escaped.replace(r"\[distance\]", "[^/]+")
    escaped = escaped.replace(r"\[conversion\]", "[^/]+")
    return re.compile("^" + escaped + "$")


def _collect_link_targets() -> List[Dict]:
    targets: List[Dict] = []
    for ts_file in sorted(WEB_ROOT.rglob("*.ts*")):
        rel = _rel(ts_file)
        if "/__tests__/" in rel:
            continue
        text = _read_text(ts_file)
        for m in HREF_RE.finditer(text):
            targets.append({"file": rel, "target": m.group(1), "kind": "href"})
        for m in ROUTER_PUSH_RE.finditer(text):
            targets.append({"file": rel, "target": m.group(1), "kind": "router.push"})
    # de-dup
    seen = set()
    deduped = []
    for t in targets:
        key = (t["file"], t["target"], t["kind"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)
    return deduped


def _collect_nav_routes() -> Set[str]:
    nav_routes: Set[str] = set()
    nav_path = WEB_ROOT / "app" / "components" / "Navigation.tsx"
    if nav_path.exists():
        text = _read_text(nav_path)
        nav_routes.update(re.findall(r"href:\s*'([^']+)'", text))
        nav_routes.update(re.findall(r'href:\s*"([^"]+)"', text))
    tabs_path = WEB_ROOT / "app" / "components" / "BottomTabs.tsx"
    if tabs_path.exists():
        text = _read_text(tabs_path)
        nav_routes.update(re.findall(r'href:\s*"([^"]+)"', text))
    return {r for r in nav_routes if r.startswith("/")}


def _collect_hooks() -> List[Dict]:
    hooks: List[Dict] = []
    hook_files = sorted((WEB_ROOT / "lib" / "hooks").rglob("*.ts*"))
    hook_defs: List[Tuple[str, str]] = []
    for hook_file in hook_files:
        rel = _rel(hook_file)
        text = _read_text(hook_file)
        for m in HOOK_DEF_RE.finditer(text):
            hook_name = m.group(1)
            hook_defs.append((hook_name, rel))

    # Build a global call index once to avoid O(hooks * files) scans.
    token_call_index: Dict[str, int] = defaultdict(int)
    token_re = re.compile(r"\b(use[A-Z][a-zA-Z0-9_]*)\s*\(")
    for ts_file in sorted(WEB_ROOT.rglob("*.ts*")):
        rel = _rel(ts_file)
        if "/__tests__/" in rel:
            continue
        text = _read_text(ts_file)
        for token in token_re.findall(text):
            token_call_index[token] += 1

    for hook_name, hook_file in hook_defs:
        # Subtract one for the function declaration in its own file.
        usage = max(0, token_call_index.get(hook_name, 0) - 1)
        if usage == 0:
            status = "dormant"
            reason = "No consumers found outside defining file."
            priority = "P2"
        else:
            status = "active"
            reason = "Hook has active consumers."
            priority = "P4"
        hooks.append(
            {
                "hook": hook_name,
                "file": hook_file,
                "consumer_count": usage,
                "status": status,
                "failure_reason": reason,
                "owner": "frontend",
                "fix_priority": priority,
            }
        )
    return hooks


def build_ledger() -> Dict:
    backend_routes = _collect_backend_routes()
    runtime_paths = _collect_runtime_paths()
    frontend_refs = _collect_frontend_api_refs()
    pages = _collect_pages()
    link_targets = _collect_link_targets()
    nav_routes = _collect_nav_routes()
    hooks = _collect_hooks()

    backend_path_patterns = [(r["path"], _route_pattern(r["path"])) for r in backend_routes]

    consumed_route_keys: Set[Tuple[str, str, str]] = set()
    unmatched_frontend_refs: List[Dict] = []
    for ref in frontend_refs:
        norm = _normalize_dynamic_path(ref["path"])
        matched = False
        for route, pat in backend_path_patterns:
            if pat.match(norm):
                matched = True
                for r in backend_routes:
                    if r["path"] == route:
                        consumed_route_keys.add((r["method"], r["path"], r["file"]))
                break
        if not matched:
            unmatched_frontend_refs.append(ref)

    route_entries: List[RouteEntry] = []
    for r in backend_routes:
        key = (r["method"], r["path"], r["file"])
        runtime_registered = r["path"] in runtime_paths
        frontend_consumed = key in consumed_route_keys

        if not runtime_registered:
            status = "broken_unregistered"
            reason = "Declared in router file but not registered in FastAPI runtime."
            priority = "P0"
        elif frontend_consumed:
            status = "wired"
            reason = "Has frontend consumer."
            priority = "P4"
        else:
            status = "backend_only_or_unwired"
            reason = "No direct frontend consumer detected; may be internal/admin/webhook."
            priority = "P3"

        route_entries.append(
            RouteEntry(
                method=r["method"],
                path=r["path"],
                file=r["file"],
                function=r["function"],
                runtime_registered=runtime_registered,
                frontend_consumed=frontend_consumed,
                status=status,
                failure_reason=reason,
                owner="backend",
                fix_priority=priority,
            )
        )

    page_route_patterns = [(p["route"], _route_regex_from_next_route(p["route"])) for p in pages]

    bad_links: List[Dict] = []
    for target in link_targets:
        href = target["target"].split("?")[0].split("#")[0].rstrip("/") or "/"
        if href.startswith("/v1/") or href.startswith("/v2/"):
            continue
        exists = any(pat.match(href) for _, pat in page_route_patterns)
        if not exists:
            bad_links.append(target)

    inbound_link_map: Dict[str, int] = defaultdict(int)
    for target in link_targets:
        href = target["target"].split("?")[0].split("#")[0].rstrip("/") or "/"
        if any(pat.match(href) for _, pat in page_route_patterns):
            inbound_link_map[href] += 1

    page_entries: List[Dict] = []
    for p in pages:
        route = p["route"]
        inbound = inbound_link_map.get(route, 0)
        in_nav = route in nav_routes
        if route in ["/", "/login", "/register"]:
            status = "core_entry"
            reason = "Primary entry route."
            priority = "P4"
        elif inbound == 0:
            status = "hidden_or_orphan"
            reason = "No inbound href/router.push detected."
            priority = "P2"
        elif in_nav:
            status = "discoverable"
            reason = "Linked and present in nav."
            priority = "P4"
        else:
            status = "reachable_not_nav"
            reason = "Linked but not in primary nav/tabs."
            priority = "P3"
        page_entries.append(
            {
                "route": route,
                "file": p["file"],
                "inbound_links": inbound,
                "in_navigation": in_nav,
                "status": status,
                "failure_reason": reason,
                "owner": "frontend",
                "fix_priority": priority,
            }
        )

    bad_link_entries: List[Dict] = []
    for bl in bad_links:
        bad_link_entries.append(
            {
                "source_file": bl["file"],
                "target": bl["target"],
                "status": "broken_link",
                "failure_reason": "Link target does not map to any existing app page route.",
                "owner": "frontend",
                "fix_priority": "P0",
            }
        )

    unmatched_api_entries: List[Dict] = []
    for ref in unmatched_frontend_refs:
        unmatched_api_entries.append(
            {
                "source_file": ref["file"],
                "path": ref["path"],
                "status": "unmatched_api_ref",
                "failure_reason": "Frontend API reference does not match declared backend routes.",
                "owner": "frontend",
                "fix_priority": "P1",
            }
        )

    data = {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "backend routes, frontend pages, frontend hooks, link/path validity",
            "owner_policy": {
                "backend_routes": "backend",
                "frontend_pages": "frontend",
                "frontend_hooks": "frontend",
                "broken_links": "frontend",
                "unmatched_api_refs": "frontend",
            },
            "priority_scale": ["P0", "P1", "P2", "P3", "P4"],
        },
        "summary": {
            "backend_route_count": len(route_entries),
            "backend_runtime_registered_count": sum(1 for r in route_entries if r.runtime_registered),
            "backend_broken_unregistered_count": sum(1 for r in route_entries if r.status == "broken_unregistered"),
            "backend_frontend_wired_count": sum(1 for r in route_entries if r.frontend_consumed),
            "frontend_page_count": len(page_entries),
            "frontend_hidden_or_orphan_pages": sum(1 for p in page_entries if p["status"] == "hidden_or_orphan"),
            "frontend_hook_count": len(hooks),
            "frontend_dormant_hook_count": sum(1 for h in hooks if h["status"] == "dormant"),
            "broken_link_count": len(bad_link_entries),
            "unmatched_api_ref_count": len(unmatched_api_entries),
        },
        "backend_routes": [r.__dict__ for r in route_entries],
        "frontend_pages": page_entries,
        "frontend_hooks": hooks,
        "broken_links": bad_link_entries,
        "unmatched_api_refs": unmatched_api_entries,
    }
    return data


def write_outputs(ledger: Dict) -> None:
    json_path = ROOT / "docs" / "SYSTEM_LEDGER.json"
    md_path = ROOT / "docs" / "SYSTEM_LEDGER.md"

    json_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")

    s = ledger["summary"]
    p0_issues = []
    p0_issues.extend(ledger["broken_links"])
    p0_issues.extend([r for r in ledger["backend_routes"] if r["fix_priority"] == "P0"])

    lines: List[str] = []
    lines.append("# System Ledger")
    lines.append("")
    lines.append("Canonical source: `docs/SYSTEM_LEDGER.json`.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Backend routes: `{s['backend_route_count']}`")
    lines.append(f"- Runtime-registered backend routes: `{s['backend_runtime_registered_count']}`")
    lines.append(f"- Broken unregistered backend routes: `{s['backend_broken_unregistered_count']}`")
    lines.append(f"- Backend routes with frontend consumers: `{s['backend_frontend_wired_count']}`")
    lines.append(f"- Frontend pages: `{s['frontend_page_count']}`")
    lines.append(f"- Hidden/orphan frontend pages: `{s['frontend_hidden_or_orphan_pages']}`")
    lines.append(f"- Frontend hooks: `{s['frontend_hook_count']}`")
    lines.append(f"- Dormant frontend hooks: `{s['frontend_dormant_hook_count']}`")
    lines.append(f"- Broken internal links: `{s['broken_link_count']}`")
    lines.append(f"- Unmatched frontend API refs: `{s['unmatched_api_ref_count']}`")
    lines.append("")
    lines.append("## P0 Items")
    lines.append("")
    if not p0_issues:
        lines.append("- None.")
    else:
        for issue in p0_issues:
            if "target" in issue:
                lines.append(
                    f"- `broken_link` owner=`{issue['owner']}` priority=`{issue['fix_priority']}` "
                    f"source=`{issue['source_file']}` target=`{issue['target']}`"
                )
            else:
                lines.append(
                    f"- `route_unregistered` owner=`{issue['owner']}` priority=`{issue['fix_priority']}` "
                    f"route=`{issue['method']} {issue['path']}` file=`{issue['file']}`"
                )
    lines.append("")
    lines.append("## Operating Rule")
    lines.append("")
    lines.append(
        "- Builder checks this ledger before touching any surface. "
        "If `P0`/`P1` exists on a target path, fix those first."
    )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    ledger_data = build_ledger()
    write_outputs(ledger_data)
    print(json.dumps(ledger_data["summary"], indent=2))
