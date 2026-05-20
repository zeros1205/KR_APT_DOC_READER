// Parses "1.2.3" or "1.2.3-beta.1" into comparable parts. Returns null for
// malformed input so callers can fall back to "no update" rather than guessing.
type ParsedVersion = {
  release: [number, number, number];
  prerelease: string | null;
};

function parseVersion(raw: string | undefined | null): ParsedVersion | null {
  if (!raw) return null;
  const trimmed = raw.trim();
  const match = trimmed.match(/^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$/);
  if (!match) return null;
  const major = Number(match[1]);
  const minor = Number(match[2]);
  const patch = Number(match[3]);
  if (![major, minor, patch].every(Number.isFinite)) return null;
  return {
    release: [major, minor, patch],
    prerelease: match[4] ?? null
  };
}

function comparePrerelease(a: string | null, b: string | null): number {
  // Per semver: a release version has higher precedence than any prerelease.
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  const aIds = a.split(".");
  const bIds = b.split(".");
  const len = Math.max(aIds.length, bIds.length);
  for (let i = 0; i < len; i += 1) {
    const ai = aIds[i];
    const bi = bIds[i];
    if (ai === undefined) return -1;
    if (bi === undefined) return 1;
    const aNum = /^\d+$/.test(ai) ? Number(ai) : null;
    const bNum = /^\d+$/.test(bi) ? Number(bi) : null;
    if (aNum !== null && bNum !== null) {
      if (aNum !== bNum) return aNum - bNum;
    } else if (aNum !== null) {
      return -1;
    } else if (bNum !== null) {
      return 1;
    } else if (ai !== bi) {
      return ai < bi ? -1 : 1;
    }
  }
  return 0;
}

export function compareVersions(a: string, b: string): number {
  const pa = parseVersion(a);
  const pb = parseVersion(b);
  if (!pa || !pb) return 0;
  for (let i = 0; i < 3; i += 1) {
    if (pa.release[i] !== pb.release[i]) return pa.release[i] - pb.release[i];
  }
  return comparePrerelease(pa.prerelease, pb.prerelease);
}

// True only when `latest` is strictly newer than `installed`. Returns false
// for equal, downgrade, missing, or malformed inputs — we never want to
// nag users toward a lower version.
export function isUpdateAvailable(installed: string, latest: string): boolean {
  if (!parseVersion(installed) || !parseVersion(latest)) return false;
  return compareVersions(latest, installed) > 0;
}
