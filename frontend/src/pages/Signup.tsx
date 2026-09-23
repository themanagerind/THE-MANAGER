import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { apiErrorMessage } from "@/components/States";
import { societiesApi, type SocietySearchResultOut } from "@/api/societies";
import { residentsApi } from "@/api/residents";
import { adminsApi } from "@/api/admins";
import type { PropertyOut } from "@/api/properties";
import type { HouseType, LocationType, RelationshipType } from "@/types/enums";

type SignupRole = "RESIDENT" | "ADMIN";
type Step = "society" | "details" | "done";
/** Admin-only — whether they also link themselves to a unit right here.
 * EXISTING picks from properties already on record (Owner or Tenant, same
 * picker Resident signup uses); NEW describes a brand-new unit (Owner
 * only, unchanged behavior from before). */
type AdminUnitMode = "NONE" | "EXISTING" | "NEW";

function propertyLabel(p: PropertyOut): string {
  const kind = p.house_type === "FLAT" ? "Flat" : "Bungalow";
  const floor = p.floor_number != null ? `, Floor ${p.floor_number}` : "";
  return `${p.house_number} (${kind}${floor})${p.is_occupied ? " — occupied" : ""}`;
}

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

  // Every ACTIVE property already on record for the chosen society (public,
  // no auth) — powers the Resident's required house picker and the Admin's
  // "link to an existing unit" option, below. Fetched once a society is
  // picked; a Flats or Bungalow society both just show up as PropertyOut
  // rows here, so nothing here needs to branch on society type.
  const [properties, setProperties] = useState<PropertyOut[]>([]);
  const [propertiesLoading, setPropertiesLoading] = useState(false);
  const [propertiesError, setPropertiesError] = useState<string | null>(null);

  // Resident: required — picks which already-on-record house is theirs,
  // Owner or Tenant, right at signup (no more manual Admin linking after
  // approval).
  const [propertyId, setPropertyId] = useState("");
  const [relationshipType, setRelationshipType] = useState<RelationshipType>("OWNER");

  // Admin-only: optionally link themselves to a unit here (Section 4
  // dual-role — ADMIN+RESIDENT), right at signup instead of a separate
  // manual step after approval. EXISTING picks a real unit (Owner or
  // Tenant); NEW describes a brand-new one (Owner only — a just-described
  // unit can never already have a Tenant on it, Section 12 invariant).
  const [adminUnitMode, setAdminUnitMode] = useState<AdminUnitMode>("NONE");
  const [existingPropertyId, setExistingPropertyId] = useState("");
  const [existingRelationshipType, setExistingRelationshipType] = useState<RelationshipType>("OWNER");
  const [locationName, setLocationName] = useState("");
  const [locationType, setLocationType] = useState<LocationType>("WING");
  const [houseNumber, setHouseNumber] = useState("");
  const [houseType, setHouseType] = useState<HouseType>("FLAT");
  const [floorNumber, setFloorNumber] = useState("");

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
    setProperties([]);
    setPropertiesError(null);
    setPropertyId("");
    setRelationshipType("OWNER");
    setAdminUnitMode("NONE");
    setExistingPropertyId("");
    setExistingRelationshipType("OWNER");
    setLocationName("");
    setLocationType("WING");
    setHouseNumber("");
    setHouseType("FLAT");
    setFloorNumber("");
  }

  // Load the chosen society's public property list once it's picked —
  // both roles' pickers below read from this same list.
  useEffect(() => {
    if (!society) {
      setProperties([]);
      return;
    }
    setPropertiesLoading(true);
    setPropertiesError(null);
    societiesApi
      .publicProperties(society.id)
      .then((r) => setProperties(r.data))
      .catch((e) => setPropertiesError(apiErrorMessage(e, "Couldn't load this society's properties.")))
      .finally(() => setPropertiesLoading(false));
  }, [society]);

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
        await residentsApi.signup({ ...body, property_id: propertyId, relationship_type: relationshipType });
      } else {
        await adminsApi.signup({
          ...body,
          ...(adminUnitMode === "EXISTING" && {
            existing_property_id: existingPropertyId,
            existing_property_relationship: existingRelationshipType,
          }),
          ...(adminUnitMode === "NEW" && {
            property_location_name: locationName.trim(),
            property_location_type: locationType,
            house_number: houseNumber.trim(),
            house_type: houseType,
            floor_number: houseType === "FLAT" ? Number(floorNumber) : (floorNumber ? Number(floorNumber) : undefined),
          }),
        });
      }
      setStep("done");
    } catch (e) {
      setError(apiErrorMessage(e, "Signup could not be submitted."));
    } finally {
      setLoading(false);
    }
  }

  const newUnitValid =
    adminUnitMode !== "NEW" ||
    (locationName.trim().length > 0 &&
      houseNumber.trim().length > 0 &&
      (houseType === "BUNGALOW" || !!floorNumber));
  const existingUnitValid = adminUnitMode !== "EXISTING" || existingPropertyId.length > 0;
  const canSubmit =
    fullName.trim().length > 0 &&
    MOBILE_RE.test(mobile) &&
    (role === "RESIDENT" ? propertyId.length > 0 : newUnitValid && existingUnitValid);

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

            {role === "RESIDENT" && (
              <div className="border border-line rounded p-3 space-y-3">
                <label className="block text-sm text-navy-muted">Which house is yours?</label>
                {propertiesLoading && <p className="text-sm text-navy-muted">Loading properties…</p>}
                {propertiesError && <p className="text-sm text-danger">{propertiesError}</p>}
                {!propertiesLoading && !propertiesError && properties.length === 0 && (
                  <p className="text-xs text-navy-muted">
                    No properties are on record for this society yet — ask your Admin to add them
                    (Wings/Rows and flats/houses) before signing up.
                  </p>
                )}
                {properties.length > 0 && (
                  <>
                    <select
                      value={propertyId}
                      onChange={(e) => setPropertyId(e.target.value)}
                      className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
                    >
                      <option value="">Select your house</option>
                      {properties.map((p) => (
                        <option key={p.id} value={p.id}>{propertyLabel(p)}</option>
                      ))}
                    </select>
                    <div>
                      <label className="block text-sm text-navy-muted mb-1">I am the</label>
                      <div className="flex gap-2">
                        {(["OWNER", "TENANT"] as RelationshipType[]).map((opt) => (
                          <button
                            key={opt}
                            type="button"
                            onClick={() => setRelationshipType(opt)}
                            className={`px-3 py-1.5 rounded text-sm border ${
                              relationshipType === opt ? "bg-navy text-white border-navy" : "border-line text-navy-muted"
                            }`}
                          >
                            {opt === "OWNER" ? "Owner" : "Tenant"}
                          </button>
                        ))}
                      </div>
                      {relationshipType === "TENANT" && (
                        <p className="text-xs text-navy-muted mt-1">
                          A Tenant signup needs this house's Owner to already be on record — if the
                          Owner hasn't signed up yet, ask them to go first.
                        </p>
                      )}
                    </div>
                  </>
                )}
              </div>
            )}

            {role === "ADMIN" && (
              <div className="border border-line rounded p-3 space-y-3">
                <label className="block text-sm text-navy-muted">Do you also live in a unit here?</label>
                <div className="flex gap-2">
                  {(["NONE", "EXISTING", "NEW"] as AdminUnitMode[]).map((opt) => (
                    <button
                      key={opt}
                      type="button"
                      onClick={() => setAdminUnitMode(opt)}
                      className={`px-3 py-1.5 rounded text-sm border ${
                        adminUnitMode === opt ? "bg-navy text-white border-navy" : "border-line text-navy-muted"
                      }`}
                    >
                      {opt === "NONE" ? "No" : opt === "EXISTING" ? "Yes, an existing unit" : "Yes, a new unit"}
                    </button>
                  ))}
                </div>

                {adminUnitMode === "EXISTING" && (
                  <div className="space-y-3 pt-1">
                    {propertiesLoading && <p className="text-sm text-navy-muted">Loading properties…</p>}
                    {propertiesError && <p className="text-sm text-danger">{propertiesError}</p>}
                    {!propertiesLoading && !propertiesError && properties.length === 0 && (
                      <p className="text-xs text-navy-muted">
                        No properties are on record for this society yet — pick "Yes, a new unit" to
                        describe one instead.
                      </p>
                    )}
                    {properties.length > 0 && (
                      <>
                        <select
                          value={existingPropertyId}
                          onChange={(e) => setExistingPropertyId(e.target.value)}
                          className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
                        >
                          <option value="">Select the unit</option>
                          {properties.map((p) => (
                            <option key={p.id} value={p.id}>{propertyLabel(p)}</option>
                          ))}
                        </select>
                        <div>
                          <label className="block text-sm text-navy-muted mb-1">I am the</label>
                          <div className="flex gap-2">
                            {(["OWNER", "TENANT"] as RelationshipType[]).map((opt) => (
                              <button
                                key={opt}
                                type="button"
                                onClick={() => setExistingRelationshipType(opt)}
                                className={`px-3 py-1.5 rounded text-sm border ${
                                  existingRelationshipType === opt ? "bg-navy text-white border-navy" : "border-line text-navy-muted"
                                }`}
                              >
                                {opt === "OWNER" ? "Owner" : "Tenant"}
                              </button>
                            ))}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                )}

                {adminUnitMode === "NEW" && (
                  <div className="space-y-3 pt-1">
                    <p className="text-xs text-navy-muted">
                      Describes a brand-new unit not yet on record and adds you as its Owner.
                    </p>
                    <div>
                      <label className="block text-sm text-navy-muted mb-1">Unit type</label>
                      <div className="flex gap-2">
                        {(["FLAT", "BUNGALOW"] as HouseType[]).map((opt) => (
                          <button
                            key={opt}
                            type="button"
                            onClick={() => { setHouseType(opt); setLocationType(opt === "FLAT" ? "WING" : "ROW"); }}
                            className={`px-3 py-1.5 rounded text-sm border ${
                              houseType === opt ? "bg-navy text-white border-navy" : "border-line text-navy-muted"
                            }`}
                          >
                            {opt === "FLAT" ? "Flat" : "Bungalow"}
                          </button>
                        ))}
                      </div>
                    </div>
                    <Input
                      label={houseType === "FLAT" ? "Wing name" : "Row name"}
                      value={locationName}
                      onChange={(e) => setLocationName(e.target.value)}
                      placeholder="e.g. Wing A"
                    />
                    <Input
                      label="House/unit number"
                      value={houseNumber}
                      onChange={(e) => setHouseNumber(e.target.value)}
                    />
                    {houseType === "FLAT" && (
                      <Input
                        label="Floor number"
                        type="number"
                        value={floorNumber}
                        onChange={(e) => setFloorNumber(e.target.value)}
                      />
                    )}
                    {houseType === "BUNGALOW" && (
                      <Input
                        label="Floor number (optional)"
                        type="number"
                        value={floorNumber}
                        onChange={(e) => setFloorNumber(e.target.value)}
                      />
                    )}
                  </div>
                )}
              </div>
            )}

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
