const pad = (value: number): string => String(value).padStart(2, "0");

export const formatClock = (iso: string): string => {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
};

const JUST_NOW_SECONDS = 5;

export const formatRelative = (iso: string, now: number): string => {
  const stamp = Date.parse(iso);
  if (Number.isNaN(stamp)) {
    return "—";
  }
  const seconds = Math.max(0, Math.floor((now - stamp) / 1000));
  if (seconds < JUST_NOW_SECONDS) {
    return "just now";
  }
  if (seconds < 60) {
    return `${seconds} s ago`;
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes} min ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours} h ago`;
  }
  return `${Math.floor(hours / 24)} d ago`;
};
