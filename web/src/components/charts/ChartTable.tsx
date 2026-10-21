"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";

export type TableColumn<Row> = {
  key: string;
  label: string;
  /** Sort value; strings sort alphabetically, numbers numerically, null last. */
  value: (row: Row) => string | number | null;
  /** Display text (defaults to the sort value). */
  format?: (row: Row) => string;
  numeric?: boolean;
};

/** Sortable table of exactly the rows a chart draws ("Show as table"). */
export function ChartTable<Row>({
  rows,
  columns,
  rowKey,
  caption,
  initialSort,
}: {
  rows: readonly Row[];
  columns: readonly TableColumn<Row>[];
  rowKey: (row: Row) => string;
  caption: string;
  initialSort: { key: string; descending?: boolean };
}) {
  const [sort, setSort] = useState(initialSort);
  const sorted = useMemo(() => {
    const column = columns.find((c) => c.key === sort.key) ?? columns[0];
    const direction = sort.descending ? -1 : 1;
    return [...rows].sort((a, b) => {
      const left = column.value(a);
      const right = column.value(b);
      if (left === right) return rowKey(a) < rowKey(b) ? -1 : 1;
      if (left === null) return 1;
      if (right === null) return -1;
      return (left < right ? -1 : 1) * direction;
    });
  }, [rows, columns, sort, rowKey]);

  return (
    <div data-card="" className="overflow-x-auto rounded-xl border border-line bg-surface-card shadow-2xs" data-testid="chart-table">
      <table className="w-full text-left text-xs sm:text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-surface-inset text-ink-muted">
          <tr>
            {columns.map((column) => {
              const active = sort.key === column.key;
              return (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={active ? (sort.descending ? "descending" : "ascending") : "none"}
                  className={clsx("px-3 py-2 font-semibold", column.numeric && "text-right")}
                >
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
                    onClick={() =>
                      setSort(active ? { key: column.key, descending: !sort.descending } : { key: column.key })
                    }
                  >
                    {column.label}
                    <span aria-hidden>{active ? (sort.descending ? "↓" : "↑") : ""}</span>
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={rowKey(row)} className="border-t border-line">
              {columns.map((column) => (
                <td key={column.key} className={clsx("px-3 py-1.5 text-ink", column.numeric && "text-right tabular-nums")}>
                  {column.format ? column.format(row) : (column.value(row) ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
