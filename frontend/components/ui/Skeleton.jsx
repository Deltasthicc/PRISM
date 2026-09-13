// Shared route-loading skeleton, rendered instantly by Next.js App Router's
// per-segment loading.jsx while a page's JS chunk + first data fetch are
// still in flight (see the loading.jsx sibling in each app/*/page.jsx
// route). Deliberately theme-neutral (plain gray pulse blocks) since routes
// span both the light "professional" shell (NavBar, Academy, Stats, ...)
// and the dark "Quest" pages (dungeon/combat/boss/character) -- a fixed
// dark- or light-only palette here would clash with one or the other.
//
// Kept intentionally generic: a handful of `variant`s cover every route's
// rough shape (a heading + list rows, a heading + card grid, etc.) rather
// than one bespoke skeleton per page.

function Block({ className = '' }) {
  return <div className={`animate-pulse rounded-lg bg-black/[0.06] ${className}`} />;
}

function Heading() {
  return (
    <div className="flex flex-col gap-2 mb-6">
      <Block className="h-6 w-56" />
      <Block className="h-4 w-80 max-w-full" />
    </div>
  );
}

function DefaultBody() {
  return (
    <div className="flex flex-col gap-3">
      <Block className="h-24 w-full" />
      <Block className="h-4 w-full" />
      <Block className="h-4 w-5/6" />
      <Block className="h-4 w-2/3" />
    </div>
  );
}

function CardsBody() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: 6 }).map((_, index) => (
        <Block key={index} className="h-36 w-full" />
      ))}
    </div>
  );
}

function ListBody() {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: 6 }).map((_, index) => (
        <Block key={index} className="h-14 w-full" />
      ))}
    </div>
  );
}

function StatsBody() {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Block key={index} className="h-20 w-full" />
        ))}
      </div>
      <Block className="h-64 w-full" />
    </div>
  );
}

function FormBody() {
  return (
    <div className="flex flex-col gap-4 max-w-md">
      {Array.from({ length: 5 }).map((_, index) => (
        <Block key={index} className="h-10 w-full" />
      ))}
      <Block className="h-10 w-32" />
    </div>
  );
}

function CombatBody() {
  return (
    <div className="flex flex-col items-center gap-6 py-10">
      <Block className="h-6 w-40" />
      <Block className="h-40 w-40 rounded-full" />
      <Block className="h-4 w-64" />
      <div className="grid grid-cols-2 gap-3 w-full max-w-sm">
        {Array.from({ length: 4 }).map((_, index) => (
          <Block key={index} className="h-12 w-full" />
        ))}
      </div>
    </div>
  );
}

const BODIES = {
  default: DefaultBody,
  cards: CardsBody,
  list: ListBody,
  stats: StatsBody,
  form: FormBody,
  combat: CombatBody,
};

// variant: 'default' | 'cards' | 'list' | 'stats' | 'form' | 'combat'
// showHeading: set false for full-screen game views that don't have a
// plain text heading at the top (combat/boss).
export default function PageLoading({ variant = 'default', showHeading = true }) {
  const Body = BODIES[variant] || DefaultBody;
  return (
    <div role="status" aria-label="Loading" className="w-full">
      {showHeading && variant !== 'combat' && <Heading />}
      <Body />
    </div>
  );
}
