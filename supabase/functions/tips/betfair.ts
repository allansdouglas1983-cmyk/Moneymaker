/**
 * Delayed-key order-book capture (ADR 0020, SPEC-112).
 *
 * This module calls exactly four Betfair operations and nothing else: login,
 * keep-alive-by-reuse, listMarketCatalogue, listMarketBook. No account endpoint, no
 * funds endpoint, and no order endpoint exists in this file — and the App Key it runs
 * under is the DELAYED key, on which Betfair rejects order placement at their end
 * regardless of what any code asks (SPEC-102: impossible by construction, not policy).
 *
 * Credentials come from the service-role-only config table at runtime. Nothing in this
 * file, or anywhere in the repository, contains a secret.
 */

const CERT_LOGIN_URL = "https://identitysso-cert.betfair.com/api/certlogin";
const BETTING_URL = "https://api.betfair.com/exchange/betting/rest/v1.0/";

/**
 * Certificate (Automated Betting Program Access) login — the ONLY automated route
 * Betfair permits: the plain SSO endpoint sits behind Cloudflare bot protection that
 * 403s datacenter addresses before credentials are even read (verified 2026-07-30).
 * The client certificate is presented at the TLS layer via Deno.createHttpClient;
 * both current ({cert, key}) and legacy ({certChain, privateKey}) option names are
 * tried, so a runtime upgrade cannot silently break the capture.
 */
export async function login(
  username: string,
  password: string,
  appKey: string,
  certPem: string,
  keyPem: string,
): Promise<string> {
  // deno-lint-ignore no-explicit-any
  const create = (Deno as any).createHttpClient;
  if (typeof create !== "function") {
    throw new Error("runtime lacks Deno.createHttpClient — cert login impossible here");
  }
  let client;
  try {
    client = create({ cert: certPem, key: keyPem });
  } catch (_error) {
    client = create({ certChain: certPem, privateKey: keyPem });
  }
  try {
    const response = await fetch(CERT_LOGIN_URL, {
      method: "POST",
      // deno-lint-ignore no-explicit-any
      client: client as any,
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Application": appKey,
        "Accept": "application/json",
      },
      body: "username=" + encodeURIComponent(username) +
        "&password=" + encodeURIComponent(password),
    } as RequestInit);
    if (!response.ok) throw new Error("certlogin HTTP " + response.status);
    const body = await response.json();
    if (body.loginStatus !== "SUCCESS") {
      throw new Error("certlogin refused: " + body.loginStatus);
    }
    return body.sessionToken as string;
  } finally {
    client.close();
  }
}

async function betting(
  method: string,
  params: unknown,
  appKey: string,
  token: string,
): Promise<unknown> {
  const response = await fetch(BETTING_URL + method + "/", {
    method: "POST",
    headers: {
      "X-Application": appKey,
      "X-Authentication": token,
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: JSON.stringify(params),
  });
  if (response.status === 400 || response.status === 401 || response.status === 403) {
    throw new SessionError("betting API " + method + " HTTP " + response.status);
  }
  if (!response.ok) throw new Error(method + " HTTP " + response.status);
  return await response.json();
}

/** Auth-shaped failures — the caller re-logs-in once and retries. */
export class SessionError extends Error {}

export interface CatalogueMarket {
  marketId: string;
  marketName: string;
  marketStartTime?: string;
  totalMatched?: number;
  event?: { name?: string; openDate?: string };
  runners?: Array<{ selectionId: number; runnerName: string }>;
}

/** Pre-off tennis Match Odds singles, next 36 hours. */
export async function tennisMarkets(
  appKey: string,
  token: string,
): Promise<CatalogueMarket[]> {
  const now = new Date();
  const to = new Date(now.getTime() + 36 * 3600000);
  const result = await betting("listMarketCatalogue", {
    filter: {
      eventTypeIds: ["2"],
      marketTypeCodes: ["MATCH_ODDS"],
      marketStartTime: { from: now.toISOString(), to: to.toISOString() },
      turnInPlayEnabled: true,
      inPlayOnly: false,
    },
    maxResults: "100",
    marketProjection: ["EVENT", "RUNNER_DESCRIPTION", "MARKET_START_TIME"],
  }, appKey, token) as CatalogueMarket[];
  // Doubles carry "/" in runner names; the platform is singles-only.
  return result.filter((m) =>
    (m.runners ?? []).length === 2 &&
    !(m.runners ?? []).some((r) => r.runnerName.includes("/")));
}

export interface BookRunner {
  selectionId: number;
  status: string;
  lastPriceTraded?: number;
  totalMatched?: number;
  ex?: {
    availableToBack?: Array<{ price: number; size: number }>;
    availableToLay?: Array<{ price: number; size: number }>;
  };
}

export interface MarketBook {
  marketId: string;
  status: string;
  inplay: boolean;
  totalMatched?: number;
  runners?: BookRunner[];
}

export function batches<T>(items: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}

/** Best three levels each side plus traded volume, ten markets per request — inside
 *  the documented request-weight ceiling with room to spare. */
export async function marketBooks(
  marketIds: string[],
  appKey: string,
  token: string,
): Promise<MarketBook[]> {
  const out: MarketBook[] = [];
  for (const chunk of batches(marketIds, 10)) {
    const result = await betting("listMarketBook", {
      marketIds: chunk,
      priceProjection: {
        priceData: ["EX_BEST_OFFERS"],
        exBestOffersOverrides: { bestPricesDepth: 3 },
      },
    }, appKey, token) as MarketBook[];
    out.push(...result);
  }
  return out;
}
