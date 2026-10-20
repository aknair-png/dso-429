"""DSO 429 HW3 - Hourly Quiz auto-solver.

Downloads questions.csv from the course repo, solves every round that does not
yet have an answers/round-XXXX.json file, and writes those files.

All 12 question types are ordinary business arithmetic, so this solves them
with plain Python formulas (no AI API, no keys, no cost). For each question it
computes the true value, then picks the option closest to it.
"""
import csv
import io
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta

QUESTIONS_URL = "https://raw.githubusercontent.com/FaisalXL/dso429-hourly-quiz/main/questions.csv"
ANSWERS_DIR = "answers"
LETTERS = "ABCD"


# ---------- helpers ----------

def nums(text):
    """All numbers in a string, in order (handles $ and commas)."""
    return [float(n.replace(",", "")) for n in re.findall(r"-?\d[\d,]*(?:\.\d+)?", text)]


def num(text):
    return nums(text)[0]


def closest(target, options):
    """Index of the option whose number is closest to target."""
    diffs = [abs(num(o) - target) for o in options]
    return diffs.index(min(diffs))


def parse_date(text):
    return datetime.strptime(text.strip(), "%d %B %Y")


# ---------- one solver per question type ----------

def solve(q, opts):
    """Return the index (0-3) of the correct option, or raise if unknown type."""
    n = nums(q)

    if "compounded annually" in q:            # FV = P(1+r)^t
        p, r, t = n[0], n[1], n[2]
        return closest(p * (1 + r / 100) ** t, opts)

    if "gross margin" in q:                   # (Rev - COGS) / Rev
        rev, cogs = n[0], n[1]
        return closest((rev - cogs) / rev * 100, opts)

    if "series runs" in q:                    # next term of the pattern
        s = n[:5]
        diffs = [b - a for a, b in zip(s, s[1:])]
        if len(set(diffs)) == 1:              # arithmetic
            nxt = s[-1] + diffs[0]
        elif all(a != 0 for a in s[:-1]) and len({round(b / a, 9) for a, b in zip(s, s[1:])}) == 1:
            nxt = s[-1] * (s[1] / s[0])       # geometric
        else:                                 # second differences constant
            d2 = diffs[-1] - diffs[-2]
            nxt = s[-1] + diffs[-1] + d2
        return closest(nxt, opts)

    if "discounted by" in q:                  # price * (1 - d)
        price, d = n[0], n[1]
        return closest(price * (1 - d / 100), opts)

    if "percentage change" in q:              # (new - old) / old
        old, new = n[0], n[1]
        return closest((new - old) / old * 100, opts)

    if "settlement period" in q:              # date + N days
        m = re.search(r"signed on (\d{1,2} \w+ \d{4}) has a (\d+)-day", q)
        due = parse_date(m.group(1)) + timedelta(days=int(m.group(2)))
        for i, o in enumerate(opts):
            if parse_date(o) == due:
                return i
        raise ValueError("no matching date")

    if "break even" in q:                     # FC / (price - VC), rounded
        fc, price, vc = n[0], n[1], n[2]
        return closest(round(fc / (price - vc)), opts)

    if "split between two channels" in q:     # budget * a / (a + b)
        budget = n[0]
        a, b = map(float, re.search(r"ratio (\d+):(\d+)", q).groups())
        return closest(budget * a / (a + b), opts)

    if "overall average order value" in q:    # weighted average
        n1, a1, n2, a2 = n[0], n[1], n[2], n[3]
        return closest((n1 * a1 + n2 * a2) / (n1 + n2), opts)

    if "probability it is a billing ticket" in q:
        billing, tech, acct = n[0], n[1], n[2]
        return closest(billing / (billing + tech + acct) * 100, opts)

    if "total revenue" in q:                  # units * price
        units, price = n[0], n[1]
        return closest(units * price, opts)

    if "converted to euros" in q:             # USD * rate
        usd, rate = n[0], n[1]
        return closest(usd * rate, opts)

    raise ValueError("unknown question type: " + q)


# ---------- main pipeline ----------

def load_rounds(csv_text):
    rounds = {}
    for row in csv.DictReader(io.StringIO(csv_text)):
        rounds.setdefault(int(row["round_id"]), []).append(row)
    return rounds


def answer_round(rows):
    answers = {}
    for row in sorted(rows, key=lambda r: int(r["q_index"])):
        opts = [row["option_a"], row["option_b"], row["option_c"], row["option_d"]]
        try:
            letter = LETTERS[solve(row["question_text"], opts)]
        except Exception as e:  # never leave a question blank
            print(f"  WARNING round {row['round_id']} q{row['q_index']}: {e}", file=sys.stderr)
            letter = "A"
        answers[f"q{int(row['q_index'])}"] = letter
    return answers


def main():
    if len(sys.argv) > 1:                       # optional local file (for testing)
        csv_text = open(sys.argv[1]).read()
    else:
        req = urllib.request.Request(QUESTIONS_URL, headers={"Cache-Control": "no-cache"})
        csv_text = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")

    os.makedirs(ANSWERS_DIR, exist_ok=True)
    written = 0
    for rid, rows in sorted(load_rounds(csv_text).items()):
        path = os.path.join(ANSWERS_DIR, f"round-{rid:04d}.json")
        if os.path.exists(path):
            continue
        data = {"round_id": rid, "answers": answer_round(rows)}
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        written += 1
        print(f"wrote {path}")
    print(f"done: {written} new round(s)")


if __name__ == "__main__":
    main()
