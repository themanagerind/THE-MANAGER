import { useState } from "react";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { showcasePrefillApi } from "@/api/showcasePrefill";

/** Resident -> Showcase (Ecom store) handoff (user-requested, design
 * reviewed with the Showcase team). Shows the DPDP consent line before
 * issuing a prefill token, then redirects to Showcase with it.
 *
 * The token itself carries no personal data (opaque, see backend's
 * ShowcasePrefillToken docstring) — Showcase's backend fetches the actual
 * name/mobile/address/flat server-to-server after redeeming it, and only
 * reveals anything beyond the mobile number once that same mobile is
 * OTP-verified on Showcase's own side. This button's only job is consent
 * + token issuance + redirect.
 *
 * Renders nothing until Showcase has a real production domain configured
 * (VITE_SHOWCASE_BASE_URL) — no domain means nowhere to send the token. */
export function ShopNowButton() {
  const [consentOpen, setConsentOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const showcaseBaseUrl = import.meta.env.VITE_SHOWCASE_BASE_URL;
  if (!showcaseBaseUrl) return null;

  async function handleConfirm() {
    setLoading(true);
    setError(false);
    try {
      const { data } = await showcasePrefillApi.create();
      window.location.href = `${showcaseBaseUrl}/signup?prefill=${encodeURIComponent(data.token)}`;
    } catch {
      setError(true);
      setLoading(false);
    }
  }

  return (
    <>
      <Button variant="secondary" onClick={() => setConsentOpen(true)}>
        Shop Now
      </Button>
      <Modal open={consentOpen} onClose={() => setConsentOpen(false)} title="Continue to Showcase">
        <div className="space-y-4">
          <p className="text-sm text-navy">
            Your name, mobile number, flat and society address will be shared with Showcase to fill in your
            signup form — you can review and edit everything there before saving, and you'll still verify your
            mobile with an OTP on Showcase.
          </p>
          {error && (
            <p className="text-sm text-danger">Couldn't start this — please try again.</p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setConsentOpen(false)} disabled={loading}>
              Cancel
            </Button>
            <Button onClick={() => void handleConfirm()} loading={loading}>
              Continue
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
