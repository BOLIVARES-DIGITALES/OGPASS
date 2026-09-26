import { createFileRoute } from "@tanstack/react-router";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronRight,
  CircleCheck,
  Code2,
  Copy,
  CreditCard,
  ExternalLink,
  Github,
  LockKeyhole,
  Radio,
  ShieldCheck,
  Sparkles,
  Terminal,
  UserRound,
  WalletCards,
  Zap,
} from "lucide-react";
import { useEffect, useState } from "react";

import elephantMascot from "@/assets/ogpass-elephant.png";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "OGPASS — Tu pase, una sola integración" },
      {
        name: "description",
        content:
          "Consulta el saldo de tu tarjeta OG o integra pagos de transporte con el SDK de OGPASS.",
      },
      { property: "og:title", content: "OGPASS — Tu pase, una sola integración" },
      {
        property: "og:description",
        content:
          "Consulta saldos y prueba una integración moderna para pagos de transporte.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

type View = "home" | "client" | "developer";

const demoMovements = [
  { line: "Línea 1 · Estación Centro", date: "Hoy, 08:42", amount: "− $0.50" },
  { line: "Línea 2 · Plaza Norte", date: "Ayer, 18:16", amount: "− $0.50" },
  { line: "Recarga digital", date: "24 Sep, 12:05", amount: "+ $10.00" },
];

function Brand() {
  return (
    <div className="flex items-center gap-3" aria-label="OGPASS">
      <div className="grid size-9 place-items-center rounded-md bg-primary text-primary-foreground shadow-[var(--shadow-glow)]">
        <span className="font-display text-sm font-black">OG</span>
      </div>
      <span className="font-display text-lg font-extrabold tracking-normal">OGPASS</span>
      <span className="hidden rounded-sm border border-border bg-secondary px-2 py-0.5 font-mono text-[10px] font-semibold uppercase text-muted-foreground sm:inline">
        Preview
      </span>
    </div>
  );
}

function Index() {
  const [view, setView] = useState<View>("home");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const timer = window.setTimeout(() => setIsLoading(false), 1450);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <main className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <div
        className={cn(
          "fixed inset-0 z-50 grid place-items-center bg-background transition-[opacity,visibility] duration-500",
          isLoading ? "visible opacity-100" : "invisible opacity-0",
        )}
        aria-hidden={!isLoading}
      >
        <div className="text-center">
          <div className="elephant-walk mx-auto w-40 sm:w-48">
            <img
              src={elephantMascot}
              alt="Elefante de OGPASS caminando"
              width={1024}
              height={1024}
              className="h-auto w-full"
            />
          </div>
          <p className="mt-2 font-display text-lg font-bold">Preparando tu viaje</p>
          <div className="mx-auto mt-4 h-1 w-32 overflow-hidden rounded-full bg-secondary">
            <span className="loading-track block h-full rounded-full bg-primary" />
          </div>
        </div>
      </div>
      <div className="pointer-events-none absolute inset-0 bg-grid opacity-50" />
      <header className="relative z-20 mx-auto grid h-20 max-w-7xl grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-5 lg:px-8">
        <button
          type="button"
          onClick={() => setView("home")}
          className="cursor-pointer rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Brand />
        </button>
        <div className="flex items-center gap-3">
          <span className="hidden items-center gap-2 text-xs text-muted-foreground md:flex">
            <span className="size-1.5 rounded-full bg-success shadow-[0_0_10px_var(--success)]" />
            Sandbox operativo
          </span>
          <Button variant="ghost" size="sm" asChild>
            <a
              href="https://github.com/BOLIVARES-DIGITALES/OGPASS"
              target="_blank"
              rel="noreferrer"
            >
              <Github />
              <span className="hidden sm:inline">GitHub</span>
            </a>
          </Button>
        </div>
      </header>

      <div className="relative z-10 mx-auto max-w-7xl px-5 pb-[max(3rem,env(safe-area-inset-bottom))] pt-3 lg:px-8 lg:pt-8">
        {view === "home" && <HomeView onSelect={setView} />}
        {view === "client" && <ClientView onBack={() => setView("home")} />}
        {view === "developer" && <DeveloperView onBack={() => setView("home")} />}
      </div>
    </main>
  );
}

