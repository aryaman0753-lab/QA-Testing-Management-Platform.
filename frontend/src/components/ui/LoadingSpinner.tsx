export function LoadingSpinner({ fullPage = false }: { fullPage?: boolean }) {
  return (
    <div className={fullPage ? "spinner-fullpage" : "spinner-inline"}>
      <div className="spinner" />
    </div>
  );
}
