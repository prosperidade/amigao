type Comparison = "greater" | "less"

export function getStatusStyle(
  value: number,
  threshold: number,
  comparison: Comparison,
): string {
  const isOk = comparison === "greater" ? value > threshold : value < threshold
  return isOk ? "status-ok" : "status-alert"
}
