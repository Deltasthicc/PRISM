'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { Award, BookOpen, Star } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { courseCatalog, courseEnrollment, courseFeedback, certificates } from '@/lib/api/client';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

// One connected screen for the real internal-course lifecycle: enroll ->
// (stand-in for consuming course content, which has no dedicated player
// UI yet) mark complete -> certificate issued automatically
// (routes/course_enrollment.py) -> leave feedback. Each state below maps
// to a real, persisted backend state, not a client-side simulation.
export default function CourseDetailPage() {
  const { courseId } = useParams();
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);

  const [course, setCourse] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [enrollment, setEnrollment] = useState(null);
  const [enrolling, setEnrolling] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [actionError, setActionError] = useState('');

  const [myCert, setMyCert] = useState(null);
  const [summary, setSummary] = useState(null);
  const [myFeedback, setMyFeedback] = useState(null);
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState('');
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [feedbackError, setFeedbackError] = useState('');
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);

  async function refresh() {
    if (!player?.player_id) return;
    const [enrollments, certs, feedbackSummary, mine] = await Promise.all([
      courseEnrollment.list(player.player_id),
      certificates.listMine(player.player_id),
      courseFeedback.summary(courseId),
      courseFeedback.mine(courseId, player.player_id),
    ]);
    const existing = (enrollments.enrollments || []).find(
      (row) => row.course_id === `internal::${courseId}`
    );
    setEnrollment(existing || null);
    setMyCert((certs || []).find((c) => c.course_id === courseId) || null);
    setSummary(feedbackSummary);
    setMyFeedback(mine);
    if (mine) {
      setRating(mine.rating);
      setComment(mine.comment);
    }
  }

  useEffect(() => {
    if (!ready || !player?.player_id) return;
    setLoading(true);
    setLoadError('');
    courseCatalog
      .get(courseId)
      .then(async (data) => {
        setCourse(data);
        await refresh();
      })
      .catch((cause) => setLoadError(cause.message || 'Could not load this course.'))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, player?.player_id, courseId]);

  async function handleEnroll() {
    setEnrolling(true);
    setActionError('');
    try {
      const result = await courseEnrollment.enroll(player.player_id, `internal::${courseId}`, course.title);
      setEnrollment(result);
    } catch (cause) {
      setActionError(cause.message || 'Could not enroll.');
    } finally {
      setEnrolling(false);
    }
  }

  async function handleComplete() {
    setCompleting(true);
    setActionError('');
    try {
      const result = await courseEnrollment.complete(enrollment.enrollment_id, player.player_id);
      setEnrollment(result);
      await refresh();
    } catch (cause) {
      setActionError(cause.message || 'Could not mark this course complete.');
    } finally {
      setCompleting(false);
    }
  }

  async function handleFeedbackSubmit(event) {
    event.preventDefault();
    setSubmittingFeedback(true);
    setFeedbackError('');
    try {
      await courseFeedback.submit(courseId, player.player_id, rating, comment);
      setFeedbackSubmitted(true);
      const [feedbackSummary, mine] = await Promise.all([
        courseFeedback.summary(courseId),
        courseFeedback.mine(courseId, player.player_id),
      ]);
      setSummary(feedbackSummary);
      setMyFeedback(mine);
    } catch (cause) {
      setFeedbackError(cause.message || 'Could not submit feedback.');
    } finally {
      setSubmittingFeedback(false);
    }
  }

  if (!ready) return null;
  if (loading) return <p className="font-sans text-sm text-[#757682] text-center mt-10">Loading course…</p>;
  if (loadError) {
    return (
      <div className="max-w-2xl mx-auto">
        <Panel>
          <p className="font-sans text-sm text-[#b3261e]">{loadError}</p>
          <Link href="/courses" className="font-sans text-xs text-[#00236f] underline mt-2 inline-block">
            Back to courses
          </Link>
        </Panel>
      </div>
    );
  }
  if (!course) return null;

  const isEnrolled = Boolean(enrollment);
  const isCompleted = enrollment?.status === 'completed';

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1 flex items-center gap-1.5">
          <BookOpen size={12} />
          {course.competency_id}
        </p>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">{course.title}</h1>
        {course.description && <p className="font-sans text-sm text-[#757682] mt-1">{course.description}</p>}
      </div>

      <Panel>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            {isCompleted ? (
              <Badge tone="success">Completed</Badge>
            ) : isEnrolled ? (
              <Badge tone="accent">Enrolled</Badge>
            ) : (
              <Badge>Not enrolled</Badge>
            )}
            {summary?.count > 0 && (
              <span className="font-sans text-xs text-[#757682] flex items-center gap-1">
                <Star size={12} className="fill-current" /> {summary.average_rating} ({summary.count})
              </span>
            )}
          </div>
          {!isEnrolled && (
            <Button onClick={handleEnroll} disabled={enrolling}>
              {enrolling ? 'Enrolling…' : 'Enroll'}
            </Button>
          )}
          {isEnrolled && !isCompleted && (
            <Button onClick={handleComplete} disabled={completing}>
              {completing ? 'Marking complete…' : 'Mark as complete'}
            </Button>
          )}
        </div>
        {actionError && <p className="mt-2 font-sans text-xs text-[#b3261e]">{actionError}</p>}
      </Panel>

      {isCompleted && myCert && (
        <Panel className="border-[#166a3f]/30 bg-[#e3f3e9]/40">
          <div className="flex items-center gap-2 mb-1">
            <Award size={16} className="text-[#166a3f]" />
            <h2 className="font-sans text-sm font-bold text-[#166a3f]">Certificate issued</h2>
          </div>
          <p className="font-sans text-xs text-[#757682]">
            Issued {new Date(myCert.issued_at).toLocaleDateString()}. Verification code:{' '}
            <span className="font-mono">{myCert.verification_code}</span>
          </p>
          <Link
            href={`/certificates/verify/${myCert.verification_code}`}
            className="font-sans text-xs text-[#166a3f] underline mt-1 inline-block"
          >
            View public verification page
          </Link>
        </Panel>
      )}

      {isEnrolled && (
        <Panel>
          <h2 className="font-sans text-sm font-bold text-[#131b2e] mb-3">
            {myFeedback ? 'Your feedback' : 'Leave feedback'}
          </h2>
          <form onSubmit={handleFeedbackSubmit} className="flex flex-col gap-3">
            <div className="flex gap-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setRating(n)}
                  aria-label={`${n} star${n === 1 ? '' : 's'}`}
                  className="p-0.5"
                >
                  <Star size={20} className={n <= rating ? 'fill-[#00236f] text-[#00236f]' : 'text-[#c5c5d3]'} />
                </button>
              ))}
            </div>
            <textarea
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              placeholder="What did you think of this course? (optional)"
              rows={3}
              className="px-3.5 py-2.5 rounded-lg border border-[#c5c5d3]/60 font-sans text-sm outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]"
            />
            {feedbackError && <p className="font-sans text-xs text-[#b3261e]">{feedbackError}</p>}
            {feedbackSubmitted && !feedbackError && (
              <p className="font-sans text-xs text-[#166a3f]">Thanks — your feedback was recorded.</p>
            )}
            <Button type="submit" disabled={submittingFeedback} className="self-start">
              {submittingFeedback ? 'Submitting…' : myFeedback ? 'Update feedback' : 'Submit feedback'}
            </Button>
          </form>
        </Panel>
      )}

      {summary?.comments?.length > 0 && (
        <Panel>
          <h2 className="font-sans text-sm font-bold text-[#131b2e] mb-2">What other trainees said</h2>
          <ul className="flex flex-col gap-2">
            {summary.comments.map((text, i) => (
              <li key={i} className="font-sans text-xs text-[#757682] border-l-2 border-[#c5c5d3]/50 pl-2">
                {text}
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}
