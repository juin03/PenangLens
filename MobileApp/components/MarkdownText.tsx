import React from 'react';
import { Text, View, StyleSheet } from 'react-native';
import { Colors, scale } from '@/constants/theme';

interface MarkdownTextProps {
  children: string;
  style?: any;
}

/**
 * Simple markdown renderer for chat messages.
 * Handles: ### headers, **bold**, *italic*, `code`, [links](url), - bullets, numbered lists
 */
export function MarkdownText({ children, style }: MarkdownTextProps) {
  if (!children) return <Text style={[styles.text, style]}>...</Text>;

  const lines = children.split('\n');

  return (
    <View>
      {lines.map((line, li) => {
        const trimmed = line.trimStart();

        // Headers: ### or ####
        if (trimmed.startsWith('#### ')) {
          return <Text key={li} style={[styles.text, style, styles.h4]}>{parseInline(trimmed.slice(5))}</Text>;
        }
        if (trimmed.startsWith('### ')) {
          return <Text key={li} style={[styles.text, style, styles.h3]}>{parseInline(trimmed.slice(4))}</Text>;
        }
        if (trimmed.startsWith('## ')) {
          return <Text key={li} style={[styles.text, style, styles.h3]}>{parseInline(trimmed.slice(3))}</Text>;
        }

        // Bullet: - text or * text
        if (/^[-*]\s/.test(trimmed)) {
          return (
            <View key={li} style={styles.bulletRow}>
              <Text style={[styles.text, style, styles.bullet]}>•</Text>
              <Text style={[styles.text, style, styles.bulletText]}>{parseInline(trimmed.slice(2))}</Text>
            </View>
          );
        }

        // Numbered list: 1. text
        const numMatch = trimmed.match(/^(\d+)\.\s/);
        if (numMatch) {
          return (
            <View key={li} style={styles.bulletRow}>
              <Text style={[styles.text, style, styles.bullet]}>{numMatch[1]}.</Text>
              <Text style={[styles.text, style, styles.bulletText]}>{parseInline(trimmed.slice(numMatch[0].length))}</Text>
            </View>
          );
        }

        // Empty line
        if (!trimmed) return <View key={li} style={{ height: scale(6) }} />;

        // Regular text
        return <Text key={li} style={[styles.text, style]}>{parseInline(line)}</Text>;
      })}
    </View>
  );
}

function parseInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let current = '';
  let i = 0;
  let key = 0;

  while (i < text.length) {
    // Bold: **text**
    if (text.slice(i, i + 2) === '**') {
      if (current) { parts.push(<Text key={key++}>{current}</Text>); current = ''; }
      const end = text.indexOf('**', i + 2);
      if (end !== -1) {
        parts.push(<Text key={key++} style={styles.bold}>{text.slice(i + 2, end)}</Text>);
        i = end + 2;
        continue;
      }
    }

    // Italic: *text* (not **)
    if (text[i] === '*' && text[i + 1] !== '*') {
      if (current) { parts.push(<Text key={key++}>{current}</Text>); current = ''; }
      const end = text.indexOf('*', i + 1);
      if (end !== -1) {
        parts.push(<Text key={key++} style={styles.italic}>{text.slice(i + 1, end)}</Text>);
        i = end + 1;
        continue;
      }
    }

    // Code: `text`
    if (text[i] === '`') {
      if (current) { parts.push(<Text key={key++}>{current}</Text>); current = ''; }
      const end = text.indexOf('`', i + 1);
      if (end !== -1) {
        parts.push(<Text key={key++} style={styles.code}>{text.slice(i + 1, end)}</Text>);
        i = end + 1;
        continue;
      }
    }

    // Link: [text](url)
    if (text[i] === '[') {
      const textEnd = text.indexOf(']', i);
      const urlStart = text.indexOf('(', textEnd);
      const urlEnd = text.indexOf(')', urlStart);
      if (textEnd !== -1 && urlStart === textEnd + 1 && urlEnd !== -1) {
        if (current) { parts.push(<Text key={key++}>{current}</Text>); current = ''; }
        parts.push(<Text key={key++} style={styles.link}>{text.slice(i + 1, textEnd)}</Text>);
        i = urlEnd + 1;
        continue;
      }
    }

    current += text[i];
    i++;
  }

  if (current) parts.push(<Text key={key++}>{current}</Text>);
  return parts;
}

const styles = StyleSheet.create({
  text: {
    fontSize: scale(13),
    color: Colors.textPrimary,
    lineHeight: scale(20),
  },
  h3: {
    fontSize: scale(15),
    fontWeight: '700',
    marginTop: scale(8),
    marginBottom: scale(4),
  },
  h4: {
    fontSize: scale(14),
    fontWeight: '600',
    marginTop: scale(6),
    marginBottom: scale(2),
  },
  bold: {
    fontWeight: '700',
  },
  italic: {
    fontStyle: 'italic',
  },
  code: {
    fontFamily: 'monospace',
    backgroundColor: 'rgba(0,0,0,0.06)',
    paddingHorizontal: scale(4),
    borderRadius: scale(3),
    fontSize: scale(12),
  },
  link: {
    color: Colors.primary,
    textDecorationLine: 'underline',
  },
  bulletRow: {
    flexDirection: 'row',
    paddingLeft: scale(4),
    marginBottom: scale(2),
  },
  bullet: {
    width: scale(16),
    color: Colors.textMuted,
  },
  bulletText: {
    flex: 1,
  },
});
