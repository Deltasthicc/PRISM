import { describe, expect, it } from 'vitest';
import {
  MAX_UPLOAD_BYTES,
  fileExtension,
  formatBytes,
  kindLabel,
  validateFileHint,
} from '@/lib/api/contentLibrary';

describe('content library client hints', () => {
  it('extracts a lower-cased extension from the last path segment only', () => {
    expect(fileExtension('Lecture.PDF')).toBe('pdf');
    expect(fileExtension('..\\..\\evil.docx')).toBe('docx');
    expect(fileExtension('archive.tar.gz')).toBe('gz');
    expect(fileExtension('noextension')).toBe('');
    expect(fileExtension('.hidden')).toBe('');
    expect(fileExtension(undefined)).toBe('');
  });

  it('accepts an allowed file and rejects disallowed, empty and oversize ones', () => {
    expect(validateFileHint({ name: 'notes.md', size: 10 })).toBe('');
    expect(validateFileHint({ name: 'run.exe', size: 10 })).toMatch(/Unsupported/);
    expect(validateFileHint({ name: 'a.pdf', size: 0 })).toMatch(/empty/);
    expect(validateFileHint({ name: 'a.mp4', size: MAX_UPLOAD_BYTES + 1 })).toMatch(/too large/);
    expect(validateFileHint(null)).toMatch(/Choose a file/);
  });

  it('formats sizes and labels kinds', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(2048)).toBe('2.0 KB');
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB');
    expect(kindLabel('recorded_lecture')).toBe('Recorded lecture');
    expect(kindLabel('unknown_kind')).toBe('unknown_kind');
  });
});
