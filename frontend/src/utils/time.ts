// 24-hour clock regardless of browser locale: railway timetables are read
// that way, and "02:45 am–06:15 am" wraps in a narrow plan cell.
export function hhmm(time: string | Date): string {
  return new Date(time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
}
