// V7: Log line color classifier
export function getLogLineClass(line: string): string {
  const l = line.toLowerCase();
  if (l.includes("error") || l.includes("failed") || l.includes("exception") || l.includes("[download failed")) {
    return "log-line-error";
  }
  if (l.includes("warning") || l.includes("warn")) {
    return "log-line-warning";
  }
  if (l.includes("completed successfully") || l.includes("finished") || l.includes("done") || l.includes("100%")) {
    return "log-line-success";
  }
  if (l.includes("[running command]") || l.includes("info") || l.startsWith("[")) {
    return "log-line-info";
  }
  return "log-line-default";
}

export function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
