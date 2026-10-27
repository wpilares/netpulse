import type { ReactNode } from "react";
import { ThemeToggle } from "../components/ui";
import styles from "./AppShell.module.css";
import { COMPACT_VIEWPORT_QUERY, useMediaQuery } from "./useMediaQuery";

export interface AppShellProps {
  readonly status: ReactNode;
  readonly version: string | null;
  readonly summary: ReactNode;
  readonly alerts: ReactNode;
  readonly topology: ReactNode;
  readonly ports: ReactNode;
}

const PRODUCT_NAME = "NetPulse";
const TAGLINE = "Real-time SDN network monitoring";

export const AppShell = ({ status, version, summary, alerts, topology, ports }: AppShellProps) => {
  const compact = useMediaQuery(COMPACT_VIEWPORT_QUERY);
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.brand}>
          <h1 className={styles.title}>{PRODUCT_NAME}</h1>
          <p className={styles.subtitle}>{TAGLINE}</p>
        </div>
        <div className={styles.status}>{status}</div>
        <div className={styles.theme}>
          <ThemeToggle compact={compact} />
        </div>
      </header>
      <main className={styles.main}>
        <div className={styles.summary}>{summary}</div>
        <div className={styles.alerts}>{alerts}</div>
        <div className={styles.topology}>{topology}</div>
        <div className={styles.ports}>{ports}</div>
      </main>
      <footer className={styles.footer}>
        <span className={styles.footerName}>{PRODUCT_NAME}</span>
        {version === null ? null : <span>API v{version}</span>}
        <span>{TAGLINE}</span>
      </footer>
    </div>
  );
};
