'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Award } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { certificates } from '@/lib/api/client';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';

export default function CertificatesPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const [certs, setCerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!ready || !player?.player_id) return;
    setLoading(true);
    setError('');
    certificates
      .listMine(player.player_id)
      .then((data) => setCerts(data || []))
      .catch((cause) => setError(cause.message || 'Could not load certificates.'))
      .finally(() => setLoading(false));
  }, [ready, player?.player_id]);

  if (!ready) return null;

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1 flex items-center gap-1.5">
          <Award size={12} />
          Certificates
        </p>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">Your certificates</h1>
        <p className="font-sans text-sm text-[#757682] mt-1">
          Issued automatically when you complete a course. Each one is publicly verifiable.
        </p>
      </div>

      {loading && <p className="font-sans text-sm text-[#757682] text-center mt-6">Loading…</p>}
      {!loading && error && <p className="font-sans text-sm text-[#b3261e]">{error}</p>}

      {!loading && !error && certs.length === 0 && (
        <Panel>
          <p className="font-sans text-sm text-[#757682]">
            No certificates yet. Complete a course from{' '}
            <Link href="/courses" className="text-[#00236f] underline">
              the catalog
            </Link>{' '}
            to earn one.
          </p>
        </Panel>
      )}

      {!loading &&
        !error &&
        certs.map((cert) => (
          <Panel key={cert.certificate_id}>
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div>
                <h2 className="font-sans text-sm font-bold text-[#131b2e]">{cert.title}</h2>
                <p className="font-sans text-xs text-[#757682]">
                  Issued {new Date(cert.issued_at).toLocaleDateString()}
                </p>
              </div>
              {cert.revoked ? <Badge tone="warning">Revoked</Badge> : <Badge tone="success">Valid</Badge>}
            </div>
            <div className="flex items-center justify-between gap-3 flex-wrap mt-2 pt-2 border-t border-[#c5c5d3]/30">
              <span className="font-mono text-[10px] text-[#8a8f9d]">{cert.verification_code}</span>
              <Link
                href={`/certificates/verify/${cert.verification_code}`}
                className="font-sans text-xs text-[#00236f] underline"
              >
                Public verification page
              </Link>
            </div>
          </Panel>
        ))}
    </div>
  );
}
