import type { ReactNode } from "react";
import { clsx } from "clsx";

const colHeaderBase =
  "py-1 text-[10px] font-medium uppercase tracking-wide text-ink-faint";
const rowHeaderBase = "py-1.5 pr-2 text-left font-medium text-ink-muted";

export type BetTableColumn = {
  header: string;
  /** Narrow-viewport width share (e.g. "w-[28%]"); omit on fluid tables. */
  widthClass?: string;
};

export type BetTableRow = {
  label: string;
  cells: ReactNode[];
};

/**
 * Shared market-vs-model table renderer. Each column declares its header and
 * optional width; each row supplies one cell node per column. Callers pass
 * the breakpoint-specific table/header/body classes so desktop (full Model
 * Bet + Bet Result columns), mobile (stacked "Bet" column combining both),
 * and market-mode (no model columns, fail-closed) tables share one renderer
 * instead of three hand-rolled copies.
 */
export function BetTable({
  ariaLabel,
  tableClassName,
  rowHeaderWidthClass,
  headerCellClassName,
  bodyCellClassName,
  columns,
  rows,
}: {
  ariaLabel: string;
  tableClassName: string;
  rowHeaderWidthClass?: string;
  headerCellClassName: string;
  /** One class for every body cell, or one per column. */
  bodyCellClassName: string | string[];
  columns: BetTableColumn[];
  rows: BetTableRow[];
}) {
  return (
    <table className={tableClassName} aria-label={ariaLabel}>
      <thead>
        <tr>
          <th
            scope="col"
            className={clsx(colHeaderBase, rowHeaderWidthClass)}
          >
            <span className="sr-only">Bet type</span>
          </th>
          {columns.map((col) => (
            <th
              key={col.header}
              scope="col"
              className={clsx(colHeaderBase, col.widthClass, headerCellClassName)}
            >
              {col.header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, rowIndex) => (
          <tr
            key={row.label}
            className={clsx(
              "border-line",
              rowIndex === 0 ? "border-t" : "border-y",
            )}
          >
            <th scope="row" className={rowHeaderBase}>
              {row.label}
            </th>
            {row.cells.map((cell, cellIndex) => (
              <td
                key={`${row.label}-${cellIndex}`}
                className={
                  Array.isArray(bodyCellClassName)
                    ? bodyCellClassName[cellIndex]
                    : bodyCellClassName
                }
              >
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
