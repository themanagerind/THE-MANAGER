import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { apiErrorMessage } from "@/components/States";
import { societiesApi, type SocietySearchResultOut } from "@/api/societies";
import { residentsApi } from "@/api/residents";
import { adminsApi } from "@/api/admins";

type SignupRole = "RESIDENT" | "ADMIN";
type Step = "society" | "details" | "done";

// Audit #20 pattern (see Login.tsx) — stops an obviously-invalid mobile
// before it's sent; the backend stays the authoritative check.
const MOBILE_RE = /^\d{10}$/;
const MIN_SEARCH_LENGTH = 3;

/**
 * A society only ever comes into existence via the Platform Owner's own
 * dashboard now (POST /societies, Admin-only) — this page never creates
 * one. Both roles here join an EXISTING, ACTIVE society, picked by
 * searching its name (GET /societies/search) instead of needing its
 * code:
 *   - Resident signup -> approved by that society's own Admin
 *   - Admin signup    -> approved by the Platform Owner (a different
 *                        society may have a different Admin approve them,
 *                        but it's always the platform-level role that
 *                        signs off on a new Admin, not a peer Admin)
 */
export function Signup() {
  const [role, setRole] = useState<SignupRole>("RESIDENT");
  const [step, setStep] = useState<Step>("society");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SocietySearchResultOut[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [society, setSociety] = useState<{ id: string; name: string } | null>(null);
  const [fullName, setFullName] = useState("");
  const [mobile, setMobile] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function resetForRoleChange(next: SignupRole) {
    setRole(next);
    setStep("society");
    setSociety(null);
    setQuery("");
    setResults([]);
    setSearchError(null);
    setFullName("");
    setMobile("");
    setEmail("");
    setError(null);
  }

  // Debounced name search — picks a society without needing to already
  // know its code (backend enforces a 3-char minimum and rate-limits by
  // IP, see society_service.search_societies_by_name).
  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < MIN_SEARCH_LENGTH) {
      setResults([]);
      setSearchError(null);
      setSearching(false);
      return;
    }
    setSearching(true);
    const timeout = setTimeout(() => {
      societiesApi
        .search(trimmed)
        .then((r) => {
          setResults(r.data);
          setSearchError(null);
        })
        .catch((e) => {
          setResults([]);
          setSearchError(apiErrorMessage(e, "Couldn't search societies."));
        })
        .finally(() => setSearching(false));
    }, 350);
    return () => clearTimeout(timeout);
  }, [query]);

  function selectSociety(s: SocietySearchResultOut) {
    setSociety({ id: s.id, name: s.name });
    setStep("details");
  }

  async function handleSubmit() {
    if (!society) return;
    setError(null);
    setLoading(true);
    try {
      const body = { full_name: fullName, mobile, email: email.trim() || undefined, society_id: society.id };
      if (role === "RESIDENT") {
        await residentsApi.signup(body);
      } else {
        await adminsApi.signup(body);
      }
      setStep("done");
    } catch (e) {
      setError(apiErrorMessage(e, "Signup could not be submitted."));
    } finally {
      setLoading(false);
    }
  }

  const canSubmit = fullName.trim().length > 0 && MOBILE_RE.test(mobile);

  return (
    <div className="min-h-screen flex items-center justify-center bg-paper px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <img src="/logo.png" alt="Housing Society Manager" className="w-40 h-40 rounded-full mb-3" />
          <h1 className="text-2xl font-bold text-navy tracking-wide">THE MANAGER</h1>
          <p className="text-sm text-navy-muted mt-1">Create account</p>
        </div>

        {step !== "done" && (
          <div className="flex gap-2 mb-6">
            {(["RESIDENT", "ADMIN"] as SignupRole[]).map((r) => (
              <button
                key={r}
                onClick={() => resetForRoleChange(r)}
                className={`flex-1 px-3 py-2 rounded text-sm font-medium border transition-colors ${
                  role === r ? "bg-navy text-white border-navy" : "border-line text-navy-muted hover:border-navy"
                }`}
              >
                {r === "RESIDENT" ? "As a Resident" : "As an Admin"}
              </button>
            ))}
          </div>
        )}

        {step === "society" && (
          <div className="space-y-2">
            <p className="text-sm text-navy-muted mb-2">
              {role === "RESIDENT"
                ? "Search for your society by name."
                : "Search for the society you'll administer by name."}
            </p>
            <Input
              label="Society name"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Start typing your society's name..."
              autoFocus
            />
            {query.trim().length >= MIN_SEARCH_LENGTH && (
              <div className="border border-line rounded divide-y divide-line max-h-56 overflow-y-auto">
                {searching && <p className="px-3 py-2 text-sm text-navy-muted">Searching…</p>}
                {!searching && results.length === 0 && !searchError && (
                  <p className="px-3 py-2 text-sm text-navy-muted">No society found — check the spelling.</p>
                )}
                {!searching &&
                  results.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => selectSociety(s)}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-paper transition-colors"
                    >
                      <span className="font-medium text-ink">{s.name}</span>
                      {s.city && <span className="text-navy-muted"> — {s.city}</span>}
                    </button>
                  ))}
              </div>
            )}
            {searchError && <p className="text-sm text-danger">{searchError}</p>}
          </div>
        )}

        {step === "details" && society && (
          <div className="space-y-4">
            <div className="flex items-center justify-between px-3 py-2 rounded bg-success/10 text-success text-sm">
              <span>
                Joining <span className="font-medium">{society.name}</span>
              </span>
              <button className="underline shrink-0 ml-2" onClick={() => setStep("society")}>
                Change
              </button>
            </div>
            <Input label="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)} autoFocus />
            <Input
              label="Mobile number"
              type="tel"
              inputMode="numeric"
              placeholder="10-digit mobile number"
              value={mobile}
              onChange={(e) => setMobile(e.target.value.replace(/\D/g, "").slice(0, 10))}
            />
            <Input
              label="Email (optional)"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            {error && <p className="text-sm text-danger">{error}</p>}
            <Button className="w-full" loading={loading} disabled={!canSubmit} onClick={handleSubmit}>
              Submit
            </Button>
          </div>
        )}

        {step === "done" && (
          <div className="space-y-4 text-center">
            <p className="text-sm text-ink">
              Submitted.{" "}
              {role === "RESIDENT"
                ? "Your society's Admin will review and approve your account."
                : "The Platform Owner will review and approve your account."}
            </p>
            <Link to="/login" className="text-sm text-navy underline">
              Back to login
            </Link>
          </div>
        )}

        {step !== "done" && (
          <p className="text-sm text-navy-muted text-center mt-6">
            Already have an account?{" "}
            <Link to="/login" className="text-navy underline">
              Log in
            </Link>
          </p>
        )}
      </div>
    </div>
  );
}
