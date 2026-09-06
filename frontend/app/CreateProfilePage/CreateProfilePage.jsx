'use client';

import React, { useState } from 'react';

export default function CreateProfilePage({
  initialProfile,
  onSaveAndProceedToQuiz,
  onBackToLogin,
}) {
  const [name, setName] = useState(
    initialProfile?.name || 'Dr. Rajesh Sharma'
  );

  const [email, setEmail] = useState(
    initialProfile?.email || 'rajesh.sharma@mospi.gov.in'
  );

  const [cadreId, setCadreId] = useState(
    initialProfile?.cadreId || 'IND-88219'
  );

  const [designation, setDesignation] = useState(
    initialProfile?.designation || 'Assistant Director'
  );

  const [division, setDivision] = useState(
    initialProfile?.division ||
      'CSO Analytics & National Accounts'
  );

  const [cadreStream, setCadreStream] = useState(
    'Indian Statistical Service (ISS)'
  );

  const [cadreBand, setCadreBand] = useState(
    'Cadre Band 3'
  );

  const [yearsOfService, setYearsOfService] =
    useState(
      initialProfile?.yearsOfService || '5-10 years'
    );

  const [targetBand, setTargetBand] = useState(
    initialProfile?.targetBand ||
      'Director — National Accounts (Band 4)'
  );

  const [phone, setPhone] = useState(
    '+91 98101 23456'
  );

  const [specializations, setSpecializations] =
    useState(
      initialProfile?.specialization || [
        'Sampling Design',
        'Econometric Forecasting',
        'PySpark & Distributed SQL',
      ]
    );

  const [validationError, setValidationError] =
    useState('');

  const designationOptions = [
    {
      label: 'Junior Statistical Officer (JSO)',
      band: 'Cadre Band 1 (SSS)',
      defaultTarget:
        'Senior Statistical Officer (Band 2)',
    },
    {
      label: 'Senior Statistical Officer (SSO)',
      band: 'Cadre Band 2 (SSS)',
      defaultTarget:
        'Assistant Director (Band 3)',
    },
    {
      label: 'Assistant Director',
      band: 'Cadre Band 3 (ISS)',
      defaultTarget:
        'Deputy Director (Band 4)',
    },
    {
      label: 'Deputy Director',
      band: 'Cadre Band 4 (ISS)',
      defaultTarget:
        'Director — National Accounts (Band 4+)',
    },
    {
      label: 'Joint Director',
      band: 'Cadre Band 4+ (ISS)',
      defaultTarget:
        'Director General — Statistics (Band 5)',
    },
    {
      label: 'Director — National Accounts',
      band: 'Cadre Band 5 (ISS)',
      defaultTarget:
        'Principal Advisor / DG',
    },
    {
      label: 'Data Science & Big Data Specialist',
      band: 'Technical Cadre (NIC/MoSPI)',
      defaultTarget:
        'Chief Data Architect',
    },
    {
      label: 'Statistical Research Fellow',
      band: 'Cadre Band 1 (Fellowship)',
      defaultTarget:
        'Junior Statistical Officer',
    },
  ];

  const divisionOptions = [
    'Central Statistics Office (CSO) — National Accounts Division (NAD)',
    'CSO Analytics & Big Data Systems',
    'National Sample Survey Office (NSSO) — Survey Design & Research Division (SDRD)',
    'Data Quality & Assurance Division (DQAD) — Kolkata',
    'Field Operations Division (FOD) — Zonal Field Survey Unit',
    'Economic Statistics Division (ESD) — New Delhi',
    'National Statistical Systems Training Academy (NSSTA) — Greater Noida',
    'Computer Centre & Sovereign Cloud Infrastructure — New Delhi',
  ];

  const domainSpecialtyList = [
    {
      id: 'sampling',
      label: 'NSSO Sampling Design & Weighting',
    },
    {
      id: 'econometrics',
      label: 'Econometric Forecasting & Time-Series',
    },
    {
      id: 'pyspark',
      label: 'PySpark & Large-Scale SQL Wrangling',
    },
    {
      id: 'dpdp',
      label: 'DPDP Act 2023 & Sovereign Cloud Security',
    },
    {
      id: 'dist_ml',
      label: 'Distributed ML & Imputation Systems',
    },
    {
      id: 'dsa',
      label: 'Algorithms & Graph Theory (DSA)',
    },
  ];

  const handleDesignationChange = (newDesig) => {
    setDesignation(newDesig);

    const matched = designationOptions.find(
      (d) => d.label === newDesig
    );

    if (matched) {
      setCadreBand(matched.band);
      setTargetBand(matched.defaultTarget);
    }
  };

  const toggleSpecialization = (itemLabel) => {
    if (specializations.includes(itemLabel)) {
      setSpecializations(
        specializations.filter(
          (s) => s !== itemLabel
        )
      );
    } else {
      setSpecializations([
        ...specializations,
        itemLabel,
      ]);
    }
  };

  const getInitials = (nameStr) => {
    const cleaned = nameStr
      .replace(/Dr\.|Mr\.|Ms\.|Mrs\./g, '')
      .trim();

    const parts = cleaned.split(' ');

    if (parts.length >= 2) {
      return (
        parts[0][0] + parts[1][0]
      ).toUpperCase();
    }

    return nameStr
      .slice(0, 2)
      .toUpperCase();
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setValidationError('');

    if (!name.trim()) {
      setValidationError(
        'Please provide the Officer Full Name.'
      );
      return;
    }

    if (
      !email.trim() ||
      !email.includes('@')
    ) {
      setValidationError(
        'Please provide a valid official government email address.'
      );
      return;
    }

    if (!cadreId.trim()) {
      setValidationError(
        'Please provide an official Cadre ID.'
      );
      return;
    }

    if (!designation) {
      setValidationError(
        'Please select your official Designation.'
      );
      return;
    }

    if (specializations.length === 0) {
      setValidationError(
        'Please select at least one primary domain specialization.'
      );
      return;
    }

    const updatedProfile = {
      name: name.trim(),
      email: email.trim(),
      cadreId: cadreId.trim(),
      designation,
      division,
      cadreStream,
      cadre: cadreBand,
      yearsOfService,
      targetBand,
      phone,
      specialization: specializations,
      avatarInitials: getInitials(name),
      isRegistered: true,
      registeredAt: new Date().toISOString(),
    };

    if (onSaveAndProceedToQuiz) {
      onSaveAndProceedToQuiz(updatedProfile);
    }
  };

  return (
    <div className="min-h-full w-full bg-[#f7f8fc] px-4 py-5 sm:px-6 sm:py-8">

      <div className="mx-auto w-full max-w-6xl">

        {/* TOP */}
        <div className="mb-5 flex items-center justify-between">

        </div>

        {/* HEADER */}
        <div className="mb-6 rounded-2xl border border-[#dfe2eb] bg-white p-5 shadow-sm sm:p-6">

          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">

            <div>
              <div className="flex flex-wrap items-center gap-2">

                <h1 className="text-xl font-bold tracking-tight text-[#00236f]">
                  Create Officer Profile
                </h1>

                <span className="rounded-full bg-[#effcf9] px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-[#006b61]">
                  Secure
                </span>

              </div>

              <p className="mt-1 max-w-2xl text-xs leading-5 text-[#707382]">
                Complete your official cadre information
                to generate a personalized competency
                baseline.
              </p>
            </div>

            <div className="rounded-xl border border-[#e1e4ec] bg-[#fafbfc] px-4 py-2.5">

              <p className="text-[9px] font-bold uppercase tracking-wide text-[#858895]">
                Form
              </p>

              <p className="text-[10px] font-semibold text-[#202536]">
                MOSPI-PERS-2024
              </p>

            </div>

          </div>
        </div>

        {/* ERROR */}
        {validationError && (
          <div className="mb-5 rounded-xl border border-[#ffc8c3] bg-[#fff4f2] p-4 text-xs text-[#93000a]">
            <p className="font-bold">
              Please check your profile
            </p>

            <p className="mt-1">
              {validationError}
            </p>
          </div>
        )}

        {/* CONTENT */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">

          {/* FORM */}
          <div className="lg:col-span-8">

            <form
              onSubmit={handleSubmit}
              className="space-y-5"
            >

              {/* DESIGNATION */}
              <section className="rounded-2xl border border-[#dfe2eb] bg-white p-5 shadow-sm sm:p-6">

                <div className="mb-5 border-b border-[#edf0f5] pb-4">

                  <div className="flex items-center justify-between gap-3">

                    <div>
                      <h2 className="text-sm font-bold text-[#202536]">
                        Official Designation & Cadre
                      </h2>

                      <p className="mt-1 text-[10px] leading-4 text-[#7a7d8b]">
                        Your designation determines the initial
                        competency benchmark.
                      </p>
                    </div>

                    <span className="rounded-full bg-[#fff5ed] px-2.5 py-1 text-[9px] font-bold text-[#904d00]">
                      REQUIRED
                    </span>

                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">

                  <Field
                    label="Cadre Designation"
                    required
                  >
                    <select
                      value={designation}
                      onChange={(e) =>
                        handleDesignationChange(
                          e.target.value
                        )
                      }
                      className="field"
                    >
                      {designationOptions.map(
                        (opt) => (
                          <option
                            key={opt.label}
                            value={opt.label}
                          >
                            {opt.label}
                          </option>
                        )
                      )}
                    </select>
                  </Field>

                  <Field label="Cadre Band / Pay Matrix Level">
                    <input
                      type="text"
                      value={cadreBand}
                      onChange={(e) =>
                        setCadreBand(e.target.value)
                      }
                      className="field"
                    />
                  </Field>

                  <Field label="Cadre Service Stream">
                    <select
                      value={cadreStream}
                      onChange={(e) =>
                        setCadreStream(
                          e.target.value
                        )
                      }
                      className="field"
                    >
                      <option>
                        Indian Statistical Service (ISS)
                      </option>

                      <option>
                        Subordinate Statistical Service (SSS)
                      </option>

                      <option>
                        Technical & IT Cadre (NIC/MoSPI)
                      </option>

                      <option>
                        Contractual Specialist / Research Fellow
                      </option>
                    </select>
                  </Field>

                  <Field label="Target Promotional Benchmark">
                    <select
                      value={targetBand}
                      onChange={(e) =>
                        setTargetBand(
                          e.target.value
                        )
                      }
                      className="field"
                    >
                      <option>
                        Director — National Accounts (Band 4)
                      </option>

                      <option>
                        Joint Director — Survey & Sampling (Band 4+)
                      </option>

                      <option>
                        Deputy Director — Cloud & Systems (Band 4)
                      </option>

                      <option>
                        Assistant Director (Band 3)
                      </option>

                      <option>
                        Senior Statistical Officer (Band 2)
                      </option>
                    </select>
                  </Field>

                </div>
              </section>

              {/* IDENTIFICATION */}
              <section className="rounded-2xl border border-[#dfe2eb] bg-white p-5 shadow-sm sm:p-6">

                <div className="mb-5 border-b border-[#edf0f5] pb-4">

                  <h2 className="text-sm font-bold text-[#202536]">
                    Officer Identification
                  </h2>

                  <p className="mt-1 text-[10px] text-[#7a7d8b]">
                    Official identity and contact information.
                  </p>

                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">

                  <Field
                    label="Officer Full Name"
                    required
                  >
                    <input
                      type="text"
                      value={name}
                      onChange={(e) =>
                        setName(e.target.value)
                      }
                      placeholder="Dr. Rajesh Sharma"
                      className="field"
                      required
                    />
                  </Field>

                  <Field
                    label="Official Email Address"
                    required
                  >
                    <input
                      type="email"
                      value={email}
                      onChange={(e) =>
                        setEmail(e.target.value)
                      }
                      placeholder="rajesh.sharma@mospi.gov.in"
                      className="field"
                      required
                    />
                  </Field>

                  <Field
                    label="Employee / Cadre ID"
                    required
                  >
                    <input
                      type="text"
                      value={cadreId}
                      onChange={(e) =>
                        setCadreId(e.target.value)
                      }
                      placeholder="IND-88219"
                      className="field"
                      required
                    />
                  </Field>

                  <Field label="Years of Service">
                    <select
                      value={yearsOfService}
                      onChange={(e) =>
                        setYearsOfService(
                          e.target.value
                        )
                      }
                      className="field"
                    >
                      <option>
                        Less than 2 years (Probationer / Entry)
                      </option>

                      <option>
                        2 - 5 years (Junior Cadre)
                      </option>

                      <option>
                        5 - 10 years (Mid Cadre)
                      </option>

                      <option>
                        10+ years (Senior Administrative Cadre)
                      </option>
                    </select>
                  </Field>

                  <Field
                    label="Government Mobile Number"
                    className="sm:col-span-2"
                  >
                    <input
                      type="tel"
                      value={phone}
                      onChange={(e) =>
                        setPhone(e.target.value)
                      }
                      className="field"
                    />
                  </Field>

                </div>
              </section>

              {/* DIVISION */}
              <section className="rounded-2xl border border-[#dfe2eb] bg-white p-5 shadow-sm sm:p-6">

                <div className="mb-4">

                  <h2 className="text-sm font-bold text-[#202536]">
                    Department & Division
                  </h2>

                  <p className="mt-1 text-[10px] text-[#7a7d8b]">
                    Select your current operational division.
                  </p>

                </div>

                <select
                  value={division}
                  onChange={(e) =>
                    setDivision(e.target.value)
                  }
                  className="field"
                >
                  {divisionOptions.map(
                    (div) => (
                      <option
                        key={div}
                        value={div}
                      >
                        {div}
                      </option>
                    )
                  )}
                </select>

              </section>

              {/* SPECIALIZATIONS */}
              <section className="rounded-2xl border border-[#dfe2eb] bg-white p-5 shadow-sm sm:p-6">

                <div className="mb-5 flex items-start justify-between gap-4">

                  <div>
                    <h2 className="text-sm font-bold text-[#202536]">
                      Primary Domain Specializations
                    </h2>

                    <p className="mt-1 text-[10px] leading-4 text-[#7a7d8b]">
                      Select the competency areas that best
                      represent your current role.
                    </p>
                  </div>

                  <span className="shrink-0 rounded-full bg-[#e9edff] px-2.5 py-1 text-[10px] font-bold text-[#00236f]">
                    {specializations.length} selected
                  </span>

                </div>

                <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">

                  {domainSpecialtyList.map(
                    (domain) => {
                      const isChecked =
                        specializations.includes(
                          domain.label
                        );

                      return (
                        <button
                          type="button"
                          key={domain.id}
                          onClick={() =>
                            toggleSpecialization(
                              domain.label
                            )
                          }
                          className={`flex min-h-[58px] items-center justify-between gap-3 rounded-xl border p-3 text-left transition ${
                            isChecked
                              ? 'border-[#9eafff] bg-[#f1f3ff] text-[#00236f]'
                              : 'border-[#e2e4eb] bg-[#fafbfc] text-[#4e5260] hover:border-[#cbd0df] hover:bg-white'
                          }`}
                        >
                          <span className="text-[11px] font-semibold leading-4">
                            {domain.label}
                          </span>

                          <span
                            className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border text-xs ${
                              isChecked
                                ? 'border-[#00236f] bg-[#00236f] text-white'
                                : 'border-[#c9ccd7] bg-white'
                            }`}
                          >
                            {isChecked ? '✓' : ''}
                          </span>

                        </button>
                      );
                    }
                  )}

                </div>
              </section>

              {/* ACTIONS */}
              <div className="flex flex-col-reverse gap-3 rounded-2xl border border-[#dfe2eb] bg-white p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between sm:p-5">

                <button
                  type="button"
                  onClick={onBackToLogin}
                  className="w-full rounded-xl border border-[#d9dce6] bg-white px-5 py-3 text-xs font-semibold text-[#555967] transition hover:bg-[#f7f8fb] hover:text-[#00236f] sm:w-auto"
                >
                  Cancel & Return to Login
                </button>

                <button
                  type="submit"
                  className="w-full rounded-xl bg-[#00236f] px-6 py-3 text-xs font-bold text-white shadow-[0_6px_18px_rgba(0,35,111,0.18)] transition hover:bg-[#00358f] sm:w-auto"
                >
                  Save Profile & Take Baseline Quiz
                </button>

              </div>

            </form>
          </div>

          {/* RIGHT PREVIEW */}
          <div className="lg:col-span-4">

            <div className="sticky top-6 space-y-4">

              <div className="rounded-2xl border border-[#dfe2eb] bg-white shadow-sm">

                <div className="border-b border-[#edf0f5] bg-[#fafbff] p-5">

                  <div className="flex items-center justify-between">

                    <div>
                      <p className="text-[9px] font-bold uppercase tracking-wide text-[#858895]">
                        Live Preview
                      </p>

                      <h3 className="mt-1 text-sm font-bold text-[#00236f]">
                        Officer Profile
                      </h3>
                    </div>

                    <span className="rounded-full bg-[#effcf9] px-2 py-1 text-[9px] font-bold text-[#006b61]">
                      Draft
                    </span>

                  </div>

                </div>

                <div className="p-5">

                  {/* AVATAR */}
                  <div className="flex items-center gap-3.5">

                    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-[#00236f] text-lg font-bold text-white">
                      {getInitials(name)}
                    </div>

                    <div className="min-w-0">

                      <h3 className="truncate text-sm font-bold text-[#202536]">
                        {name || 'Officer Name'}
                      </h3>

                      <p className="mt-0.5 truncate text-[11px] font-semibold text-[#00236f]">
                        {designation}
                      </p>

                      <p className="mt-1 text-[9px] text-[#858895]">
                        {cadreBand} · {cadreId}
                      </p>

                    </div>

                  </div>

                  {/* DETAILS */}
                  <div className="mt-5 divide-y divide-[#edf0f5] rounded-xl border border-[#e4e6ed] bg-[#fafbfc]">

                    <PreviewRow
                      label="Division"
                      value={
                        division.split('—')[0]
                      }
                    />

                    <PreviewRow
                      label="Government Email"
                      value={email}
                    />

                    <PreviewRow
                      label="Service"
                      value={yearsOfService}
                    />

                    <PreviewRow
                      label="Target"
                      value={
                        targetBand.split('—')[0]
                      }
                      highlight
                    />

                  </div>

                  {/* COMPETENCY */}
                  <div className="mt-5">

                    <div className="mb-2 flex items-center justify-between">

                      <span className="text-[9px] font-bold uppercase tracking-wide text-[#777a88]">
                        Competency Scope
                      </span>

                      <span className="text-[9px] font-semibold text-[#00236f]">
                        {specializations.length}/6
                      </span>

                    </div>

                    <div className="flex flex-wrap gap-1.5">

                      {specializations.map(
                        (spec) => (
                          <span
                            key={spec}
                            className="rounded-md border border-[#dce1f5] bg-[#f3f5ff] px-2 py-1 text-[9px] font-medium text-[#00236f]"
                          >
                            {spec
                              .split('&')[0]
                              .trim()}
                          </span>
                        )
                      )}

                    </div>
                  </div>

                  {/* STATUS */}
                  <div className="mt-5 rounded-xl border border-[#bde5df] bg-[#effcf9] p-3">

                    <p className="text-[10px] font-bold text-[#005147]">
                      Baseline ready
                    </p>

                    <p className="mt-1 text-[9px] leading-4 text-[#36756d]">
                      Your baseline quiz will be tailored to
                      your designation and selected competency
                      areas.
                    </p>

                  </div>

                </div>
              </div>

              {/* SECURITY */}
              <div className="rounded-2xl border border-[#dfe2eb] bg-white p-4 shadow-sm">

                <p className="text-xs font-bold text-[#202536]">
                  Secure Profile Registration
                </p>

                <p className="mt-1 text-[10px] leading-4 text-[#777a88]">
                  Profile information is used to establish
                  your competency baseline and personalize
                  your learning path.
                </p>

              </div>

            </div>
          </div>

        </div>
      </div>

      <style jsx>{`
        .field {
          width: 100%;
          border-radius: 0.75rem;
          border: 1px solid #dfe2eb;
          background: #fafbfc;
          padding: 0.7rem 0.8rem;
          font-size: 0.72rem;
          color: #202536;
          outline: none;
          transition: all 0.15s ease;
        }

        .field:hover {
          border-color: #cdd2df;
          background: #ffffff;
        }

        .field:focus {
          border-color: #00236f;
          background: #ffffff;
          box-shadow: 0 0 0 3px rgba(0, 35, 111, 0.07);
        }

        select.field {
          cursor: pointer;
        }
      `}</style>
    </div>
  );
}

function Field({
  label,
  required = false,
  children,
  className = '',
}) {
  return (
    <div className={className}>
      <label className="mb-1.5 block text-[10px] font-bold text-[#343846]">
        {label}

        {required && (
          <span className="ml-1 text-[#ba1a1a]">
            *
          </span>
        )}
      </label>

      {children}
    </div>
  );
}

function PreviewRow({
  label,
  value,
  highlight = false,
}) {
  return (
    <div className="flex items-start justify-between gap-3 px-3 py-2.5">

      <span className="shrink-0 text-[9px] font-medium text-[#858895]">
        {label}
      </span>

      <span
        className={`max-w-[65%] truncate text-right text-[9px] font-semibold ${
          highlight
            ? 'text-[#904d00]'
            : 'text-[#343846]'
        }`}
      >
        {value || '—'}
      </span>

    </div>
  );
}