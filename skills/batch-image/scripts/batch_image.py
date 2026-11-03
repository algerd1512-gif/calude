#!/usr/bin/env python3
"""Helper for the batch-image skill: parse numbered prompts, track state, report.

Commands (all paths are explicit; nothing is read from cwd implicitly):
  init   <project_dir> <prompts_file>    parse prompts -> <project_dir>/state.json
  todo   <project_dir> [--only 012,045]  list numbers still needing an image (file missing)
  mark   <project_dir> <num> <field> <value>
           fields: job (job id), status (done|failed|error), check (ok|bad),
                   note (free text), retry (+1 to retry counter)
  report <project_dir>                   print final short report
  show   <project_dir> <num>             print one entry as JSON
"""
import json
import os
import re
import sys

LINE_RE = re.compile(r"^\s*(\d{1,4})\s*[.)]\s*(.+?)\s*$")
# reads "..." / reading "..." / that reads "..." ; supports straight and curly quotes
TEXT_RE = re.compile(r"\bread(?:s|ing)?\s*[:]?\s*[\"“”]([^\"“”]+)[\"“”]", re.I)
# quoted labels listed after "labels are"/"labeled"/"the only text" etc.
QUOTE_RE = re.compile(r"[\"“”]([^\"“”]+)[\"“”]")


def parse(path):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    items, cur = [], None
    for line in raw.splitlines():
        m = LINE_RE.match(line)
        if m:
            cur = {"num": m.group(1).zfill(3), "prompt": m.group(2)}
            items.append(cur)
        elif cur and line.strip() and not line.strip().startswith("```"):
            cur["prompt"] += " " + line.strip()  # wrapped continuation line
    for it in items:
        p = it["prompt"]
        texts = TEXT_RE.findall(p)
        # any quoted string in a prompt that has text-intent also counts (labels, brand names)
        if texts or re.search(r"\b(label|labels|labeled|text|title|brand name|sign)\b", p, re.I):
            texts = list(dict.fromkeys(texts + QUOTE_RE.findall(p)))
        it["texts"] = texts
        it["has_text"] = bool(texts)
    nums = [i["num"] for i in items]
    dups = sorted({n for n in nums if nums.count(n) > 1})
    return items, dups


def state_path(d):
    return os.path.join(d, "state.json")


def load(d):
    with open(state_path(d), encoding="utf-8") as f:
        return json.load(f)


def save(d, st):
    tmp = state_path(d) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, state_path(d))


def img_exists(d, num):
    return any(os.path.exists(os.path.join(d, f"{num}.{e}")) for e in ("png", "jpg", "jpeg", "webp"))


def main(a):
    if len(a) < 2:
        print(__doc__)
        return 1
    cmd, d = a[0], a[1]
    if cmd == "init":
        os.makedirs(d, exist_ok=True)
        items, dups = parse(a[2])
        if not items:
            print("ERROR: no numbered prompts found (expected lines like '001. prompt')")
            return 2
        old = {}
        if os.path.exists(state_path(d)):
            old = {e["num"]: e for e in load(d)["items"]}
        for it in items:
            prev = old.get(it["num"], {})
            same = prev.get("prompt") == it["prompt"]
            it.update({k: prev[k] for k in ("job", "status", "check", "retries", "notes") if same and k in prev})
            it.setdefault("retries", 0)
            it.setdefault("notes", [])
        save(d, {"items": items})
        n_text = sum(i["has_text"] for i in items)
        print(f"OK {len(items)} prompts ({items[0]['num']}..{items[-1]['num']}), {n_text} with text")
        for i in items:
            if i["has_text"]:
                print(f"  {i['num']} text: {i['texts']}")
        nums = sorted(int(i["num"]) for i in items)
        gaps = sorted(set(range(nums[0], nums[-1] + 1)) - set(nums))
        if gaps:
            print("WARN missing numbers:", ",".join(str(g).zfill(3) for g in gaps))
        if dups:
            print("WARN duplicate numbers:", ",".join(dups))
        return 0
    st = load(d)
    items = st["items"]
    by = {i["num"]: i for i in items}
    if cmd == "todo":
        only = None
        if "--only" in a:
            only = {x.strip().zfill(3) for x in re.split(r"[ ,;]+", a[a.index("--only") + 1]) if x.strip()}
            unknown = only - set(by)
            if unknown:
                print("WARN not in list:", ",".join(sorted(unknown)))
            print(" ".join(sorted(only & set(by))))
        else:
            print(" ".join(i["num"] for i in items if not img_exists(d, i["num"])))
        return 0
    if cmd == "mark":
        num, field = a[2].zfill(3), a[3]
        val = a[4] if len(a) > 4 else ""
        e = by[num]
        if field == "retry":
            e["retries"] = e.get("retries", 0) + 1
        elif field == "note":
            e.setdefault("notes", []).append(val)
        else:
            e[field] = val
        save(d, st)
        print(json.dumps({k: e.get(k) for k in ("num", "status", "check", "retries")}, ensure_ascii=False))
        return 0
    if cmd == "show":
        print(json.dumps(by[a[2].zfill(3)], ensure_ascii=False, indent=1))
        return 0
    if cmd == "report":
        missing = [i["num"] for i in items if not img_exists(d, i["num"])]
        retried = [i["num"] for i in items if i.get("retries", 0) > 0]
        bad = [i for i in items if i["has_text"] and i.get("check") == "bad"]
        print(f"Dự án: {os.path.basename(os.path.abspath(d))}  |  Thư mục: {os.path.abspath(d)}")
        print(f"Tổng số ảnh: {len(items) - len(missing)}/{len(items)}")
        print(f"Ảnh có chữ đã kiểm tra: {sum(1 for i in items if i['has_text'] and i.get('check'))}"
              f"/{sum(i['has_text'] for i in items)}")
        print(f"Số ảnh tạo lại: {len(retried)}" + (f" ({', '.join(retried)})" if retried else ""))
        print("Vẫn lỗi sau 2 lần tạo lại: " + (", ".join(i["num"] for i in bad) or "không có"))
        for i in bad:
            print(f"  {i['num']}: {(i.get('notes') or ['?'])[-1]}")
        if missing:
            print("Chưa có file ảnh: " + ", ".join(missing))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
