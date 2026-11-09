import * as React from "react";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  FileCode,
  FileText,
  FolderGit2,
  Github,
  Loader2,
  MessageSquare,
  Sparkles,
  Upload,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useCreateSource, useLoadDemo, useUploadSourceFile } from "@/lib/api/sources";
import { cn } from "@/lib/utils";

export interface AddSourceWizardDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
}

type SourceType = "demo" | "github" | "jira" | "slack" | "docs";

interface SourceOption {
  id: SourceType;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  isRecommended?: boolean;
}

const SOURCE_OPTIONS: SourceOption[] = [
  {
    id: "demo",
    title: "Load PayFlow Demo Dataset",
    description:
      "Instant one-click loading: ~240 commits, PRs, Jira tickets, Slack threads, and ADRs with realistic contradictions.",
    icon: Sparkles,
    isRecommended: true,
  },
  {
    id: "github",
    title: "GitHub Repository",
    description:
      "Connect via repository URL to ingest commits, pull requests, review comments, and unmerged branches.",
    icon: Github,
  },
  {
    id: "jira",
    title: "Jira / Issue Tracker JSON",
    description:
      "Upload exported issues with keys (e.g. PAY-101), statuses, blockers, and dependencies.",
    icon: FileCode,
  },
  {
    id: "slack",
    title: "Slack / Teams JSON Export",
    description:
      "Ingest developer chat channels with thread offsets preserved for micro-evidence citations.",
    icon: MessageSquare,
  },
  {
    id: "docs",
    title: "Markdown Docs / ADRs / Runbooks",
    description: "Upload architectural decision records (.md), runbooks, or meeting notes.",
    icon: FileText,
  },
];

