import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useActiveProperty } from "@/hooks/useActiveProperty";
import { paymentsApi } from "@/api/payments";
import { propertiesApi } from "@/api/properties";
import { locationsApi } from "@/api/societies";
import { PropertySelector } from "@/components/PropertySelector";
import { StructureDiagram } from "@/components/StructureDiagram";
import { Loader, EmptyState, ErrorState } from "@/components/States";
import { Badge } from "@/components/Badge";

export function ResidentDashboard() {
  const { activePropertyId, setActivePropertyId, options, hasMultipleProperties, isLoading, error } = useActiveProperty();

  const duesQuery = useQuery({
    queryKey: ["dues", activePropertyId],
    queryFn: () => paymentsApi.duesForProperty(activePropertyId!).then((r) => r.data),
    enabled: !!activePropertyId,
  });
  const walletQuery = useQuery({
    queryKey: ["wallet", "me"],
    queryFn: () => paymentsApi.myWallet().then((r) => r.data),
  });
  const societyPropertiesQuery = useQuery({
    queryKey: ["resident", "society-properties"],
    queryFn: () => propertiesApi.list().then((r) => r.data),
  });
  const societyLocationsQuery = useQuery({
    queryKey: ["resident", "society-locations"],
    queryFn: () => locationsApi.list().then((r) => r.data),
  });

  if (isLoading) return <Loader />;
  if (error) return <ErrorState message="Couldn't load your properties." />;
  if (options.length === 0) {
    return <EmptyState title="No linked property yet" description="Once an Admin links you to a property, it will show up here." />;
  }

  const pendingDues = (duesQuery.data ?? []).filter((d) => d.status === "PENDING");
  const totalPending = pendingDues.reduce((sum, d) => sum + d.amount, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-semibold text-navy">Home</h1>
        {hasMultipleProperties && (
          <PropertySelector properties={options} activePropertyId={activePropertyId} onChange={setActivePropertyId} />
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Link to="/resident/dues" className="border border-line rounded p-4 hover:border-navy transition-colors">
          <p className="text-xs text-navy-muted mb-1">Pending dues</p>
          <p className="text-2xl font-semibold text-navy">
            {duesQuery.isLoading ? "…" : `₹${totalPending.toLocaleString("en-IN")}`}
          </p>
          {pendingDues.length > 0 && <Badge status="PENDING">{pendingDues.length} due</Badge>}
        </Link>
        <Link to="/resident/wallet" className="border border-line rounded p-4 hover:border-navy transition-colors">
          <p className="text-xs text-navy-muted mb-1">Wallet balance</p>
          <p className="text-2xl font-semibold text-navy">
            {walletQuery.isLoading ? "…" : `₹${(walletQuery.data?.balance ?? 0).toLocaleString("en-IN")}`}
          </p>
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {[
          { to: "/resident/complaints", label: "Complaints" },
          { to: "/resident/visitors", label: "Visitors" },
          { to: "/resident/notices", label: "Notices" },
          { to: "/resident/amenities", label: "Amenities" },
        ].map((item) => (
          <Link key={item.to} to={item.to} className="border border-line rounded p-4 text-sm text-navy hover:border-navy transition-colors">
            {item.label}
          </Link>
        ))}
      </div>

      {societyLocationsQuery.data && societyPropertiesQuery.data && (
        <div className="border border-line rounded p-4">
          <p className="text-xs text-navy-muted mb-2">Society structure</p>
          <StructureDiagram locations={societyLocationsQuery.data} properties={societyPropertiesQuery.data} />
        </div>
      )}
    </div>
  );
}
