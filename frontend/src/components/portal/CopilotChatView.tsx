import * as React from "react";
import {
  Bot,
  Check,
  Copy,
  HelpCircle,
  Loader2,
  Send,
  ShieldAlert,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  User,
} from "lucide-react";
import { toast } from "sonner";

import { CitationPill } from "@/components/shared/CitationPill";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  useCopilotChat,
  useCopilotFeedback,
  useCopilotMessages,
  type ChatMessage,
} from "@/lib/api/portal";
import { AskQuestionDialog } from "./AskQuestionDialog";

interface CopilotChatViewProps {
  handoverId: string;
  outgoingName?: string;
  fullHeight?: boolean;
}

const STARTER_QUESTIONS = [
  "What is the webhook retry policy in production?",
  "Who is the primary escalation contact for PAY-142?",
  "Why was PostgreSQL chosen over MongoDB for the ledger?",
  "What is our quantum computing rollout plan for 2027?", // Test refusal path
];

export function CopilotChatView({
  handoverId,
  outgoingName = "Outgoing Contributor",
  fullHeight = false,
}: CopilotChatViewProps) {
  const [inputMessage, setInputMessage] = React.useState("");
  const [copiedId, setCopiedId] = React.useState<string | null>(null);
  const [askDialogOpen, setAskDialogOpen] = React.useState(false);
  const [askQuery, setAskQuery] = React.useState("");

  const { data: dbMessages } = useCopilotMessages(handoverId);
  const chatMutation = useCopilotChat(handoverId);
  const feedbackMutation = useCopilotFeedback(handoverId);

  // Local optimistic messages list combined with backend history
  const [localMessages, setLocalMessages] = React.useState<ChatMessage[]>([]);

  React.useEffect(() => {
    if (dbMessages && dbMessages.length > 0) {
      setLocalMessages(dbMessages);
    }
  }, [dbMessages]);

  const messagesEndRef = React.useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  React.useEffect(() => {
    scrollToBottom();
  }, [localMessages, chatMutation.isPending]);

  const handleSend = async (messageToSend?: string) => {
    const text = (messageToSend ?? inputMessage).trim();
    if (!text || chatMutation.isPending) return;

    setInputMessage("");

    // Optimistic user message
    const tempUserMsg: ChatMessage = {
      id: `temp-${Date.now()}`,
      session_id: "active",
      role: "user",
      content: text,
      citations: [],
      refused: false,
      created_at: new Date().toISOString(),
    };

    setLocalMessages((prev) => [...prev, tempUserMsg]);

    try {
      const res = await chatMutation.mutateAsync({
        message: text,
      });

      // Optimistic assistant message
      const tempAsstMsg: ChatMessage = {
        id: res.message_id,
        session_id: res.session_id,
        role: "assistant",
        content: res.answer,
        citations: res.citations.map((c) => ({ id: c.id, snippet: c.snippet })),
        refused: res.refused,
        created_at: new Date().toISOString(),
      };

      setLocalMessages((prev) => [...prev, tempAsstMsg]);
    } catch {
      // Error toast handled by hook
    }
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    toast.success("Copied to clipboard");
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleFeedback = (messageId: string, feedback: "up" | "down") => {
    feedbackMutation.mutate({ messageId, feedback });
    setLocalMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, feedback } : m)),
    );
  };

  const handleRefusalAskOutgoing = (content: string) => {
    setAskQuery(content);
    setAskDialogOpen(true);
  };

  return (
    <div className={`flex flex-col ${fullHeight ? "h-full" : "h-[540px]"} w-full`}>
      {/* Scrollable messages area */}
      <ScrollArea className="flex-1 p-4 pr-3">
        <div className="space-y-4">
          {/* Welcome / Empty intro banner */}
          {localMessages.length === 0 && (
            <div className="rounded-xl border border-brand bg-brand-soft p-4 text-xs space-y-3">
              <div className="flex items-center gap-2">
                <div className="rounded-lg bg-brand-soft p-2 text-brand-text">
                  <Bot className="h-5 w-5" />
                </div>
                <div>
                  <p className="font-semibold text-ink">RelayOps Grounded Copilot</p>
                  <p className="text-[11px] text-ink-muted">
                    Ask questions grounded strictly in verified handover artifacts and PRs.
                  </p>
                </div>
              </div>

              <div className="space-y-1.5 pt-2 border-t border-brand">
                <p className="text-[11px] font-medium text-ink-muted">
                  Suggested inquiries:
                </p>
                <div className="flex flex-col gap-1.5">
                  {STARTER_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => handleSend(q)}
                      className="text-left rounded-md border border-card-border bg-canvas/80 px-2.5 py-1.5 text-xs text-ink hover:border-brand hover:bg-canvas-2 transition-colors flex items-center justify-between"
                    >
                      <span>{q}</span>
                      <Sparkles className="h-3 w-3 text-brand-text opacity-60" />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Render message bubbles */}
          {localMessages.map((msg) => {
            const isUser = msg.role === "user";

            if (isUser) {
              return (
                <div key={msg.id} className="flex justify-end gap-2 text-xs">
                  <div className="max-w-[85%] rounded-2xl rounded-tr-xs bg-primary px-3.5 py-2.5 text-primary-foreground shadow-xs">
                    <p className="leading-relaxed">{msg.content}</p>
                  </div>
                  <div className="h-6 w-6 rounded-full bg-brand-soft flex items-center justify-center shrink-0 mt-0.5 text-brand-text">
                    <User className="h-3.5 w-3.5" />
                  </div>
                </div>
              );
            }

            // Refusal style
            if (msg.refused) {
              return (
                <div key={msg.id} className="flex gap-2 text-xs">
                  <div className="h-6 w-6 rounded-full bg-warn-soft flex items-center justify-center shrink-0 mt-0.5 text-needs-review">
                    <ShieldAlert className="h-3.5 w-3.5" />
                  </div>
                  <div className="max-w-[90%] space-y-2 rounded-2xl rounded-tl-xs border border-needs-review bg-warn-soft p-3 text-needs-review dark:text-needs-review">
                    <div className="flex items-center gap-1.5 font-semibold text-needs-review dark:text-needs-review">
                      <ShieldAlert className="h-3.5 w-3.5" />
                      Deterministic Refusal (Missing Evidence)
                    </div>
                    <p className="leading-relaxed text-xs">{msg.content}</p>

                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleRefusalAskOutgoing(msg.content)}
                      className="gap-1.5 text-xs h-7 border-needs-review text-needs-review dark:text-needs-review hover:bg-warn-soft"
                    >
                      <HelpCircle className="h-3 w-3" />
                      Ask {outgoingName.split(" ")[0]} directly
                    </Button>
                  </div>
                </div>
              );
            }

            // Normal verified assistant response
            return (
              <div key={msg.id} className="flex gap-2 text-xs">
                <div className="h-6 w-6 rounded-full bg-brand-soft flex items-center justify-center shrink-0 mt-0.5 text-brand-text">
                  <Bot className="h-3.5 w-3.5" />
                </div>
                <div className="max-w-[90%] space-y-2.5 rounded-2xl rounded-tl-xs border border-card-border bg-card p-3.5 shadow-xs">
                  <p className="leading-relaxed text-ink whitespace-pre-wrap">
                    {msg.content}
                  </p>

                  {/* Citations Pill list */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap pt-1 border-t border-card-border">
                      <span className="text-[10px] font-medium text-ink-muted">
                        Verified Sources:
                      </span>
                      {msg.citations.map((c, i) => (
                        <CitationPill
                          key={`${c.id}-${i}`}
                          artifactId={c.id}
                          snippet={c.snippet}
                        />
                      ))}
                    </div>
                  )}

                  {/* Footer actions: Copy, Thumbs up/down */}
                  <div className="flex items-center justify-between pt-1 text-ink-muted">
                    <span className="text-[10px] font-mono opacity-60">Grounded Answer</span>

                    <div className="flex items-center gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-6 w-6"
                        onClick={() => handleCopy(msg.id, msg.content)}
                        title="Copy answer"
                      >
                        {copiedId === msg.id ? (
                          <Check className="h-3 w-3 text-verified" />
                        ) : (
                          <Copy className="h-3 w-3" />
                        )}
                      </Button>

                      <Button
                        size="icon"
                        variant="ghost"
                        className={`h-6 w-6 ${msg.feedback === "up" ? "text-verified bg-verified/10" : ""}`}
                        onClick={() => handleFeedback(msg.id, "up")}
                        title="Helpful"
                      >
                        <ThumbsUp className="h-3 w-3" />
                      </Button>

                      <Button
                        size="icon"
                        variant="ghost"
                        className={`h-6 w-6 ${msg.feedback === "down" ? "text-destructive bg-destructive/10" : ""}`}
                        onClick={() => handleFeedback(msg.id, "down")}
                        title="Needs improvement"
                      >
                        <ThumbsDown className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}

          {/* Typing / streaming indicator */}
          {chatMutation.isPending && (
            <div className="flex gap-2 text-xs">
              <div className="h-6 w-6 rounded-full bg-brand-soft flex items-center justify-center shrink-0 mt-0.5 text-brand-text">
                <Bot className="h-3.5 w-3.5" />
              </div>
              <div className="rounded-2xl rounded-tl-xs border border-card-border bg-card px-3.5 py-2.5 shadow-xs flex items-center gap-2 text-ink-muted">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-brand-text" />
                <span className="text-[11px] animate-pulse">
                  Retrieving verified evidence and synthesizing answer...
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Input box */}
      <div className="border-t p-3 bg-card">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center gap-2"
        >
          <Input
            placeholder="Ask anything about architecture, blockers, or credentials..."
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            disabled={chatMutation.isPending}
            className="text-xs h-9"
          />
          <Button
            type="submit"
            size="sm"
            disabled={!inputMessage.trim() || chatMutation.isPending}
            className="h-9 gap-1 text-xs shrink-0 px-3"
          >
            <Send className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Ask</span>
          </Button>
        </form>
      </div>

      {/* Dialog for forwarding unanswered queries to outgoing owner */}
      <AskQuestionDialog
        open={askDialogOpen}
        onOpenChange={setAskDialogOpen}
        handoverId={handoverId}
        outgoingName={outgoingName}
        initialTitle="Unverified Question from Copilot"
        initialQuestion={askQuery}
      />
    </div>
  );
}
