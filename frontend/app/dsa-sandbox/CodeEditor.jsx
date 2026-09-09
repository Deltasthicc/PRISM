'use client';

import { useEffect, useMemo, useRef } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { indentWithTab } from '@codemirror/commands';
import { cpp } from '@codemirror/lang-cpp';
import { java } from '@codemirror/lang-java';
import { javascript } from '@codemirror/lang-javascript';
import { python } from '@codemirror/lang-python';
import { indentUnit, StreamLanguage } from '@codemirror/language';
import { csharp } from '@codemirror/legacy-modes/mode/clike';
import { EditorState } from '@codemirror/state';
import { oneDark } from '@codemirror/theme-one-dark';
import { EditorView, keymap } from '@codemirror/view';

const LANGUAGE_EXTENSIONS = {
  python: python(),
  javascript: javascript(),
  java: java(),
  cpp: cpp(),
  csharp: StreamLanguage.define(csharp),
};

const prismEditorTheme = EditorView.theme({
  '&': {
    backgroundColor: '#0b1020',
    color: '#dbe7ff',
    fontSize: '14px',
  },
  '.cm-content': {
    caretColor: '#7dd3fc',
    fontFamily: 'var(--font-mono), Consolas, "Courier New", monospace',
    lineHeight: '1.7',
    padding: '14px 0 24px',
  },
  '.cm-cursor, .cm-dropCursor': { borderLeftColor: '#7dd3fc' },
  '.cm-gutters': {
    backgroundColor: '#0b1020',
    borderRight: '1px solid #1e293b',
    color: '#52627a',
  },
  '.cm-activeLine': { backgroundColor: '#111a2e' },
  '.cm-activeLineGutter': { backgroundColor: '#111a2e', color: '#9fb4d0' },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': {
    backgroundColor: '#294675 !important',
  },
  '.cm-scroller': { overflow: 'auto' },
});

export default function CodeEditor({ language, value, onChange, onRun }) {
  const onRunRef = useRef(onRun);
  useEffect(() => {
    onRunRef.current = onRun;
  }, [onRun]);

  const extensions = useMemo(
    () => [
      LANGUAGE_EXTENSIONS[language] || python(),
      indentUnit.of('    '),
      EditorState.tabSize.of(4),
      keymap.of([
        indentWithTab,
        {
          key: 'Mod-Enter',
          run: () => {
            onRunRef.current();
            return true;
          },
        },
      ]),
      EditorView.lineWrapping,
      prismEditorTheme,
    ],
    [language]
  );

  return (
    <CodeMirror
      value={value}
      height="430px"
      theme={oneDark}
      extensions={extensions}
      onChange={onChange}
      aria-label="Code editor"
      basicSetup={{
        autocompletion: true,
        bracketMatching: true,
        closeBrackets: true,
        foldGutter: true,
        highlightActiveLine: true,
        highlightActiveLineGutter: true,
        lineNumbers: true,
      }}
    />
  );
}