function HomeView({ onSelect }: { onSelect: (view: View) => void }) {
  return (
    <div className="animate-enter">
      <section className="mx-auto max-w-4xl pb-7 pt-1 text-center sm:pb-10 lg:pb-12 lg:pt-5">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-secondary/70 px-3 py-1.5 text-xs font-semibold text-secondary-foreground backdrop-blur">
          <Radio className="size-3.5 text-primary" />
          Una infraestructura, cada viaje
        </div>
        <h1 className="font-display text-[2.45rem] font-extrabold leading-[1.06] tracking-normal sm:text-6xl lg:text-7xl">
          Tu pase. Tu saldo.
          <br />
          <span className="text-primary">Una sola integración.</span>
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-sm leading-6 text-muted-foreground sm:mt-6 sm:text-lg sm:leading-7">
          Consulta tu tarjeta OG o construye la próxima experiencia de movilidad con una API
          diseñada para pagos de transporte.
        </p>
      </section>

      <section className="mx-auto grid max-w-4xl gap-4" aria-label="Elige cómo entrar">
        <PortalCard
          icon={<UserRound className="size-6" />}
          eyebrow="Para pasajeros"
          title="Soy cliente OG"
          description="Consulta tu saldo, revisa movimientos y conoce el estado de tu tarjeta en segundos."
          features={["Saldo al instante", "Movimientos recientes", "Datos protegidos"]}
          cta="Consultar mi tarjeta"
          visual={<TransitCard />}
          onClick={() => onSelect("client")}
        />
        <PortalCard
          icon={<Code2 className="size-6" />}
          eyebrow="Para equipos técnicos"
          title="Soy desarrollador"
          description="Explora el SDK, prueba autorizaciones y conecta wallets con una interfaz simple."
          features={["API REST", "Sandbox incluido", "Código abierto"]}
          cta="Explorar el SDK"
          visual={<CodePreview />}
          onClick={() => onSelect("developer")}
          accent
        />
      </section>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-xs text-muted-foreground">
        <span className="flex items-center gap-2"><ShieldCheck className="size-4" /> Cifrado en tránsito</span>
        <span className="flex items-center gap-2"><Zap className="size-4" /> Respuesta en tiempo real</span>
        <span className="flex items-center gap-2"><Github className="size-4" /> MIT Open Source</span>
      </div>
    </div>
  );
}

function PortalCard({
  icon,
  eyebrow,
  title,
  description,
  features,
  cta,
  visual,
  onClick,
  accent = false,
}: {
  icon: React.ReactNode;
  eyebrow: string;
  title: string;
  description: string;
  features: string[];
  cta: string;
  visual: React.ReactNode;
  onClick: () => void;
  accent?: boolean;
}) {
  return (
    <article
      className={cn(
        "group relative overflow-hidden rounded-lg border bg-card p-5 transition-all duration-300 hover:-translate-y-1 sm:p-7",
        accent
          ? "border-primary/35 shadow-[var(--shadow-card-accent)]"
          : "border-border shadow-[var(--shadow-card)]",
      )}
    >
      <div className="relative z-10 grid h-full gap-5 sm:grid-cols-[1.05fr_.95fr] sm:items-center sm:gap-8">
        <div className="flex flex-col">
          <div className="flex items-center gap-3 text-sm font-semibold text-primary">
            <span className="grid size-10 place-items-center rounded-md bg-primary/10">{icon}</span>
            {eyebrow}
          </div>
          <h2 className="mt-4 font-display text-2xl font-bold tracking-normal sm:mt-5 sm:text-3xl">{title}</h2>
          <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">{description}</p>
          <ul className="mt-4 space-y-2 text-sm sm:mt-5">
            {features.map((feature) => (
              <li key={feature} className="flex items-center gap-2">
                <span className="grid size-5 place-items-center rounded-full bg-success/10 text-success">
                  <Check className="size-3" strokeWidth={3} />
                </span>
                {feature}
              </li>
            ))}
          </ul>
          <Button className="mt-5 w-full justify-between sm:mt-6 sm:w-fit" size="lg" onClick={onClick}>
            {cta}
            <ArrowRight className="transition-transform group-hover:translate-x-1" />
          </Button>
        </div>
        <div className="flex min-h-44 items-center justify-center sm:min-h-52">{visual}</div>
      </div>
    </article>
  );
}

