interface PageHeaderProps {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  right?: React.ReactNode;
}

export function PageHeader({ title, subtitle, eyebrow, right }: PageHeaderProps) {
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b-2 border-clinical-border bg-clinical-surface px-6 py-4">
      <div>
        {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
        <h1 className="font-display text-xl font-bold uppercase tracking-tight text-clinical-text">
          {title}
        </h1>
        {subtitle && <p className="mt-0.5 text-sm text-clinical-muted">{subtitle}</p>}
      </div>
      {right && <div className="flex items-center gap-2">{right}</div>}
    </header>
  );
}
