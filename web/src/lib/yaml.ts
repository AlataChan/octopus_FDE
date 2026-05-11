function scalar(value: unknown): string {
  if (value === null) {
    return "null";
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  const text = String(value);
  if (!text || /[:#\n{}[\],&*?|\-<>=!%@`]/.test(text)) {
    return JSON.stringify(text);
  }
  return text;
}

export function toDisplayYaml(value: unknown, depth = 0): string {
  const pad = "  ".repeat(depth);
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return "[]";
    }
    return value
      .map((item) => {
        if (item && typeof item === "object") {
          return `${pad}- ${toDisplayYaml(item, depth + 1).trimStart()}`;
        }
        return `${pad}- ${scalar(item)}`;
      })
      .join("\n");
  }
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) {
      return "{}";
    }
    return entries
      .map(([key, item]) => {
        if (item && typeof item === "object") {
          return `${pad}${key}:\n${toDisplayYaml(item, depth + 1)}`;
        }
        return `${pad}${key}: ${scalar(item)}`;
      })
      .join("\n");
  }
  return `${pad}${scalar(value)}`;
}