export function AddSourceWizardDialog({
  open,
  onOpenChange,
  projectId,
}: AddSourceWizardDialogProps) {
  const [step, setStep] = React.useState<1 | 2 | 3 | 4>(1);
  const [selectedType, setSelectedType] = React.useState<SourceType>("demo");

  // GitHub config
  const [repoUrl, setRepoUrl] = React.useState("payflow/core");
  const [branch, setBranch] = React.useState("main");
  const [githubToken, setGithubToken] = React.useState("");

  // File upload state
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null);
  const [dragActive, setDragActive] = React.useState(false);
  const [fileError, setFileError] = React.useState<string | null>(null);

  const loadDemo = useLoadDemo();
  const createSource = useCreateSource(projectId);
  const uploadFile = useUploadSourceFile(projectId);

  const isSubmitting = loadDemo.isPending || createSource.isPending || uploadFile.isPending;

  // Reset state when opening
  React.useEffect(() => {
    if (open) {
      setStep(1);
      setSelectedType("demo");
      setSelectedFile(null);
      setFileError(null);
    }
  }, [open]);

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelected = (file: File) => {
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    const validExts = [".json", ".md", ".txt", ".pdf"];
    if (!validExts.includes(ext)) {
      setFileError(`Invalid file format '${ext}'. Supported formats: .json, .md, .txt, .pdf`);
      setSelectedFile(null);
      return;
    }
    setFileError(null);
    setSelectedFile(file);
  };

  const handleRun = async () => {
    try {
      if (selectedType === "demo") {
        await loadDemo.mutateAsync(projectId);
      } else if (selectedType === "github") {
        await createSource.mutateAsync({
          name: `GitHub: ${repoUrl}`,
          type: "github",
          config: {
            repo: repoUrl,
            branch: branch || "main",
            token: githubToken ? githubToken.trim() : undefined,
          },
        });
      } else if (selectedFile) {
        await uploadFile.mutateAsync(selectedFile);
      }
      onOpenChange(false);
    } catch {
      // Error handled by hook toast
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="grid size-7 place-items-center rounded-md bg-primary/10 text-primary">
                <FolderGit2 className="h-4 w-4" />
              </span>
              <DialogTitle className="text-base font-semibold">
                Add Source to Knowledge Gateway
              </DialogTitle>
            </div>
            <div className="flex items-center gap-1 text-[11px] font-mono text-muted-foreground">
              <span>Step {step} of 3</span>
            </div>
          </div>
          <DialogDescription className="text-xs">
            Ingest engineering activity with automated secret scrubbing and citation binding.
          </DialogDescription>
        </DialogHeader>

        {/* Step 1: Choose Type */}
        {step === 1 && (
          <div className="space-y-2.5 py-2">
            <p className="text-xs font-medium text-foreground">Select source kind:</p>
            <div className="grid grid-cols-1 gap-2">
              {SOURCE_OPTIONS.map((opt) => {
                const Icon = opt.icon;
                const isSelected = selectedType === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setSelectedType(opt.id)}
                    className={cn(
                      "flex items-start gap-3 rounded-lg border p-3 text-left transition-all",
                      isSelected
                        ? "border-primary bg-primary/5 ring-1 ring-primary"
                        : "border-border hover:border-primary/40 hover:bg-muted/40",
                    )}
                  >
                    <div
                      className={cn(
                        "mt-0.5 rounded-md p-1.5",
                        isSelected
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-muted-foreground",
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="flex-1 space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-foreground">{opt.title}</span>
                        {opt.isRecommended && (
                          <Badge variant="secondary" className="text-[9px] text-primary">
                            Recommended
                          </Badge>
                        )}
                      </div>
                      <p className="text-[11px] text-muted-foreground leading-relaxed">
                        {opt.description}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Step 2: Configure */}
        {step === 2 && (
          <div className="space-y-4 py-2">
            {selectedType === "demo" && (
              <div className="rounded-lg border border-border bg-muted/40 p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-primary" />
                  <span className="text-xs font-semibold text-foreground">
                    PayFlow Seed Dataset Configuration
                  </span>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Loads the canonical PayFlow synthetic dataset directly into this project:
                </p>
                <ul className="text-xs text-muted-foreground space-y-1 list-disc list-inside">
                  <li>80 commits (Git history & unmerged branches)</li>
                  <li>25 pull requests with review comments</li>
                  <li>32 Jira issues with blocker dependencies</li>
                  <li>3 Slack channels with thread offsets</li>
                  <li>Architectural decision records (ADR 001 - 004)</li>
                </ul>
              </div>
            )}

            {selectedType === "github" && (
              <div className="space-y-3">
                <div className="space-y-1">
                  <label htmlFor="repo-url-input" className="text-xs font-medium text-foreground">
                    Repository (owner/repo)
                  </label>
                  <Input
                    id="repo-url-input"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    placeholder="e.g. acme/payflow-core"
                    className="h-9 text-xs"
                    required
                  />
                </div>
                <div className="space-y-1">
                  <label htmlFor="branch-input" className="text-xs font-medium text-foreground">
                    Default Branch
                  </label>
                  <Input
                    id="branch-input"
                    value={branch}
                    onChange={(e) => setBranch(e.target.value)}
                    placeholder="main"
                    className="h-9 text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <label
                    htmlFor="github-token-input"
                    className="text-xs font-medium text-foreground"
                  >
                    GitHub Personal Access Token (Optional)
                  </label>
                  <Input
                    id="github-token-input"
                    type="password"
                    value={githubToken}
                    onChange={(e) => setGithubToken(e.target.value)}
                    placeholder="ghp_••••••••••••"
                    className="h-9 text-xs"
                  />
                  <p className="text-[11px] text-muted-foreground pt-1">
                    * Tokens are never stored or logged, used only in session for REST API calls.
                  </p>
                </div>
              </div>
            )}

            {(selectedType === "jira" || selectedType === "slack" || selectedType === "docs") && (
              <div className="space-y-3">
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragActive(true);
                  }}
                  onDragLeave={() => setDragActive(false)}
                  onDrop={handleFileDrop}
                  className={cn(
                    "flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center transition-colors",
                    dragActive
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-primary/50",
                  )}
                >
                  <Upload className="h-8 w-8 text-muted-foreground" />
                  <p className="mt-2 text-xs font-medium text-foreground">
                    Drag and drop file here, or browse
                  </p>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    Accepted formats: .json, .md, .txt, .pdf (Max 50MB)
                  </p>
                  <input
                    type="file"
                    id="file-upload-input"
                    className="hidden"
                    accept=".json,.md,.txt,.pdf"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        handleFileSelected(e.target.files[0]);
                      }
                    }}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => document.getElementById("file-upload-input")?.click()}
                    className="mt-3 text-xs"
                  >
                    Select File
                  </Button>
                </div>

                {selectedFile && (
                  <div className="flex items-center justify-between rounded-md border border-border bg-muted/40 p-2.5 text-xs">
                    <span className="font-mono text-foreground truncate max-w-xs">
                      {selectedFile.name}
                    </span>
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {(selectedFile.size / 1024).toFixed(1)} KB
                    </Badge>
                  </div>
                )}

                {fileError && (
                  <p className="text-xs text-destructive flex items-center gap-1.5">
                    <AlertCircle className="h-3.5 w-3.5" />
                    {fileError}
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Step 3: Review */}
        {step === 3 && (
          <div className="space-y-3 py-2 text-xs">
            <div className="rounded-lg border bg-muted/30 p-4 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Source Type:</span>
                <span className="font-semibold text-foreground capitalize">
                  {selectedType === "demo" ? "PayFlow Full Demo Dataset" : selectedType}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Target Project:</span>
                <span className="font-mono text-foreground">{projectId}</span>
              </div>
              {selectedType === "github" && (
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Repository:</span>
                  <span className="font-mono text-foreground">
                    {repoUrl} ({branch})
                  </span>
                </div>
              )}
              {selectedFile && (
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Payload File:</span>
                  <span className="font-mono text-foreground">{selectedFile.name}</span>
                </div>
              )}
              <div className="flex items-center justify-between pt-1 border-t">
                <span className="text-muted-foreground">Redaction Engine:</span>
                <span className="text-verified font-medium flex items-center gap-1">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Active (Pre-Storage Scrubbing)
                </span>
              </div>
            </div>
          </div>
        )}

        <DialogFooter className="pt-2">
          {step > 1 && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setStep((s) => (s - 1) as 1 | 2 | 3)}
              disabled={isSubmitting}
              className="gap-1 text-xs"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back
            </Button>
          )}

          {step < 3 ? (
            <Button
              type="button"
              size="sm"
              onClick={() => setStep((s) => (s + 1) as 1 | 2 | 3)}
              disabled={
                step === 2 &&
                (selectedType === "jira" || selectedType === "slack" || selectedType === "docs") &&
                !selectedFile
              }
              className="gap-1 text-xs"
            >
              Next
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              onClick={handleRun}
              disabled={isSubmitting}
              className="gap-1.5 text-xs"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Ingesting...
                </>
              ) : (
                <>
                  <Sparkles className="h-3.5 w-3.5" />
                  Ingest & Sync Source
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
