import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { apiErrorMessage } from "@/components/States";
import { societiesApi, type SocietyLocationOut, type SocietySearchResultOut } from "@/api/societies";
import { residentsApi } from "@/api/residents";
import { adminsApi } from "@/api/admins";
import type { PropertyOut } from "@/api/properties";
import type { RelationshipType } from "@/types/enums";

type SignupRole = "RESIDENT" | "ADMIN";
type Step = "society" | "details" | "done";

function propertyLabel(p: PropertyOut): string {
  const kind = p.house_type === "FLAT" ? "Flat" : "Bungalow";
  const floor = p.floor_number != null ? `, Floor ${p.floor_number}` : "";
  return `${p.house_number} (${kind}${floor})${p.is_occupied ? " — occupied" : ""}`;
}

/** Admin signup's unit link (Section 4 dual-role, mandatory — every Admin
 * is ADMIN+RESIDENT): a real address-like Wing/Row -> Floor -> Flat
 * cascade instead of one long "house_number (Flat, Floor N)" list, since
 * an Admin picks their own unit before there's any occupancy history to
 * make that list meaningful. A Row (Bungalow) has no floor step — its
 * houses aren't floor-grouped (see StructureDiagram's RowCard). */
function UnitPicker({
  locations, properties, propertyId, onPropertyIdChange, relationshipType, onRelationshipTypeChange,
}: {
  locations: SocietyLocationOut[];
  properties: PropertyOut[];
  propertyId: string;
  onPropertyIdChange: (id: string) => void;
  relationshipType: RelationshipType;
  onRelationshipTypeChange: (r: RelationshipType) => void;
}) {
  const selected = properties.find((p) => p.id === propertyId);
  const [locationId, setLocationId] = useState(selected?.location_id ?? "");
  const [floor, setFloor] = useState(selected?.floor_number != null ? String(selected.floor_number) : "");

  const sortedLocations = [...locations].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" })
  );
  const propsInLocation = properties.filter((p) => p.location_id === locationId);
  const floors = Array.from(
    new Set(propsInLocation.map((p) => p.floor_number).filter((f): f is number => f != null))
  ).sort((a, b) => a - b);
  const hasFloors = floors.length > 0;
  const flatChoices = hasFloors ? propsInLocation.filter((p) => String(p.floor_number) === floor) : propsInLocation;

  function handleLocationChange(id: string) {
    setLocationId(id);
    setFloor("");
    onPropertyIdChange("");
  }
  function handleFloorChange(f: string) {
    setFloor(f);
    onPropertyIdChange("");
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-sm text-navy-muted mb-1">Wing / Row</label>
        <select
          value={locationId}
          onChange={(e) => handleLocationChange(e.target.value)}
          className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
        >
          <option value="">Select Wing/Row</option>
          {sortedLocations.map((l) => (
            <option key={l.id} value={l.id}>
              {l.name} ({l.location_type === "WING" ? "Wing" : "Row"})
            </option>
          ))}
        </select>
      </div>

      {locationId && hasFloors && (
        <div>
          <label className="block text-sm text-navy-muted mb-1">Floor</label>
          <select
            value={floor}
            onChange={(e) => handleFloorChange(e.target.value)}
            className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
          >
            <option value="">Select floor</option>
            {floors.map((f) => (
              <option key={f} value={f}>Floor {f}</option>
            ))}
          </select>
        </div>
      )}

      {locationId && (!hasFloors || floor) && (
        <div>
          <label className="block text-sm text-navy-muted mb-1">{hasFloors ? "Flat" : "House"}</label>
          <select
            value={propertyId}
            onChange={(e) => onPropertyIdChange(e.target.value)}
            className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
          >
            <option value="">Select {hasFloors ? "flat" : "house"}</option>
            {flatChoices.map((p) => (
              <option key={p.id} value={p.id}>
                {p.house_number}{p.is_occupied ? " — occupied" : ""}
              </option>
            ))}
          </select>
        </div>
      )}

      {propertyId && (
        <div>
          <label className="block text-sm text-navy-muted mb-1">I am the</label>
          <div className="flex gap-2">
            {(["OWNER", "TENANT"] as RelationshipType[]).map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => onRelationshipTypeChange(opt)}
                className={`px-3 py-1.5 rounded text-sm border ${
                  relationshipType === opt ? "bg-navy text-white border-navy" : "border-line text-navy-muted"
                }`}
              >
                {opt === "OWNER" ? "Owner" : "Tenant"}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
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

  // Every ACTIVE property/Wing/Row already on record for the chosen society
  // (public, no auth) — powers the Resident's required house picker and the
  // Admin's mandatory unit picker, below. Fetched once a society is picked;
  // a Flats or Bungalow society both just show up as PropertyOut rows here,
  // so nothing here needs to branch on society type.
  const [properties, setProperties] = useState<PropertyOut[]>([]);
  const [locations, setLocations] = useState<SocietyLocationOut[]>([]);
  const [propertiesLoading, setPropertiesLoading] = useState(false);
  const [propertiesError, setPropertiesError] = useState<string | null>(null);

  // Resident: required — picks which already-on-record house is theirs,
  // Owner or Tenant, right at signup (no more manual Admin linking after
  // approval).
  const [propertyId, setPropertyId] = useState("");
  const [relationshipType, setRelationshipType] = useState<RelationshipType>("OWNER");

  // Admin: mandatory (Section 4 dual-role — every Admin is ADMIN+RESIDENT)
  // — picks a real unit already on record, same as Resident above, via the
  // Wing/Row -> Floor -> Flat cascade (UnitPicker).
  const [existingPropertyId, setExistingPropertyId] = useState("");
  const [existingRelationshipType, setExistingRelationshipType] = useState<RelationshipType>("OWNER");

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
    setLocations([]);
    setPropertiesError(null);
    setPropertyId("");
    setRelationshipType("OWNER");
    setExistingPropertyId("");
    setExistingRelationshipType("OWNER");
  }

  // Load the chosen society's public property + Wing/Row lists once it's
  // picked — both roles' pickers below read from these.
  useEffect(() => {
    if (!society) {
      setProperties([]);
      setLocations([]);
      return;
    }
    setPropertiesLoading(true);
    setPropertiesError(null);
    Promise.all([societiesApi.publicProperties(society.id), societiesApi.publicLocations(society.id)])
      .then(([propsRes, locsRes]) => {
        setProperties(propsRes.data);
        setLocations(locsRes.data);
      })
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
          existing_property_id: existingPropertyId,
          existing_property_relationship: existingRelationshipType,
        });
      }
      setStep("done");
    } catch (e) {
      setError(apiErrorMessage(e, "Signup could not be submitted."));
    } finally {
      setLoading(false);
    }
  }

  const canSubmit =
    fullName.trim().length > 0 &&
    MOBILE_RE.test(mobile) &&
    (role === "RESIDENT" ? propertyId.length > 0 : existingPropertyId.length > 0);

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
                    </div>
                  </>
                )}
              </div>
            )}

            {role === "ADMIN" && (
              <div className="border border-line rounded p-3 space-y-3">
                <label className="block text-sm text-navy-muted">Which unit is yours?</label>
                {propertiesLoading && <p className="text-sm text-navy-muted">Loading properties…</p>}
                {propertiesError && <p className="text-sm text-danger">{propertiesError}</p>}
                {!propertiesLoading && !propertiesError && (locations.length === 0 || properties.length === 0) && (
                  <p className="text-xs text-navy-muted">
                    This society's Wings/Rows and flats/houses haven't been mapped yet — ask the
                    Platform Owner to map the structure first (every Admin account is linked to a
                    unit here).
                  </p>
                )}
                {locations.length > 0 && properties.length > 0 && (
                  <UnitPicker
                    locations={locations}
                    properties={properties}
                    propertyId={existingPropertyId}
                    onPropertyIdChange={setExistingPropertyId}
                    relationshipType={existingRelationshipType}
                    onRelationshipTypeChange={setExistingRelationshipType}
                  />
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
