/** Returns true if value is empty/blank OR is exactly in options (case-sensitive). */
export function isKnown(value: string, options: readonly string[]): boolean {
  if (value.trim() === "") return true;
  return options.includes(value);
}

/** Returns the set of field IDs that have a non-empty value NOT in their option list. */
export function collectInvalidFields(
  fields: ReadonlyArray<{ id: string; value: string; options: readonly string[] }>,
): Set<string> {
  const invalid = new Set<string>();
  for (const field of fields) {
    if (!isKnown(field.value, field.options)) {
      invalid.add(field.id);
    }
  }
  return invalid;
}
