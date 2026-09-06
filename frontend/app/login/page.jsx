'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';

import CreateProfilePage from '../CreateProfilePage/CreateProfilePage';
import CompetencyQuizPage from '../CompetencyQuizPage/CompetencyQuizPage';

export default function LoginPage() {
  const router = useRouter();

  // login → profile → quiz
  const [currentStep, setCurrentStep] = useState('login');

  // Stores the profile throughout the workflow
  const [officerProfile, setOfficerProfile] = useState(null);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');

  /*
   * LOGIN
   */
  const handleLogin = (e) => {
    e.preventDefault();
    setLoginError('');

    if (!email.trim() || !password.trim()) {
      setLoginError('Please enter your email and password.');
      return;
    }

    /*
     * Demo authenticated user.
     *
     * Replace this with your real authentication logic later.
     */
    const loggedInProfile = {
      name: 'Dr. Rajesh Sharma',
      email: email.trim(),
      cadreId: 'IND-88219',
      designation: 'Assistant Director',
      division: 'CSO Analytics & National Accounts',
      cadreStream: 'Indian Statistical Service (ISS)',
      cadre: 'Cadre Band 3',
      yearsOfService: '5-10 years',
      targetBand: 'Director — National Accounts (Band 4)',
      phone: '+91 98101 23456',
      specialization: [
        'Sampling Design',
        'Econometric Forecasting',
        'PySpark & Distributed SQL',
      ],
      avatarInitials: 'RS',
      isRegistered: false,
    };

    setOfficerProfile(loggedInProfile);

    // After login → Profile Setup
    setCurrentStep('profile');
  };

  /*
   * PROFILE SETUP → BASELINE QUIZ
   */
  const handleProfileComplete = (profile) => {
    setOfficerProfile(profile);

    // Immediately move to competency baseline quiz
    setCurrentStep('quiz');
  };

  /*
   * QUIZ COMPLETE → DASHBOARD
   */
  const handleQuizComplete = (completedProfile) => {
    setOfficerProfile(completedProfile);

    /*
     * The quiz component already adds:
     *
     * quizResults: {
     *   score,
     *   total,
     *   percentage,
     *   congruence,
     *   dimensionLevels,
     *   testedAt
     * }
     *
     * Now send the completed profile to the dashboard.
     */

    // Optional: persist the completed profile
    if (typeof window !== 'undefined') {
      localStorage.setItem(
        'officerProfile',
        JSON.stringify(completedProfile)
      );
    }

    router.push('/stats');
  };

  /*
   * ============================================================
   * STEP 2 — PROFILE SETUP
   * ============================================================
   */
  if (currentStep === 'profile') {
    return (
      <CreateProfilePage
        initialProfile={officerProfile}
        onBackToLogin={() => {
          setCurrentStep('login');
        }}
        onSaveAndProceedToQuiz={handleProfileComplete}
      />
    );
  }

  /*
   * ============================================================
   * STEP 3 — COMPETENCY BASELINE QUIZ
   * ============================================================
   */
  if (currentStep === 'quiz') {
    return (
      <CompetencyQuizPage
        officerProfile={officerProfile}
        onBackToProfile={() => {
          setCurrentStep('profile');
        }}
        onBackToLogin={() => {
          setCurrentStep('login');
        }}
        onCompleteQuizAndLaunchDashboard={
          handleQuizComplete
        }
      />
    );
  }

  /*
   * ============================================================
   * STEP 1 — LOGIN
   * ============================================================
   */
  return (
    <main className="min-h-screen bg-[#f7f8fc] px-4 py-8 sm:px-6">
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center">

        <div className="w-full max-w-md">

          {/* LOGIN CARD */}
          <div className="rounded-2xl border border-[#dfe2eb] bg-white p-6 shadow-sm sm:p-8">

            {/* Header */}
            <div className="mb-7">

              <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.15em] text-[#757987]">
                MoSPI Skill Intelligence
              </p>

              <h1 className="text-2xl font-bold tracking-tight text-[#00236f]">
                Officer Login
              </h1>

              <p className="mt-2 text-xs leading-5 text-[#707382]">
                Sign in to access your competency profile,
                baseline assessment, and personalized learning
                pathway.
              </p>

            </div>

            {/* Error */}
            {loginError && (
              <div className="mb-5 rounded-xl border border-[#ffc8c3] bg-[#fff4f2] p-3 text-xs text-[#93000a]">
                {loginError}
              </div>
            )}

            {/* Login Form */}
            <form
              onSubmit={handleLogin}
              className="space-y-5"
            >

              {/* Email */}
              <div>
                <label
                  htmlFor="email"
                  className="mb-1.5 block text-[10px] font-bold text-[#343846]"
                >
                  Official Email Address
                </label>

                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) =>
                    setEmail(e.target.value)
                  }
                  placeholder="rajesh.sharma@mospi.gov.in"
                  className="w-full rounded-xl border border-[#dfe2eb] bg-[#fafbfc] px-3 py-3 text-xs text-[#202536] outline-none transition hover:border-[#cdd2df] hover:bg-white focus:border-[#00236f] focus:bg-white focus:ring-4 focus:ring-[#00236f]/5"
                  required
                />
              </div>

              {/* Password */}
              <div>
                <div className="mb-1.5 flex items-center justify-between">

                  <label
                    htmlFor="password"
                    className="text-[10px] font-bold text-[#343846]"
                  >
                    Password
                  </label>

                  <button
                    type="button"
                    className="text-[10px] font-semibold text-[#00236f] hover:underline"
                  >
                    Forgot password?
                  </button>

                </div>

                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) =>
                    setPassword(e.target.value)
                  }
                  placeholder="Enter your password"
                  className="w-full rounded-xl border border-[#dfe2eb] bg-[#fafbfc] px-3 py-3 text-xs text-[#202536] outline-none transition hover:border-[#cdd2df] hover:bg-white focus:border-[#00236f] focus:bg-white focus:ring-4 focus:ring-[#00236f]/5"
                  required
                />
              </div>

              {/* Login */}
              <button
                type="submit"
                className="w-full rounded-xl bg-[#00236f] px-5 py-3 text-xs font-bold text-white shadow-[0_6px_18px_rgba(0,35,111,0.18)] transition hover:bg-[#00358f]"
              >
                Sign In
              </button>

            </form>

            {/* Divider */}
            <div className="my-6 flex items-center gap-3">
              <div className="h-px flex-1 bg-[#edf0f5]" />
              <span className="text-[9px] font-semibold uppercase tracking-wide text-[#999ca8]">
                New officer
              </span>
              <div className="h-px flex-1 bg-[#edf0f5]" />
            </div>

            {/* Profile Setup */}
            <button
              type="button"
              onClick={() => {
                /*
                 * If the user hasn't logged in yet,
                 * create the basic profile object so
                 * CreateProfilePage has initial values.
                 */
                if (!officerProfile) {
                  setOfficerProfile({
                    name: 'Dr. Rajesh Sharma',
                    email: email.trim(),
                    cadreId: 'IND-88219',
                    designation: 'Assistant Director',
                    division:
                      'CSO Analytics & National Accounts',
                    cadreStream:
                      'Indian Statistical Service (ISS)',
                    cadre: 'Cadre Band 3',
                    yearsOfService: '5-10 years',
                    targetBand:
                      'Director — National Accounts (Band 4)',
                    phone: '+91 98101 23456',
                    specialization: [
                      'Sampling Design',
                      'Econometric Forecasting',
                      'PySpark & Distributed SQL',
                    ],
                    avatarInitials: 'RS',
                    isRegistered: false,
                  });
                }

                setCurrentStep('profile');
              }}
              className="w-full rounded-xl border border-[#dfe2eb] bg-white px-5 py-3 text-xs font-semibold text-[#00236f] transition hover:border-[#bfc7df] hover:bg-[#f8f9ff]"
            >
              Profile Setup
            </button>

          </div>

          {/* Footer text */}
          <p className="mt-5 text-center text-[9px] leading-4 text-[#858895]">
            Secure officer authentication and competency
            assessment workflow
          </p>

        </div>
      </div>
    </main>
  );
}