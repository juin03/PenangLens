import fs from 'fs';
import path from 'path';

const taxonomy = JSON.parse(
  fs.readFileSync(path.join(process.cwd(), '../shared/taxonomy.json'), 'utf-8')
);

export const CANONICAL_TAGS = taxonomy.categories;

export const CATEGORY_TAGS = CANONICAL_TAGS.map((t: any) => t.label);

export const INTEREST_TAG_MAP: Record<string, string[]> = CANONICAL_TAGS.reduce((acc: any, cat: any) => {
  acc[cat.label] = [cat.label, ...cat.aliases];
  return acc;
}, {});

export function normalizeLegacyTag(oldTag: string): string {
  const tag = CANONICAL_TAGS.find((t: any) => 
    t.label.toLowerCase() === oldTag.toLowerCase() || 
    t.aliases.some((a: string) => a.toLowerCase() === oldTag.toLowerCase())
  );
  return tag?.label || oldTag;
}
