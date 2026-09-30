'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { BookOpen } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { courseCatalog } from '@/lib/api/client';
import Panel from '@/components/ui/Panel';

// Trainee-facing browse of real, trainer-authored courses
// (backend/routes/course_catalog.py) -- distinct from the igot/nssta
// catalogue recommendations shown elsewhere (RecommendedCourses.jsx).
export default function CoursesPage() {
  const { ready } = useRequireAuth();
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!ready) return;
    setLoading(true);
    setError('');
    courseCatalog
      .listPublished()
      .then((data) => setCourses(data || []))
      .catch((cause) => setError(cause.message || 'Could not load courses.'))
      .finally(() => setLoading(false));
  }, [ready]);

  if (!ready) return null;

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1 flex items-center gap-1.5">
          <BookOpen size={12} />
          Course Catalog
        </p>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">Courses</h1>
        <p className="font-sans text-sm text-[#757682] mt-1">
          Real, trainer-authored courses. Enroll, complete, and leave feedback.
        </p>
      </div>

      {loading && <p className="font-sans text-sm text-[#757682] text-center mt-6">Loading courses…</p>}

      {!loading && error && (
        <Panel>
          <p className="font-sans text-sm text-[#b3261e]">{error}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-2 font-sans text-xs text-[#00236f] underline"
          >
            Retry
          </button>
        </Panel>
      )}

      {!loading && !error && courses.length === 0 && (
        <Panel>
          <p className="font-sans text-sm text-[#757682]">
            No published courses yet. A trainer needs to create and publish one first.
          </p>
        </Panel>
      )}

      {!loading &&
        !error &&
        courses.map((course) => (
          <Link key={course.course_id} href={`/courses/${course.course_id}`}>
            <Panel className="hover:border-[#00236f]/40 transition-colors cursor-pointer">
              <h2 className="font-sans text-sm font-bold text-[#131b2e]">{course.title}</h2>
              {course.description && (
                <p className="font-sans text-xs text-[#757682] mt-1 line-clamp-2">{course.description}</p>
              )}
              <p className="font-mono text-[10px] text-[#8a8f9d] mt-2">{course.competency_id}</p>
            </Panel>
          </Link>
        ))}
    </div>
  );
}
