#!/usr/bin/env python3
"""Integration smoke tests for Yearbook Face Sorter API."""
import json
import sys
import time
from pathlib import Path

import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
ROOT = Path(__file__).parent


def req(method, path, body=None, timeout=120):
    url = f"{BASE}{path}"
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return resp.status, {}
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, {"_raw": raw[:200]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = raw
        return e.code, detail


def ok(name, passed, detail=""):
    mark = "PASS" if passed else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))
    return passed


def main():
    print("=== API Integration Tests ===\n")
    results = []

    # 1. Home + system info
    code, home = req("GET", "/")
    html_ok = code == 200 and ("<!DOCTYPE" in home.get("_raw", "") or "FaceSorter" in home.get("_raw", ""))
    results.append(ok("GET / (HTML)", html_ok, f"status={code}"))

    code, data = req("GET", "/api/system-info")
    results.append(ok("GET /api/system-info", code == 200 and "cpu_count" in data))

    # 2. Samples
    code, data = req("POST", "/api/create-samples", {}, timeout=180)
    samples_dir = data.get("source_dir", str(ROOT / "sample_photos"))
    results.append(ok("POST /api/create-samples", code == 200, samples_dir))

    # 3. Scan
    code, data = req("POST", "/api/scan", {"source_dir": samples_dir, "workers": 2})
    results.append(ok("POST /api/scan start", code == 200, str(data.get("status"))))

    status = {}
    for _ in range(180):
        time.sleep(1)
        code, status = req("GET", "/api/scan-status")
        if status.get("status") in ("done", "error"):
            break
    results.append(
        ok(
            "Scan completes",
            status.get("status") == "done",
            f"faces={status.get('faces_found')} eps={status.get('optimal_eps')}",
        )
    )
    if status.get("status") != "done":
        print(f"    error: {status.get('error_message')}")
        return 1

    faces = status.get("faces_found", 0)
    results.append(ok("Faces detected", faces > 0, str(faces)))

    # 4. Cluster
    code, groups = req("GET", "/api/cluster")
    results.append(ok("GET /api/cluster", code == 200 and isinstance(groups, list)))
    results.append(ok("Cluster groups exist", len(groups) > 0, f"{len(groups)} groups"))

    # 5. Auto-tune
    code, tune = req("POST", "/api/auto-tune")
    results.append(
        ok(
            "POST /api/auto-tune",
            code == 200 and "optimal_eps" in tune,
            f"eps={tune.get('optimal_eps')}",
        )
    )

    # 6. Rename
    if groups:
        cid = groups[0]["cluster_id"]
        code, _ = req("POST", "/api/rename", {"cluster_id": cid, "new_name": "Test Person A"})
        code2, groups2 = req("GET", "/api/cluster")
        renamed = any(g.get("person_name") == "Test Person A" for g in groups2)
        results.append(ok("POST /api/rename", code == 200 and renamed))

    # 7. Learning
    code, learn = req("GET", "/api/learn/suggestions?limit=5")
    suggestions = learn.get("suggestions", [])
    results.append(ok("GET /api/learn/suggestions", code == 200))
    results.append(ok("GET /api/learn/stats", req("GET", "/api/learn/stats")[0] == 200))

    if len(suggestions) >= 1:
        s = suggestions[0]
        code, fb = req(
            "POST",
            "/api/learn/feedback",
            {
                "cluster_a": s["cluster_a"],
                "cluster_b": s["cluster_b"],
                "same": False,
                "skipped": False,
            },
        )
        results.append(
            ok(
                "POST /api/learn/feedback",
                code == 200 and "stats" in fb,
                f"remaining={fb.get('remaining_suggestions')}",
            )
        )
    else:
        results.append(ok("POST /api/learn/feedback", True, "skipped — no suggestions"))

    # 8. Move face (if 2+ groups)
    code, groups = req("GET", "/api/cluster")
    if len(groups) >= 2:
        face_id = groups[1]["faces"][0]["id"]
        target = groups[0]["cluster_id"]
        code, _ = req(
            "POST",
            "/api/move-face",
            {"face_id": face_id, "target_cluster_id": target},
        )
        results.append(ok("POST /api/move-face", code == 200))
    else:
        results.append(ok("POST /api/move-face", True, "skipped — need 2 groups"))

    # 9. Export
    export_dir = str(ROOT / "output" / "_test_export")
    Path(export_dir).mkdir(parents=True, exist_ok=True)
    code, exp = req(
        "POST",
        "/api/export",
        {
            "export_dir": export_dir,
            "source_dir": samples_dir,
            "structure_type": "flat",
            "group_threshold": 5,
            "exclude_groups_from_individuals": False,
        },
    )
    results.append(ok("POST /api/export", code == 200, str(exp.get("status", exp))))

    # 10. Reset
    code, _ = req("POST", "/api/reset", {})
    code2, status2 = req("GET", "/api/scan-status")
    results.append(
        ok(
            "POST /api/reset",
            code == 200 and status2.get("status") == "idle",
        )
    )

    passed = sum(results)
    total = len(results)
    print(f"\n=== Kết quả: {passed}/{total} passed ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.URLError as e:
        print(f"FAIL: Cannot reach server at {BASE} — {e}")
        print("Start with: python -m uvicorn app:app --port 8000")
        sys.exit(1)
