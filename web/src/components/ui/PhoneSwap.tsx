/** Shows `phone` below `sm` and `full` from `sm` up; one span when they match. */
export function PhoneSwap({ full, phone }: { full: string; phone: string }) {
  if (full === phone) return <>{full}</>;
  return (
    <>
      <span className="max-sm:hidden">{full}</span>
      <span className="sm:hidden" title={full}>{phone}</span>
    </>
  );
}
