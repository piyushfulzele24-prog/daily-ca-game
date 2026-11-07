"""Nightly job: draft 25 SSC CGL current affairs MCQs, verify them, publish JSON."""
import os, re, json, random, datetime, zoneinfo
import anthropic

MODEL = "claude-sonnet-5-5"
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
TOOLS = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}]
TODAY = datetime.datetime.now(zoneinfo.ZoneInfo("Asia/Kolkata")).date().isoformat()
HIST = "questions/history.json"

MIX = """Topic mix per 25: National and schemes 4; International and bilateral 3; Economy, banking, RBI 3;
Sports 3; Awards, books 3; Science, tech, space, defence 3; Appointments 2; Days, reports, indices 2; States/polity 2.
Difficulty per 25: 8 easy, 12 medium, 5 hard (SSC CGL level). Vary styles: who/where/which, odd-one-out, statement-based."""

def call(system, prompt):
    msgs = [{"role": "user", "content": prompt}]
    for _ in range(6):
        r = client.messages.create(model=MODEL, max_tokens=8000, system=system, tools=TOOLS, messages=msgs)
        if r.stop_reason != "pause_turn":
            break
        msgs.append({"role": "assistant", "content": r.content})
    text = "".join(b.text for b in r.content if b.type == "text")
    m = re.search(r"\[.*\]", text, re.S)
    return json.loads(m.group(0))

def draft(n, avoid):
    sys_ = "You write SSC CGL current affairs MCQs about India and the world. Use web search. Output ONLY a JSON array."
    p = f"""Today is {TODAY}. Write {n} NEW MCQs from news of the last 7 to 45 days (at least 40% from the last 7 days).
Only facts reported by PIB, The Hindu, Indian Express, Times of India, DD News, RBI or ministry sites. No opinions or disputed claims.
{MIX}
Each item: {{"topic":"","d":"easy|medium|hard","q":"","o":["","","",""],"a":0,"e":"1-2 line explanation","s":"source name, date"}}
"a" is the index (0-3) of the correct option. Options must be plausible.
Do NOT repeat any of these earlier questions or their facts:
{json.dumps(avoid[-150:])}"""
    return call(sys_, p)

def verify(qs):
    ok = []
    for i in range(0, len(qs), 8):
        batch = qs[i:i + 8]
        sys_ = "You are a strict fact-checker. Use web search. Output ONLY a JSON array."
        p = f"""Check each MCQ against at least two reliable sources. Mark pass=true only if the keyed answer is correct,
the other options are wrong, and the story is not still developing. Return [{{"i":0,"pass":true,"why":""}}, ...].
{json.dumps([{"i": k, "q": q["q"], "o": q["o"], "a": q["a"]} for k, q in enumerate(batch)])}"""
        for v in call(sys_, p):
            if v.get("pass") and 0 <= v["i"] < len(batch):
                ok.append(batch[v["i"]])
    return ok

def valid(q):
    return (isinstance(q.get("o"), list) and len(q["o"]) == 4 and len(set(q["o"])) == 4
            and q.get("a") in (0, 1, 2, 3) and q.get("q") and q.get("e") and q.get("s"))

def norm(t): return re.sub(r"[^a-z0-9 ]", "", t.lower())

def shuffle(q):
    right = q["o"][q["a"]]
    random.shuffle(q["o"])
    q["a"] = q["o"].index(right)
    return q

def main():
    hist = json.load(open(HIST)) if os.path.exists(HIST) else []
    seen = {norm(h) for h in hist}
    good = []
    for _ in range(4):
        need = 25 - len(good)
        if need <= 0: break
        fresh = []
        for q in draft(need + 8, hist + [g["q"] for g in good]):
            if valid(q) and norm(q["q"]) not in seen:
                seen.add(norm(q["q"])); fresh.append(q)
        good += verify(fresh)
    if len(good) < 25:
        raise SystemExit(f"Only {len(good)} verified questions; not publishing.")
    qs = [shuffle(q) for q in good[:25]]
    pack = {"date": TODAY, "qs": qs}
    os.makedirs("questions", exist_ok=True)
    json.dump(pack, open(f"questions/{TODAY}.json", "w"), ensure_ascii=False, indent=1)
    json.dump(pack, open("questions/latest.json", "w"), ensure_ascii=False, indent=1)
    json.dump((hist + [q["q"] for q in qs])[-2000:], open(HIST, "w"), ensure_ascii=False)
    print("Published", TODAY)

main()
