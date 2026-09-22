import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { apiErrorMessage } from "@/components/States";
import { societiesApi } from "@/api/societies";
import { residentsApi } from "@/api/residents";
import { adminsApi } from "@/api/admins";

type SignupRole = "RESIDENT" | "ADMIN";
type Step = "society" | "details" | "done";

// Audit #20 pattern (see Login.tsx) — stops an obviously-invalid mobile
// before it's sent; the backend stays the authoritative check.
const MOBILE_RE = /^\d{10}$/;

/**
 * A society only ever comes into existence via the Platform Owner's own
 * dashboard now (POST /societies, Admin-only) — this page never creates
 * one. Both roles here join an EXISTING, ACTIVE society by its code:
 *   - Resident signup -> approved by that society's own Admin
 *   - Admin signup    -> approved by the Platform Owner (a different
 *                        society may have a different Admin approve them,
 *                        but it's always the platform-level role that
 *                        signs off on a new Admin, not a peer Admin)
 */
export function Signup() {
  const [role, setRole] = useState<SignupRole>("RESIDENT");
  const [step, setStep] = useState<Step>("society");
  const [societyCode, setSocietyCode] = useState("");
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
    setSocietyCode("");
    setFullName("");
    setMobile("");
    setEmail("");
    setError(null);
  }

  async function handleFindSociety() {
    setError(null);
    setLoading(true);
    try {
      const { data } = await societiesApi.lookup(societyCode.trim());
      setSociety(data);
      setStep("details");
    } catch (e) {
      setError(apiErrorMessage(e, "Society not found. Check the code and try again."));
    } finally {
      setLoading(false);
    }
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
          <img src="/logo.png" alt="Housing Society Manager" className="w-16 h-16 rounded-full mb-3" />
          <h1 className="text-xl font-semibold text-navy">Create account</h1>
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
          <div className="space-y-4">
            <p className="text-sm text-navy-muted">
              {role === "RESIDENT"
                ? "Enter your society's code — ask your society's Admin for it."
                : "Enter the code of the society you'll administer — ask the Platform Owner for it."}
            </p>
            <Input
              label="Society code"
              value={societyCode}
              onChange={(e) => setSocietyCode(e.target.value.toUpperCase())}
              autoFocus
            />
            {error && <p className="text-sm text-danger">{error}</p>}
            <Button className="w-full" loading={loading} disabled={!societyCode.trim()} onClick={handleFindSociety}>
              Find society
            </Button>
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
