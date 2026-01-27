export function formatScore(score: number): string {
  return score.toFixed(2);
}

export function formatSearchTime(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function formatDate(timestamp: number): string {
  return new Date(timestamp).toLocaleDateString();
}
