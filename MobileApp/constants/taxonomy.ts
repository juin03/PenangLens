import taxonomy from './taxonomy.json';

export const CANONICAL_TAGS = taxonomy.categories;

export const INTEREST_TAGS = CANONICAL_TAGS.map(t => t.label);

export function normalizeLegacyTag(oldTag: string): string {
  const tag = CANONICAL_TAGS.find(t => 
    t.label.toLowerCase() === oldTag.toLowerCase() || 
    t.aliases.some(a => a.toLowerCase() === oldTag.toLowerCase())
  );
  return tag?.label || oldTag;
}

export function getAllTagVariants(canonicalLabel: string): string[] {
  const tag = CANONICAL_TAGS.find(t => t.label === canonicalLabel);
  return tag ? [tag.label, ...tag.aliases] : [canonicalLabel];
}
