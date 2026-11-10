import * as React from "react";
import { ArrowRight, KeyRound, Loader2, ShieldCheck } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import { SensitivityBadge } from "@/components/shared/SensitivityBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth, type Role } from "@/lib/api/auth";

interface DemoAccount {
  name: string;
  email: string;
  role: Role;
  roleLabel: string;
  clearance: number;
  description: string;
}

const DEMO_ACCOUNTS: DemoAccount[] = [
  {
    name: "Meera Patel",
    email: "meera@payflow.dev",
    role: "lead",
    roleLabel: "Lead / Manager",
    clearance: 3,
    description: "Full authority: review, resolve ambiguities, sign off, preview roles.",
  },
  {
    name: "Aarav Kulkarni",
    email: "aarav@payflow.dev",
    role: "outgoing",
    roleLabel: "Outgoing Lead",
    clearance: 2,
    description: "Author-asserted claims, code & webhook context, dual sign-off.",
  },
  {
    name: "Kabir Sharma",
    email: "kabir@payflow.dev",
    role: "successor",
    roleLabel: "Successor (Junior)",
    clearance: 1,
    description: "Target recipient: views signed handover, acknowledges receipts, asks copilot.",
  },
  {
    name: "Dev Mukherjee",
    email: "dev@payflow.dev",
    role: "contractor",
    roleLabel: "Contractor",
    clearance: 1,
    description: "Strict firewall: restricted secrets & private tickets completely masked.",
  },
  {
    name: "Sana Chen",
    email: "sana@payflow.dev",
    role: "auditor",
    roleLabel: "Compliance Auditor",
    clearance: 1,
    description: "Audit mode: inspects tamper-evident SHA-256 chain and metrics.",
  },
];

export function LoginPage() {
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || "/";

  React.useEffect(() => {
    document.title = "Sign In — RelayOps";
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setErrorMsg("Please provide both email and password.");
      return;
    }
    setErrorMsg(null);
    setSubmitting(true);
    try {
      await login({ email, password });
      navigate(from, { replace: true });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Invalid credentials";
      setErrorMsg(message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleSelectDemo = async (account: DemoAccount) => {
    setEmail(account.email);
    setPassword("password123");
    setErrorMsg(null);
    setSubmitting(true);
    try {
      await login({ email: account.email, password: "password123" });
      navigate(from, { replace: true });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to sign in";
      setErrorMsg(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-b from-sidebar-from to-sidebar-to px-4 py-12 antialiased sm:px-6 lg:px-8">
      {/* Brand Header */}
      <div className="mb-8 flex flex-col items-center text-center">
        <span className="grid size-12 place-items-center rounded-2xl bg-white/10 font-mono text-xl font-bold text-white ring-1 ring-inset ring-white/15 shadow-md">
          R
        </span>
        <h1 className="mt-4 text-[30px] font-bold leading-tight tracking-[-0.02em] text-white">
          Sign in to RelayOps
        </h1>
        <p className="mt-2 text-xs text-sidebar-fg-muted sm:text-sm">
          Traceable, human-verified engineering handovers with tamper-evident auditing.
        </p>
      </div>

      <div className="w-full max-w-4xl space-y-8">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-12">
          {/* Main Credentials Login Card */}
          <Card className="rounded-[24px] shadow-card-hover md:col-span-5">
            <CardHeader className="pb-4">
              <CardTitle className="text-base font-semibold">Account Sign In</CardTitle>
              <CardDescription className="text-xs">
                Use your PayFlow developer credentials to continue.
              </CardDescription>
            </CardHeader>

            <form onSubmit={handleSubmit}>
              <CardContent className="space-y-4">
                {errorMsg && (
                  <div
                    role="alert"
                    className="rounded-md border border-destructive/30 bg-destructive/10 p-2.5 text-xs text-destructive"
                  >
                    {errorMsg}
                  </div>
                )}

                <div className="space-y-1.5">
                  <label
                    htmlFor="email-input"
                    className="block text-xs font-medium text-ink"
                  >
                    Email address
                  </label>
                  <Input
                    id="email-input"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@payflow.dev"
                    required
                    autoComplete="email"
                    className="h-9 text-xs"
                    disabled={submitting}
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label
                      htmlFor="password-input"
                      className="block text-xs font-medium text-ink"
                    >
                      Password
                    </label>
                  </div>
                  <Input
                    id="password-input"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    required
                    autoComplete="current-password"
                    className="h-9 text-xs"
                    disabled={submitting}
                  />
                </div>
              </CardContent>

              <CardFooter className="pt-2">
                <Button type="submit" className="w-full text-xs font-medium" disabled={submitting}>
                  {submitting ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Signing In...
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5">
                      Sign In
                      <ArrowRight className="h-3.5 w-3.5" />
                    </span>
                  )}
                </Button>
              </CardFooter>
            </form>
          </Card>

          {/* Quick One-Click Demo Accounts */}
          <div className="space-y-3 md:col-span-7">
            <div>
              <h2 className="flex items-center gap-1.5 text-sm font-semibold tracking-tight text-white">
                <KeyRound className="h-4 w-4 text-brand" />
                Select a Demo Persona
              </h2>
              <p className="text-xs text-sidebar-fg-muted">
                One-click login for team members in the PayFlow demo scenario.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-2.5">
              {DEMO_ACCOUNTS.map((account) => (
                <button
                  key={account.email}
                  type="button"
                  onClick={() => handleSelectDemo(account)}
                  disabled={submitting}
                  className="group flex flex-col justify-between rounded-2xl border border-white/10 bg-card p-3.5 text-left transition-all duration-150 hover:border-brand hover:shadow-card-hover focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-sidebar-to disabled:opacity-60"
                  aria-label={`Log in as ${account.name}, ${account.roleLabel}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-ink group-hover:text-brand-text">
                        {account.name}
                      </span>
                      <Badge variant="outline" className="text-[10px] capitalize">
                        {account.roleLabel}
                      </Badge>
                    </div>
                    <SensitivityBadge level={account.clearance} size="sm" />
                  </div>
                  <p className="mt-1 font-mono text-[11px] text-ink-muted">
                    {account.email}
                  </p>
                  <p className="mt-1 text-[11px] text-ink-muted line-clamp-1">
                    {account.description}
                  </p>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Security & Audit note */}
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-center">
          <p className="flex items-center justify-center gap-1.5 font-mono text-xs text-sidebar-fg-muted">
            <ShieldCheck className="h-4 w-4 text-verified" />
            Secrets scrubbed at ingestion. Claims verified with real artifact citations.
          </p>
        </div>
      </div>
    </div>
  );
}
