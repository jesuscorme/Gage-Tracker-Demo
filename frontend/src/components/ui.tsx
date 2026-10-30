"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { STATUS_TONE } from "@/lib/status";
import type { GageStatus } from "@/lib/types";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

// ---------------------------------------------------------------- buttons

type Variant = "primary" | "secondary" | "ghost" | "danger";
const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-white hover:bg-accent-strong border-accent",
  secondary: "bg-surface text-ink hover:bg-line-2 border-line",
  ghost: "bg-transparent text-ink-2 hover:bg-line-2 border-transparent",
  danger: "bg-surface text-bad hover:bg-bad-soft border-line",
};
const BTN = "inline-flex items-center justify-center gap-1.5 h-9 px-3.5 rounded-md border text-[13px] font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none whitespace-nowrap";

export function Button({
  variant = "secondary",
  className,
  loading,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button className={cx(BTN, VARIANTS[variant], className)} disabled={loading || props.disabled} {...props}>
      {loading && <Spinner small />}
      {children}
    </button>
  );
}

export function LinkButton({
  href,
  variant = "secondary",
  className,
  children,
}: {
  href: string;
  variant?: Variant;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Link href={href} className={cx(BTN, VARIANTS[variant], className)}>
      {children}
    </Link>
  );
}

// ---------------------------------------------------------------- form controls

const CONTROL =
  "w-full h-9 rounded-md border border-line bg-surface px-2.5 text-[13px] text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/15 disabled:bg-line-2 disabled:text-ink-3";

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(CONTROL, props.className)} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cx(CONTROL, "pr-7", props.className)} />;
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cx(CONTROL, "h-auto py-2 min-h-20", props.className)} />;
}

export function Field({
  label,
  hint,
  error,
  required,
  children,
  className,
}: {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={cx("block", className)}>
      <span className="mb-1 block text-[12px] font-medium text-ink-2">
        {label}
        {required && <span className="text-bad"> *</span>}
      </span>
      {children}
      {error ? (
        <span className="mt-1 block text-[12px] text-bad">{error}</span>
      ) : hint ? (
        <span className="mt-1 block text-[12px] text-ink-3">{hint}</span>
      ) : null}
    </label>
  );
}

// ---------------------------------------------------------------- layout

export function Card({ title, actions, children, className, flush }: {
  title?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  flush?: boolean;
}) {
  return (
    <section className={cx("rounded-lg border border-line bg-surface", className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          <h2 className="text-[13px] font-semibold tracking-wide text-ink">{title}</h2>
          {actions}
        </header>
      )}
      <div className={flush ? "" : "p-4"}>{children}</div>
    </section>
  );
}

export function PageHeader({ title, eyebrow, actions, children }: {
  title: React.ReactNode;
  eyebrow?: React.ReactNode;
  actions?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">{eyebrow}</div>}
        <h1 className="text-xl font-semibold text-ink">{title}</h1>
        {children}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Spec({ label, children, mono }: { label: string; children: React.ReactNode; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-ink-3">{label}</dt>
      <dd className={cx("mt-0.5 truncate text-[13px] text-ink", mono && "font-mono tabular")}>{children ?? "—"}</dd>
    </div>
  );
}

// ---------------------------------------------------------------- status

const TONE_CLASS: Record<string, string> = {
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
  block: "bg-block-soft text-block",
  info: "bg-info-soft text-info",
  mute: "bg-mute-soft text-mute",
};
const DOT_CLASS: Record<string, string> = {
  ok: "bg-ok", warn: "bg-warn", bad: "bg-bad", block: "bg-block", info: "bg-info", mute: "bg-mute",
};

export function StatusBadge({ status, large }: { status: GageStatus; large?: boolean }) {
  const { t } = useI18n();
  const tone = STATUS_TONE[status];
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded font-semibold uppercase tracking-wide whitespace-nowrap",
        large ? "px-2.5 py-1 text-[12px]" : "px-1.5 py-0.5 text-[10.5px]",
        TONE_CLASS[tone],
      )}
    >
      <span className={cx("inline-block size-1.5 rounded-[1px]", DOT_CLASS[tone])} />
      {t(`status.${status}`)}
    </span>
  );
}

export function StatusDot({ status }: { status: GageStatus }) {
  return <span className={cx("inline-block size-2 rounded-[2px]", DOT_CLASS[STATUS_TONE[status]])} />;
}

// ---------------------------------------------------------------- feedback

export function Spinner({ small }: { small?: boolean }) {
  return (
    <span
      aria-hidden
      className={cx(
        "inline-block animate-spin rounded-full border-2 border-current border-r-transparent",
        small ? "size-3.5" : "size-5 text-accent",
      )}
    />
  );
}

export function Loading() {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-2 py-10 text-ink-3" role="status">
      <Spinner /> {t("common.loading")}
    </div>
  );
}

export function Alert({ tone = "bad", children }: { tone?: "bad" | "ok" | "warn" | "info"; children: React.ReactNode }) {
  return (
    <div role={tone === "bad" ? "alert" : "status"} className={cx("rounded-md border px-3 py-2 text-[13px]", TONE_CLASS[tone], "border-current/20")}>
      {children}
    </div>
  );
}

export function errorText(t: ReturnType<typeof useI18n>["t"], err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 403) return t("common.forbidden");
    if (err.status === 404) return t("common.notFound");
    if (err.code === "validation_error" && Array.isArray(err.details)) {
      return (err.details as { loc: string[]; msg: string }[])
        .map((d) => `${d.loc.slice(1).join(".")}: ${d.msg}`)
        .join(" · ");
    }
    return err.message;
  }
  return t("common.error");
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap items-center gap-3 py-6">
      <Alert>{errorText(t, error)}</Alert>
      {onRetry && <Button onClick={onRetry}>{t("common.retry")}</Button>}
    </div>
  );
}

export function EmptyState({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center text-ink-3">
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none" aria-hidden className="text-line">
        <rect x="4" y="14" width="32" height="12" rx="2" stroke="currentColor" strokeWidth="2" />
        {[10, 15, 20, 25, 30].map((x, i) => (
          <line key={x} x1={x} y1="14" x2={x} y2={i % 2 ? 19 : 21} stroke="currentColor" strokeWidth="2" />
        ))}
      </svg>
      <p className="max-w-sm text-[13px]">{children}</p>
      {action}
    </div>
  );
}

// ---------------------------------------------------------------- modal

export function Modal({ open, title, onClose, children, footer }: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      className="m-auto w-[min(520px,calc(100vw-32px))] rounded-lg border border-line bg-surface p-0 text-ink shadow-xl backdrop:bg-ink/40"
    >
      <header className="border-b border-line px-5 py-3.5 text-[14px] font-semibold">{title}</header>
      <div className="space-y-4 px-5 py-4">{children}</div>
      {footer && <footer className="flex justify-end gap-2 border-t border-line bg-line-2/50 px-5 py-3">{footer}</footer>}
    </dialog>
  );
}

// ---------------------------------------------------------------- pagination

export function Pagination({ page, pageSize, total, onPage }: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (p: number) => void;
}) {
  const { t } = useI18n();
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-2.5 text-[12px] text-ink-3">
      <span className="tabular">
        {from}–{to} / {total} {t("common.results")}
      </span>
      <div className="flex gap-1.5">
        <Button variant="ghost" className="h-7 px-2" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          ‹ {t("common.previous")}
        </Button>
        <Button variant="ghost" className="h-7 px-2" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          {t("common.next")} ›
        </Button>
      </div>
    </div>
  );
}

export { cx };
