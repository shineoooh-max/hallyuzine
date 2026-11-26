/**
 * Cloudflare Pages Function: /api/vote
 * KV Binding: VOTES_KV
 *
 * GET  /api/vote?poll_id=...(&client_id=...)
 * POST /api/vote  { poll_id, choice: "A"|"B", client_id, action?: "vote"|"boost", boost?: boolean }
 */

const TTL_24H = 86400;

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}

async function sha256Hex(input) {
  const bytes = new TextEncoder().encode(input);
  const hashBuffer = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function getClientIp(request) {
  return (
    request.headers.get("CF-Connecting-IP") ||
    (request.headers.get("X-Forwarded-For") || "").split(",")[0].trim() ||
    "0.0.0.0"
  );
}

function sanitizePollId(raw) {
  return String(raw || "")
    .trim()
    .replace(/[^a-zA-Z0-9_-]/g, "")
    .slice(0, 96);
}

function formatPollStats(pollId, votesA, votesB, extra = {}) {
  const a = Math.max(0, Number(votesA) || 0);
  const b = Math.max(0, Number(votesB) || 0);
  const total = a + b;
  const pctA = total > 0 ? Math.round((a / total) * 100) : 50;
  const pctB = total > 0 ? 100 - pctA : 50;
  const neckAndNeck = Math.abs(pctA - pctB) <= 5;

  return {
    poll_id: pollId,
    votes_a: a,
    votes_b: b,
    total,
    pct_a: pctA,
    pct_b: pctB,
    neck_and_neck: neckAndNeck,
    ...extra,
  };
}

export async function onRequestOptions() {
  return jsonResponse({ ok: true }, 204);
}

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const pollId = sanitizePollId(url.searchParams.get("poll_id"));
  if (!pollId) {
    return jsonResponse({ error: "Missing or invalid poll_id" }, 400);
  }

  const kv = env && env.VOTES_KV;
  if (!kv) {
    return jsonResponse(
      formatPollStats(pollId, 0, 0, { voted: false, choice: null, boosted: false })
    );
  }

  const stored = (await kv.get(`poll:${pollId}`, "json")) || { a: 0, b: 0 };

  let votedChoice = null;
  let boosted = false;
  const clientId = String(url.searchParams.get("client_id") || "").trim().slice(0, 80);
  if (clientId) {
    const ip = getClientIp(request);
    const voterHash = await sha256Hex(`${clientId}|${ip}`);
    votedChoice = await kv.get(`voted:${pollId}:${voterHash}`);
    boosted = Boolean(await kv.get(`boosted:${pollId}:${voterHash}`));
  }

  return jsonResponse(
    formatPollStats(pollId, stored.a, stored.b, {
      voted: Boolean(votedChoice),
      choice: votedChoice,
      boosted,
    })
  );
}

export async function onRequestPost({ request, env }) {
  const kv = env && env.VOTES_KV;
  if (!kv) {
    return jsonResponse({ error: "VOTES_KV binding is not configured" }, 500);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: "Invalid JSON payload" }, 400);
  }

  const pollId = sanitizePollId(body.poll_id);
  const choice = String(body.choice || "").toUpperCase();
  const action = String(body.action || "vote").toLowerCase();
  const isBoostReferral = Boolean(body.boost);
  const clientId = String(body.client_id || "").trim().slice(0, 80) || "anon";

  if (!pollId) {
    return jsonResponse({ error: "Missing or invalid poll_id" }, 400);
  }
  if (choice !== "A" && choice !== "B") {
    return jsonResponse({ error: "choice must be 'A' or 'B'" }, 400);
  }

  const ip = getClientIp(request);
  const voterHash = await sha256Hex(`${clientId}|${ip}`);
  const pollKey = `poll:${pollId}`;
  const voteKey = `voted:${pollId}:${voterHash}`;
  const boostKey = `boosted:${pollId}:${voterHash}`;

  const stored = (await kv.get(pollKey, "json")) || { a: 0, b: 0 };
  let votesA = Number(stored.a) || 0;
  let votesB = Number(stored.b) || 0;

  // 공유 링크 복사 시 +3 Power Vote 가산
  if (action === "boost") {
    const alreadyBoosted = await kv.get(boostKey);
    const votedChoice = (await kv.get(voteKey)) || choice;
    if (alreadyBoosted) {
      return jsonResponse(
        formatPollStats(pollId, votesA, votesB, {
          voted: Boolean(votedChoice),
          choice: votedChoice,
          boosted: true,
          already_boosted: true,
          added_votes: 0,
        })
      );
    }

    const target = votedChoice === "B" ? "B" : "A";
    if (target === "A") votesA += 3;
    else votesB += 3;

    await Promise.all([
      kv.put(pollKey, JSON.stringify({ a: votesA, b: votesB })),
      kv.put(boostKey, target, { expirationTtl: TTL_24H }),
    ]);

    return jsonResponse(
      formatPollStats(pollId, votesA, votesB, {
        voted: true,
        choice: target,
        boosted: true,
        added_votes: 3,
      })
    );
  }

  // 일반 투표 (24시간 내 1인 1표 중복 방지, ?boost=1 유입 시 +3 Power Vote)
  const existingChoice = await kv.get(voteKey);
  if (existingChoice) {
    const alreadyBoosted = Boolean(await kv.get(boostKey));
    return jsonResponse(
      formatPollStats(pollId, votesA, votesB, {
        voted: true,
        choice: existingChoice,
        boosted: alreadyBoosted,
        already_voted: true,
        added_votes: 0,
      }),
      409
    );
  }

  const weight = isBoostReferral ? 3 : 1;
  if (choice === "A") votesA += weight;
  else votesB += weight;

  const writes = [
    kv.put(pollKey, JSON.stringify({ a: votesA, b: votesB })),
    kv.put(voteKey, choice, { expirationTtl: TTL_24H }),
  ];
  if (isBoostReferral) {
    writes.push(kv.put(boostKey, choice, { expirationTtl: TTL_24H }));
  }
  await Promise.all(writes);

  return jsonResponse(
    formatPollStats(pollId, votesA, votesB, {
      voted: true,
      choice,
      boosted: isBoostReferral,
      added_votes: weight,
    })
  );
}
