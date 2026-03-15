interface TableSkeletonRowsProps {
  prefix: string;
  columns: number;
  rows?: number;
}

export function TableSkeletonRows({ prefix, columns, rows = 4 }: TableSkeletonRowsProps) {
  return (
    <>
      {Array.from({ length: rows }, (_, rowIdx) => (
        <tr className="table-skeleton-row" key={`${prefix}-${rowIdx}`} aria-hidden="true">
          {Array.from({ length: columns }, (_, colIdx) => (
            <td className="table-skeleton-cell" key={`${prefix}-${rowIdx}-${colIdx}`}>
              <span
                className={`skeleton-block table-skeleton-bar ${
                  colIdx === 0
                    ? 'skeleton-w-45'
                    : (colIdx % 2 === 0 ? 'skeleton-w-65' : 'skeleton-w-85')
                }`}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}
