import { createFileRoute } from "@tanstack/react-router";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Cable,
  Check,
  ChevronDown,
  CircleCheck,
  Code2,
  Copy,
  Cpu,
  CreditCard,
  ExternalLink,
  Github,
  LockKeyhole,
  LoaderCircle,
  Radio,
  RefreshCw,
  Server,
  ShieldCheck,
  Terminal,
  TrainFront,
  UserRound,
  WalletCards,
  Wifi,
  Zap,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

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
        content: "Consulta saldos y prueba una integración moderna para pagos de transporte.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

type View = "home" | "client" | "developer";

type TransitIssuer = "OG" | "RED" | "SUBE";
type ConsultationStatus =
  | "idle"
  | "loading"
  | "verified"
  | "verification_required"
  | "integration_required"
  | "unavailable"
  | "revoked"
  | "error"
  | "authentication_required";

type HardwareState =
  | "idle"
  | "requesting"
  | "checking"
  | "ready"
  | "partial"
  | "reader_missing"
  | "firmware_outdated"
  | "unsupported"
  | "error";

type HardwareDiagnostic = {
  device: "OGPASS-ESP32-PN532";
  protocol: 1;
  reader_ready: boolean;
  wifi_connected: boolean;
  backend_online: boolean;
  heartbeat_code: number;
  pending_operation: boolean;
};

type SerialPortLike = {
  readable: ReadableStream<Uint8Array> | null;
  writable: WritableStream<Uint8Array> | null;
  open: (options: { baudRate: number }) => Promise<void>;
  close: () => Promise<void>;
  getInfo?: () => { usbVendorId?: number; usbProductId?: number };
};

type SerialAccessLike = {
  requestPort: (options?: {
    filters?: Array<{ usbVendorId: number; usbProductId?: number }>;
  }) => Promise<SerialPortLike>;
  getPorts: () => Promise<SerialPortLike[]>;
  addEventListener: (type: "disconnect", listener: () => void) => void;
  removeEventListener: (type: "disconnect", listener: () => void) => void;
};

type BalanceResult = {
  status: Exclude<ConsultationStatus, "idle" | "loading" | "error" | "authentication_required">;
  balance: number | null;
  currency: string;
  source: string;
  source_url: string | null;
  observed_at: string | null;
  message: string;
  products: string[];
  product_details?: {
    red_metro: {
      integration_status: string;
      available_balance: number | null;
      outstanding_balance: number | null;
      billed_balance: number | null;
      currency: string;
      updated_at: string | null;
      recent_movements: Array<{
        id: string;
        description: string;
        amount: number;
        occurred_at: string;
      }>;
      message: string;
    };
    red_web3: {
      integration_status: string;
      accounts: Array<{
        network: "testnet" | "mainnet";
        address: string;
        status: string;
        available_xlm: string | null;
        updated_at: string | null;
        source_url: string | null;
      }>;
      credit_line_xlm: string | null;
      debt_xlm: string | null;
      message: string;
    };
  };
  credential: {
    id: string;
    issuer: TransitIssuer;
    reference_masked: string;
    verification_status: "declared" | "verified" | "revoked";
  };
};

const consentVersion = "transit-v1-2026-09-30";
const apiBase = (import.meta.env.VITE_OGPASS_API_BASE_URL ?? "").replace(/\/$/, "");

function apiUrl(path: string) {
  return `${apiBase}${path}`;
}

function cookie(name: string) {
  const item = document.cookie.split("; ").find((entry) => entry.startsWith(`${name}=`));
  return item ? decodeURIComponent(item.slice(name.length + 1)) : "";
}

function clp(value: number | null) {
  if (value === null) return "No disponible";
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(value);
}

function integrationLabel(status: string) {
  const labels: Record<string, string> = {
    verified: "Verificada",
    connected: "Conectada",
    not_linked: "No vinculada",
    integration_required: "Integración pendiente",
    verification_required: "Requiere verificación",
    unavailable: "Temporalmente no disponible",
    unfunded: "Cuenta sin fondos",
  };
  return labels[status] ?? status;
}

function xlm(value: string | null) {
  if (value === null) return "No disponible";
  const amount = Number(value);
  return `${Number.isFinite(amount) ? amount.toLocaleString("es-CL", { maximumFractionDigits: 7 }) : value} XLM`;
}

