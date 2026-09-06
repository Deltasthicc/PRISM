'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';

import { useAuthStore } from '@/store/useAuthStore';
import CreateProfilePage from '../CreateProfilePage/CreateProfilePage';
import CompetencyQuizPage from '../CompetencyQuizPage/CompetencyQuizPage';
import { COMPETENCY_TOPICS } from '@/lib/competencyTopics';

export default function LoginPage() {
  const router = useRouter();
  const authLogin = useAuthStore((s) => s.login);
  const authRegister = useAuthStore((s) => s.register);

  // The demo starts with profile setup, then continues to the quiz.
  const [currentStep, setCurrentStep] = useState('profile');

  // Stores the profile throughout the workflow
  const [officerProfile, setOfficerProfile] = useState(null);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Demo login: this is a placeholder page with no real credential check --
  // any non-empty email/password combination is accepted, matching this
  // project's actual auth model right now (backend DISABLE_AUTH grants every
  // request full access; see routes/authorization.py). What *does* need to
  // be real is the player_id behind it: the email is used as a stable
  // backend username so /stats, /academy and the competency quiz below all
  // have a genuine player record to read and write, instead of the previous
  // flow which only ever set local React state and never touched the real
  // auth store -- that mismatch (useRequireAuth() always seeing no player)
  // was the actual cause of the login loop.
  async function resolveRealPlayer(usernameSeed) {
    const username = usernameSeed.trim().toLowerCase();
    let ok = await authLogin(username);
    if (!ok) ok = await authRegister(username);
    return ok ? useAuthStore.getState().player : null;
  }

  function profileEmail(input, username) {
    return input.includes('@') ? input : `${username}@demo.prism.local`;
  }

  /*
   * LOGIN
   */
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError('');

    if (!email.trim()) {
      setLoginError('Please enter any demo username or email.');
      return;
    }

    setSubmitting(true);
    const realPlayer = await resolveRealPlayer(email);
    setSubmitting(false);

    if (!realPlayer) {
      setLoginError('Could not reach the backend. Please try again.');
      return;
    }

    const loggedInProfile = {
      name: 'Dr. Rajesh Sharma',
      email: profileEmail(email.trim(), realPlayer.username),
      player_id: realPlayer.player_id,
      username: realPlayer.username,
      cadreId: 'IND-88219',
      designation: 'Assistant Director',
      division: 'CSO Analytics & National Accounts',
      cadreStream: 'Indian Statistical Service (ISS)',
      cadre: 'Cadre Band 3',
      yearsOfService: '5-10 years',
      targetBand: 'Director — National Accounts (Band 4)',
      phone: '+91 98101 23456',
      specialization: COMPETENCY_TOPICS.slice(0, 3).map((topic) => topic.label),
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
        onResolvePlayer={resolveRealPlayer}
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
                  Demo Username or Email
                </label>

                <input
                  id="email"
                  type="text"
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
                    Demo Password (optional)
                  </label>

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
                />
              </div>

              {/* Login */}
              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-xl bg-[#00236f] px-5 py-3 text-xs font-bold text-white shadow-[0_6px_18px_rgba(0,35,111,0.18)] transition hover:bg-[#00358f] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? 'Signing in…' : 'Sign In'}
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
              disabled={submitting}
              onClick={async () => {
                /*
                 * This shortcut skips the login form entirely, but it must
                 * still resolve to a real backend player -- same reasoning
                 * as handleLogin above. Uses whatever email the user may
                 * have already typed, or a generated demo identity otherwise.
                 */
                if (!officerProfile) {
                  setSubmitting(true);
                  const seed = email.trim() || `demo-officer-${Date.now()}`;
                  const realPlayer = await resolveRealPlayer(seed);
                  setSubmitting(false);
                  if (!realPlayer) {
                    setLoginError('Could not reach the backend. Please try again.');
                    return;
                  }
                  setOfficerProfile({
                    name: 'Dr. Rajesh Sharma',
                    email: profileEmail(seed, realPlayer.username),
                    player_id: realPlayer.player_id,
                    username: realPlayer.username,
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
                    specialization: [COMPETENCY_TOPICS[0].label],
                    avatarInitials: 'RS',
                    isRegistered: false,
                  });
                }

                setCurrentStep('profile');
              }}
              className="w-full rounded-xl border border-[#dfe2eb] bg-white px-5 py-3 text-xs font-semibold text-[#00236f] transition hover:border-[#bfc7df] hover:bg-[#f8f9ff] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Profile Setup
            </button>

          </div>

          {/* Footer text */}
          <p className="mt-5 text-center text-[9px] leading-4 text-[#858895]">
            Demo access and competency assessment workflow
          </p>

        </div>
      </div>
    </main>
  );
}
