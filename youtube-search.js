// v4 OPTIMIZED: early-exit single-pass parse + indexOf loop + lazy fields + timing
// Usage: node youtube-search.js "latest ai news" --last24h --views100k [--no-save]
// Same output as v3, faster parse. HTML view format: "134,421 views" (also "134K"/"1.2M").
// Today filter sp=EgIIAg== (from HTML Upload date -> Today).

const fs = require("fs");

// Precompiled regex (was: re-created per chunk)
const RE_ID = /"videoId":"([a-zA-Z0-9_-]{11})"/;
const RE_TITLE = /"title":\{"runs":\[\{"text":"((?:[^"\\]|\\.)+?)"/;
const RE_TIME = /"publishedTimeText":\{"simpleText":"([^"]+)"/;
const RE_VIEWS = /"viewCountText":\{"simpleText":"([^"]+)"\}/;
const MARK = '"videoRenderer":';
const WINDOW = 5000; // was 8000; measured max field distance 4882 in 1.2MB page
const MAX_OUT = 10;

function parseViews(t) {
  if (!t) return 0;
  // fast path: "134,421 views" (most common) — avoid toLowerCase/replace
  const s = t.length < 32 ? t : t.toLowerCase();
  if (s[0] === "N" || s[0] === "n") return 0; // "No views"
  // K/M/B suffix: "134K views", "1.2M views"
  const last = s[s.length - 1];
  // quick digit-comma parse for "12,345 views"
  let m;
  if (s.includes("K") || s.includes("M") || s.includes("B")) {
    const low = s.toLowerCase().replace(/views?/g, "").trim();
    m = low.match(/([\d,.]+)\s*([kmb])$/);
    if (m) {
      const n = parseFloat(m[1].replace(/,/g, ""));
      const mult = m[2] === "k" ? 1e3 : m[2] === "m" ? 1e6 : 1e9;
      return Math.round(n * mult);
    }
  }
  let n = 0;
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    if (c >= 48 && c <= 57) n = n * 10 + (c - 48);
  }
  void last;
  return n;
}

function isLast24h(t) {
  if (!t) return false;
  // fast path: contains "hour" (covers "5 hours ago", "Streamed 5 hours ago")
  if (t.includes("hour")) return true;
  const s = t.length < 32 ? t : t.toLowerCase();
  if (s.includes("second") || s.includes("minute") || s.includes("hour"))
    return true;
  let m = /(\d+)\s*([smhd])\s*ago/.exec(s);
  if (m) {
    const u = m[2];
    if (u === "s" || u === "m" || u === "h") return true;
    if (u === "d") return +m[1] <= 1;
  }
  m = /(\d+)\s*days?\s*ago/.exec(s);
  if (m) return +m[1] <= 1;
  return false;
}

