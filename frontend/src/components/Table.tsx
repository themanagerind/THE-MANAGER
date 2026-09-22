interface Column<T> {
  header: string;
  render: (row: T) => React.ReactNode;
  className?: string;
}

export function Table<T>({ columns, rows, keyFor }: { columns: Column<T>[]; rows: T[]; keyFor: (row: T) => string }) {
  return (
    <div className="border border-line rounded overflow-hidden overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-navy/5 text-left text-navy-muted">
            {columns.map((col) => (
              <th key={col.header} className={`px-3 py-2 font-medium whitespace-nowrap ${col.className ?? ""}`}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={keyFor(row)} className="border-t border-line hover:bg-navy/[0.03]">
              {columns.map((col) => (
                <td key={col.header} className={`px-3 py-2 ${col.className ?? ""}`}>
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
