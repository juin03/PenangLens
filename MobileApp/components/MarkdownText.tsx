import React from 'react';
import { Text, StyleSheet } from 'react-native';
import { Colors, scale } from '@/constants/theme';

interface MarkdownTextProps {
  children: string;
  style?: any;
}

/**
 * Simple markdown renderer for chat messages.
 * Handles: **bold**, *italic*, `code`, bullet points
 */
export function MarkdownText({ children, style }: MarkdownTextProps) {
  const parts = parseMarkdown(children);
  
  return (
    <Text style={[styles.text, style]}>
      {parts.map((part, i) => {
        if (part.type === 'bold') {
          return <Text key={i} style={styles.bold}>{part.content}</Text>;
        } else if (part.type === 'italic') {
          return <Text key={i} style={styles.italic}>{part.content}</Text>;
        } else if (part.type === 'code') {
          return <Text key={i} style={styles.code}>{part.content}</Text>;
        } else if (part.type === 'link') {
          return <Text key={i} style={styles.link}>{part.content}</Text>;
        } else {
          return <Text key={i}>{part.content}</Text>;
        }
      })}
    </Text>
  );
}

interface MarkdownPart {
  type: 'text' | 'bold' | 'italic' | 'code' | 'link';
  content: string;
}

function parseMarkdown(text: string): MarkdownPart[] {
  const parts: MarkdownPart[] = [];
  let current = '';
  let i = 0;

  while (i < text.length) {
    // Bold: **text**
    if (text.slice(i, i + 2) === '**') {
      if (current) {
        parts.push({ type: 'text', content: current });
        current = '';
      }
      const end = text.indexOf('**', i + 2);
      if (end !== -1) {
        parts.push({ type: 'bold', content: text.slice(i + 2, end) });
        i = end + 2;
        continue;
      }
    }

    // Italic: *text*
    if (text[i] === '*' && text[i + 1] !== '*') {
      if (current) {
        parts.push({ type: 'text', content: current });
        current = '';
      }
      const end = text.indexOf('*', i + 1);
      if (end !== -1) {
        parts.push({ type: 'italic', content: text.slice(i + 1, end) });
        i = end + 1;
        continue;
      }
    }

    // Code: `text`
    if (text[i] === '`') {
      if (current) {
        parts.push({ type: 'text', content: current });
        current = '';
      }
      const end = text.indexOf('`', i + 1);
      if (end !== -1) {
        parts.push({ type: 'code', content: text.slice(i + 1, end) });
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
        if (current) {
          parts.push({ type: 'text', content: current });
          current = '';
        }
        parts.push({ type: 'link', content: text.slice(i + 1, textEnd) });
        i = urlEnd + 1;
        continue;
      }
    }

    current += text[i];
    i++;
  }

  if (current) {
    parts.push({ type: 'text', content: current });
  }

  return parts;
}

const styles = StyleSheet.create({
  text: {
    fontSize: scale(13),
    color: Colors.white,
    lineHeight: scale(20),
  },
  bold: {
    fontWeight: '700',
  },
  italic: {
    fontStyle: 'italic',
  },
  code: {
    fontFamily: 'monospace',
    backgroundColor: 'rgba(255,255,255,0.1)',
    paddingHorizontal: scale(4),
    paddingVertical: scale(2),
    borderRadius: scale(3),
  },
  link: {
    color: Colors.accent,
    textDecorationLine: 'underline',
  },
});
