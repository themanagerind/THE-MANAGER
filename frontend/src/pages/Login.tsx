import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import type { AccountChoice } from "@/api/auth";

const ACCOUNTS_CACHE_KEY = "hs_otp_accounts_cache";

type Step = "mobile" | "otp" | "choose-account";

// Audit #20: length-only checks (`length < 10`, `length < 4`) let obviously
// invalid input reach the backend (letters, wrong digit counts, an OTP
// UI describes as 6 digits accepting 4). Backend validation stays
// authoritative; this only stops a doomed request before it's sent.
const MOBILE_RE = /^\d{10}$/;
const OTP_RE = /^\d{6}$/;

export function Login() {
  const { requestOtp, verifyOtp, selectAccount } = useAuth();
  const navigate = useNavigate();

  // Fix #4: if a page reload happens mid multi-account selection, restore
  // straight to the picker (the otp_session_token itself is restored by
  // AuthContext from sessionStorage) instead of forcing the OTP re-send.
  const [step, setStep] = useState<Step>(() => {
    const cached = sessionStorage.getItem(ACCOUNTS_CACHE_KEY);
    return cached ? "choose-account" : "mobile";
  });
  const [mobile, setMobile] = useState("");
  const [otp, setOtp] = useState("");
  const [accounts, setAccounts] = useState<AccountChoice[]>(() => {
    const cached = sessionStorage.getItem(ACCOUNTS_CACHE_KEY);
    return cached ? (JSON.parse(cached) as AccountChoice[]) : [];
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (accounts.length > 0) {
      sessionStorage.setItem(ACCOUNTS_CACHE_KEY, JSON.stringify(accounts));
    }
  }, [accounts]);

  async function handleRequestOtp() {
    setError(null);
    setLoading(true);
    try {
      await requestOtp(mobile);
      setStep("otp");
    } catch (e) {
      setError(errorMessage(e, "Could not send OTP. Try again in a moment."));
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifyOtp() {
    setError(null);
    setLoading(true);
    try {
      const accountChoices = await verifyOtp(mobile, otp);
      if (accountChoices) {
        setAccounts(accountChoices);
        setStep("choose-account");
      } else {
        navigate("/");
      }
    } catch (e) {
      setError(errorMessage(e, "That code didn't work. Check it and try again."));
    } finally {
      setLoading(false);
    }
  }

  async function handleChooseAccount(userId: string) {
    setError(null);
    setLoading(true);
    try {
      await selectAccount(userId);
      sessionStorage.removeItem(ACCOUNTS_CACHE_KEY);
      navigate("/");
    } catch (e) {
      setError(errorMessage(e, "Couldn't log in to that account."));
      // The OTP session token is short-lived (10 min) — if it expired
      // between page-load and click, don't leave the user stuck.
      const status = (e as { response?: { status?: number } })?.response?.status;
      if (status === 401) {
        sessionStorage.removeItem(ACCOUNTS_CACHE_KEY);
        setStep("mobile");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-paper px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <img src="/logo.png" alt="Housing Society Manager" className="w-16 h-16 rounded-full mb-3" />
          <h1 className="text-xl font-semibold text-navy">Society Manager</h1>
        </div>

        {step === "mobile" && (
          <div className="space-y-4">
            <Input
              label="Mobile number"
              type="tel"
              inputMode="numeric"
              placeholder="10-digit mobile number"
              value={mobile}
              onChange={(e) => setMobile(e.target.value.replace(/\D/g, "").slice(0, 10))}
              autoFocus
            />
            {error && <p className="text-sm text-danger">{error}</p>}
            <Button className="w-full" loading={loading} disabled={!MOBILE_RE.test(mobile)} onClick={handleRequestOtp}>
              Send code
            </Button>
            <p className="text-sm text-navy-muted text-center">
              New here?{" "}
              <Link to="/signup" className="text-navy underline">
                Create an account
              </Link>
            </p>
          </div>
        )}

        {step === "otp" && (
          <div className="space-y-4">
            <p className="text-sm text-navy-muted">Enter the code sent to {mobile}.</p>
            <Input
              label="Verification code"
              type="text"
              inputMode="numeric"
              placeholder="6-digit code"
              value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
              autoFocus
            />
            {error && <p className="text-sm text-danger">{error}</p>}
            <Button className="w-full" loading={loading} disabled={!OTP_RE.test(otp)} onClick={handleVerifyOtp}>
              Verify &amp; continue
            </Button>
            <button className="text-sm text-navy-muted underline" onClick={() => setStep("mobile")}>
              Use a different number
            </button>
          </div>
        )}

        {step === "choose-account" && (
          <div className="space-y-3">
            <p className="text-sm text-navy-muted">
              This number is linked to more than one account. Choose which one to continue with.
            </p>
            {accounts.map((acc) => (
              <button
                key={acc.user_id}
                onClick={() => handleChooseAccount(acc.user_id)}
                disabled={loading}
                className="w-full text-left px-4 py-3 border border-line rounded hover:border-navy transition-colors"
              >
                <div className="font-medium text-ink">{acc.full_name}</div>
                <div className="text-xs text-navy-muted">
                  {acc.society_name ?? "Platform"} — {acc.roles.join(", ")}
                </div>
              </button>
            ))}
            {error && <p className="text-sm text-danger">{error}</p>}
          </div>
        )}
      </div>
    </div>
  );
}

function errorMessage(e: unknown, fallback: string): string {
  const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}