function TransitCard() {
  return (
    <div className="relative aspect-[1.58/1] w-full max-w-72 rotate-2 rounded-lg border border-primary/25 bg-ticket p-5 shadow-[var(--shadow-ticket)] transition-transform duration-300 group-hover:rotate-0">
      <div className="flex items-start justify-between">
        <Brand />
        <Radio className="size-5 text-primary" />
      </div>
      <div className="mt-10">
        <p className="text-[10px] font-semibold uppercase text-muted-foreground">Saldo disponible</p>
        <p className="font-mono text-3xl font-bold">$ 12.50</p>
      </div>
      <div className="absolute bottom-5 left-5 right-5 flex justify-between font-mono text-[10px] text-muted-foreground">
        <span>•••• 0248</span><span>ACTIVA</span>
      </div>
    </div>
  );
}

function CodePreview() {
  return (
    <div className="w-full max-w-sm overflow-hidden rounded-md border border-code-border bg-code text-code-foreground shadow-[var(--shadow-code)]">
      <div className="flex h-9 items-center gap-1.5 border-b border-code-border px-3">
        <span className="size-2 rounded-full bg-danger" />
        <span className="size-2 rounded-full bg-warning" />
        <span className="size-2 rounded-full bg-success" />
        <span className="ml-auto font-mono text-[9px] text-code-muted">authorize.py</span>
      </div>
      <pre className="overflow-hidden p-4 font-mono text-[10px] leading-5 sm:text-xs">
        <code>
          <span className="text-code-muted">from</span> ogpass <span className="text-code-muted">import</span> Client{"\n\n"}
          client = Client(env=<span className="text-code-accent">&quot;sandbox&quot;</span>){"\n"}
          result = client.authorize({"\n"}
          {"  "}folio=<span className="text-code-accent">&quot;OG-0248&quot;</span>,{"\n"}
          {"  "}amount=<span className="text-code-number">0.50</span>{"\n"}
          ){"\n\n"}
          <span className="text-success">✓ APPROVED</span>
        </code>
      </pre>
    </div>
  );
}

function BackButton({ onBack }: { onBack: () => void }) {
  return (
    <Button variant="ghost" size="sm" onClick={onBack} className="mb-6 -ml-3 text-muted-foreground">
      <ArrowLeft /> Volver
    </Button>
  );
}

