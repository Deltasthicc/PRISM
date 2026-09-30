'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Award, CheckCircle2, XCircle } from 'lucide-react';
import { certificates } from '@/lib/api/client';
import Badge from '@/components/ui/Badge';
import Panel from '@/components/ui/Panel';

// Deliberately unauthenticated -- no useRequireAuth, matching
// backend/routes/certificates.py's verify_certificate() being the one
// public read in the whole API. Anyone holding a code, with or without a
// PRISM account, can land here directly and confirm a certificate is
// real.
export default function VerifyCertificatePage() {
  const { code } = useParams();
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    setError('');
    certificates
      .verify(code)
      .then(setResult)
      .catch((cause) => setError(cause.message || 'Could not reach the verification service.'))
      .finally(() => setLoading(false));
  }, [code]);

  return (
    <div className="flex flex-col items-center pt-16 gap-6 px-4 pb-16">
      <div className="flex flex-col items-center gap-2">
        <span className="font-sans text-xl font-bold text-[#00236f] tracking-tight">PRISM</span>
        <span className="font-mono text-[11px] text-[#757682] uppercase tracking-wider">
          Certificate verification
        </span>
      </div>

      <Panel className="w-full max-w-sm p-6 text-center">
        {loading && <p className="font-sans text-sm text-[#757682]">Checking…</p>}
        {!loading && error && <p className="font-sans text-sm text-[#b3261e]">{error}</p>}
        {!loading && !error && result?.valid && (
          <>
            <CheckCircle2 size={32} className="text-[#166a3f] mx-auto mb-3" />
            <h1 className="font-sans text-base font-bold text-[#166a3f]">Valid certificate</h1>
            <p className="font-sans text-sm text-[#131b2e] mt-2">{result.title}</p>
            <p className="font-sans text-xs text-[#757682] mt-1">
              Issued {new Date(result.issued_at).toLocaleDateString()}
            </p>
          </>
        )}
        {!loading && !error && result && !result.valid && (
          <>
            <XCircle size={32} className="text-[#b3261e] mx-auto mb-3" />
            <h1 className="font-sans text-base font-bold text-[#b3261e]">
              {result.revoked ? 'Certificate revoked' : 'Not a valid certificate'}
            </h1>
            <p className="font-sans text-sm text-[#757682] mt-2">{result.detail}</p>
          </>
        )}
        <p className="font-mono text-[10px] text-[#8a8f9d] mt-5 pt-4 border-t border-[#c5c5d3]/30 break-all">
          <Award size={10} className="inline mr-1" />
          {code}
        </p>
      </Panel>
    </div>
  );
}