async function readJson<T>(response: Response): Promise<T> {
  const type = response.headers.get("content-type") ?? "";
  if (!type.includes("application/json")) {
    throw new Error("El servicio OGPASS no está conectado en este dominio.");
  }
  const data = (await response.json()) as T & { error?: string };
  if (!response.ok) throw new Error(data.error || "No fue posible completar la consulta.");
  return data;
}

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
            Consulta protegida
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
        <span className="flex items-center gap-2">
          <ShieldCheck className="size-4" /> Cifrado en tránsito
        </span>
        <span className="flex items-center gap-2">
          <Zap className="size-4" /> Respuesta en tiempo real
        </span>
        <span className="flex items-center gap-2">
          <Github className="size-4" /> MIT Open Source
        </span>
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
          <h2 className="mt-4 font-display text-2xl font-bold tracking-normal sm:mt-5 sm:text-3xl">
            {title}
          </h2>
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
          <Button
            className="mt-5 w-full justify-between sm:mt-6 sm:w-fit"
            size="lg"
            onClick={onClick}
          >
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
        <p className="text-[10px] font-semibold uppercase text-muted-foreground">
          Tu saldo verificado
        </p>
        <p className="font-mono text-3xl font-bold">$ —</p>
      </div>
      <div className="absolute bottom-5 left-5 right-5 flex justify-between font-mono text-[10px] text-muted-foreground">
        <span>REFERENCIA PROTEGIDA</span>
        <span>OGPASS</span>
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
          <span className="text-code-muted">from</span> ogpass{" "}
          <span className="text-code-muted">import</span> Client{"\n\n"}
          client = Client(env=<span className="text-code-accent">&quot;sandbox&quot;</span>){"\n"}
          result = client.authorize({"\n"}
          {"  "}folio=<span className="text-code-accent">&quot;OG-0248&quot;</span>,{"\n"}
          {"  "}amount=<span className="text-code-number">0.50</span>
          {"\n"}){"\n\n"}
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
  const [issuer, setIssuer] = useState<TransitIssuer>("OG");
  const [reference, setReference] = useState("");
  const [consent, setConsent] = useState(false);
  const [status, setStatus] = useState<ConsultationStatus>("idle");
  const [result, setResult] = useState<BalanceResult | null>(null);
  const [error, setError] = useState("");

  async function consult() {
    setStatus("loading");
    setError("");
    setResult(null);
    try {
      const sessionResponse = await fetch(apiUrl("/api/session/"), {
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      const session = await readJson<{ authenticated: boolean }>(sessionResponse);
      if (!session.authenticated) {
        setStatus("authentication_required");
        return;
      }
      const credentialResponse = await fetch(apiUrl("/api/transit/credentials/"), {
        method: "POST",
        credentials: "include",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": cookie("csrftoken"),
        },
        body: JSON.stringify({
          issuer,
          reference,
          consent,
          consent_version: consentVersion,
        }),
      });
      const declared = await readJson<{ credential: { id: string } }>(credentialResponse);
      const balanceResponse = await fetch(
        apiUrl(`/api/transit/credentials/${declared.credential.id}/balance/`),
        {
          method: "POST",
          credentials: "include",
          headers: { Accept: "application/json", "X-CSRFToken": cookie("csrftoken") },
        },
      );
      const balance = await readJson<BalanceResult>(balanceResponse);
      setResult(balance);
      setStatus(balance.status);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No fue posible completar la consulta.");
      setStatus("error");
    }
  }

  async function revoke() {
    if (!result) return;
    try {
      const response = await fetch(
        apiUrl(`/api/transit/credentials/${result.credential.id}/revoke/`),
        {
          method: "POST",
          credentials: "include",
          headers: { Accept: "application/json", "X-CSRFToken": cookie("csrftoken") },
        },
      );
      await readJson(response);
      setResult({
        ...result,
        status: "revoked",
        balance: null,
        observed_at: null,
        message: "La credencial fue desvinculada de tu cuenta.",
        products: [],
        credential: { ...result.credential, verification_status: "revoked" },
      });
      setStatus("revoked");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "No fue posible desvincular la credencial.",
      );
      setStatus("error");
    }
  }

  return (
    <div className="mx-auto max-w-5xl animate-enter">
      <BackButton onBack={onBack} />
      <div className="grid gap-8 lg:grid-cols-[.85fr_1.15fr] lg:items-start">
        <section>
          <div className="flex size-12 items-center justify-center rounded-md bg-primary/10 text-primary">
            <WalletCards />
          </div>
          <h1 className="mt-5 font-display text-4xl font-bold tracking-normal">
            Consulta tu tarjeta
          </h1>
          <p className="mt-3 max-w-md leading-7 text-muted-foreground">
            Elige el emisor e ingresa la referencia impresa. OGPASS cifra el número y mantiene cada
            saldo separado por su fuente.
          </p>
          <form
            className="mt-8 space-y-5"
            onSubmit={(event) => {
              event.preventDefault();
              void consult();
            }}
          >
            <div>
              <label htmlFor="issuer" className="mb-2 block text-sm font-semibold">
                Emisor
              </label>
              <select
                id="issuer"
                value={issuer}
                onChange={(event) => {
                  setIssuer(event.target.value as TransitIssuer);
                  setReference("");
                  setStatus("idle");
                  setResult(null);
                }}
                className="h-11 w-full rounded-md border border-input bg-card px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="OG">OGPASS</option>
                <option value="RED">Red Movilidad · bip! / TNE / TAM</option>
                <option value="SUBE">SUBE Argentina</option>
              </select>
            </div>
            <div>
              <label htmlFor="folio" className="mb-2 block text-sm font-semibold">
                {issuer === "OG" ? "Número de tarjeta OGPASS" : "Número impreso de la tarjeta"}
              </label>
              <Input
                id="folio"
                value={reference}
                onChange={(event) => {
                  setReference(event.target.value);
                  setStatus("idle");
                  setResult(null);
                }}
                placeholder={issuer === "OG" ? "Ej. OG0248" : "Sólo números"}
                autoComplete="off"
                inputMode={issuer === "OG" ? "text" : "numeric"}
                className="h-11 bg-card font-mono uppercase"
                maxLength={24}
              />
            </div>
            <label className="flex cursor-pointer items-start gap-3 rounded-md border border-border bg-secondary/35 p-4 text-xs leading-5 text-muted-foreground">
              <input
                type="checkbox"
                checked={consent}
                onChange={(event) => setConsent(event.target.checked)}
                className="mt-0.5 size-4 accent-[var(--primary)]"
              />
              <span>
                Autorizo a OGPASS a proteger esta referencia y usarla sólo para consultar y mostrar
                los productos asociados. Versión {consentVersion}.
              </span>
            </label>
            <Button
              type="submit"
              size="lg"
              className="w-full"
              disabled={!reference.trim() || !consent || status === "loading"}
            >
              {status === "loading" ? <LoaderCircle className="animate-spin" /> : <ShieldCheck />}
              {status === "loading" ? "Consultando fuente…" : "Asociar y consultar"}
            </Button>
          </form>
          <div className="mt-5 flex gap-3 rounded-md border border-border bg-secondary/55 p-4 text-xs leading-5 text-muted-foreground">
            <LockKeyhole className="mt-0.5 size-4 shrink-0 text-primary" />
            No solicitamos claves, PIN, datos bancarios ni acceso a la memoria NFC. El número se
            cifra y se guarda sólo con tu consentimiento.
          </div>
        </section>

        <section className="rounded-lg border border-border bg-card p-5 shadow-[var(--shadow-card)] sm:p-7">
          {status === "idle" ? (
            <div className="grid min-h-96 place-items-center text-center">
              <div>
                <div className="mx-auto grid size-16 place-items-center rounded-full bg-secondary text-muted-foreground">
                  <CreditCard className="size-7" />
                </div>
                <p className="mt-5 font-semibold">Tu consulta aparecerá aquí</p>
                <p className="mt-2 max-w-sm text-sm leading-6 text-muted-foreground">
                  Sólo mostramos montos confirmados por el ledger OGPASS o por una integración
                  autorizada del emisor.
                </p>
              </div>
            </div>
          ) : status === "loading" ? (
            <div className="grid min-h-96 place-items-center text-center" role="status">
              <div>
                <LoaderCircle className="mx-auto size-10 animate-spin text-primary" />
                <p className="mt-5 font-semibold">Consultando la fuente correcta</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Estamos verificando la credencial sin exponer su número.
                </p>
              </div>
            </div>
          ) : status === "authentication_required" ? (
            <div className="grid min-h-96 place-items-center text-center">
              <div className="max-w-sm">
                <LockKeyhole className="mx-auto size-10 text-primary" />
                <p className="mt-5 font-semibold">Ingresa a tu cuenta OG</p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  La asociación requiere una sesión para impedir que otra cuenta registre tu
                  referencia.
                </p>
                <Button asChild className="mt-5">
                  <a href={apiUrl("/login/?next=/")}>Ingresar</a>
                </Button>
              </div>
            </div>
          ) : status === "error" ? (
            <div className="grid min-h-96 place-items-center text-center" role="alert">
              <div className="max-w-sm">
                <AlertCircle className="mx-auto size-10 text-danger" />
                <p className="mt-5 font-semibold">No completamos la consulta</p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{error}</p>
                <Button variant="outline" className="mt-5" onClick={() => void consult()}>
                  <RefreshCw /> Reintentar
                </Button>
              </div>
            </div>
          ) : result ? (
            <div className="animate-enter">
              <div className="flex items-start justify-between border-b border-border pb-6">
                <div>
                  <span
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold",
                      result.status === "verified"
                        ? "bg-success/10 text-success"
                        : "bg-warning/10 text-warning",
                    )}
                  >
                    {result.status === "verified" ? (
                      <CircleCheck className="size-3.5" />
                    ) : (
                      <AlertCircle className="size-3.5" />
                    )}
                    {result.status === "verified" ? "Verificada" : "Pendiente de integración"}
                  </span>
                  <p className="mt-3 font-mono text-xs text-muted-foreground">
                    {result.credential.issuer} · {result.credential.reference_masked}
                  </p>
                </div>
                <Radio className="text-primary" />
              </div>
              <div className="py-7">
                <p className="text-sm text-muted-foreground">Saldo disponible</p>
                <p className="mt-1 font-mono text-4xl font-bold sm:text-5xl">
                  {result.balance === null
                    ? "No disponible"
                    : new Intl.NumberFormat("es-CL", {
                        style: "currency",
                        currency: result.currency,
                        maximumFractionDigits: 0,
                      }).format(result.balance)}
                </p>
                <p className="mt-2 text-xs text-muted-foreground">
                  Fuente: {result.source}
                  {result.observed_at
                    ? ` · ${new Date(result.observed_at).toLocaleString("es-CL")}`
                    : ""}
                </p>
                <p className="mt-4 rounded-md bg-secondary/55 p-3 text-sm leading-6 text-muted-foreground">
                  {result.message}
                </p>
              </div>
              {result.products.length > 0 && (
                <div className="border-t border-border pt-5">
                  <p className="mb-3 text-xs font-bold uppercase text-muted-foreground">
                    Productos asociados
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {result.products.map((product) => (
                      <span
                        key={product}
                        className="rounded-full border border-border bg-secondary px-3 py-1.5 text-xs font-semibold"
                      >
                        {product}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {result.credential.issuer === "OG" && result.product_details && (
                <div className="mt-6 space-y-3 border-t border-border pt-5">
                  <p className="text-xs font-bold uppercase text-muted-foreground">
                    Redes asociadas a tu tarjeta OG
                  </p>

                  <details className="group rounded-md border border-border bg-secondary/25">
                    <summary className="flex cursor-pointer list-none items-center gap-3 p-4 [&::-webkit-details-marker]:hidden">
                      <span className="grid size-9 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
                        <TrainFront className="size-5" />
                      </span>
                      <span>
                        <span className="block text-sm font-semibold">Red Metro</span>
                        <span className="text-xs text-muted-foreground">
                          {integrationLabel(result.product_details.red_metro.integration_status)}
                        </span>
                      </span>
                      <ChevronDown className="ml-auto size-4 text-muted-foreground transition-transform group-open:rotate-180" />
                    </summary>
                    <div className="border-t border-border p-4">
                      <div className="grid gap-3 sm:grid-cols-3">
                        {[
                          [
                            "Saldo disponible",
                            clp(result.product_details.red_metro.available_balance),
                          ],
                          [
                            "Saldo adeudado",
                            clp(result.product_details.red_metro.outstanding_balance),
                          ],
                          ["Saldo facturado", clp(result.product_details.red_metro.billed_balance)],
                        ].map(([label, value]) => (
                          <div key={label} className="rounded-md border border-border bg-card p-3">
                            <p className="text-[11px] text-muted-foreground">{label}</p>
                            <p className="mt-1 font-mono text-sm font-semibold">{value}</p>
                          </div>
                        ))}
                      </div>
                      <p className="mt-4 text-xs leading-5 text-muted-foreground">
                        Estado de integración:{" "}
                        {integrationLabel(result.product_details.red_metro.integration_status)}.
                        {result.product_details.red_metro.updated_at
                          ? ` Actualizado ${new Date(result.product_details.red_metro.updated_at).toLocaleString("es-CL")}.`
                          : ""}
                      </p>
                      <p className="mt-2 text-xs leading-5 text-muted-foreground">
                        {result.product_details.red_metro.message}
                      </p>
                      <div className="mt-4 border-t border-border pt-4">
                        <p className="text-xs font-semibold">Últimos movimientos</p>
                        {result.product_details.red_metro.recent_movements.length === 0 ? (
                          <p className="mt-2 text-xs text-muted-foreground">
                            No hay movimientos entregados por una integración autorizada.
                          </p>
                        ) : (
                          <ul className="mt-2 space-y-2">
                            {result.product_details.red_metro.recent_movements.map((movement) => (
                              <li key={movement.id} className="flex justify-between gap-3 text-xs">
                                <span>{movement.description}</span>
                                <span className="font-mono">{clp(movement.amount)}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  </details>

                  <details className="group rounded-md border border-border bg-secondary/25">
                    <summary className="flex cursor-pointer list-none items-center gap-3 p-4 [&::-webkit-details-marker]:hidden">
                      <span className="grid size-9 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
                        <Zap className="size-5" />
                      </span>
                      <span>
                        <span className="block text-sm font-semibold">Red Web3</span>
                        <span className="text-xs text-muted-foreground">
                          {integrationLabel(result.product_details.red_web3.integration_status)}
                        </span>
                      </span>
                      <ChevronDown className="ml-auto size-4 text-muted-foreground transition-transform group-open:rotate-180" />
                    </summary>
                    <div className="border-t border-border p-4">
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="rounded-md border border-border bg-card p-3">
                          <p className="text-[11px] text-muted-foreground">Línea de crédito</p>
                          <p className="mt-1 font-mono text-sm font-semibold">
                            {xlm(result.product_details.red_web3.credit_line_xlm)}
                          </p>
                        </div>
                        <div className="rounded-md border border-border bg-card p-3">
                          <p className="text-[11px] text-muted-foreground">Deuda Web3</p>
                          <p className="mt-1 font-mono text-sm font-semibold">
                            {xlm(result.product_details.red_web3.debt_xlm)}
                          </p>
                        </div>
                      </div>
                      <div className="mt-4 space-y-3">
                        <p className="text-xs font-semibold">Saldo disponible XLM</p>
                        {result.product_details.red_web3.accounts.length === 0 ? (
                          <p className="text-xs text-muted-foreground">
                            No hay una dirección pública Stellar vinculada.
                          </p>
                        ) : (
                          result.product_details.red_web3.accounts.map((account) => (
                            <div
                              key={`${account.network}:${account.address}`}
                              className="rounded-md border border-border bg-card p-3"
                            >
                              <div className="flex items-center justify-between gap-3">
                                <span className="rounded-full bg-secondary px-2 py-1 text-[10px] font-bold uppercase">
                                  {account.network}
                                </span>
                                <span className="font-mono text-sm font-semibold">
                                  {xlm(account.available_xlm)}
                                </span>
                              </div>
                              <p className="mt-2 truncate font-mono text-[10px] text-muted-foreground">
                                {account.address}
                              </p>
                            </div>
                          ))
                        )}
                      </div>
                      <p className="mt-4 text-xs leading-5 text-muted-foreground">
                        {result.product_details.red_web3.message}
                      </p>
                    </div>
                  </details>
                </div>
              )}
              <div className="mt-6 flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => void consult()}>
                  <RefreshCw /> Actualizar
                </Button>
                {result.source_url && result.status !== "verified" && (
                  <Button variant="ghost" asChild>
                    <a href={result.source_url} target="_blank" rel="noreferrer">
                      Abrir fuente oficial <ExternalLink />
                    </a>
                  </Button>
                )}
                {result.status !== "revoked" && (
                  <Button variant="ghost" onClick={() => void revoke()}>
                    Desvincular
                  </Button>
                )}
              </div>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}

function DeveloperView({ onBack }: { onBack: () => void }) {
  const [copied, setCopied] = useState(false);
  const [hardwareState, setHardwareState] = useState<HardwareState>("idle");
  const [diagnostic, setDiagnostic] = useState<HardwareDiagnostic | null>(null);
  const [hardwareError, setHardwareError] = useState("");
  const [portConnected, setPortConnected] = useState(false);
  const portRef = useRef<SerialPortLike | null>(null);
  const snippet = [
    "const port = await navigator.serial.requestPort();",
    "await port.open({ baudRate: 115200 });",
    "",
    "const writer = port.writable.getWriter();",
    'await writer.write(new TextEncoder().encode("STATUS\\n"));',
    "writer.releaseLock();",
    "",
    '// Espera: OGPASS_STATUS { "reader_ready": true, ... }',
  ].join("\n");

  function serialAccess() {
    if (typeof navigator === "undefined") return undefined;
    return (navigator as Navigator & { serial?: SerialAccessLike }).serial;
  }

  useEffect(() => {
    const serial = serialAccess();
    const disconnected = () => {
      portRef.current = null;
      setPortConnected(false);
      setDiagnostic(null);
      setHardwareError("El lector USB fue desconectado del equipo.");
      setHardwareState("error");
    };
    serial?.addEventListener("disconnect", disconnected);
    return () => {
      serial?.removeEventListener("disconnect", disconnected);
      const port = portRef.current;
      portRef.current = null;
      if (port) void port.close().catch(() => undefined);
    };
  }, []);

  async function disconnectHardware() {
    const port = portRef.current;
    portRef.current = null;
    if (port) await port.close().catch(() => undefined);
    setPortConnected(false);
    setDiagnostic(null);
    setHardwareError("");
    setHardwareState("idle");
  }

  async function verifyHardware() {
    const serial = serialAccess();
    if (!serial) {
      setHardwareState("unsupported");
      setHardwareError(
        "Usa Chrome o Edge de escritorio sobre HTTPS o localhost para acceder al puerto USB.",
      );
      return;
    }
    setHardwareError("");
    setDiagnostic(null);
    try {
      let port = portRef.current;
      if (!port) {
        const approved = await serial.getPorts();
        port = approved.find((candidate) => {
          const info = candidate.getInfo?.() ?? {};
          return (
            (info.usbVendorId === 0x10c4 && info.usbProductId === 0xea60) ||
            info.usbVendorId === 0x1a86 ||
            info.usbVendorId === 0x303a
          );
        });
        if (!port) {
          setHardwareState("requesting");
          port = await serial.requestPort({
            filters: [
              { usbVendorId: 0x10c4, usbProductId: 0xea60 },
              { usbVendorId: 0x1a86 },
              { usbVendorId: 0x303a },
            ],
          });
        }
        portRef.current = port;
      }
      if (!port.readable || !port.writable) {
        await port.close().catch(() => undefined);
        await port.open({ baudRate: 115200 });
        await new Promise((resolve) => window.setTimeout(resolve, 1200));
      }
      setPortConnected(true);
      setHardwareState("checking");

      const reader = port.readable?.getReader();
      if (!reader) throw new Error("El puerto no permite recibir la respuesta del lector.");
      const sendStatus = async () => {
        const writer = port.writable?.getWriter();
        if (!writer) return;
        try {
          await writer.write(new TextEncoder().encode("STATUS\n"));
        } finally {
          writer.releaseLock();
        }
      };
      let buffer = "";
      let payload: HardwareDiagnostic | null = null;
      let i2cError = false;
      await sendStatus();
      const retry = window.setTimeout(() => void sendStatus().catch(() => undefined), 1400);
      const timeout = window.setTimeout(() => void reader.cancel(), 4200);
      try {
        while (!payload && !i2cError) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += new TextDecoder().decode(value, { stream: true });
          for (const line of buffer.split(/\r?\n/)) {
            if (/i2cRead returned Error|PN532 NO DETECTADO/i.test(line)) {
              i2cError = true;
              break;
            }
            if (!line.startsWith("OGPASS_STATUS ")) continue;
            const candidate = JSON.parse(line.slice("OGPASS_STATUS ".length)) as HardwareDiagnostic;
            if (
              candidate.device !== "OGPASS-ESP32-PN532" ||
              candidate.protocol !== 1 ||
              typeof candidate.reader_ready !== "boolean" ||
              typeof candidate.wifi_connected !== "boolean" ||
              typeof candidate.backend_online !== "boolean"
            ) {
              throw new Error("El dispositivo respondió con un protocolo OGPASS no válido.");
            }
            payload = candidate;
            break;
          }
        }
      } finally {
        window.clearTimeout(retry);
        window.clearTimeout(timeout);
        reader.releaseLock();
      }
      if (i2cError) {
        setHardwareError(
          "El CP2102 y el ESP32 responden, pero el PN532 reporta un error I²C. Revisa SDA GPIO21, SCL GPIO22, alimentación, tierra común y el selector I²C.",
        );
        setHardwareState("reader_missing");
        return;
      }
      if (!payload && buffer.trim()) {
        setHardwareError(
          "El puerto serie responde, pero el firmware instalado todavía no implementa OGPASS_STATUS. Actualiza el firmware antes de una lectura operativa.",
        );
        setHardwareState("firmware_outdated");
        return;
      }
      if (!payload) throw new Error("El CP2102 abrió correctamente, pero el ESP32 no envió datos.");
      setDiagnostic(payload);
      if (!payload.reader_ready) setHardwareState("reader_missing");
      else if (!payload.wifi_connected || !payload.backend_online) setHardwareState("partial");
      else setHardwareState("ready");
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "NotFoundError") {
        setHardwareState("idle");
        setHardwareError("No seleccionaste ningún puerto.");
        return;
      }
      const port = portRef.current;
      portRef.current = null;
      if (port) await port.close().catch(() => undefined);
      setPortConnected(false);
      setHardwareState("error");
      setHardwareError(
        caught instanceof Error ? caught.message : "No fue posible verificar el lector.",
      );
    }
  }

  return (
    <div className="mx-auto max-w-6xl animate-enter">
      <BackButton onBack={onBack} />
      <div className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-primary">
            <Terminal className="size-4" /> OGPASS Hardware Lab
          </div>
          <h1 className="mt-3 font-display text-4xl font-bold tracking-normal sm:text-5xl">
            Conecta. Verifica. Lee.
          </h1>
          <p className="mt-3 max-w-2xl leading-7 text-muted-foreground">
            Comprueba desde el navegador que el ESP32, el lector PN532 y la conexión con OGPASS
            están listos antes de acercar una tarjeta.
          </p>
        </div>
        <Button variant="outline" asChild>
          <a href="https://github.com/BOLIVARES-DIGITALES/OGPASS" target="_blank" rel="noreferrer">
            Ver repositorio <ExternalLink />
          </a>
        </Button>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.15fr_.85fr]">
        <section className="overflow-hidden rounded-lg border border-code-border bg-code text-code-foreground shadow-[var(--shadow-code)]">
          <div className="flex h-12 items-center border-b border-code-border px-4">
            <div className="flex gap-1.5">
              <span className="size-2.5 rounded-full bg-danger" />
              <span className="size-2.5 rounded-full bg-warning" />
              <span className="size-2.5 rounded-full bg-success" />
            </div>
            <span className="ml-4 font-mono text-xs text-code-muted">hardware-check.js</span>
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
          <pre className="min-h-80 overflow-x-auto p-5 font-mono text-xs leading-6 sm:p-7 sm:text-sm">
            <code>{snippet}</code>
          </pre>
          <div className="border-t border-code-border bg-code-panel p-4 font-mono text-xs">
            <span className="text-code-muted">USB</span> Web Serial · 115200 baud · STATUS
          </div>
        </section>

        <section className="rounded-lg border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase text-muted-foreground">Diagnóstico local</p>
              <h2 className="mt-1 font-display text-xl font-bold">Estado del lector</h2>
            </div>
            <span
              className={cn(
                "size-2 rounded-full",
                hardwareState === "ready"
                  ? "bg-success shadow-[0_0_10px_var(--success)]"
                  : hardwareState === "partial" || hardwareState === "firmware_outdated"
                    ? "bg-warning"
                    : hardwareState === "reader_missing" || hardwareState === "error"
                      ? "bg-danger"
                      : "bg-muted-foreground",
              )}
            />
          </div>

          <div className="mt-6 space-y-2 rounded-md border border-border bg-secondary/45 p-4 text-xs">
            {[
              {
                icon: <Cable />,
                label: "Puerto USB",
                value: portConnected
                  ? "CP2102 conectado"
                  : hardwareState === "requesting"
                    ? "Selecciona CP2102"
                    : hardwareState === "checking"
                      ? "Comprobando"
                      : "No verificado",
                ok: portConnected ? true : null,
              },
              {
                icon: <Cpu />,
                label: "Lector PN532",
                value: diagnostic
                  ? diagnostic.reader_ready
                    ? "Detectado"
                    : "No detectado"
                  : hardwareState === "reader_missing"
                    ? "Error I²C"
                    : "No verificado",
                ok: diagnostic
                  ? diagnostic.reader_ready
                  : hardwareState === "reader_missing"
                    ? false
                    : null,
              },
              {
                icon: <Wifi />,
                label: "Wi-Fi del ESP32",
                value: diagnostic
                  ? diagnostic.wifi_connected
                    ? "Conectado"
                    : "Sin conexión"
                  : "No verificado",
                ok: diagnostic ? diagnostic.wifi_connected : null,
              },
              {
                icon: <Server />,
                label: "API OGPASS",
                value: diagnostic
                  ? diagnostic.backend_online
                    ? "Heartbeat confirmado"
                    : `Sin confirmar (${diagnostic.heartbeat_code})`
                  : "No verificado",
                ok: diagnostic ? diagnostic.backend_online : null,
              },
            ].map((item) => (
              <div key={item.label} className="flex items-center gap-3 rounded-sm bg-card/65 p-3">
                <span className="text-primary [&_svg]:size-4">{item.icon}</span>
                <span className="text-muted-foreground">{item.label}</span>
                <span
                  className={cn(
                    "ml-auto text-right font-mono font-semibold",
                    item.ok === true
                      ? "text-success"
                      : item.ok === false
                        ? "text-danger"
                        : "text-foreground",
                  )}
                >
                  {item.value}
                </span>
              </div>
            ))}
          </div>

          <Button
            className="mt-4 w-full"
            size="lg"
            onClick={() => void verifyHardware()}
            disabled={hardwareState === "requesting" || hardwareState === "checking"}
          >
            {hardwareState === "requesting" || hardwareState === "checking" ? (
              <LoaderCircle className="animate-spin" />
            ) : (
              <Cable />
            )}
            {hardwareState === "requesting"
              ? "Esperando selección…"
              : hardwareState === "checking"
                ? "Consultando dispositivo…"
                : portConnected
                  ? "Verificar nuevamente"
                  : "Conectar y verificar"}
          </Button>
          {portRef.current && (
            <Button
              className="mt-2 w-full"
              variant="ghost"
              onClick={() => void disconnectHardware()}
            >
              Desconectar puerto
            </Button>
          )}

          <div
            className={cn(
              "mt-5 min-h-28 rounded-md border p-4 text-xs leading-5 transition-colors",
              hardwareState === "ready"
                ? "border-success/30 bg-success/5"
                : hardwareState === "partial" || hardwareState === "firmware_outdated"
                  ? "border-warning/30 bg-warning/5"
                  : hardwareState === "reader_missing" || hardwareState === "error"
                    ? "border-danger/30 bg-danger/5"
                    : "border-dashed border-border",
            )}
            role="status"
          >
            {hardwareState === "idle" && (
              <p className="text-muted-foreground">
                Conecta el ESP32 por USB, pulsa verificar y selecciona su puerto. El navegador
                solicitará permiso explícito.
              </p>
            )}
            {(hardwareState === "requesting" || hardwareState === "checking") && (
              <p className="text-muted-foreground">
                {hardwareState === "requesting"
                  ? "Haz clic sobre CP2102 USB to UART Bridge Controller y luego pulsa Conectar."
                  : "Esperando la respuesta OGPASS_STATUS del firmware…"}
              </p>
            )}
            {hardwareState === "ready" && (
              <div className="animate-enter">
                <p className="flex items-center gap-2 font-bold text-success">
                  <CircleCheck className="size-4" /> LECTOR LISTO
                </p>
                <p className="mt-2 text-muted-foreground">
                  USB, ESP32, PN532, Wi-Fi y API están confirmados. Ya puedes realizar una lectura.
                </p>
                {diagnostic?.pending_operation && (
                  <p className="mt-2 font-semibold text-warning">
                    Existe una operación pendiente almacenada en el dispositivo.
                  </p>
                )}
              </div>
            )}
            {hardwareState === "partial" && (
              <div>
                <p className="font-bold text-warning">HARDWARE LOCAL DETECTADO</p>
                <p className="mt-2 text-muted-foreground">
                  El PN532 está conectado, pero falta Wi-Fi o el heartbeat con OGPASS. No realices
                  una lectura operativa todavía.
                </p>
              </div>
            )}
            {hardwareState === "reader_missing" && (
              <div>
                <p className="font-bold text-danger">PN532 NO DETECTADO</p>
                <p className="mt-2 text-muted-foreground">
                  {hardwareError ||
                    "El ESP32 respondió, pero revisa alimentación, conexión I2C y selector del módulo."}
                </p>
              </div>
            )}
            {hardwareState === "firmware_outdated" && (
              <div>
                <p className="font-bold text-warning">FIRMWARE PENDIENTE DE ACTUALIZAR</p>
                <p className="mt-2 text-muted-foreground">{hardwareError}</p>
              </div>
            )}
            {(hardwareState === "unsupported" || hardwareState === "error") && (
              <div>
                <p className="font-bold text-danger">NO VERIFICADO</p>
                <p className="mt-2 text-muted-foreground">{hardwareError}</p>
              </div>
            )}
          </div>
          <div className="mt-5 flex items-start gap-3 text-xs leading-5 text-muted-foreground">
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" />
            Esta prueba sólo solicita estado al equipo seleccionado. No lee, escribe ni modifica una
            tarjeta NFC.
          </div>
        </section>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        {[
          { icon: <Cable />, title: "Puerto explícito", text: "El usuario elige el USB" },
          { icon: <Cpu />, title: "Hardware real", text: "ESP32 y PN532 confirmados" },
          { icon: <Server />, title: "Extremo a extremo", text: "Heartbeat con OGPASS" },
        ].map((item) => (
          <div
            key={item.title}
            className="flex items-center gap-3 rounded-md border border-border bg-card/70 p-4"
          >
            <span className="text-primary [&_svg]:size-5">{item.icon}</span>
            <div>
              <p className="text-sm font-semibold">{item.title}</p>
              <p className="text-xs text-muted-foreground">{item.text}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