async function main() {
  const tStart = Date.now();
  const rawArgs = process.argv.slice(2);
  const last24h =
    rawArgs.includes("--last24h") ||
    rawArgs.includes("--today") ||
    rawArgs.includes("--24h");
  const noSave = rawArgs.includes("--no-save");
  let minViews = 0;
  if (rawArgs.includes("--views100k") || rawArgs.includes("--100k"))
    minViews = 100000;
  const minIdx = rawArgs.indexOf("--minViews");
  let minViewsVal = null;
  if (minIdx !== -1 && rawArgs[minIdx + 1]) {
    const n = parseInt(rawArgs[minIdx + 1].replace(/[^0-9]/g, ""), 10);
    if (!isNaN(n)) {
      minViews = n;
      minViewsVal = rawArgs[minIdx + 1];
    }
  }
  const queryParts = [];
  for (let k = 0; k < rawArgs.length; k++) {
    const a = rawArgs[k];
    if (a.startsWith("--")) continue;
    if (
      minViewsVal !== null &&
      a === minViewsVal &&
      rawArgs[k - 1] === "--minViews"
    )
      continue;
    queryParts.push(a);
  }
  const query = queryParts.join(" ").trim();
  if (!query) {
    console.error(
      'Usage: node youtube-search.js "<query>" [--last24h] [--views100k | --minViews N] [--no-save]'
    );
    process.exit(1);
  }

  let url =
    "https://www.youtube.com/results?search_query=" +
    encodeURIComponent(query);
  if (last24h) url += "&sp=EgIIAg%3D%3D";

  console.log(
    `Searching YouTube for: "${query}"${last24h ? " [last 24h]" : ""}${
      minViews ? ` [views>${minViews}]` : ""
    }`
  );
  console.log(`URL: ${url}`);

  const tFetch0 = Date.now();
  const res = await fetch(url, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9",
    },
  });
  if (!res.ok) throw new Error(`Fetch failed: ${res.status} ${res.statusText}`);
  const html = await res.text();
  const tFetch = Date.now() - tFetch0;
  console.log(`Fetched ${html.length} bytes`);

  // Parse first (timed), save after so parse timing is clean
  const tParse0 = Date.now();
  const needTime = last24h;
  const needViews = minViews > 0;
  const out = [];
  const seen = new Set();
  let scanned = 0;
  let pos = 0;
  // indexOf loop: avoids html.split() allocating ~60 huge strings
  while (out.length < MAX_OUT) {
    const j = html.indexOf(MARK, pos);
    if (j === -1) break;
    pos = j + MARK.length;
    scanned++;
    // cap scan to avoid pathological pages (was: collect 60 always)
    if (scanned > 80) break;
    const c = html.substr(pos, WINDOW);
    const idM = RE_ID.exec(c);
    if (!idM) continue;
    const id = idM[1];
    if (seen.has(id)) continue;
    seen.add(id);
    const titleM = RE_TITLE.exec(c);
    const title = titleM
      ? titleM[1].replace(/\\u0026/g, "&").replace(/\\"/g, '"')
      : "(title not parsed)";
    let time = "";
    if (needTime || true) {
      // time shown in output; parse only if needed for filter or display
      const timeM = RE_TIME.exec(c);
      time = timeM ? timeM[1] : "";
      if (needTime && !isLast24h(time)) continue; // early-skip before views work
    }
    let viewsText = "";
    let views = 0;
    if (needViews || true) {
      const viewsM = RE_VIEWS.exec(c);
      viewsText = viewsM ? viewsM[1] : "";
      if (needViews) {
        views = parseViews(viewsText);
        if (views <= minViews) continue; // early-skip
      } else {
        views = 0;
      }
    }
    out.push({ id, title, time, viewsText, views });
  }
  const tParse = Date.now() - tParse0;

  // Save (optional, timed separately)
  const tSave0 = Date.now();
  let outFile = "";
  if (!noSave) {
    const safe = query.replace(/[^a-z0-9]+/gi, "-").slice(0, 40) || "search";
    outFile = `youtube-search-${safe}${last24h ? "-last24h" : ""}${
      minViews ? `-min${minViews}` : ""
    }.html`;
    fs.writeFileSync(outFile, html);
    console.log(`Saved HTML to ${outFile}`);
  }
  const tSave = Date.now() - tSave0;

  console.log(
    `\nFound ${out.length} videos (scanned ${scanned} blocks)${
      last24h ? " (last 24h only)" : ""
    }${minViews ? ` (views>${minViews})` : ""}:`
  );
  let i = 1;
  for (const v of out) {
    console.log(
      `${i}. ${v.title}${v.time ? ` [${v.time}]` : ""}${
        v.viewsText ? ` [${v.viewsText}]` : ""
      }`
    );
    console.log(`   https://www.youtube.com/watch?v=${v.id}`);
    i++;
  }
  if (out.length === 0) {
    console.log(
      "No videos match filters (fresh <24h videos rarely exceed 100k)."
    );
  }
  const tTotal = Date.now() - tStart;
  console.log(
    `\nTiming: fetch=${tFetch}ms parse=${tParse}ms save=${tSave}ms total=${tTotal}ms`
  );
}

main().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
