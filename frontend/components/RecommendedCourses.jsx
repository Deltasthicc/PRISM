'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { courseEnrollment } from '@/lib/api/client';
import Panel from '@/components/ui/Panel';
import { ExternalLink, GraduationCap, CheckCircle2 } from 'lucide-react';

// Renders services/learning_catalog.py::recommend_courses()' output --
// computed correctly since before this component existed, but never
// surfaced anywhere in the UI. "igot"/"nssta" entries are real,
// persisted enroll/complete actions (routes/course_enrollment.py) against
// a SIMULATED provider (see README's Known limitations); "internal-practice"
// entries are plain links into this app's own quest content, so there is
// nothing to "enroll" in there beyond visiting the page.
//
// Not yet translated into the other 10 UI languages -- same honesty
// convention as this project's other documented pending items (see
// app/sampling-lab/page.jsx).

const PROVIDER_LABEL = {
  igot: 'iGOT Karmayogi',
  nssta: 'NSSTA TPAC',
  'internal-practice': 'In-app practice',
};

const PROVIDER_BADGE = {
  igot: 'bg-[#dce1ff] text-[#00236f] border border-[#00236f]/20',
  nssta: 'bg-[#ffdcc3] text-[#904d00] border border-[#ffb77d]',
  'internal-practice': 'bg-[#f2f3ff] text-[#757682] border border-[#c5c5d3]/60',
};

function CourseRow({ course, playerId, enrollment, onEnrolled, onCompleted }) {
  const enrollMutation = useMutation({
    mutationFn: () => courseEnrollment.enroll(playerId, course.course_id, course.title),
    onSuccess: (data) => onEnrolled(data),
  });
  const completeMutation = useMutation({
    mutationFn: () => courseEnrollment.complete(enrollment.enrollment_id, playerId),
    onSuccess: (data) => onCompleted(data),
  });

  const isPractice = course.provider_type === 'internal-practice';
  const isCompleted = enrollment?.status === 'completed';
  const isEnrolled = Boolean(enrollment) && !isCompleted;

  return (
    <div className="flex items-center justify-between gap-3 py-2.5 border-b border-[#c5c5d3]/20 last:border-b-0">
      <div className="flex items-center gap-3 min-w-0">
        <span
          className={`px-2 py-0.5 rounded font-mono text-[10px] font-bold uppercase tracking-wide shrink-0 ${
            PROVIDER_BADGE[course.provider_type] || PROVIDER_BADGE['internal-practice']
          }`}
        >
          {PROVIDER_LABEL[course.provider_type] || course.provider}
        </span>
        <div className="min-w-0">
          <p className="font-sans text-sm text-[#131b2e] font-semibold truncate">{course.title}</p>
          <p className="font-mono text-[11px] text-[#757682] truncate">{course.verification_note}</p>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {isPractice ? (
          <a
            href={course.url}
            className="flex items-center gap-1 text-xs font-mono text-[#00236f] hover:underline"
          >
            Open <ExternalLink size={12} />
          </a>
        ) : isCompleted ? (
          <span className="flex items-center gap-1 text-xs font-mono text-[#1e7a34] font-semibold">
            <CheckCircle2 size={14} /> Completed
          </span>
        ) : isEnrolled ? (
          <button
            type="button"
            onClick={() => completeMutation.mutate()}
            disabled={completeMutation.isPending}
            className="px-2.5 py-1 rounded-md text-xs font-mono font-semibold bg-[#eaedff] text-[#00236f] hover:bg-[#dce1ff] disabled:opacity-50 cursor-pointer"
          >
            {completeMutation.isPending ? 'Marking...' : 'Mark complete'}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => enrollMutation.mutate()}
            disabled={enrollMutation.isPending}
            className="px-2.5 py-1 rounded-md text-xs font-mono font-semibold bg-[#00236f] text-white hover:bg-[#001a52] disabled:opacity-50 cursor-pointer"
          >
            {enrollMutation.isPending ? 'Enrolling...' : 'Enroll'}
          </button>
        )}
      </div>
    </div>
  );
}

export function RecommendedCourses({ playerId, courses }) {
  const queryClient = useQueryClient();

  const { data: enrollmentsData } = useQuery({
    queryKey: ['course-enrollments', playerId],
    queryFn: () => courseEnrollment.list(playerId),
    enabled: !!playerId,
  });

  const enrollmentByCourseId = new Map(
    (enrollmentsData?.enrollments || []).map((row) => [row.course_id, row])
  );

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['course-enrollments', playerId] });

  if (!courses || courses.length === 0) return null;

  return (
    <Panel>
      <div className="flex items-center gap-2 mb-2">
        <GraduationCap size={16} className="text-[#00236f]" />
        <h3 className="font-sans text-sm text-[#131b2e] font-bold">Recommended learning</h3>
      </div>
      <div className="flex flex-col">
        {courses.map((course) => (
          <CourseRow
            key={course.course_id}
            course={course}
            playerId={playerId}
            enrollment={enrollmentByCourseId.get(course.course_id)}
            onEnrolled={refresh}
            onCompleted={refresh}
          />
        ))}
      </div>
    </Panel>
  );
}