function ClientView({ onBack }: { onBack: () => void }) {
  const [folio, setFolio] = useState("");
  const [searched, setSearched] = useState(false);

  return (
    <div className="mx-auto max-w-5xl animate-enter">
      <BackButton onBack={onBack} />
      <div className="grid gap-8 lg:grid-cols-[.85fr_1.15fr] lg:items-start">
        <section>
          <div className="flex size-12 items-center justify-center rounded-md bg-primary/10 text-primary">
            <WalletCards />
          </div>
          <h1 className="mt-5 font-display text-4xl font-bold tracking-normal">Consulta tu tarjeta</h1>
          <p className="mt-3 max-w-md leading-7 text-muted-foreground">
            Ingresa tu folio para ver un resultado de prueba. Nunca solicitaremos tu contraseña ni datos bancarios.
          </p>
          <form
            className="mt-8"
            onSubmit={(event) => {
              event.preventDefault();
              setSearched(true);
            }}
          >
            <label htmlFor="folio" className="mb-2 block text-sm font-semibold">Folio de tu tarjeta</label>
            <div className="flex gap-2">
              <Input
                id="folio"
                value={folio}
                onChange={(event) => { setFolio(event.target.value); setSearched(false); }}
                placeholder="Ej. OG-0248"
                autoComplete="off"
                className="h-11 bg-card font-mono uppercase"
                maxLength={24}
              />
              <Button type="submit" size="lg" disabled={!folio.trim()}>Consultar</Button>
            </div>
          </form>
          <div className="mt-5 flex gap-3 rounded-md border border-border bg-secondary/55 p-4 text-xs leading-5 text-muted-foreground">
            <LockKeyhole className="mt-0.5 size-4 shrink-0 text-primary" />
            Esta prueba no consulta tarjetas reales ni guarda el folio ingresado.
          </div>
        </section>

        <section className="rounded-lg border border-border bg-card p-5 shadow-[var(--shadow-card)] sm:p-7">
          {!searched ? (
            <div className="grid min-h-96 place-items-center text-center">
              <div>
                <div className="mx-auto grid size-16 place-items-center rounded-full bg-secondary text-muted-foreground">
                  <CreditCard className="size-7" />
                </div>
                <p className="mt-5 font-semibold">Tu saldo aparecerá aquí</p>
                <p className="mt-2 text-sm text-muted-foreground">Prueba con cualquier folio para ver la demostración.</p>
              </div>
            </div>
          ) : (
            <div className="animate-enter">
              <div className="flex items-start justify-between border-b border-border pb-6">
                <div>
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-success/10 px-2.5 py-1 text-xs font-semibold text-success">
                    <CircleCheck className="size-3.5" /> Activa
                  </span>
                  <p className="mt-3 font-mono text-xs text-muted-foreground">{folio.toUpperCase()}</p>
                </div>
                <Radio className="text-primary" />
              </div>
              <div className="py-7">
                <p className="text-sm text-muted-foreground">Saldo disponible</p>
                <p className="mt-1 font-mono text-5xl font-bold">$ 12.50</p>
                <p className="mt-2 text-xs text-muted-foreground">Saldo de demostración · USD</p>
              </div>
              <div>
                <p className="mb-3 text-xs font-bold uppercase text-muted-foreground">Movimientos recientes</p>
                <div className="divide-y divide-border">
                  {demoMovements.map((movement) => (
                    <div key={movement.line} className="flex items-center justify-between py-3">
                      <div><p className="text-sm font-medium">{movement.line}</p><p className="mt-0.5 text-xs text-muted-foreground">{movement.date}</p></div>
                      <span className={cn("font-mono text-sm font-semibold", movement.amount.startsWith("+") && "text-success")}>{movement.amount}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function DeveloperView({ onBack }: { onBack: () => void }) {
  const [copied, setCopied] = useState(false);
  const [result, setResult] = useState<"idle" | "loading" | "approved">("idle");
  const snippet = `from ogpass import Client\n\nclient = Client(environment="sandbox")\nresult = client.authorize(\n  folio="OG-DEMO-0248",\n  amount=0.50,\n  terminal_id="METRO-001"\n)`;

  function simulate() {
    setResult("loading");
    window.setTimeout(() => setResult("approved"), 700);
  }

  return (
    <div className="mx-auto max-w-6xl animate-enter">
      <BackButton onBack={onBack} />
      <div className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-primary"><Terminal className="size-4" /> OGPASS SDK</div>
          <h1 className="mt-3 font-display text-4xl font-bold tracking-normal sm:text-5xl">Integra. Valida. Avanza.</h1>
          <p className="mt-3 max-w-2xl leading-7 text-muted-foreground">Prueba el flujo de autorización con datos aislados antes de conectar tu entorno.</p>
        </div>
        <Button variant="outline" asChild>
          <a href="https://github.com/BOLIVARES-DIGITALES/OGPASS" target="_blank" rel="noreferrer">Ver repositorio <ExternalLink /></a>
        </Button>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.15fr_.85fr]">
        <section className="overflow-hidden rounded-lg border border-code-border bg-code text-code-foreground shadow-[var(--shadow-code)]">
          <div className="flex h-12 items-center border-b border-code-border px-4">
            <div className="flex gap-1.5"><span className="size-2.5 rounded-full bg-danger" /><span className="size-2.5 rounded-full bg-warning" /><span className="size-2.5 rounded-full bg-success" /></div>
            <span className="ml-4 font-mono text-xs text-code-muted">quickstart.py</span>
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto text-code-muted hover:bg-code-border hover:text-code-foreground"
              onClick={async () => {
                await navigator.clipboard.writeText(snippet);
                setCopied(true);
                window.setTimeout(() => setCopied(false), 1400);
              }}
            >
              {copied ? <Check /> : <Copy />} {copied ? "Copiado" : "Copiar"}
            </Button>
          </div>
          <pre className="min-h-80 overflow-x-auto p-5 font-mono text-xs leading-6 sm:p-7 sm:text-sm"><code>{snippet}</code></pre>
          <div className="border-t border-code-border bg-code-panel p-4 font-mono text-xs">
            <span className="text-code-muted">$</span> pip install ogpass-sdk
          </div>
        </section>

        <section className="rounded-lg border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <div className="flex items-center justify-between">
            <div><p className="text-xs font-bold uppercase text-muted-foreground">Consola sandbox</p><h2 className="mt-1 font-display text-xl font-bold">Simular autorización</h2></div>
            <span className="size-2 rounded-full bg-success shadow-[0_0_10px_var(--success)]" />
          </div>
          <div className="mt-6 space-y-3 rounded-md border border-border bg-secondary/45 p-4 font-mono text-xs">
            <div className="flex justify-between"><span className="text-muted-foreground">folio</span><span>OG-DEMO-0248</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">amount</span><span>$0.50</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">terminal</span><span>METRO-001</span></div>
          </div>
          <Button className="mt-4 w-full" size="lg" onClick={simulate} disabled={result === "loading"}>
            <Zap /> {result === "loading" ? "Autorizando…" : "Ejecutar prueba"}
          </Button>
          <div className={cn("mt-5 min-h-28 rounded-md border p-4 transition-colors", result === "approved" ? "border-success/30 bg-success/5" : "border-dashed border-border")}>
            {result === "idle" && <p className="text-center text-xs leading-20 text-muted-foreground">Esperando una solicitud</p>}
            {result === "loading" && <p className="text-center text-xs leading-20 text-muted-foreground">Validando credencial y saldo…</p>}
            {result === "approved" && (
              <div className="animate-enter font-mono text-xs">
                <p className="flex items-center gap-2 font-bold text-success"><CircleCheck className="size-4" /> APPROVED</p>
                <div className="mt-3 flex justify-between text-muted-foreground"><span>latency</span><span className="text-foreground">84 ms</span></div>
                <div className="mt-2 flex justify-between text-muted-foreground"><span>balance_after</span><span className="text-foreground">12.50</span></div>
              </div>
            )}
          </div>
          <div className="mt-5 flex items-start gap-3 text-xs leading-5 text-muted-foreground">
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" />
            Las claves privadas deben permanecer en el servidor. Esta consola usa datos simulados.
          </div>
        </section>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        {[{ icon: <Sparkles />, title: "Simple", text: "Una llamada para autorizar" }, { icon: <ShieldCheck />, title: "Seguro", text: "Credenciales fuera del cliente" }, { icon: <ChevronRight />, title: "Predecible", text: "Respuestas claras y tipadas" }].map((item) => (
          <div key={item.title} className="flex items-center gap-3 rounded-md border border-border bg-card/70 p-4">
            <span className="text-primary [&_svg]:size-5">{item.icon}</span><div><p className="text-sm font-semibold">{item.title}</p><p className="text-xs text-muted-foreground">{item.text}</p></div>
          </div>
        ))}
      </div>
    </div>
  );
}