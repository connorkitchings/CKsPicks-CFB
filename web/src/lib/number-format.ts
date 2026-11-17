/**
 * A number with an explicit sign: "+0.53", "-1.20". Rounds first so a value that rounds to zero
 * prints "0.00" with no sign (never "-0.00" or "+0.00").
 */
export function signedFixed(value: number, places = 2): string {
  const text = value.toFixed(places);
  const rounded = Number(text);
  if (rounded === 0) return (0).toFixed(places);
  return rounded > 0 ? `+${text}` : text;
}
