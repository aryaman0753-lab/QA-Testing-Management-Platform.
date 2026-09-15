import { Button } from "../ui/Button";

export function Pagination({ page, totalPages, total, onChange }: {
  page: number; totalPages: number; total: number; onChange: (page: number) => void;
}) {
  if (!total) return null;
  return (
    <div className="pagination" aria-label="Pagination">
      <span className="muted">Page {page} of {Math.max(totalPages, 1)} · {total} bugs</span>
      <div className="button-row">
        <Button variant="secondary" disabled={page <= 1} onClick={() => onChange(page - 1)}>Previous</Button>
        <Button variant="secondary" disabled={page >= totalPages} onClick={() => onChange(page + 1)}>Next</Button>
      </div>
    </div>
  );
}
