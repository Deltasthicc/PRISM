'use client';

import { useState } from 'react';
import Button from '@/components/ui/Button';
import {
  BLANK_CERTIFICATE,
  BLANK_EXPERIENCE,
  BLANK_QUALIFICATION,
  parseTags,
  tagsToText,
} from '@/lib/profileForm';

// Editor for the structured, self-declared profile lists (PS75-02):
// qualifications, work experience, certificates earned elsewhere, interests
// and skills. English only, like the other panels added after the original
// translation pass. Everything here is declared by the learner and is not
// verified or used as competency evidence.

const INPUT_CLASS =
  'bg-white text-[#131b2e] font-sans text-sm px-3 py-2 rounded-lg border border-[#c5c5d3]/60 outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f] w-full';

// Keeps the text the user is typing separate from the parsed tags, so a
// trailing comma or space is not swallowed on every keystroke.
function TagsInput({ label, tags, placeholder, onChange }) {
  const [text, setText] = useState(tagsToText(tags));
  return (
    <label className="flex flex-col gap-1.5">
      <span className="font-sans text-xs font-semibold text-[#444651]">{label}</span>
      <input
        type="text"
        className={INPUT_CLASS}
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          onChange(parseTags(event.target.value));
        }}
        onBlur={() => setText(tagsToText(parseTags(text)))}
        placeholder={placeholder}
      />
    </label>
  );
}

function Rows({ legend, hint, rows, blank, fields, noun, onChange }) {
  function update(index, key, value) {
    onChange(rows.map((row, i) => (i === index ? { ...row, [key]: value } : row)));
  }
  return (
    <fieldset className="md:col-span-2 border border-[#c5c5d3]/60 rounded-lg p-4">
      <legend className="font-sans text-sm font-semibold text-[#00236f] px-1">{legend}</legend>
      <p className="font-sans text-xs text-[#757682] mb-3">{hint}</p>
      {rows.length === 0 && <p className="font-sans text-sm text-[#757682] mb-3">None added yet.</p>}
      <ul className="flex flex-col gap-4">
        {rows.map((row, index) => (
          <li key={index} className="grid grid-cols-1 sm:grid-cols-2 gap-3 border-b border-[#c5c5d3]/40 pb-4">
            {fields.map((field) => (
              <label key={field.key} className={`flex flex-col gap-1 ${field.wide ? 'sm:col-span-2' : ''}`}>
                <span className="font-sans text-xs font-semibold text-[#444651]">
                  {field.label} <span className="sr-only">for {noun} {index + 1}</span>
                </span>
                {field.multiline ? (
                  <textarea
                    rows={2}
                    maxLength={field.max}
                    className={INPUT_CLASS}
                    value={row[field.key] ?? ''}
                    onChange={(event) => update(index, field.key, event.target.value)}
                  />
                ) : (
                  <input
                    type={field.year ? 'number' : 'text'}
                    {...(field.year ? { min: 1950, max: 2100 } : { maxLength: field.max })}
                    className={INPUT_CLASS}
                    value={row[field.key] ?? ''}
                    onChange={(event) => update(index, field.key, event.target.value)}
                  />
                )}
              </label>
            ))}
            <div className="sm:col-span-2">
              <Button type="button" variant="ghost" onClick={() => onChange(rows.filter((_, i) => i !== index))}>
                Remove {noun} {index + 1}
              </Button>
            </div>
          </li>
        ))}
      </ul>
      {rows.length < 30 && (
        <div className="mt-3">
          <Button type="button" variant="ghost" onClick={() => onChange([...rows, { ...blank }])}>
            Add {noun}
          </Button>
        </div>
      )}
    </fieldset>
  );
}

export default function ProfileCredentials({ profile, onChange }) {
  const set = (key) => (value) => onChange({ ...profile, [key]: value });
  return (
    <>
      <Rows
        legend="Qualifications"
        hint="Degrees and diplomas, as you declare them. They are not verified."
        rows={profile.qualifications || []}
        blank={BLANK_QUALIFICATION}
        noun="qualification"
        onChange={set('qualifications')}
        fields={[
          { key: 'degree', label: 'Degree or diploma', max: 200 },
          { key: 'institution', label: 'Institution', max: 200 },
          { key: 'year', label: 'Year', year: true },
        ]}
      />
      <Rows
        legend="Work experience"
        hint="Roles you have held. Leave the end year empty for a current role."
        rows={profile.work_experience || []}
        blank={BLANK_EXPERIENCE}
        noun="role"
        onChange={set('work_experience')}
        fields={[
          { key: 'title', label: 'Title', max: 200 },
          { key: 'organization', label: 'Organization', max: 200 },
          { key: 'start_year', label: 'Start year', year: true },
          { key: 'end_year', label: 'End year', year: true },
          { key: 'description', label: 'What you did', multiline: true, wide: true, max: 1000 },
        ]}
      />
      <Rows
        legend="Certificates earned elsewhere"
        hint="Credentials from other bodies, as you declare them and not verified. Certificates issued by this platform are listed under Certificates."
        rows={profile.external_certificates || []}
        blank={BLANK_CERTIFICATE}
        noun="certificate"
        onChange={set('external_certificates')}
        fields={[
          { key: 'name', label: 'Certificate name', max: 200 },
          { key: 'issuer', label: 'Issued by', max: 200 },
          { key: 'year', label: 'Year', year: true },
          { key: 'credential_id', label: 'Credential ID (optional)', max: 100 },
        ]}
      />
      <TagsInput
        label="Skills (comma separated)"
        tags={profile.skills}
        placeholder="Python, GIS, report writing"
        onChange={set('skills')}
      />
      <TagsInput
        label="Interests (comma separated)"
        tags={profile.interests}
        placeholder="Climate modelling, open data"
        onChange={set('interests')}
      />
    </>
  );
}
