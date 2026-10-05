'use client';

import { useQuery } from '@tanstack/react-query';
import { Megaphone, Award, BookOpen } from 'lucide-react';
import { announcementsApi } from '@/lib/api/announcements';
import { KIND_LABELS, formatFeedDate, isFeedEmpty } from '@/lib/homeFeed';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

// In-app home feed (SIH26075 PS75-13), backed by GET /learning/home/feed.
// "Notifications" here means this feed only -- nothing is pushed or emailed.
// Every section is derived from real rows: admin-published announcements,
// recently created published courses, and THIS learner's own certificates.
// An empty section is shown as empty, never filled with placeholders.
//
// Usage: <HomeFeed playerId={player.player_id} />

function SectionHeading({ icon: Icon, children, id }) {
  return (
    <h3 id={id} className="font-sans text-sm text-[#131b2e] font-bold flex items-center gap-2 mb-2">
      <Icon size={16} className="text-[#00236f]" aria-hidden="true" />
      {children}
    </h3>
  );
}

function EmptyLine({ children }) {
  return <p className="font-sans text-xs text-[#757682]">{children}</p>;
}

/** Pure presentational view -- takes an already-fetched feed. */
export function HomeFeedView({ feed }) {
  const announcements = feed?.announcements || [];
  const courses = feed?.new_courses || [];
  const achievements = feed?.my_achievements || [];

  return (
    <div className="flex flex-col gap-3">
      {isFeedEmpty(feed) && (
        <p className="font-sans text-sm text-[#757682]">Nothing new to show right now.</p>
      )}

      <Panel as="section" aria-labelledby="home-feed-announcements">
        <SectionHeading icon={Megaphone} id="home-feed-announcements">
          Announcements
        </SectionHeading>
        {announcements.length === 0 ? (
          <EmptyLine>No current announcements.</EmptyLine>
        ) : (
          <ul className="flex flex-col divide-y divide-[#c5c5d3]/20">
            {announcements.map((item) => (
              <li key={item.announcement_id} className="py-2 first:pt-0 last:pb-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge tone={item.kind === 'achievement' ? 'success' : 'accent'}>
                    {KIND_LABELS[item.kind] || item.kind}
                  </Badge>
                  <p className="font-sans text-sm font-semibold text-[#131b2e]">{item.title}</p>
                </div>
                <p className="font-sans text-xs text-[#444651] mt-1 whitespace-pre-line">{item.body}</p>
                {item.published_at && (
                  <p className="font-mono text-[10px] text-[#757682] mt-1">
                    Posted {formatFeedDate(item.published_at)}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel as="section" aria-labelledby="home-feed-courses">
        <SectionHeading icon={BookOpen} id="home-feed-courses">
          New courses (last 30 days)
        </SectionHeading>
        {courses.length === 0 ? (
          <EmptyLine>No new courses in the last 30 days.</EmptyLine>
        ) : (
          <ul className="flex flex-col divide-y divide-[#c5c5d3]/20">
            {courses.map((course) => (
              <li key={course.course_id} className="py-2 first:pt-0 last:pb-0">
                <p className="font-sans text-sm font-semibold text-[#131b2e]">{course.title}</p>
                {course.description && (
                  <p className="font-sans text-xs text-[#444651] mt-0.5 line-clamp-2">{course.description}</p>
                )}
                <p className="font-mono text-[10px] text-[#757682] mt-1">
                  Added {formatFeedDate(course.created_at)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel as="section" aria-labelledby="home-feed-achievements">
        <SectionHeading icon={Award} id="home-feed-achievements">
          My achievements (last 90 days)
        </SectionHeading>
        {achievements.length === 0 ? (
          <EmptyLine>No certificates earned in the last 90 days.</EmptyLine>
        ) : (
          <ul className="flex flex-col divide-y divide-[#c5c5d3]/20">
            {achievements.map((item) => (
              <li key={item.certificate_id} className="py-2 first:pt-0 last:pb-0">
                <p className="font-sans text-sm font-semibold text-[#131b2e]">{item.title}</p>
                <p className="font-mono text-[10px] text-[#757682] mt-0.5">
                  Certificate issued {formatFeedDate(item.issued_at)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

export default function HomeFeed({ playerId }) {
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['home-feed', playerId],
    queryFn: () => announcementsApi.getHomeFeed(playerId),
    enabled: !!playerId,
  });

  if (!playerId) return null;

  if (isLoading) {
    return (
      <Panel role="status" aria-live="polite">
        <p className="font-sans text-sm text-[#757682]">Loading your feed…</p>
      </Panel>
    );
  }

  if (isError) {
    return (
      <Panel>
        <p role="alert" className="font-sans text-sm text-[#b3261e]">
          Could not load your feed: {error?.message || 'unknown error'}
        </p>
        <Button type="button" onClick={() => refetch()} disabled={isFetching} className="mt-3 text-xs px-3 py-2">
          {isFetching ? 'Retrying…' : 'Retry'}
        </Button>
      </Panel>
    );
  }

  return <HomeFeedView feed={data} />;
}
